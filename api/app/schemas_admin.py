"""Contrats d'API de l'espace administrateur (cahier des charges V2, module 1)."""

from datetime import date, datetime
from typing import Annotated

from pkp_engine import Niveau, TypeQuestion
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.referentiel import Adaptation, Parcours, Role, StatutValidation

TAILLE_PAGE = 50


def _email(v: str) -> str:
    v = v.strip().lower()
    if "@" not in v or v.startswith("@") or v.endswith("@"):
        raise ValueError("Adresse e-mail invalide.")
    return v


# --- Connexion ----------------------------------------------------------------


class ConnexionAdmin(BaseModel):
    email: Annotated[str, Field(min_length=3, max_length=254)]
    mot_de_passe: Annotated[str, Field(min_length=1, max_length=200)]
    code_totp: Annotated[str | None, Field(max_length=10)] = None

    @field_validator("email")
    @classmethod
    def _normaliser(cls, v: str) -> str:
        return v.strip().lower()


class JetonAdmin(BaseModel):
    jeton: str
    nom: str
    expire_dans_min: int


# --- Professeurs ------------------------------------------------------------------


class EnseignantAdmin(BaseModel):
    id: int
    nom: str
    email: str
    role: Role
    actif: bool
    mdp_provisoire: bool
    totp_configure: bool
    nb_classes: int
    nb_eleves: int
    derniere_connexion: datetime | None


class EnseignantEdition(BaseModel):
    nom: Annotated[str, Field(min_length=1, max_length=100)]
    email: Annotated[str, Field(min_length=3, max_length=254)]
    role: Role = Role.ENSEIGNANT

    @field_validator("email")
    @classmethod
    def _valider_email(cls, v: str) -> str:
        return _email(v)


class EnseignantCree(BaseModel):
    """Le mot de passe provisoire n'est affiché qu'une fois (EA3.2)."""

    enseignant: EnseignantAdmin
    mot_de_passe_provisoire: str


class Activation(BaseModel):
    actif: bool


class Transfert(BaseModel):
    vers_enseignant_id: int


# --- Élèves et classes ------------------------------------------------------------


class EleveAdmin(BaseModel):
    id: int
    prenom: str
    classe_id: int
    classe: str
    niveau: Niveau
    enseignant: str
    nb_seances: int
    derniere_activite: datetime | None
    a_un_code: bool


class PageEleves(BaseModel):
    total: int
    elements: list[EleveAdmin]


class Deplacement(BaseModel):
    classe_id: int


class ClasseAdmin(BaseModel):
    id: int
    code: str
    niveau: Niveau
    parcours: Parcours
    enseignant_id: int
    enseignant: str
    nb_eleves: int
    nb_chapitres_ouverts: int


# --- Cours ------------------------------------------------------------------------


class CompetenceArbre(BaseModel):
    id: int
    code: str
    libelle: str
    ordre: int
    masque: bool
    a_une_lecon: bool
    lecon_maj_le: datetime | None
    nb_questions: int


class ChapitreArbre(BaseModel):
    id: int
    code: str
    niveau: Niveau
    parcours: Parcours
    titre: str
    ordre: int
    masque: bool
    competences: list[CompetenceArbre]


class ChapitreCreation(BaseModel):
    code: Annotated[str, Field(min_length=2, max_length=40, pattern=r"^[A-Z0-9-]+$")]
    niveau: Niveau
    parcours: Parcours
    titre: Annotated[str, Field(min_length=1, max_length=200)]


class ChapitreEdition(BaseModel):
    titre: Annotated[str, Field(min_length=1, max_length=200)]
    masque: bool = False


class CompetenceCreation(BaseModel):
    chapitre_id: int
    code: Annotated[str, Field(min_length=2, max_length=40, pattern=r"^[A-Z0-9-]+$")]
    libelle: Annotated[str, Field(min_length=1, max_length=200)]


class CompetenceEdition(BaseModel):
    libelle: Annotated[str, Field(min_length=1, max_length=200)]
    masque: bool = False


class Ordre(BaseModel):
    """Identifiants dans le nouvel ordre (glisser-déposer)."""

    ids: Annotated[list[int], Field(min_length=1, max_length=200)]


class LeconEdition(BaseModel):
    cours: Annotated[str, Field(min_length=1, max_length=50_000)]
    resume: Annotated[str, Field(min_length=1, max_length=10_000)]


class VersionLecon(BaseModel):
    id: int
    le: datetime
    auteur: str | None


class VersionLeconDetail(VersionLecon):
    cours: str
    resume: str


class LeconAdmin(BaseModel):
    competence_id: int
    code: str
    libelle: str
    chapitre: str
    cours: str
    resume: str
    maj_le: datetime | None
    modifiee_admin_le: datetime | None
    versions: list[VersionLecon]


# --- Exercices -------------------------------------------------------------------


class QuestionAdmin(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str | None
    competence_id: int
    competence: str
    chapitre: str
    niveau: Niveau
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
    valide_par: str | None
    valide_le: date | None
    auteur: str | None
    nb_reponses: int
    taux_reussite: float | None


class PageQuestions(BaseModel):
    total: int
    elements: list[QuestionAdmin]


class QuestionEdition(BaseModel):
    competence_id: int
    enonce: Annotated[str, Field(min_length=1, max_length=2000)]
    type: TypeQuestion
    solution: Annotated[str, Field(min_length=1, max_length=200)]
    difficulte: Annotated[int, Field(ge=1, le=5)]
    source: Annotated[str, Field(min_length=1, max_length=200)] = "PKP Math"
    source_url: Annotated[str | None, Field(max_length=500)] = None
    licence_source: Annotated[str | None, Field(max_length=100)] = None
    adaptation: Adaptation = Adaptation.ORIGINALE
    auteur: Annotated[str | None, Field(max_length=100)] = None


class EssaiReponse(BaseModel):
    type: TypeQuestion
    solution: Annotated[str, Field(min_length=1, max_length=200)]
    reponse: Annotated[str, Field(min_length=1, max_length=200)]


class ResultatEssai(BaseModel):
    correcte: bool
    solution_lisible: bool


class Validation(BaseModel):
    statut: StatutValidation


class Archivage(BaseModel):
    archivee: bool


# --- Ressources ------------------------------------------------------------------


class Masquage(BaseModel):
    masquee: bool
    motif: Annotated[str | None, Field(max_length=300)] = None


class DomaineInterditInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    domaine: str


class DomaineInterditCreation(BaseModel):
    domaine: Annotated[str, Field(min_length=3, max_length=253, pattern=r"^[a-z0-9.-]+\.[a-z]{2,}$")]

    @field_validator("domaine", mode="before")
    @classmethod
    def _minuscules(cls, v: str) -> str:
        return v.strip().lower().removeprefix("www.")


# --- Journal ---------------------------------------------------------------------


class EntreeJournal(BaseModel):
    id: int
    le: datetime
    admin: str | None
    action: str
    objet: str
    objet_id: int | None
    avant: dict | None
    apres: dict | None


class PageJournal(BaseModel):
    total: int
    elements: list[EntreeJournal]


# --- Statistiques ----------------------------------------------------------------


class PointJour(BaseModel):
    jour: date
    valeur: int


class PointReussiteJour(BaseModel):
    jour: date
    reponses: int
    correctes: int


class ReussiteChapitre(BaseModel):
    chapitre_id: int
    titre: str
    niveau: Niveau
    reponses: int
    # None quand moins de 5 élèves ont répondu : agrégat masqué (EA3.20).
    taux_reussite: float | None


class QuestionDifficile(BaseModel):
    question_id: int
    code: str | None
    enonce: str
    chapitre: str
    reponses: int
    taux_reussite: float


class CouvertureNiveau(BaseModel):
    niveau: Niveau
    a_valider: int
    validees: int
    a_corriger: int


class Repartition(BaseModel):
    niveau: Niveau
    parcours: Parcours
    classes: int
    eleves: int


class RessourceTop(BaseModel):
    ressource_id: int
    titre: str
    type: str
    consultations: int


class Statistiques(BaseModel):
    periode_jours: int
    calcule_le: datetime
    professeurs_actifs: int
    professeurs_total: int
    eleves_actifs: int
    eleves_total: int
    seances: int
    reponses: int
    taux_reussite: float | None
    seances_par_jour: list[PointJour]
    reponses_par_jour: list[PointReussiteJour]
    reussite_par_chapitre: list[ReussiteChapitre]
    questions_difficiles: list[QuestionDifficile]
    couverture: list[CouvertureNiveau]
    competences_sans_cours: int
    chapitres_sans_question_validee: list[str]
    repartition: list[Repartition]
    ressources_liens: int
    ressources_pdf: int
    ressources_consultees: list[RessourceTop]
