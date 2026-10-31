"""Contenu pédagogique versionné : contenu/<niveau>/<NN-chapitre>.yaml → base de données.

Un fichier = un chapitre, ses compétences, leur cours/résumé (Markdown + LaTeX)
et leurs questions. Voir docs/CONTENU.md pour le format.

Usage, depuis `api/` :
    python -m app.contenu verifier              # contrôle tous les fichiers, sans base
    python -m app.contenu matrice               # docs/matrices/MATRICE-<programme>.md (couverture du BO)
    python -m app.contenu ecarts                # attendus officiels absents ou incomplets
    python -m app.contenu importer --simulation # montre ce qui changerait
    python -m app.contenu importer              # applique

Règles de l'import (idempotent : le relancer ne change rien) :
- chapitres, compétences et questions sont reconnus par leur `code` ;
- une question retirée des fichiers est archivée, jamais supprimée ;
- les questions créées depuis l'interface enseignant (sans code) ne sont pas touchées.
"""

import argparse
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Annotated

import pkp_engine
import yaml
from pkp_engine import ExpressionInvalide, Niveau, TypeQuestion
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import programmes
from app.db import models
from app.referentiel import (
    LICENCES_NON_CLAIRES,
    PARCOURS_PAR_NIVEAU,
    SOURCE_PKP,
    Adaptation,
    Parcours,
    StatutValidation,
)

DOSSIER_PAR_DEFAUT = Path(__file__).resolve().parents[2] / "contenu"
ORDRE_NIVEAUX = {Niveau.SECONDE: 0, Niveau.PREMIERE: 1, Niveau.TERMINALE: 2}
ORDRE_PARCOURS = {p: i for i, p in enumerate(Parcours)}
# Rangement attendu : contenu/<dossier du niveau>/<parcours>/NN-chapitre.yaml
DOSSIERS_NIVEAU = {Niveau.SECONDE: "2nde", Niveau.PREMIERE: "1re", Niveau.TERMINALE: "tle"}

Code = Annotated[str, Field(pattern=r"^[A-Z0-9][A-Z0-9-]{1,59}$")]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ValidationYaml(_Strict):
    """Validation pédagogique : qui a relu la question, et quand."""

    statut: StatutValidation = StatutValidation.A_VALIDER
    par: Annotated[str, Field(min_length=1, max_length=100)] | None = None
    le: date | None = None

    @model_validator(mode="after")
    def _signee(self):
        if self.statut is StatutValidation.VALIDEE and (self.par is None or self.le is None):
            raise ValueError("une question « validee » indique qui l'a validée (`par`) et quand (`le`)")
        return self


Texte = Annotated[str, Field(min_length=1, max_length=2000)]
Etapes = Annotated[list[Texte], Field(min_length=1, max_length=12)]


class CorrectionYaml(_Strict):
    """Correction détaillée, montrée à l'élève après sa réponse (cahier des charges V2, E0.1)."""

    methode: Annotated[str, Field(min_length=1, max_length=300)] | None = None  # la propriété ou la méthode utilisée
    etapes: Etapes
    # Obligatoire pour les types numérique et expression : contrôlé équivalent à `solution` par le moteur.
    resultat: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    erreurs_frequentes: list[Texte] = []

    @field_validator("resultat", mode="before")
    @classmethod
    def _texte(cls, v):
        return str(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v


class QuestionYaml(_Strict):
    code: Code
    difficulte: Annotated[int, Field(ge=1, le=5)]
    type: TypeQuestion
    enonce: Annotated[str, Field(min_length=1, max_length=2000)]
    solution: Annotated[str, Field(min_length=1, max_length=200)]
    archivee: bool = False
    # Auteur de la question : la personne qui la valide doit être une autre personne (règle E0.2).
    auteur: Annotated[str, Field(min_length=1, max_length=100)] | None = None
    correction: CorrectionYaml | None = None
    # Exercice de synthèse : autres compétences mobilisées (la compétence principale est celle qui le contient).
    competences_secondaires: list[Code] = []
    # Registre des sources (traçabilité et droits de réutilisation)
    source: Annotated[str, Field(min_length=1, max_length=200)] = SOURCE_PKP
    source_url: Annotated[str, Field(pattern=r"^https?://", max_length=500)] | None = None
    licence_source: Annotated[str, Field(max_length=100)] | None = None
    adaptation: Adaptation = Adaptation.ORIGINALE
    validation: ValidationYaml = ValidationYaml()

    @model_validator(mode="after")
    def _registre_coherent(self):
        externe = self.source != SOURCE_PKP
        if self.adaptation is Adaptation.ORIGINALE and externe:
            raise ValueError("adaptation « originale » mais source externe : utiliser « inspiree », « adaptee » ou « reproduite »")
        if self.adaptation is not Adaptation.ORIGINALE and not externe:
            raise ValueError(f"adaptation « {self.adaptation.value} » : indiquer la `source` d'origine")
        if self.adaptation in (Adaptation.ADAPTEE, Adaptation.REPRODUITE):
            if self.source_url is None:
                raise ValueError(f"adaptation « {self.adaptation.value} » : indiquer `source_url`")
            if (self.licence_source or "").strip().lower() in LICENCES_NON_CLAIRES:
                raise ValueError(
                    f"source sans licence claire (« {self.licence_source or 'non renseignée'} ») : "
                    "elle ne peut servir que d'inspiration (adaptation « inspiree », énoncé entièrement réécrit)"
                )
        return self

    @field_validator("solution", mode="before")
    @classmethod
    def _texte(cls, v):
        # YAML lit « 32 » comme un entier : la solution est toujours du texte.
        return str(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v

    @field_validator("enonce")
    @classmethod
    def _sans_espaces_finaux(cls, v: str) -> str:
        return v.strip()


class ExempleResoluYaml(_Strict):
    enonce: Texte
    resolution: Etapes
    resultat: Annotated[str, Field(min_length=1, max_length=300)] | None = None


class MethodeYaml(_Strict):
    """« Comment résoudre… » : une procédure réutilisable, illustrée par un exemple résolu."""

    titre: Annotated[str, Field(min_length=1, max_length=200)]
    quand: Annotated[str, Field(max_length=500)] | None = None  # dans quelles situations l'utiliser
    etapes: Etapes
    exemple: ExempleResoluYaml


class ErreurFrequenteYaml(_Strict):
    erreur: Texte
    explication: Texte  # d'où vient l'erreur, et comment l'éviter


class CompetenceYaml(_Strict):
    code: Code
    libelle: Annotated[str, Field(min_length=1, max_length=200)]
    # Attendus officiels couverts (codes des référentiels, voir app/programmes.py).
    attendus: list[str] = []
    objectifs: list[Texte] = []
    prerequis: list[Code] = []  # codes d'autres compétences, à revoir en cas de difficulté
    cours: str | None = None
    resume: str | None = None
    methodes: list[MethodeYaml] = []
    erreurs_frequentes: list[ErreurFrequenteYaml] = []
    questions: list[QuestionYaml] = []

    def textes(self) -> list[tuple[str, str]]:
        """Tous les textes affichés de la compétence (hors questions), pour les contrôles de formules."""
        textes = [("cours", self.cours or ""), ("resume", self.resume or "")]
        textes += [(f"objectifs[{i}]", t) for i, t in enumerate(self.objectifs)]
        for i, m in enumerate(self.methodes):
            textes += [(f"methodes[{i}].etapes", e) for e in m.etapes]
            textes += [(f"methodes[{i}].exemple", t) for t in [m.exemple.enonce, *m.exemple.resolution, m.exemple.resultat or ""]]
        for i, e in enumerate(self.erreurs_frequentes):
            textes += [(f"erreurs_frequentes[{i}]", e.erreur), (f"erreurs_frequentes[{i}]", e.explication)]
        return textes

    @model_validator(mode="after")
    def _lecon_complete(self):
        if (self.cours is None) != (self.resume is None):
            raise ValueError("`cours` et `resume` vont ensemble : renseigner les deux ou aucun")
        return self


class ChapitreYaml(_Strict):
    code: Code
    niveau: Niveau
    parcours: Parcours
    ordre: Annotated[int, Field(ge=1, le=99)]
    titre: Annotated[str, Field(min_length=1, max_length=200)]

    @model_validator(mode="after")
    def _parcours_du_niveau(self):
        permis = PARCOURS_PAR_NIVEAU[self.niveau]
        if self.parcours not in permis:
            raise ValueError(
                f"parcours « {self.parcours.value} » impossible en {self.niveau.value} "
                f"(permis : {', '.join(p.value for p in permis)})"
            )
        return self


class FichierContenu(_Strict):
    chapitre: ChapitreYaml
    competences: Annotated[list[CompetenceYaml], Field(min_length=1)]


class ContenuInvalide(Exception):
    def __init__(self, erreurs: list[str]):
        self.erreurs = erreurs
        super().__init__(f"{len(erreurs)} erreur(s) dans le contenu :\n- " + "\n- ".join(erreurs))


# --- Vérification ------------------------------------------------------------


def _dollars_equilibres(texte: str) -> bool:
    return len(re.findall(r"(?<!\\)\$", texte)) % 2 == 0


def _verifier_question(q: QuestionYaml) -> str | None:
    if q.type is TypeQuestion.QCM:
        # Même découpage que l'écran élève (decouperQcm) : « P(A) » y serait pris pour une option.
        lettres = re.findall(r"\b([A-F])\)", q.enonce)
        if lettres != [chr(ord("A") + i) for i in range(len(lettres))] or len(lettres) < 2:
            return f"choix illisibles ({' '.join(l + ')' for l in lettres)}) : écrire « A) …  B) … », sans « X) » dans le texte"
        if not re.search(rf"(?<![A-Za-z]){re.escape(q.solution)}\)", q.enonce):
            return f"solution « {q.solution} » absente des choix de l'énoncé (attendu « {q.solution}) … »)"
        return None
    domaine = pkp_engine.Question(0, 0, q.enonce, q.type, q.solution, q.difficulte)
    try:
        if not pkp_engine.corriger(domaine, q.solution):
            return f"le moteur n'accepte pas sa propre solution « {q.solution} »"
    except ExpressionInvalide as exc:
        return f"solution « {q.solution} » illisible par le moteur ({exc})"
    return None


def _verifier_correction(q: QuestionYaml) -> list[str]:
    """Règles du lot 0 (E0.2) : pas de validation sans correction ni par l'auteur ; correction cohérente."""
    erreurs = []
    if q.validation.statut is StatutValidation.VALIDEE:
        if q.correction is None:
            erreurs.append("une question « validee » a une correction détaillée (`correction`)")
        if q.auteur is None:
            erreurs.append("une question « validee » indique son `auteur`")
        elif q.validation.par and q.validation.par.strip().lower() == q.auteur.strip().lower():
            erreurs.append("le relecteur (`validation.par`) ne peut pas être l'auteur de la question")
    c = q.correction
    if c is None:
        return erreurs
    textes = [c.methode or "", *c.etapes, c.resultat or "", *c.erreurs_frequentes]
    if not all(_dollars_equilibres(t) for t in textes):
        erreurs.append("nombre impair de « $ » dans la correction")
    if q.type is TypeQuestion.QCM:
        if c.resultat is not None and c.resultat.strip() != q.solution.strip():
            erreurs.append(f"correction.resultat « {c.resultat} » différent de la solution « {q.solution} »")
        return erreurs
    if c.resultat is None:
        erreurs.append("correction.resultat obligatoire pour une réponse numérique ou une expression")
        return erreurs
    try:
        equivalents = pkp_engine.corriger(pkp_engine.Question(0, 0, q.enonce, q.type, q.solution, q.difficulte), c.resultat)
    except ExpressionInvalide:
        equivalents = False
    if not equivalents:
        erreurs.append(f"correction.resultat « {c.resultat} » non équivalent à la solution « {q.solution} » selon le moteur")
    return erreurs


def _verifier_liens(fichiers, dossier: Path, codes_attendus: set[str] | None, erreurs: list[str]) -> None:
    """Attendus officiels, prérequis et compétences secondaires : chaque code cité doit exister."""
    competences = {c.code for _, contenu in fichiers for c in contenu.competences}
    for chemin, contenu in fichiers:
        nom = chemin.relative_to(dossier).as_posix()
        for c in contenu.competences:
            if codes_attendus is not None:
                for a in c.attendus:
                    if a not in codes_attendus:
                        erreurs.append(f"{nom} : {c.code} : attendu « {a} » absent des référentiels")
            for p in c.prerequis:
                if p == c.code or p not in competences:
                    erreurs.append(f"{nom} : {c.code} : prérequis « {p} » inconnu (code de compétence attendu)")
            for q in c.questions:
                for s in q.competences_secondaires:
                    if s == c.code or s not in competences:
                        erreurs.append(f"{nom} : {q.code} : compétence secondaire « {s} » inconnue")


def charger(
    dossier: Path = DOSSIER_PAR_DEFAUT, codes_attendus: set[str] | None = None
) -> list[tuple[Path, FichierContenu]]:
    """Lit et vérifie tous les fichiers. Lève ContenuInvalide avec toutes les erreurs trouvées.

    `codes_attendus` : attendus officiels connus ; par défaut, ceux de referentiels/ s'il existe."""
    if codes_attendus is None and programmes.DOSSIER_PAR_DEFAUT.is_dir():
        codes_attendus = set(programmes.charger(verifier_empreintes=False).attendus)
    erreurs: list[str] = []
    fichiers: list[tuple[Path, FichierContenu]] = []
    chemins = sorted(dossier.rglob("*.yaml"))
    if not chemins:
        raise ContenuInvalide([f"aucun fichier .yaml dans {dossier}"])

    for chemin in chemins:
        nom = chemin.relative_to(dossier).as_posix()
        try:
            donnees = yaml.safe_load(chemin.read_text(encoding="utf-8"))
            contenu = FichierContenu.model_validate(donnees)
        except yaml.YAMLError as exc:
            erreurs.append(f"{nom} : YAML invalide ({exc})")
            continue
        except ValidationError as exc:
            erreurs.extend(f"{nom} : {'.'.join(map(str, e['loc']))} : {e['msg']}" for e in exc.errors())
            continue
        ch = contenu.chapitre
        attendu = f"{DOSSIERS_NIVEAU[ch.niveau]}/{ch.parcours.value}/"
        if not nom.startswith(attendu) or nom.count("/") != 2:
            erreurs.append(f"{nom} : à ranger dans contenu/{attendu} (niveau {ch.niveau.value}, parcours {ch.parcours.value})")
        for c in contenu.competences:
            for champ, texte in c.textes():
                if texte and not _dollars_equilibres(texte):
                    erreurs.append(f"{nom} : {c.code}.{champ} : nombre impair de « $ » (formule non fermée)")
            for q in c.questions:
                if not q.code.startswith(c.code + "-"):
                    erreurs.append(f"{nom} : {q.code} : le code doit commencer par « {c.code}- »")
                if not _dollars_equilibres(q.enonce):
                    erreurs.append(f"{nom} : {q.code} : nombre impair de « $ » dans l'énoncé")
                if probleme := _verifier_question(q):
                    erreurs.append(f"{nom} : {q.code} : {probleme}")
                erreurs.extend(f"{nom} : {q.code} : {p}" for p in _verifier_correction(q))
        fichiers.append((chemin, contenu))

    _verifier_unicite(fichiers, dossier, erreurs)
    _verifier_liens(fichiers, dossier, codes_attendus, erreurs)
    if erreurs:
        raise ContenuInvalide(erreurs)
    return sorted(
        fichiers,
        key=lambda f: (ORDRE_NIVEAUX[f[1].chapitre.niveau], ORDRE_PARCOURS[f[1].chapitre.parcours], f[1].chapitre.ordre),
    )


def _verifier_unicite(fichiers, dossier: Path, erreurs: list[str]) -> None:
    vus: dict[tuple[str, str], str] = {}

    def noter(genre: str, cle: str, nom: str) -> None:
        if (genre, cle) in vus:
            erreurs.append(f"{nom} : {genre} « {cle} » déjà défini dans {vus[(genre, cle)]}")
        else:
            vus[(genre, cle)] = nom

    for chemin, contenu in fichiers:
        nom = chemin.relative_to(dossier).as_posix()
        noter("chapitre", contenu.chapitre.code, nom)
        noter("ordre", f"{contenu.chapitre.niveau.value} {contenu.chapitre.parcours.value} n°{contenu.chapitre.ordre}", nom)
        for c in contenu.competences:
            noter("compétence", c.code, nom)
            for q in c.questions:
                noter("question", q.code, nom)


# --- Import ------------------------------------------------------------------


@dataclass
class Rapport:
    crees: dict[str, int] = field(default_factory=lambda: {"chapitres": 0, "compétences": 0, "leçons": 0, "questions": 0})
    modifies: dict[str, int] = field(default_factory=lambda: {"chapitres": 0, "compétences": 0, "leçons": 0, "questions": 0})
    questions_archivees: list[str] = field(default_factory=list)
    # Modifiées dans l'IHM d'administration : laissées telles quelles (décision DA2), sauf --forcer.
    protegees: list[str] = field(default_factory=list)

    @property
    def vide(self) -> bool:
        return not any(self.crees.values()) and not any(self.modifies.values()) and not self.questions_archivees

    def __str__(self) -> str:
        if self.vide:
            return "Aucun changement : la base est à jour."
        lignes = [f"Créés   : {', '.join(f'{n} {k}' for k, n in self.crees.items() if n) or '—'}"]
        lignes.append(f"Modifiés : {', '.join(f'{n} {k}' for k, n in self.modifies.items() if n) or '—'}")
        if self.questions_archivees:
            lignes.append(f"Archivées (absentes des fichiers) : {', '.join(self.questions_archivees)}")
        return "\n".join(lignes)


def _appliquer(objet, valeurs: dict) -> bool:
    """Affecte les valeurs qui diffèrent ; indique si l'objet a changé."""
    change = False
    for cle, valeur in valeurs.items():
        if getattr(objet, cle) != valeur:
            setattr(objet, cle, valeur)
            change = True
    return change


def importer(
    session: Session,
    fichiers: list[tuple[Path, FichierContenu]],
    *,
    archiver_absentes: bool = True,
    simulation: bool = False,
    forcer: bool = False,
) -> Rapport:
    rapport = Rapport()

    # Les ordres de chapitre peuvent s'échanger entre deux imports : on les rend
    # provisoirement négatifs pour ne pas heurter la contrainte unique (niveau, ordre).
    chapitres = []
    for _, contenu in fichiers:
        ch = contenu.chapitre
        chapitre = session.scalar(select(models.Chapitre).where(models.Chapitre.code == ch.code))
        if chapitre is None:  # base antérieure à la migration 0004 : reconnu par sa position
            chapitre = session.scalar(
                select(models.Chapitre).where(
                    models.Chapitre.niveau == ch.niveau,
                    models.Chapitre.parcours == ch.parcours,
                    models.Chapitre.ordre == ch.ordre,
                )
            )
        chapitres.append(chapitre)
    for chapitre in chapitres:
        if chapitre is not None:
            chapitre.ordre = -chapitre.id
    session.flush()

    codes_importes: set[str] = set()
    for (_, contenu), chapitre in zip(fichiers, chapitres):
        ch = contenu.chapitre
        if chapitre is None:
            chapitre = models.Chapitre(code=ch.code, niveau=ch.niveau, parcours=ch.parcours, ordre=ch.ordre, titre=ch.titre)
            session.add(chapitre)
            rapport.crees["chapitres"] += 1
        else:
            avant = (chapitre.code, chapitre.niveau, chapitre.parcours, chapitre.titre)
            _appliquer(
                chapitre, {"code": ch.code, "niveau": ch.niveau, "parcours": ch.parcours, "titre": ch.titre, "ordre": ch.ordre}
            )
            rapport.modifies["chapitres"] += avant != (ch.code, ch.niveau, ch.parcours, ch.titre)

        for rang, c in enumerate(contenu.competences, start=1):
            competence = session.scalar(select(models.Competence).where(models.Competence.code == c.code))
            valeurs = {"libelle": c.libelle, "ordre": rang, "chapitre": chapitre, **_pedagogie(c)}
            if competence is None:
                competence = models.Competence(code=c.code, **valeurs)
                session.add(competence)
                rapport.crees["compétences"] += 1
            elif _appliquer(competence, valeurs):
                rapport.modifies["compétences"] += 1
            session.flush()
            _importer_lecon(session, competence, c, rapport, forcer)

            for q in c.questions:
                codes_importes.add(q.code)
                _importer_question(session, competence, q, rapport, forcer)

    if archiver_absentes:
        for question in session.scalars(
            select(models.Question).where(models.Question.code.is_not(None), models.Question.archivee.is_(False))
        ):
            if question.code not in codes_importes and (forcer or question.modifiee_admin_le is None):
                question.archivee = True
                rapport.questions_archivees.append(question.code)

    if simulation:
        session.rollback()
    else:
        session.commit()
    return rapport


def _pedagogie(c: CompetenceYaml) -> dict:
    """Champs structurés d'une compétence, stockés en JSON (listes vides si non renseignés)."""
    return {
        "attendus": list(c.attendus),
        "objectifs": list(c.objectifs),
        "prerequis": list(c.prerequis),
        "methodes": [m.model_dump(exclude_none=True) for m in c.methodes],
        "erreurs_frequentes": [e.model_dump() for e in c.erreurs_frequentes],
    }


def _importer_lecon(
    session: Session, competence: models.Competence, c: CompetenceYaml, rapport: Rapport, forcer: bool = False
) -> None:
    lecon = session.scalar(select(models.Lecon).where(models.Lecon.competence_id == competence.id))
    if lecon is not None and lecon.modifiee_admin_le is not None and not forcer:
        rapport.protegees.append(f"leçon {competence.code}")
        return
    if c.cours is None:
        if lecon is not None:  # leçon retirée du fichier
            session.delete(lecon)
            rapport.modifies["leçons"] += 1
        return
    valeurs = {"cours": c.cours.strip(), "resume": c.resume.strip()}
    if lecon is None:
        session.add(models.Lecon(competence=competence, **valeurs))
        rapport.crees["leçons"] += 1
    elif _appliquer(lecon, valeurs):
        rapport.modifies["leçons"] += 1


def _importer_question(
    session: Session, competence: models.Competence, q: QuestionYaml, rapport: Rapport, forcer: bool = False
) -> None:
    question = session.scalar(select(models.Question).where(models.Question.code == q.code))
    if question is None:
        # Question déjà présente sans code (base antérieure) : on l'adopte au lieu de la dupliquer.
        question = session.scalar(
            select(models.Question).where(
                models.Question.code.is_(None),
                models.Question.competence_id == competence.id,
                models.Question.enonce == q.enonce,
            )
        )
    if question is not None and question.modifiee_admin_le is not None and not forcer:
        rapport.protegees.append(q.code)
        return
    valeurs = {
        "code": q.code,
        "competence": competence,
        "enonce": q.enonce,
        "type": q.type,
        "solution": q.solution,
        "difficulte": q.difficulte,
        "archivee": q.archivee,
        "source": q.source,
        "source_url": q.source_url,
        "licence_source": q.licence_source,
        "adaptation": q.adaptation,
        "statut_validation": q.validation.statut,
        "valide_par": q.validation.par,
        "valide_le": q.validation.le,
        "auteur": q.auteur,
        "correction": q.correction.model_dump(exclude_none=True) if q.correction else None,
        "competences_secondaires": list(q.competences_secondaires),
    }
    if question is None:
        session.add(models.Question(**valeurs))
        rapport.crees["questions"] += 1
    elif _appliquer(question, valeurs):
        rapport.modifies["questions"] += 1


# --- Inventaire et matrice de couverture ---------------------------------------

DIFFICULTES = range(1, 6)
INVENTAIRE_PAR_DEFAUT = Path(__file__).resolve().parents[2] / "docs" / "CONTENU-INVENTAIRE.md"
MATRICES_PAR_DEFAUT = Path(__file__).resolve().parents[2] / "docs" / "matrices"


def inventaire(fichiers: list[tuple[Path, FichierContenu]]) -> str:
    """Matrice niveau → parcours → chapitre → compétence × difficulté, en Markdown.

    Signale les trous : niveau de difficulté sans question, compétence sans cours,
    questions à valider. Le registre des sources récapitule l'origine des questions.
    """
    from collections import Counter

    from app.referentiel import LIBELLES_PARCOURS

    actives = [(f, c, q) for _, f in fichiers for c in f.competences for q in c.questions if not q.archivee]
    statuts = Counter(q.validation.statut.value for _, _, q in actives)
    lignes = [
        "# Inventaire de la banque de questions",
        "",
        "Fichier **généré** par `python -m app.contenu inventaire` (depuis `api/`) : ne pas modifier à la main.",
        "",
        f"- Chapitres : **{len(fichiers)}** · compétences : **{sum(len(f.competences) for _, f in fichiers)}** · "
        f"questions actives : **{len(actives)}**",
        f"- Validation pédagogique : {statuts.get('validee', 0)} validée(s), {statuts.get('a-valider', 0)} à valider, "
        f"{statuts.get('a-corriger', 0)} à corriger",
        "",
        "## Matrice de couverture",
        "",
        "Nombre de questions actives par difficulté (1 = application directe … 5 = niveau bac). "
        "⚠ signale un trou : une difficulté sans question, ou une compétence sans cours.",
        "",
    ]
    trous: list[str] = []
    niveau_courant = None
    for _, f in fichiers:
        ch = f.chapitre
        if (ch.niveau, ch.parcours) != niveau_courant:
            if niveau_courant is not None:
                lignes.append("")
            niveau_courant = (ch.niveau, ch.parcours)
            lignes += [f"### {ch.niveau.value} — {LIBELLES_PARCOURS[ch.parcours]}", "",
                       "| Chapitre | Compétence | Cours | 1 | 2 | 3 | 4 | 5 | Total | À valider |",
                       "|---|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|"]
        for c in f.competences:
            qs = [q for q in c.questions if not q.archivee]
            par_difficulte = Counter(q.difficulte for q in qs)
            cellules = [str(par_difficulte[d]) if par_difficulte[d] else "⚠ 0" for d in DIFFICULTES]
            manquantes = [str(d) for d in DIFFICULTES if not par_difficulte[d]]
            if manquantes:
                trous.append(f"`{c.code}` ({c.libelle}) : aucune question de difficulté {', '.join(manquantes)}")
            if c.cours is None:
                trous.append(f"`{c.code}` ({c.libelle}) : pas de cours")
            a_valider = sum(q.validation.statut is not StatutValidation.VALIDEE for q in qs)
            lignes.append(
                f"| {ch.ordre}. {ch.titre} | `{c.code}` {c.libelle} | {'✓' if c.cours else '⚠'} | "
                + " | ".join(cellules) + f" | {len(qs)} | {a_valider} |"
            )
    lignes += ["", "## Trous à combler", ""] + ([f"- {t}" for t in trous] or ["Aucun."])

    sources = Counter((q.source, q.licence_source or "—", q.adaptation.value) for _, _, q in actives)
    lignes += ["", "## Registre des sources", "", "| Source | Licence de la source | Adaptation | Questions |", "|---|---|---|:-:|"]
    lignes += [f"| {s} | {lic} | {a} | {n} |" for (s, lic, a), n in sorted(sources.items(), key=lambda x: (-x[1], x[0]))]
    return "\n".join(lignes) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Contenu pédagogique PKP Math Lycée")
    parser.add_argument("commande", choices=["verifier", "importer", "inventaire", "matrice", "ecarts"])
    parser.add_argument("--programme", help="matrice, ecarts : code du programme (défaut : tous)")
    parser.add_argument("--dossier", type=Path, default=DOSSIER_PAR_DEFAUT)
    parser.add_argument("--simulation", action="store_true", help="importer : montre les changements sans les appliquer")
    parser.add_argument(
        "--forcer", action="store_true", help="importer : écrase aussi les leçons et questions modifiées dans l'administration"
    )
    parser.add_argument("--sortie", type=Path, default=INVENTAIRE_PAR_DEFAUT, help="inventaire : fichier Markdown produit")
    args = parser.parse_args()
    # Console Windows (cp1252) : les symboles de statut (✗ ◐ ✓) ne doivent pas faire échouer la commande.
    sys.stdout.reconfigure(errors="replace")

    try:
        fichiers = charger(args.dossier)
    except ContenuInvalide as exc:
        sys.exit(str(exc))
    nb_questions = sum(len(c.questions) for _, f in fichiers for c in f.competences)
    print(f"Contenu valide : {len(fichiers)} chapitre(s), {nb_questions} question(s).")
    if args.commande == "inventaire":
        args.sortie.write_text(inventaire(fichiers), encoding="utf-8")
        print(f"Inventaire écrit dans {args.sortie}")
    if args.commande in ("matrice", "ecarts"):
        from app import matrice

        try:
            referentiels = programmes.charger()
        except programmes.ReferentielInvalide as exc:
            sys.exit(str(exc))
        codes = [args.programme] if args.programme else list(referentiels.programmes)
        if inconnus := [c for c in codes if c not in referentiels.programmes]:
            sys.exit(f"Programme inconnu : {', '.join(inconnus)} (connus : {', '.join(referentiels.programmes)})")
        for code in codes:
            if args.commande == "ecarts":
                print(matrice.ecarts(referentiels, fichiers, code))
                continue
            sortie = MATRICES_PAR_DEFAUT / f"MATRICE-{code}.md"
            sortie.parent.mkdir(parents=True, exist_ok=True)
            sortie.write_text(matrice.en_markdown(referentiels, fichiers, code, date.today()), encoding="utf-8")
            print(f"Matrice écrite dans {sortie}")
    if args.commande == "importer":
        from app.db.session import SessionLocale

        with SessionLocale() as session:
            rapport = importer(session, fichiers, simulation=args.simulation, forcer=args.forcer)
        print(("[simulation] " if args.simulation else "") + str(rapport))


if __name__ == "__main__":
    main()
