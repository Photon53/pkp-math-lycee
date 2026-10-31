"""Référentiels officiels : ce que l'élève doit apprendre, attendu par attendu (programmes du BO).

Trois objets distincts, reliés par des identifiants stables :
- le référentiel (ici) : les attendus officiels, recopiés du BO, avec leur source ;
- le contenu (app/contenu.py) : chaque compétence déclare les attendus qu'elle couvre ;
- l'évaluation : les questions de la compétence, validées ou non.

Arborescence, depuis la racine du dépôt :
    referentiels/sources/sources.yaml        PDF officiels conservés, avec leur empreinte SHA-256
    referentiels/<programme>/programme.yaml  métadonnées du programme (BO, niveau, parcours, période)
    referentiels/<programme>/<theme>.yaml    les attendus d'un thème

Un programme est nommé par sa classe et son année de publication (1re-specialite-2026,
tle-specialite-2019), jamais par l'année scolaire : il s'applique plusieurs années de suite.
"""

import hashlib
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Annotated

import yaml
from pkp_engine import Niveau
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.referentiel import PARCOURS_PAR_NIVEAU, Parcours

DOSSIER_PAR_DEFAUT = Path(__file__).resolve().parents[2] / "referentiels"

CodeProgramme = Annotated[str, Field(pattern=r"^[A-Z0-9][A-Z0-9-]{2,30}$")]
CodeAttendu = Annotated[str, Field(pattern=r"^[A-Z0-9][A-Z0-9-]{4,40}$")]


class TypeAttendu(str, Enum):
    CONTENU = "contenu"  # notion à connaitre (rubrique « Contenus » du BO)
    CAPACITE = "capacite"  # savoir-faire (rubrique « Capacités attendues »)
    DEMONSTRATION = "demonstration"  # démonstration exigible
    AUTOMATISME = "automatisme"  # rubrique « Automatismes » : entrainement régulier, sans calculatrice
    APPROFONDISSEMENT = "approfondissement"  # « Approfondissements possibles » : non exigible


class ModeEvaluation(str, Enum):
    AUTOMATIQUE = "automatique"  # QCM, réponse numérique, expression : corrigé par le moteur
    AUTO_EVALUATION = "auto_evaluation"  # rédaction comparée par l'élève à un corrigé et une grille
    ENSEIGNANT = "enseignant"  # jugement humain du raisonnement


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Source(_Strict):
    code: Annotated[str, Field(pattern=r"^[a-z0-9-]+$")]
    titre: str
    bulletin: str  # ex. « BO n° 14 du 2 avril 2026 »
    fichier: str  # nom du PDF dans referentiels/sources/
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    url: str | None = None
    obtenu_le: date


class Programme(_Strict):
    code: CodeProgramme
    titre: str
    niveau: Niveau
    parcours: Parcours
    source: str  # code d'une Source
    en_vigueur_du: date
    en_vigueur_jusqu_au: date | None = None

    @model_validator(mode="after")
    def _parcours_du_niveau(self):
        if self.parcours not in PARCOURS_PAR_NIVEAU[self.niveau]:
            raise ValueError(f"parcours « {self.parcours.value} » impossible en {self.niveau.value}")
        return self

    def en_vigueur(self, jour: date) -> bool:
        return self.en_vigueur_du <= jour and (self.en_vigueur_jusqu_au is None or jour <= self.en_vigueur_jusqu_au)


class Attendu(_Strict):
    code: CodeAttendu
    type: TypeAttendu
    # Formulation du BO, recopiée telle quelle : c'est la preuve de l'attendu.
    texte: Annotated[str, Field(min_length=3)]
    evaluation: ModeEvaluation = ModeEvaluation.AUTOMATIQUE
    page: Annotated[int, Field(ge=1)] | None = None  # page du PDF source

    @property
    def obligatoire(self) -> bool:
        return self.type is not TypeAttendu.APPROFONDISSEMENT


class Theme(_Strict):
    code: Annotated[str, Field(pattern=r"^[A-Z0-9]{1,10}$")]
    titre: str
    partie: str  # grande partie du programme (Algèbre, Analyse, …)


class FichierTheme(_Strict):
    theme: Theme
    attendus: Annotated[list[Attendu], Field(min_length=1)]


class ReferentielInvalide(Exception):
    def __init__(self, erreurs: list[str]):
        self.erreurs = erreurs
        super().__init__(f"{len(erreurs)} erreur(s) dans les référentiels :\n- " + "\n- ".join(erreurs))


class Referentiels(BaseModel):
    """Tout ce qui a été chargé : sources, programmes, et chaque attendu avec son programme et son thème."""

    sources: dict[str, Source]
    programmes: dict[str, Programme]
    attendus: dict[str, tuple[str, Theme, Attendu]]  # code attendu → (code programme, thème, attendu)

    def du_programme(self, code_programme: str) -> list[tuple[Theme, Attendu]]:
        return [(t, a) for p, t, a in self.attendus.values() if p == code_programme]


def _lire(chemin: Path, modele, nom: str, erreurs: list[str]):
    try:
        return modele.model_validate(yaml.safe_load(chemin.read_text(encoding="utf-8")))
    except yaml.YAMLError as exc:
        erreurs.append(f"{nom} : YAML invalide ({exc})")
    except ValidationError as exc:
        erreurs.extend(f"{nom} : {'.'.join(map(str, e['loc']))} : {e['msg']}" for e in exc.errors())
    return None


def charger(dossier: Path = DOSSIER_PAR_DEFAUT, verifier_empreintes: bool = True) -> Referentiels:
    """Lit et vérifie tous les référentiels. Lève ReferentielInvalide avec toutes les erreurs trouvées."""
    erreurs: list[str] = []
    sources: dict[str, Source] = {}
    chemin_sources = dossier / "sources" / "sources.yaml"
    if chemin_sources.exists():
        for donnees in yaml.safe_load(chemin_sources.read_text(encoding="utf-8")) or []:
            try:
                s = Source.model_validate(donnees)
            except ValidationError as exc:
                erreurs.extend(f"sources.yaml : {e['msg']}" for e in exc.errors())
                continue
            pdf = dossier / "sources" / s.fichier
            if not pdf.is_file():
                erreurs.append(f"sources.yaml : {s.code} : fichier {s.fichier} absent")
            elif verifier_empreintes and hashlib.sha256(pdf.read_bytes()).hexdigest() != s.sha256:
                erreurs.append(f"sources.yaml : {s.code} : le PDF ne correspond plus à son empreinte SHA-256")
            sources[s.code] = s

    programmes: dict[str, Programme] = {}
    attendus: dict[str, tuple[str, Theme, Attendu]] = {}
    for dossier_programme in sorted(p for p in dossier.iterdir() if p.is_dir() and p.name != "sources"):
        nom = dossier_programme.name
        programme = _lire(dossier_programme / "programme.yaml", Programme, f"{nom}/programme.yaml", erreurs)
        if programme is None:
            continue
        if programme.source not in sources:
            erreurs.append(f"{nom}/programme.yaml : source « {programme.source} » inconnue (sources.yaml)")
        if programme.code in programmes:
            erreurs.append(f"{nom}/programme.yaml : programme « {programme.code} » déjà défini")
        programmes[programme.code] = programme
        for chemin in sorted(dossier_programme.glob("*.yaml")):
            if chemin.name == "programme.yaml":
                continue
            fichier = _lire(chemin, FichierTheme, f"{nom}/{chemin.name}", erreurs)
            if fichier is None:
                continue
            for a in fichier.attendus:
                if not a.code.startswith(f"{programme.code}-{fichier.theme.code}-"):
                    erreurs.append(f"{nom}/{chemin.name} : {a.code} : doit commencer par « {programme.code}-{fichier.theme.code}- »")
                if a.code in attendus:
                    erreurs.append(f"{nom}/{chemin.name} : attendu « {a.code} » déjà défini")
                attendus[a.code] = (programme.code, fichier.theme, a)

    if erreurs:
        raise ReferentielInvalide(erreurs)
    return Referentiels(sources=sources, programmes=programmes, attendus=attendus)
