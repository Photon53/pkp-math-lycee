"""Contrats d'API de l'espace administrateur (cahier des charges V2, module 1)."""

from datetime import date, datetime
from typing import Annotated, Literal

from pkp_engine import Forme, Niveau, TypeQuestion
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.referentiel import Adaptation, Parcours, Role, StatutValidation
from app.schemas import EnfantFamille, ParentCreation

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


class HabilitationEntree(BaseModel):
    """Professeur ou validateur d'un domaine ; niveau vide = tout le domaine (CDC V2, EX.6 et EX.9-bis)."""

    role: Literal["professeur", "validateur"]
    domaine: Annotated[str, Field(min_length=1, max_length=30)]
    niveau: Annotated[str | None, Field(max_length=4)] = None


class HabilitationVue(HabilitationEntree):
    libelle: str
    accordee_le: datetime | None = None


class EnseignantAdmin(BaseModel):
    id: int
    nom: str
    email: str
    role: Role
    enseigne_maths: bool
    enseigne_anglais: bool
    referent_anglais: bool = False
    actif: bool
    mdp_provisoire: bool
    totp_configure: bool
    nb_classes: int
    nb_eleves: int
    nb_groupes_anglais: int = 0
    nb_eleves_anglais: int = 0
    derniere_connexion: datetime | None
    habilitations: list[HabilitationVue] = []
    # Permissions du compte (EX.7) : l'admin n'affiche que les espaces permis (EA.3).
    permissions: list[str] = []


class EnseignantEdition(BaseModel):
    nom: Annotated[str, Field(min_length=1, max_length=100)]
    email: Annotated[str, Field(min_length=3, max_length=254)]
    role: Role = Role.ENSEIGNANT
    enseigne_maths: bool = True
    enseigne_anglais: bool = False
    # Référent : valide les séances PKP Anglais des autres auteurs.
    referent_anglais: bool = False
    # Fournies : elles remplacent les cases ci-dessus, qui en sont alors déduites.
    habilitations: Annotated[list[HabilitationEntree] | None, Field(max_length=40)] = None

    @field_validator("email")
    @classmethod
    def _valider_email(cls, v: str) -> str:
        return _email(v)

    @model_validator(mode="after")
    def _une_discipline(self) -> "EnseignantEdition":
        if self.habilitations is not None:
            if not self.habilitations:
                raise ValueError("Donnez au moins une habilitation (professeur ou validateur d'un domaine).")
            return self
        if not (self.enseigne_maths or self.enseigne_anglais):
            raise ValueError("Cochez au moins une discipline.")
        if self.referent_anglais and not self.enseigne_anglais:
            raise ValueError("Un référent anglais doit enseigner l'anglais.")
        return self


class EnseignantCree(BaseModel):
    """Le mot de passe provisoire n'est affiché qu'une fois (EA3.2)."""

    enseignant: EnseignantAdmin
    mot_de_passe_provisoire: str


class Activation(BaseModel):
    actif: bool


# --- Domaines pédagogiques ----------------------------------------------------------


class DomaineAdmin(BaseModel):
    code: str
    matiere: str
    cycle: str
    libelle: str
    niveaux: list[str]
    actif: bool
    public: bool
    nb_professeurs: int
    nb_validateurs: int


class DomaineEdition(BaseModel):
    actif: bool
    public: bool

    @model_validator(mode="after")
    def _public_si_actif(self) -> "DomaineEdition":
        if self.public and not self.actif:
            raise ValueError("Un domaine ouvert aux élèves doit d'abord être activé.")
        return self


# --- Familles (comptes parents) -----------------------------------------------------


class EnfantRattache(BaseModel):
    id: int
    prenom: str
    classe: str
    niveau: Niveau
    enseignant: str


class FamilleAdmin(BaseModel):
    id: int
    email: str
    nom: str = ""
    prenom: str = ""
    mdp_provisoire: bool
    cree_le: datetime
    derniere_connexion: datetime | None
    enfants: list[EnfantRattache]
    # Enfants de la famille (créés par l'administrateur), avec leur niveau : « Inès Martin (2nde) ».
    famille: list[str] = []
    bloque: bool = False


class PageFamilles(BaseModel):
    total: int
    elements: list[FamilleAdmin]


class EntreeRattachement(BaseModel):
    le: datetime
    action: Literal["ajout", "retrait"]
    par: str
    enfant: str


class FamilleDetail(FamilleAdmin):
    historique: list[EntreeRattachement]


class FamilleCreee(BaseModel):
    """Le mot de passe provisoire n'est donné qu'à la création du compte."""

    famille: FamilleDetail
    mot_de_passe_provisoire: str | None = None


class RattachementEnfant(BaseModel):
    eleve_id: int


class FamilleCreation(ParentCreation):
    """Même contrôle de l'adresse que lorsqu'un professeur crée le compte."""

    eleve_id: int


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
    domaine_code: str
    enseignant_id: int
    enseignant: str
    nb_eleves: int
    nb_chapitres_ouverts: int


# --- PKP Anglais ------------------------------------------------------------------


class EleveAnglaisAdmin(BaseModel):
    id: int
    prenom: str
    identifiant: str | None = None
    a_un_code: bool = False


class GroupeAnglaisAdmin(BaseModel):
    id: int
    nom: str
    niveau: str
    enseignant_id: int
    enseignant: str
    eleves: list[EleveAnglaisAdmin]


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
    forme: Forme | None = None
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
    # « Développer », « Factoriser »… : forme exigée en plus de la valeur (questions de type expression).
    forme: Forme | None = None
    source: Annotated[str, Field(min_length=1, max_length=200)] = "PKP Math"
    source_url: Annotated[str | None, Field(max_length=500)] = None
    licence_source: Annotated[str | None, Field(max_length=100)] = None
    adaptation: Adaptation = Adaptation.ORIGINALE
    auteur: Annotated[str | None, Field(max_length=100)] = None


class EssaiReponse(BaseModel):
    type: TypeQuestion
    solution: Annotated[str, Field(min_length=1, max_length=200)]
    reponse: Annotated[str, Field(min_length=1, max_length=200)]
    forme: Forme | None = None


class ResultatEssai(BaseModel):
    correcte: bool
    solution_lisible: bool
    # Valeur juste mais pas sous la forme demandée.
    forme_non_respectee: bool = False


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


class SeanceAnglaisEdition(BaseModel):
    """Version complète d'une séance PKP Anglais : fichier de séance, cahier et QCM de grammaire."""

    contenu: dict
    cahier: dict
    quiz: list[dict] = []


class ResultatRecherche(BaseModel):
    """Une ligne de la recherche globale (EA.1) : ce qui a été trouvé et la page qui le gère."""

    type: str
    libelle: str
    detail: str | None = None
    vers: str


# --- Répertoire des élèves (V3, Lot 1) --------------------------------------------------------


class ResponsableResume(BaseModel):
    id: int
    email: str
    nom: str
    prenom: str
    mdp_provisoire: bool
    bloque: bool
    derniere_connexion: datetime | None


class EnfantRepertoire(EnfantFamille):
    cree_le: datetime
    responsables: list[ResponsableResume]
    alertes: list[str]


class PageRepertoire(BaseModel):
    total: int
    elements: list[EnfantRepertoire]


class SuiviMaths(BaseModel):
    eleve_id: int
    code_classe: str
    niveau: Niveau
    parcours: Parcours
    libelle_parcours: str
    principal: bool
    enseignant: str
    inscrit_le: datetime
    seances: int
    reponses: int
    taux_reussite: float | None
    derniere_activite: datetime | None


class SuiviAnglais(BaseModel):
    eleve_id: int
    groupe: str
    niveau: str
    enseignant: str
    inscrit_le: datetime
    seances: int
    derniere_activite: datetime | None


class EntreeHistoriqueEleve(BaseModel):
    le: datetime
    admin: str | None
    action: str
    objet: str
    avant: dict | None
    apres: dict | None


class FicheEleve(BaseModel):
    eleve: EnfantRepertoire
    maths: list[SuiviMaths]
    anglais: list[SuiviAnglais]
    archives: list["ArchiveResume"]
    historique: list[EntreeHistoriqueEleve]


class ChangementNiveau(BaseModel):
    ids: Annotated[list[int], Field(min_length=1, max_length=500)]
    niveau: Niveau


class ResponsableRattache(BaseModel):
    responsable: ResponsableResume
    cree: bool
    mot_de_passe_provisoire: str | None = None


from app.schemas import ArchiveResume  # noqa: E402  (référence avant de FicheEleve)

FicheEleve.model_rebuild()

