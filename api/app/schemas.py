"""Contrats d'API. La séparation QuestionPublique / ResultatReponse garantit
que la bonne réponse n'est envoyée au navigateur qu'après soumission."""

import re
from datetime import datetime
from typing import Annotated

from pkp_engine import Niveau, TypeQuestion
from pydantic import BaseModel, ConfigDict, Field, field_validator

_PRENOM = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ' -]+$")


def normaliser_prenom(prenom: str) -> str:
    """« inès », « INÈS » et « Inès » désignent le même élève."""
    return " ".join(prenom.split()).title()


class _Modele(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Élève ----------------------------------------------------------------


def valider_prenom(v: str) -> str:
    v = normaliser_prenom(v)
    if not v or len(v) > 50 or not _PRENOM.match(v):
        raise ValueError("Le prénom ne doit contenir que des lettres, espaces, tirets ou apostrophes.")
    return v


class ConnexionEleve(BaseModel):
    prenom: Annotated[str, Field(min_length=1, max_length=50)]
    code_classe: Annotated[str, Field(min_length=1, max_length=20)]
    code_personnel: Annotated[str, Field(min_length=1, max_length=20)]

    @field_validator("prenom")
    @classmethod
    def _prenom(cls, v: str) -> str:
        return valider_prenom(v)

    @field_validator("code_classe")
    @classmethod
    def _code(cls, v: str) -> str:
        return v.strip().upper()


class EleveInfo(BaseModel):
    id: int
    prenom: str
    code_classe: str
    niveau: Niveau


class JetonEleve(BaseModel):
    jeton: str
    eleve: EleveInfo


class SeanceInfo(_Modele):
    id: int
    debut: datetime
    fin: datetime | None


class QuestionPublique(_Modele):
    """Ce que voit l'élève avant de répondre : jamais de champ `solution`."""

    id: int
    competence_id: int
    enonce: str
    type: TypeQuestion
    difficulte: int


class CompetenceCours(BaseModel):
    id: int
    code: str
    libelle: str
    a_une_lecon: bool


class ChapitreCours(BaseModel):
    id: int
    code: str
    titre: str
    competences: list[CompetenceCours]


class LeconInfo(BaseModel):
    competence_id: int
    code: str
    libelle: str
    chapitre: str
    cours: str
    resume: str


class SoumissionReponse(BaseModel):
    question_id: int
    reponse_donnee: Annotated[str, Field(max_length=200)]


class ResultatReponse(BaseModel):
    correcte: bool
    solution: str
    maitrise: float = Field(description="Maîtrise de la compétence après cette réponse, entre 0 et 1.")
    maitrisee: bool


class ProgressionCompetence(BaseModel):
    competence_id: int
    code: str
    libelle: str
    chapitre: str
    nb_reponses: int
    maitrise: float
    maitrisee: bool


# --- Enseignant -----------------------------------------------------------


class ConnexionEnseignant(BaseModel):
    email: Annotated[str, Field(min_length=3, max_length=254)]
    mot_de_passe: Annotated[str, Field(min_length=1, max_length=200)]

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return v.strip().lower()


class JetonEnseignant(BaseModel):
    jeton: str
    nom: str


class ClasseCreation(BaseModel):
    niveau: Niveau


class ClasseResume(BaseModel):
    id: int
    code: str
    niveau: Niveau
    nb_eleves: int


class EleveResume(BaseModel):
    id: int
    prenom: str
    a_un_code: bool
    nb_reponses: int
    taux_reussite: float | None
    competences_maitrisees: int
    competences_total: int


class CreationEleves(BaseModel):
    """Prénoms à inscrire dans une classe (un par ligne côté interface)."""

    prenoms: Annotated[list[str], Field(min_length=1, max_length=60)]

    @field_validator("prenoms")
    @classmethod
    def _prenoms(cls, v: list[str]) -> list[str]:
        propres = [valider_prenom(p) for p in v if p.strip()]
        if not propres:
            raise ValueError("Aucun prénom fourni.")
        return list(dict.fromkeys(propres))  # sans doublons, ordre conservé


class CodeEleve(BaseModel):
    """Code personnel en clair : affiché une seule fois, à la génération."""

    id: int
    prenom: str
    code: str


class ResultatCreationEleves(BaseModel):
    crees: list[CodeEleve]
    deja_presents: list[str]


class CompetenceInfo(BaseModel):
    id: int
    code: str
    libelle: str
    chapitre: str
    niveau: Niveau


class QuestionCreation(BaseModel):
    competence_id: int
    enonce: Annotated[str, Field(min_length=1, max_length=2000)]
    type: TypeQuestion
    solution: Annotated[str, Field(min_length=1, max_length=200)]
    difficulte: Annotated[int, Field(ge=1, le=5)]


class QuestionEnseignant(_Modele):
    """Vue enseignant : contient la solution."""

    id: int
    competence_id: int
    enonce: str
    type: TypeQuestion
    solution: str
    difficulte: int
    archivee: bool
