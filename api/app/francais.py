"""Dossiers de français : contrat du fichier d'import, import idempotent, vues séparées et circuit de validation.

Contrat documenté dans docs/francais/FORMAT-IMPORT.md. Le dépôt (contenu/francais) fournit les versions ; l'import
ne modifie jamais une version existante : un fichier identique ne crée rien, un fichier modifié crée une nouvelle
version soumise à relecture.

Garde-fous (#98) :
- les questions du dossier sont rédigées et relèvent d'un retour humain : ni solution automatique, ni barème, ni
  note ; l'élève peut les saisir en ligne et son professeur y répond (#217, règles RGPD-2) ;
- seul le **quiz** facultatif (#217, comme l'anglais) est corrigé par la plateforme : QCM dont la bonne réponse et
  l'explication sont stockées à part (`version.quiz`) et ne sont rendues à l'élève qu'après sa réponse (ARCH-4) ;
- la partie élève et la partie professeur sont stockées séparément ; un corrigé recopié côté élève est refusé ;
- préparation réservée aux adultes habilités dans le domaine (ou à un administrateur) ;
- diffusion (#212, même circuit que l'anglais) : un élève ne lit que la partie élève de la version **validée**, et
  seulement si son professeur a ouvert le dossier à sa classe et que la classe a accès au domaine (classe pilote d'un
  domaine fermé, SEC-D6). Une révision soumise ou refusée ne remplace jamais la version validée déjà diffusée.
"""
# Issue #98 — Intégration du premier dossier Français 3e en DEV (Claude)

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import circuit_validation, permissions
from app.db import models
from app.referentiel import Role

DOSSIER_PAR_DEFAUT = Path(__file__).resolve().parents[2] / "contenu" / "francais"
FORMAT = "boussole-francais-dossier/1"
DOMAINES_FRANCAIS = {d.code: d for d in permissions.DOMAINES if d.matiere == "francais"}

Texte = Annotated[str, StringConstraints(strip_whitespace=False, min_length=1, max_length=5000)]
Court = Annotated[str, StringConstraints(min_length=1, max_length=300)]


class _Strict(BaseModel):
    # Champ inconnu refusé : ni « solution », ni « bareme », ni « points » ne peuvent entrer par le fichier.
    model_config = ConfigDict(extra="forbid")


class Attribution(_Strict):
    redaction: Court
    redaction_issue: int | None = None
    redaction_pr: int | None = None
    redaction_le: Court
    integration: Court
    integration_issue: int | None = None
    sources_markdown: list[Court] = []


class Registre(_Strict):
    source: Court
    source_url: Court | None = None
    licence_source: Court | None = None
    adaptation: Literal["originale", "adaptee", "reprise"]
    mention: Texte | None = None


class Section(_Strict):
    titre: Court
    markdown: Texte


class TexteSupport(_Strict):
    code: Annotated[str, StringConstraints(pattern=r"^[A-Z0-9-]{1,20}$")]
    titre: Court
    lignes: list[Texte] = Field(min_length=1, max_length=200)
    mention: Texte | None = None


class ModeReponse(_Strict):
    # Seul mode accepté : la réponse est rédigée et relue par un adulte. Aucune correction automatique.
    mode: Literal["retour_humain"]


class Question(_Strict):
    code: Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9]{0,9}$")]
    partie: Literal["entrainement", "transfert"]
    texte: str
    # Proposition pédagogique à confirmer par le professeur : ni difficulté du moteur, ni taux de maîtrise.
    difficulte_proposee: Annotated[int, Field(ge=1, le=5)] | None = None
    consigne: Texte
    coup_de_pouce: Texte | None = None
    reponse: ModeReponse


class PartieEleve(_Strict):
    presentation: list[Texte] = []
    objectifs: list[Texte] = []
    lecon: list[Section] = Field(min_length=1)
    textes: list[TexteSupport] = Field(min_length=1)
    consignes_questions: list[Texte] = []
    questions: list[Question] = Field(min_length=1)
    je_verifie: Texte | None = None
    # Auto-évaluation (#217, comme le « I can » de l'anglais) : « Je sais… », un niveau par phrase.
    je_sais: list[Court] = Field(default=[], max_length=10)


class EtapeDeroulement(_Strict):
    duree: Court
    activite: Texte
    observation: Texte


class Deroulement(_Strict):
    titre: Court
    etapes: list[EtapeDeroulement] = []
    adaptations: list[Texte] = []


class Corrige(_Strict):
    question: str
    intitule: Court | None = None
    paragraphes: list[Texte] = Field(min_length=1)


class CritereGrille(_Strict):
    critere: Court
    questions: Court
    indice: Texte


class Grille(_Strict):
    titre: Court
    criteres: list[CritereGrille] = []
    consignes: list[Texte] = []


class PartieProfesseur(_Strict):
    presentation: list[Texte] = []
    deroulement: Deroulement | None = None
    principes_correction: Texte | None = None
    corriges: list[Corrige] = Field(min_length=1)
    grille: Grille | None = None
    controle_avant_utilisation: list[Texte] = []
    remarques: list[Texte] = []
    retour_seance: Texte | None = None


class QuestionQuiz(_Strict):
    """Question du quiz corrigé (#217) : la bonne réponse est l'indice d'un choix, avec une explication."""

    question: Texte
    texte: Annotated[str, StringConstraints(pattern=r"^[A-Z0-9-]{1,20}$")] | None = None  # texte support cité
    choix: list[Court] = Field(min_length=2, max_length=6)
    reponse: Annotated[int, Field(ge=0)]
    explication: Texte

    @model_validator(mode="after")
    def _choix(self):
        if self.reponse >= len(self.choix):
            raise ValueError("la bonne réponse doit désigner un des choix")
        if len({c.strip().casefold() for c in self.choix}) != len(self.choix):
            raise ValueError("deux choix identiques")
        return self


class FichierDossier(_Strict):
    format: Literal["boussole-francais-dossier/1"]
    code: Annotated[str, StringConstraints(pattern=r"^FR[0-9A-Z-]{2,28}$")]
    domaine: str
    niveau: str
    titre: Court
    cible: Court | None = None
    competences_locales: list[Court] = []
    attribution: Attribution
    registre: Registre
    eleve: PartieEleve
    professeur: PartieProfesseur
    quiz: list[QuestionQuiz] = Field(default=[], max_length=30)

    @model_validator(mode="after")
    def _coherence(self):
        domaine = DOMAINES_FRANCAIS.get(self.domaine)
        if domaine is None:
            raise ValueError(f"domaine « {self.domaine} » : un dossier de français relève de {sorted(DOMAINES_FRANCAIS)}")
        if self.niveau not in domaine.niveaux:
            raise ValueError(f"niveau « {self.niveau} » absent de {domaine.libelle}")
        codes_textes = [t.code for t in self.eleve.textes]
        codes_questions = [q.code for q in self.eleve.questions]
        for nom, codes in (("texte", codes_textes), ("question", codes_questions)):
            if doublons := sorted({c for c in codes if codes.count(c) > 1}):
                raise ValueError(f"code de {nom} en double : {', '.join(doublons)}")
        if inconnus := sorted({q.texte for q in self.eleve.questions} - set(codes_textes)):
            raise ValueError(f"texte inconnu cité par une question : {', '.join(inconnus)}")
        if inconnus := sorted({q.texte for q in self.quiz if q.texte} - set(codes_textes)):
            raise ValueError(f"texte inconnu cité par le quiz : {', '.join(inconnus)}")
        corriges = [c.question for c in self.professeur.corriges]
        if doublons := sorted({c for c in corriges if corriges.count(c) > 1}):
            raise ValueError(f"corrigé en double : {', '.join(doublons)}")
        if manquants := [c for c in codes_questions if c not in corriges]:
            raise ValueError(f"question sans corrigé : {', '.join(manquants)}")
        if orphelins := [c for c in corriges if c not in codes_questions]:
            raise ValueError(f"corrigé sans question : {', '.join(orphelins)}")
        # Aucun corrigé ne doit se retrouver dans la partie élève (protection des solutions, ARCH-4).
        cote_eleve = "\n".join(_textes(self.eleve.model_dump()))
        for c in self.professeur.corriges:
            for p in c.paragraphes:
                if len(p) >= 40 and p in cote_eleve:
                    raise ValueError(f"le corrigé de {c.question} figure dans la partie élève")
        return self


def _textes(valeur) -> list[str]:
    if isinstance(valeur, str):
        return [valeur]
    if isinstance(valeur, dict):
        return [t for v in valeur.values() for t in _textes(v)]
    if isinstance(valeur, list):
        return [t for v in valeur for t in _textes(v)]
    return []


class DossierInvalide(ValueError):
    def __init__(self, erreurs: list[str]):
        self.erreurs = erreurs
        super().__init__("Contenu français invalide :\n" + "\n".join(f"  - {e}" for e in erreurs))


def empreinte(donnees: dict) -> str:
    """SHA-256 du contenu normalisé : l'ordre des clés et l'indentation du fichier n'en changent pas la valeur.

    Un quiz vide n'entre pas dans l'empreinte : les dossiers importés avant #217 gardent la leur (pas de version
    fantôme au déploiement)."""
    if not donnees.get("quiz"):
        donnees = {k: v for k, v in donnees.items() if k != "quiz"}
    if isinstance(donnees.get("eleve"), dict) and not donnees["eleve"].get("je_sais"):
        donnees = {**donnees, "eleve": {k: v for k, v in donnees["eleve"].items() if k != "je_sais"}}
    canon = json.dumps(donnees, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


@dataclass
class Charge:
    chemin: Path
    dossier: FichierDossier
    empreinte: str


def charger(dossier: Path = DOSSIER_PAR_DEFAUT) -> list[Charge]:
    """Lit et contrôle tous les fichiers ; lève DossierInvalide avec toutes les erreurs trouvées."""
    erreurs: list[str] = []
    charges: list[Charge] = []
    chemins = sorted(dossier.rglob("*.json")) if dossier.is_dir() else []
    for chemin in chemins:
        nom = chemin.relative_to(dossier).as_posix()
        try:
            brut = json.loads(chemin.read_text(encoding="utf-8"))
            fichier = FichierDossier.model_validate(brut)
        except json.JSONDecodeError as exc:
            erreurs.append(f"{nom} : JSON invalide ({exc})")
            continue
        except ValidationError as exc:
            erreurs.extend(f"{nom} : {'.'.join(map(str, e['loc'])) or 'fichier'} : {e['msg']}" for e in exc.errors())
            continue
        if not nom.startswith(f"{fichier.niveau}/"):
            erreurs.append(f"{nom} : à ranger dans contenu/francais/{fichier.niveau}/")
        # Empreinte du contenu validé (les valeurs par défaut comprises) : stable quelle que soit la mise en forme.
        charges.append(Charge(chemin, fichier, empreinte(fichier.model_dump(mode="json"))))
    codes = [c.dossier.code for c in charges]
    erreurs.extend(f"code de dossier en double : {c}" for c in sorted({c for c in codes if codes.count(c) > 1}))
    if erreurs:
        raise DossierInvalide(erreurs)
    return charges


# --- Import idempotent ---------------------------------------------------------------------------

@dataclass
class RapportImport:
    crees: list[str] = field(default_factory=list)
    nouvelles_versions: list[str] = field(default_factory=list)
    inchanges: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return (f"Dossiers de français : {len(self.crees)} créé(s), {len(self.nouvelles_versions)} nouvelle(s) version(s), "
                f"{len(self.inchanges)} inchangé(s). Aucune publication aux élèves.")


def importer(session: Session, charges: list[Charge], simulation: bool = False) -> RapportImport:
    """Ajoute ce qui manque, sans jamais modifier une version existante ni toucher aux domaines.

    - dossier absent : créé, version 1 « soumis » (à relire par un validateur habilité) ;
    - fichier déjà importé (même empreinte, quelle que soit la version) : rien ;
    - fichier modifié : nouvelle version « soumis » ; la version validée éventuelle reste en place.
    """
    rapport = RapportImport()
    for c in charges:
        f = c.dossier
        dossier = session.scalar(select(models.DossierFrancais).where(models.DossierFrancais.code == f.code))
        donnees = f.model_dump(mode="json")
        meta = {k: donnees[k] for k in ("format", "cible", "competences_locales", "attribution", "registre")}
        if dossier is None:
            rapport.crees.append(f.code)
            if simulation:
                continue
            dossier = models.DossierFrancais(code=f.code, domaine_code=f.domaine, niveau=f.niveau, titre=f.titre)
            session.add(dossier)
        elif any(v.empreinte == c.empreinte for v in dossier.versions):
            rapport.inchanges.append(f.code)
            continue
        else:
            if dossier.domaine_code != f.domaine or dossier.niveau != f.niveau:
                raise DossierInvalide([f"{f.code} : le domaine et le niveau d'un dossier existant ne changent pas"])
            rapport.nouvelles_versions.append(f.code)
            if simulation:
                continue
            dossier.titre = f.titre
        numero = (dossier.versions[-1].numero + 1) if dossier.versions else 1
        dossier.versions.append(models.DossierFrancaisVersion(
            numero=numero, eleve=donnees["eleve"], professeur=donnees["professeur"], quiz=donnees["quiz"], meta=meta,
            empreinte=c.empreinte, statut="soumis",
        ))
    if not simulation:
        session.commit()
    return rapport


# --- Accès des adultes ---------------------------------------------------------------------------

def peut_lire(enseignant: models.Enseignant, domaine: str, niveau: str | None) -> bool:
    """Administrateur, ou professeur/validateur habilité dans ce domaine (pour tout le domaine ou ce niveau)."""
    if enseignant.role == Role.ADMIN:
        return True
    return any(
        h.domaine_code == domaine and (niveau is None or h.niveau is None or h.niveau == niveau)
        for h in enseignant.habilitations
    )


# Administrateur compris (V2-D15) ; l'auteur d'une version ne la valide jamais (`peut_decider`).
peut_valider = permissions.peut_valider
refus_validation = permissions.refus_validation


def domaine_actif(session: Session, domaine: str) -> bool:
    d = session.get(models.DomainePedagogique, domaine)
    return bool(d and d.actif)


def lisibles(session: Session, enseignant: models.Enseignant) -> list[models.DossierFrancais]:
    dossiers = session.scalars(select(models.DossierFrancais).order_by(models.DossierFrancais.code))
    return [d for d in dossiers if domaine_actif(session, d.domaine_code) and peut_lire(enseignant, d.domaine_code, d.niveau)]


def etat(session: Session) -> dict:
    """État du français sur l'instance, pour l'administrateur (#212) : domaines et nombre de dossiers par domaine.

    Explique une liste vide ou un refus sans rien divulguer d'autre : ni contenu de dossier, ni donnée personnelle.
    """
    nombres = dict(session.execute(
        select(models.DossierFrancais.domaine_code, func.count(models.DossierFrancais.id))
        .group_by(models.DossierFrancais.domaine_code)
    ).all())
    domaines = [
        {"code": code, "libelle": d.libelle, "actif": domaine_actif(session, code), "dossiers": nombres.get(code, 0)}
        for code, d in DOMAINES_FRANCAIS.items()
    ]
    return {"domaines": domaines, "dossiers": sum(nombres.values())}


# --- Vues ------------------------------------------------------------------------------------------

def version_professeur(dossier: models.DossierFrancais) -> models.DossierFrancaisVersion:
    """Comme l'anglais : la version validée si elle existe (celle que voient les élèves) ; sinon la version courante,
    montrée avec la mention NON VALIDÉ. La relecture d'une version soumise passe par la file de validation."""
    return dossier.validee or dossier.courante


def vue_eleve(version: models.DossierFrancaisVersion) -> dict:
    """Ce qu'un élève voit : leçon, textes et consignes, sans aucun corrigé ni consigne professeur (ARCH-4).

    Servie aux élèves pour la seule version validée d'un dossier ouvert à leur classe, et aux adultes comme aperçu.
    """
    e = version.eleve
    return {
        "presentation": e.get("presentation", []), "objectifs": e.get("objectifs", []), "lecon": e["lecon"],
        "textes": e["textes"], "consignes_questions": e.get("consignes_questions", []),
        "questions": [
            {k: q.get(k) for k in ("code", "partie", "texte", "difficulte_proposee", "consigne", "coup_de_pouce")}
            | {"retour": "humain"}
            for q in e["questions"]
        ],
        "je_verifie": e.get("je_verifie"), "je_sais": e.get("je_sais", []),
        # Quiz (#217) : questions et choix seulement ; bonne réponse et explication après la réponse (ARCH-4).
        "quiz": [{"question": q["question"], "texte": q.get("texte"), "choix": q["choix"]} for q in version.quiz or []],
    }


def vue_professeur(version: models.DossierFrancaisVersion) -> dict:
    """Supports professeur : corrigés rapprochés de chaque question, déroulement, grille et contrôles."""
    corriges = {c["question"]: c for c in version.professeur["corriges"]}
    return {
        **version.professeur,
        "questions": [
            {"code": q["code"], "partie": q["partie"], "consigne": q["consigne"], "corrige": corriges[q["code"]]}
            for q in version.eleve["questions"]
        ],
        "quiz": list(version.quiz or []),
    }


def resume(dossier: models.DossierFrancais, qui: models.Enseignant | None = None) -> dict:
    c, v = dossier.courante, dossier.validee
    ligne = {
        "code": dossier.code, "titre": dossier.titre, "domaine": dossier.domaine_code, "niveau": dossier.niveau,
        "libelle_domaine": permissions.LIBELLES.get(dossier.domaine_code, dossier.domaine_code),
        "version": c.numero, "statut": c.statut, "motif_refus": c.motif_refus,
        "version_validee": v.numero if v else None, "nb_questions": len(c.eleve["questions"]),
        "nb_quiz": len(c.quiz or []),
        "attribution": c.meta.get("attribution", {}), "registre": c.meta.get("registre", {}),
        "cible": c.meta.get("cible"), "competences_locales": c.meta.get("competences_locales", []),
        "auteur": c.auteur.nom if c.auteur else None, "validateur": c.validateur.nom if c.validateur else None,
        "decide_le": c.decide_le.isoformat() if c.decide_le else None,
        # Diffusé : version validée ET ouverte à au moins une classe (l'accès de chaque classe suit SEC-D6).
        "classes_ouvertes": len(dossier.ouvertures),
        "visible_eleves": v is not None and bool(dossier.ouvertures),
    }
    if qui is not None:
        ligne["peut_valider"] = (
            c.statut == "soumis" and c.auteur_id != qui.id
            and peut_valider(qui, dossier.domaine_code, dossier.niveau)
        )
        ligne["est_auteur"] = c.auteur_id is not None and c.auteur_id == qui.id
    return ligne


def a_valider(session: Session, qui: models.Enseignant) -> list[models.DossierFrancais]:
    """File de validation, comme l'anglais : versions soumises que ce validateur est qualifié pour relire.

    Ses propres versions y figurent, signalées par `est_auteur` : il ne peut pas les valider.
    """
    return [
        d for d in lisibles(session, qui)
        if d.courante.statut == "soumis" and peut_valider(qui, d.domaine_code, d.niveau)
    ]


# --- Ouverture aux classes (#212) -----------------------------------------------------------------------------

def niveau_de(classe: models.Classe) -> str:
    return getattr(classe.niveau, "value", classe.niveau)


def classes_compatibles(enseignant: models.Enseignant, dossier: models.DossierFrancais) -> list[models.Classe]:
    """Classes actives de ce professeur, du domaine et du niveau du dossier."""
    return sorted(
        (c for c in enseignant.classes
         if c.archivee_le is None and c.domaine_code == dossier.domaine_code and niveau_de(c) == dossier.niveau),
        key=lambda c: c.code,
    )


def ouverture(dossier: models.DossierFrancais, classe: models.Classe) -> models.OuvertureDossierFrancais | None:
    return next((o for o in dossier.ouvertures if o.classe_id == classe.id), None)


def ouverts_a(session: Session, classe: models.Classe) -> list[models.DossierFrancais]:
    """Dossiers que les élèves de la classe peuvent lire : ouverts par le professeur, version validée existante,
    domaine actif et accès de la classe accordé (SEC-D6) ; aucun sinon."""
    if not classe.domaine_code.startswith("francais-") or permissions.refus_acces_classe(session, classe):
        return []
    dossiers = session.scalars(
        select(models.DossierFrancais)
        .join(models.OuvertureDossierFrancais)
        .where(models.OuvertureDossierFrancais.classe_id == classe.id)
        .order_by(models.DossierFrancais.code)
    )
    return [
        d for d in dossiers
        if d.validee is not None and d.domaine_code == classe.domaine_code and d.niveau == niveau_de(classe)
        and domaine_actif(session, d.domaine_code)
    ]


def historique(dossier: models.DossierFrancais) -> list[dict]:
    return [
        {"numero": v.numero, "statut": v.statut, "empreinte": v.empreinte,
         "auteur": v.auteur.nom if v.auteur else "Import du dépôt",
         "cree_le": v.cree_le.isoformat() if v.cree_le else None,
         "validateur": v.validateur.nom if v.validateur else None,
         "decide_le": v.decide_le.isoformat() if v.decide_le else None, "motif_refus": v.motif_refus}
        for v in reversed(dossier.versions)
    ]


# --- Circuit de validation (décision humaine uniquement) ------------------------------------------

# Circuit commun aux contenus versionnés (#215) : mêmes règles qu'en anglais.
peut_decider = circuit_validation.peut_decider
valider = circuit_validation.valider
refuser = circuit_validation.refuser


# --- Ligne de commande -----------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Dossiers de français (contenu/francais) : contrôle et import")
    parser.add_argument("commande", choices=["verifier", "importer"])
    parser.add_argument("--dossier", type=Path, default=DOSSIER_PAR_DEFAUT)
    parser.add_argument("--simulation", action="store_true", help="importer : montre les changements sans les appliquer")
    args = parser.parse_args()
    sys.stdout.reconfigure(errors="replace")
    try:
        charges = charger(args.dossier)
    except DossierInvalide as exc:
        sys.exit(str(exc))
    nb_questions = sum(len(c.dossier.eleve.questions) for c in charges)
    print(f"Contenu français valide : {len(charges)} dossier(s), {nb_questions} question(s) à retour humain.")
    if args.commande == "importer":
        from app.db.session import SessionLocale

        with SessionLocale() as session:
            rapport = importer(session, charges, simulation=args.simulation)
        print(("[simulation] " if args.simulation else "") + str(rapport))


if __name__ == "__main__":
    main()
