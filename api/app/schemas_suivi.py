"""Schémas du suivi en séance (ticket #28) : demandes d'aide des élèves et tableau de bord du professeur."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, field_validator

ObjetDemande = Literal["cours", "exercice", "corrige"]


class AvisCours(BaseModel):
    competence_id: int
    compris: bool


class AvisCoursVue(BaseModel):
    competence_id: int
    compris: bool | None  # None : l'élève n'a encore rien indiqué
    le: datetime | None = None


class NouvelleDemande(BaseModel):
    question_id: int
    objet: Literal["exercice", "corrige"]


class DemandeVue(BaseModel):
    id: int
    objet: ObjetDemande
    statut: str
    cree_le: datetime

    @field_validator("cree_le")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return v.replace(tzinfo=UTC) if v.tzinfo is None else v  # SQLite rend des dates sans fuseau


class Traitement(BaseModel):
    statut: Literal["prise-en-charge", "resolue"]


class QuestionSuivie(BaseModel):
    question_id: int
    code: str | None
    enonce: str
    solution: str
    correction: dict | None
    competence_id: int
    competence: str
    chapitre: str
    nb_tentatives: int
    nb_eleves: int
    nb_reussites: int
    nb_erreurs: int
    taux_erreur: float | None
    # Élèves dont la dernière tentative est fausse ; élèves qui ont réussi après au moins une erreur.
    eleves_en_echec: list[str]
    nb_reussies_apres_erreur: int
    # Question affichée à l'élève, pas encore répondue (séance ouverte) : non-réponse, distincte d'une erreur.
    eleves_sans_reponse: list[str]


class NotionAPrioriser(BaseModel):
    competence_id: int
    competence: str
    chapitre: str
    nb_eleves_en_difficulte: int
    taux_erreur: float | None
    nb_demandes: int


class DemandeSuivie(BaseModel):
    id: int
    objet: ObjetDemande
    statut: str
    eleve: str
    classe: str
    competence_id: int
    competence: str
    chapitre: str
    question_id: int | None = None
    question_code: str | None = None
    enonce: str | None = None
    cree_le: datetime
    traitee_par: str | None = None


class Compteurs(BaseModel):
    demandes_cours: int
    demandes_exercices: int
    demandes_corriges: int
    resolues: int
    eleves_actifs: int


class TableauSeance(BaseModel):
    genere_le: datetime
    depuis: datetime
    jusqua: datetime
    compteurs: Compteurs
    notions: list[NotionAPrioriser]
    demandes_cours: list[DemandeSuivie]
    demandes_exercices: list[DemandeSuivie]  # exercices et corrigés
    questions: list[QuestionSuivie]
