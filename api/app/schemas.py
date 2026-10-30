"""Contrats d'API. La séparation QuestionPublique / ResultatReponse garantit
que la bonne réponse n'est envoyée au navigateur qu'après soumission."""

import re
from datetime import datetime
from typing import Annotated

from pkp_engine import Niveau, TypeQuestion
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.referentiel import (
    PARCOURS_PAR_NIVEAU,
    Adaptation,
    Parcours,
    PublicRessource,
    Role,
    StatutValidation,
    TypeRessource,
    parcours_par_defaut,
)

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
    parcours: Parcours


class JetonEleve(BaseModel):
    jeton: str
    eleve: EleveInfo


class ChapitreResume(_Modele):
    id: int
    titre: str


class SeanceCreation(BaseModel):
    """Chapitres choisis par l'élève ; vide = tous les chapitres ouverts de sa classe."""

    chapitre_ids: Annotated[list[int], Field(max_length=60)] = []


class SeanceInfo(_Modele):
    id: int
    debut: datetime
    fin: datetime | None
    chapitres: list[ChapitreResume] = []


class ChapitreOuvert(BaseModel):
    """Chapitre proposé par l'enseignant, tel que l'élève le voit."""

    id: int
    code: str
    titre: str
    nb_questions: int


class ChapitreProgramme(BaseModel):
    """Chapitre du programme d'une classe, vu par l'enseignant."""

    id: int
    code: str
    titre: str
    ordre: int
    propose: bool
    nb_competences: int
    nb_questions: int


class ChoixChapitres(BaseModel):
    chapitre_ids: Annotated[list[int], Field(max_length=60)]


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


class RessourceVue(BaseModel):
    """Ressource telle qu'affichée sous un cours (élève ou enseignant)."""

    id: int
    type: str
    titre: str
    description: str
    url: str | None
    domaine: str | None
    taille_octets: int | None
    portee: str


class RessourceCreation(BaseModel):
    """Lien (avec `url`) ou PDF (le fichier est envoyé ensuite, à part)."""

    type: TypeRessource
    titre: Annotated[str, Field(min_length=1, max_length=120)]
    description: Annotated[str, Field(max_length=300)] = ""
    url: Annotated[str | None, Field(max_length=500)] = None
    source: Annotated[str | None, Field(max_length=200)] = None
    licence: Annotated[str | None, Field(max_length=100)] = None
    chapitre_id: int | None = None
    competence_id: int | None = None
    public: PublicRessource = PublicRessource.TOUS
    # Portée « classe » : classes du professeur qui verront la ressource.
    classe_ids: Annotated[list[int], Field(max_length=60)] = []
    # PDF : le professeur déclare détenir les droits de diffusion à ses élèves (EA5.10).
    droits_declares: bool = False
    ordre: int = 0

    @model_validator(mode="after")
    def _coherence(self):
        if (self.chapitre_id is None) == (self.competence_id is None):
            raise ValueError("Rattacher la ressource à un chapitre ou à une compétence (un seul des deux).")
        if self.type == TypeRessource.LIEN and not self.url:
            raise ValueError("Un lien doit avoir une adresse.")
        if self.type == TypeRessource.PDF:
            self.url = None
            if not (self.source and self.licence):
                raise ValueError("Pour un PDF, indiquer la source et la licence.")
        return self


class RessourceDetail(RessourceVue):
    """Vue de gestion : rattachement, public, état du lien, modération."""

    source: str | None
    licence: str | None
    chapitre_id: int | None
    competence_id: int | None
    rattachement: str
    public: str
    auteur: str
    classes: list[str]
    masquee: bool
    motif_masquage: str | None
    echecs_lien: int
    a_un_fichier: bool
    consultations: int
    cree_le: datetime


class LeconInfo(BaseModel):
    competence_id: int
    code: str
    libelle: str
    chapitre: str
    chapitre_id: int | None = None
    cours: str
    resume: str
    ressources: list[RessourceVue] = []


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
    role: Role = Role.ENSEIGNANT
    # Vrai : l'interface demande un nouveau mot de passe avant tout le reste.
    mdp_provisoire: bool = False


class ChangementMotDePasse(BaseModel):
    actuel: Annotated[str, Field(min_length=1, max_length=200)]
    nouveau: Annotated[str, Field(min_length=12, max_length=200)]


class CompetenceCoursEnseignant(BaseModel):
    id: int
    code: str
    libelle: str
    a_une_lecon: bool
    nb_questions: int


class ChapitreCoursEnseignant(BaseModel):
    id: int
    code: str
    titre: str
    niveau: Niveau
    parcours: Parcours
    # Codes des classes du professeur où ce chapitre est ouvert aux élèves.
    ouvert_dans: list[str]
    competences: list[CompetenceCoursEnseignant]


class ClasseCreation(BaseModel):
    niveau: Niveau
    parcours: Parcours | None = None  # par défaut : tronc commun en 2nde, spécialité ensuite

    @model_validator(mode="after")
    def _parcours_du_niveau(self):
        if self.parcours is None:
            self.parcours = parcours_par_defaut(self.niveau)
        elif self.parcours not in PARCOURS_PAR_NIVEAU[self.niveau]:
            raise ValueError(f"Le parcours « {self.parcours.value} » n'existe pas en {self.niveau.value}.")
        return self


class ClasseResume(BaseModel):
    id: int
    code: str
    niveau: Niveau
    parcours: Parcours
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
    parcours: Parcours


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
    source: str
    source_url: str | None
    licence_source: str | None
    adaptation: Adaptation
    statut_validation: StatutValidation
