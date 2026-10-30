"""Cours et résumés, consultables par les élèves (chapitres ouverts de leur classe uniquement)."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app import ressources
from app.auth import EleveCourant, SessionDB
from app.db import models
from app.progression import ids_ouverts
from app.schemas import ChapitreCours, CompetenceCours, LeconInfo

router = APIRouter(prefix="/cours", tags=["cours"])


@router.get("", response_model=list[ChapitreCours])
def sommaire(eleve: EleveCourant, session: SessionDB) -> list[ChapitreCours]:
    chapitres = session.scalars(
        select(models.Chapitre)
        .where(models.Chapitre.id.in_(ids_ouverts(eleve.classe)))
        .options(selectinload(models.Chapitre.competences).selectinload(models.Competence.lecon))
        .order_by(models.Chapitre.ordre)
    )
    return [
        ChapitreCours(
            id=ch.id,
            code=ch.code,
            titre=ch.titre,
            competences=[
                CompetenceCours(id=c.id, code=c.code, libelle=c.libelle, a_une_lecon=c.lecon is not None)
                for c in sorted(ch.competences, key=lambda c: (c.ordre, c.code))
                if not c.masque
            ],
        )
        for ch in chapitres
    ]


@router.get("/{competence_id}", response_model=LeconInfo)
def lecon(competence_id: int, eleve: EleveCourant, session: SessionDB) -> LeconInfo:
    competence = session.get(models.Competence, competence_id)
    if (
        competence is None
        or competence.lecon is None
        or competence.masque
        or competence.chapitre_id not in ids_ouverts(eleve.classe)
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cours introuvable.")
    return LeconInfo(
        competence_id=competence.id,
        code=competence.code,
        libelle=competence.libelle,
        chapitre=competence.chapitre.titre,
        chapitre_id=competence.chapitre_id,
        cours=competence.lecon.cours,
        resume=competence.lecon.resume,
        ressources=ressources.pour_eleve(session, eleve, None, competence.id)
        + ressources.pour_eleve(session, eleve, competence.chapitre_id, None),
    )
