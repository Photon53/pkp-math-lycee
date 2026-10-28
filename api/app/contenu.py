"""Contenu pédagogique versionné : contenu/<niveau>/<NN-chapitre>.yaml → base de données.

Un fichier = un chapitre, ses compétences, leur cours/résumé (Markdown + LaTeX)
et leurs questions. Voir docs/CONTENU.md pour le format.

Usage, depuis `api/` :
    python -m app.contenu verifier              # contrôle tous les fichiers, sans base
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
from pathlib import Path
from typing import Annotated

import pkp_engine
import yaml
from pkp_engine import ExpressionInvalide, Niveau, TypeQuestion
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models

DOSSIER_PAR_DEFAUT = Path(__file__).resolve().parents[2] / "contenu"
ORDRE_NIVEAUX = {Niveau.SECONDE: 0, Niveau.PREMIERE: 1, Niveau.TERMINALE: 2}

Code = Annotated[str, Field(pattern=r"^[A-Z0-9][A-Z0-9-]{1,59}$")]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QuestionYaml(_Strict):
    code: Code
    difficulte: Annotated[int, Field(ge=1, le=5)]
    type: TypeQuestion
    enonce: Annotated[str, Field(min_length=1, max_length=2000)]
    solution: Annotated[str, Field(min_length=1, max_length=200)]
    archivee: bool = False

    @field_validator("solution", mode="before")
    @classmethod
    def _texte(cls, v):
        # YAML lit « 32 » comme un entier : la solution est toujours du texte.
        return str(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v

    @field_validator("enonce")
    @classmethod
    def _sans_espaces_finaux(cls, v: str) -> str:
        return v.strip()


class CompetenceYaml(_Strict):
    code: Code
    libelle: Annotated[str, Field(min_length=1, max_length=200)]
    cours: str | None = None
    resume: str | None = None
    questions: list[QuestionYaml] = []

    @model_validator(mode="after")
    def _lecon_complete(self):
        if (self.cours is None) != (self.resume is None):
            raise ValueError("`cours` et `resume` vont ensemble : renseigner les deux ou aucun")
        return self


class ChapitreYaml(_Strict):
    code: Code
    niveau: Niveau
    ordre: Annotated[int, Field(ge=1, le=99)]
    titre: Annotated[str, Field(min_length=1, max_length=200)]


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


def charger(dossier: Path = DOSSIER_PAR_DEFAUT) -> list[tuple[Path, FichierContenu]]:
    """Lit et vérifie tous les fichiers. Lève ContenuInvalide avec toutes les erreurs trouvées."""
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
        for c in contenu.competences:
            for champ in ("cours", "resume"):
                texte = getattr(c, champ)
                if texte and not _dollars_equilibres(texte):
                    erreurs.append(f"{nom} : {c.code}.{champ} : nombre impair de « $ » (formule non fermée)")
            for q in c.questions:
                if not q.code.startswith(c.code + "-"):
                    erreurs.append(f"{nom} : {q.code} : le code doit commencer par « {c.code}- »")
                if not _dollars_equilibres(q.enonce):
                    erreurs.append(f"{nom} : {q.code} : nombre impair de « $ » dans l'énoncé")
                if probleme := _verifier_question(q):
                    erreurs.append(f"{nom} : {q.code} : {probleme}")
        fichiers.append((chemin, contenu))

    _verifier_unicite(fichiers, dossier, erreurs)
    if erreurs:
        raise ContenuInvalide(erreurs)
    return sorted(fichiers, key=lambda f: (ORDRE_NIVEAUX[f[1].chapitre.niveau], f[1].chapitre.ordre))


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
        noter("ordre", f"{contenu.chapitre.niveau.value} n°{contenu.chapitre.ordre}", nom)
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
                select(models.Chapitre).where(models.Chapitre.niveau == ch.niveau, models.Chapitre.ordre == ch.ordre)
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
            chapitre = models.Chapitre(code=ch.code, niveau=ch.niveau, ordre=ch.ordre, titre=ch.titre)
            session.add(chapitre)
            rapport.crees["chapitres"] += 1
        else:
            avant = (chapitre.code, chapitre.niveau, chapitre.titre)
            _appliquer(chapitre, {"code": ch.code, "niveau": ch.niveau, "titre": ch.titre, "ordre": ch.ordre})
            rapport.modifies["chapitres"] += avant != (ch.code, ch.niveau, ch.titre)

        for rang, c in enumerate(contenu.competences, start=1):
            competence = session.scalar(select(models.Competence).where(models.Competence.code == c.code))
            if competence is None:
                competence = models.Competence(code=c.code, libelle=c.libelle, ordre=rang, chapitre=chapitre)
                session.add(competence)
                rapport.crees["compétences"] += 1
            elif _appliquer(competence, {"libelle": c.libelle, "ordre": rang, "chapitre": chapitre}):
                rapport.modifies["compétences"] += 1
            session.flush()
            _importer_lecon(session, competence, c, rapport)

            for q in c.questions:
                codes_importes.add(q.code)
                _importer_question(session, competence, q, rapport)

    if archiver_absentes:
        for question in session.scalars(
            select(models.Question).where(models.Question.code.is_not(None), models.Question.archivee.is_(False))
        ):
            if question.code not in codes_importes:
                question.archivee = True
                rapport.questions_archivees.append(question.code)

    if simulation:
        session.rollback()
    else:
        session.commit()
    return rapport


def _importer_lecon(session: Session, competence: models.Competence, c: CompetenceYaml, rapport: Rapport) -> None:
    lecon = session.scalar(select(models.Lecon).where(models.Lecon.competence_id == competence.id))
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


def _importer_question(session: Session, competence: models.Competence, q: QuestionYaml, rapport: Rapport) -> None:
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
    valeurs = {
        "code": q.code,
        "competence": competence,
        "enonce": q.enonce,
        "type": q.type,
        "solution": q.solution,
        "difficulte": q.difficulte,
        "archivee": q.archivee,
    }
    if question is None:
        session.add(models.Question(**valeurs))
        rapport.crees["questions"] += 1
    elif _appliquer(question, valeurs):
        rapport.modifies["questions"] += 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Contenu pédagogique PKP Math Lycée")
    parser.add_argument("commande", choices=["verifier", "importer"])
    parser.add_argument("--dossier", type=Path, default=DOSSIER_PAR_DEFAUT)
    parser.add_argument("--simulation", action="store_true", help="importer : montre les changements sans les appliquer")
    args = parser.parse_args()

    try:
        fichiers = charger(args.dossier)
    except ContenuInvalide as exc:
        sys.exit(str(exc))
    nb_questions = sum(len(c.questions) for _, f in fichiers for c in f.competences)
    print(f"Contenu valide : {len(fichiers)} chapitre(s), {nb_questions} question(s).")
    if args.commande == "importer":
        from app.db.session import SessionLocale

        with SessionLocale() as session:
            rapport = importer(session, fichiers, simulation=args.simulation)
        print(("[simulation] " if args.simulation else "") + str(rapport))


if __name__ == "__main__":
    main()
