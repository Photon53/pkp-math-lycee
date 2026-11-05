"""État public des parcours, pour la page d'accueil : lecture seule, sans authentification ni donnée personnelle."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from app.db import models
from app.auth import SessionDB
from app.progression import filtre_validation

router = APIRouter(prefix="/domaines", tags=["domaines"])

EtatParcours = Literal["ouvert", "en_preparation", "en_chantier"]


class DomainePublic(BaseModel):
    code: str
    matiere: str
    cycle: str
    libelle: str
    niveaux: list[str]
    etat: EtatParcours


def etat_du_domaine(d: models.DomainePedagogique) -> EtatParcours:
    """Ouvert aux élèves, en préparation par l'équipe (actif mais fermé au public), ou encore à construire."""
    if d.public:
        return "ouvert"
    return "en_preparation" if d.actif else "en_chantier"


class ChiffresPublics(BaseModel):
    chapitres: int
    questions: int
    seances_anglais: int


@router.get("/chiffres", response_model=ChiffresPublics)
def chiffres_publics(session: SessionDB) -> ChiffresPublics:
    """Totaux du contenu ouvert aux élèves (domaines publics, rien de masqué), pour la page d'accueil."""
    publics = select(models.DomainePedagogique.code).where(models.DomainePedagogique.public.is_(True))
    chapitres = (models.Chapitre.masque.is_(False), models.Chapitre.domaine_code.in_(publics))
    nb_chapitres = session.scalar(select(func.count(models.Chapitre.id)).where(*chapitres))
    nb_questions = session.scalar(
        select(func.count(models.Question.id))
        .join(models.Competence, models.Question.competence_id == models.Competence.id)
        .join(models.Chapitre, models.Competence.chapitre_id == models.Chapitre.id)
        .where(models.Question.archivee.is_(False), *chapitres, *filtre_validation())
    )
    nb_seances = session.scalar(
        select(func.count(func.distinct(models.SeanceAnglais.id)))
        .join(models.SeanceAnglaisVersion, models.SeanceAnglaisVersion.seance_id == models.SeanceAnglais.id)
        .where(models.SeanceAnglais.domaine_code.in_(publics), models.SeanceAnglaisVersion.statut == "valide")
    )
    return ChiffresPublics(chapitres=nb_chapitres or 0, questions=nb_questions or 0, seances_anglais=nb_seances or 0)


@router.get("/publics", response_model=list[DomainePublic])
def domaines_publics(session: SessionDB) -> list[DomainePublic]:
    return [
        DomainePublic(code=d.code, matiere=d.matiere, cycle=d.cycle, libelle=d.libelle, niveaux=d.niveaux, etat=etat_du_domaine(d))
        for d in session.scalars(select(models.DomainePedagogique).order_by(models.DomainePedagogique.ordre))
    ]
