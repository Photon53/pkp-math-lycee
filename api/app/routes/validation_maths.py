"""Espace professeur, page « Validation » des maths (ticket #29).

Un professeur habilité « validateur » sur Maths collège ou Maths lycée (éventuellement pour un seul niveau) consulte,
modifie et valide les cours et les exercices de son périmètre, sans compte administrateur. Les règles sont celles
de l'administration (mêmes fonctions) :
- lecture et modification limitées au périmètre ; hors périmètre, la ressource n'existe pas (404) ;
- validation refusée à l'auteur de la question (règle E0.2) ;
- une question validée dont le contenu change repart « à valider » ;
- chaque modification et chaque décision est inscrite au journal, au nom du professeur.
Archiver, créer ou réorganiser restent réservés à l'administration.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, false, or_

from app import permissions
from app.auth import EnseignantAuthentifie, SessionDB
from app.db import models
from pkp_engine import TypeQuestion

from app.referentiel import Niveau, StatutValidation
from app.routes import admin_contenu
from app.schemas_admin import (
    ChapitreArbre,
    EssaiReponse,
    LeconAdmin,
    LeconEdition,
    PageQuestions,
    QuestionAdmin,
    QuestionEdition,
    ResultatEssai,
    Validation,
    VersionLeconDetail,
)


def validateur_maths(enseignant: EnseignantAuthentifie) -> models.Enseignant:
    if not permissions.valide_les_maths(enseignant):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Réservé aux validateurs de mathématiques.")
    return enseignant


router = APIRouter(prefix="/enseignants/validation", tags=["validation-maths"])
Validateur = models.Enseignant


def _habilitations(enseignant: models.Enseignant) -> list[models.Habilitation]:
    return [
        h for h in enseignant.habilitations
        if h.role == permissions.VALIDATEUR and h.domaine_code in permissions.DOMAINES_MATHS
    ]


def perimetre(enseignant: models.Enseignant):
    """Condition SQL sur `chapitre` : domaines (et niveaux) que ce professeur valide."""
    conditions = [
        and_(models.Chapitre.domaine_code == h.domaine_code, *([models.Chapitre.niveau == Niveau(h.niveau)] if h.niveau else []))
        for h in _habilitations(enseignant)
    ]
    return or_(*conditions) if conditions else false()


def _dans_le_perimetre(enseignant: models.Enseignant, chapitre: models.Chapitre) -> bool:
    return permissions.peut_valider(enseignant, chapitre.domaine_code, chapitre.niveau.value) and (
        chapitre.domaine_code in permissions.DOMAINES_MATHS
    )


def _question(session: SessionDB, enseignant: models.Enseignant, question_id: int) -> models.Question:
    q = session.get(models.Question, question_id)
    if q is None or not _dans_le_perimetre(enseignant, q.competence.chapitre):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question introuvable dans votre périmètre de validation.")
    return q


def _competence(session: SessionDB, enseignant: models.Enseignant, competence_id: int) -> models.Competence:
    c = session.get(models.Competence, competence_id)
    if c is None or not _dans_le_perimetre(enseignant, c.chapitre):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Compétence introuvable dans votre périmètre de validation.")
    return c


@router.get("/perimetre")
def mon_perimetre(enseignant: Validateur = Depends(validateur_maths)) -> list[dict]:
    return [
        {"domaine": h.domaine_code, "libelle": permissions.LIBELLES.get(h.domaine_code, h.domaine_code), "niveau": h.niveau}
        for h in _habilitations(enseignant)
    ]


@router.get("/contenu", response_model=list[ChapitreArbre])
def arbre(session: SessionDB, niveau: Niveau | None = None, enseignant: Validateur = Depends(validateur_maths)):
    return [
        ch for ch in admin_contenu.arbre(enseignant, session, None, niveau)
        if _dans_le_perimetre(enseignant, session.get(models.Chapitre, ch.id))
    ]


@router.get("/questions", response_model=PageQuestions)
def questions(
    session: SessionDB,
    niveau: Niveau | None = None,
    type: TypeQuestion | None = None,
    statut: StatutValidation | None = None,
    q: str | None = None,
    page: int = 1,
    enseignant: Validateur = Depends(validateur_maths),
) -> PageQuestions:
    return admin_contenu.lister_questions(
        session, enseignant, niveau=niveau, type=type, statut=statut, q=q, page=page, perimetre=perimetre(enseignant)
    )


@router.post("/questions/tester", response_model=ResultatEssai)
def tester(corps: EssaiReponse, enseignant: Validateur = Depends(validateur_maths)) -> ResultatEssai:
    return admin_contenu.tester(corps, enseignant)


@router.post("/questions/{question_id}", response_model=QuestionAdmin)
def modifier(
    question_id: int, corps: QuestionEdition, session: SessionDB, enseignant: Validateur = Depends(validateur_maths)
) -> QuestionAdmin:
    _question(session, enseignant, question_id)
    _competence(session, enseignant, corps.competence_id)  # pas de déplacement hors du périmètre
    return admin_contenu.modifier_question(question_id, corps, enseignant, session)


@router.post("/questions/{question_id}/validation", response_model=QuestionAdmin)
def valider(
    question_id: int, corps: Validation, session: SessionDB, enseignant: Validateur = Depends(validateur_maths)
) -> QuestionAdmin:
    _question(session, enseignant, question_id)
    return admin_contenu.valider(question_id, corps, enseignant, session)


@router.get("/lecons/{competence_id}", response_model=LeconAdmin)
def lire_lecon(competence_id: int, session: SessionDB, enseignant: Validateur = Depends(validateur_maths)) -> LeconAdmin:
    return admin_contenu._vue_lecon(_competence(session, enseignant, competence_id))


@router.post("/lecons/{competence_id}", response_model=LeconAdmin)
def enregistrer_lecon(
    competence_id: int, corps: LeconEdition, session: SessionDB, enseignant: Validateur = Depends(validateur_maths)
) -> LeconAdmin:
    _competence(session, enseignant, competence_id)
    return admin_contenu.enregistrer_lecon(competence_id, corps, enseignant, session)


def _version(session: SessionDB, enseignant: models.Enseignant, version_id: int) -> models.LeconVersion:
    v = admin_contenu._version(session, version_id)
    _competence(session, enseignant, v.lecon.competence_id)
    return v


@router.get("/lecons/versions/{version_id}", response_model=VersionLeconDetail)
def lire_version(version_id: int, session: SessionDB, enseignant: Validateur = Depends(validateur_maths)):
    _version(session, enseignant, version_id)
    return admin_contenu.lire_version(version_id, enseignant, session)


@router.post("/lecons/versions/{version_id}/restaurer", response_model=LeconAdmin)
def restaurer_version(version_id: int, session: SessionDB, enseignant: Validateur = Depends(validateur_maths)):
    _version(session, enseignant, version_id)
    return admin_contenu.restaurer_version(version_id, enseignant, session)
