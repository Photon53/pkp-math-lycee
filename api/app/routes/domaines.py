"""État public des parcours, pour la page d'accueil : lecture seule, sans authentification ni donnée personnelle."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from app.db import models
from app.auth import SessionDB

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


@router.get("/publics", response_model=list[DomainePublic])
def domaines_publics(session: SessionDB) -> list[DomainePublic]:
    return [
        DomainePublic(code=d.code, matiere=d.matiere, cycle=d.cycle, libelle=d.libelle, niveaux=d.niveaux, etat=etat_du_domaine(d))
        for d in session.scalars(select(models.DomainePedagogique).order_by(models.DomainePedagogique.ordre))
    ]
