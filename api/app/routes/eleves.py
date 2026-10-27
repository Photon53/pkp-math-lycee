"""Parcours élève : connexion → séance → question → réponse → question…

Une séance n'a qu'une question en cours à la fois. Redemander la question
suivante renvoie la même tant qu'elle n'a pas reçu de réponse : impossible de
« passer » une question difficile, ou de répondre à une question non servie.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, Response, status
from pkp_engine import calculer_maitrise, choisir_prochaine_question, corriger, est_maitrisee
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app import limitation
from app.auth import ELEVE, EleveCourant, SessionDB
from app.config import settings
from app.db import models
from app.db.conversions import historique_eleve, question_vers_domaine
from app.progression import progression_eleve
from app.schemas import (
    ConnexionEleve,
    EleveInfo,
    JetonEleve,
    ProgressionCompetence,
    QuestionPublique,
    ResultatReponse,
    SeanceInfo,
    SoumissionReponse,
)
from app.security import creer_jeton

router = APIRouter(tags=["élève"])


def _maintenant() -> datetime:
    return datetime.now(UTC)


def _utc(instant: datetime) -> datetime:
    # SQLite rend des dates sans fuseau : elles ont été enregistrées en UTC.
    return instant if instant.tzinfo else instant.replace(tzinfo=UTC)


def _info(eleve: models.Eleve) -> EleveInfo:
    return EleveInfo(id=eleve.id, prenom=eleve.prenom, code_classe=eleve.classe.code, niveau=eleve.classe.niveau)


@router.post("/eleves/connexion", response_model=JetonEleve)
def connexion(corps: ConnexionEleve, request: Request, session: SessionDB) -> JetonEleve:
    """Première connexion avec un prénom : l'élève est créé dans la classe."""
    ip = limitation.adresse_ip(request)
    limitation.verifier((limitation.par_ip, ip), (limitation.codes_inconnus, ip))
    limitation.par_ip.enregistrer(ip)

    classe = session.scalar(select(models.Classe).where(models.Classe.code == corps.code_classe))
    if classe is None:
        # Freine la recherche de codes classe par essais successifs.
        limitation.codes_inconnus.enregistrer(ip)
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Code classe inconnu.")
    requete = select(models.Eleve).where(models.Eleve.classe_id == classe.id, models.Eleve.prenom == corps.prenom)
    eleve = session.scalar(requete)
    if eleve is None:
        eleve = models.Eleve(prenom=corps.prenom, classe=classe)
        session.add(eleve)
        try:
            session.commit()
        except IntegrityError:  # deux premières connexions simultanées avec le même prénom
            session.rollback()
            eleve = session.scalar(requete)
    return JetonEleve(jeton=creer_jeton(ELEVE, eleve.id, settings.duree_jeton_eleve_h), eleve=_info(eleve))


@router.get("/eleves/moi", response_model=EleveInfo)
def moi(eleve: EleveCourant) -> EleveInfo:
    return _info(eleve)


@router.get("/eleves/moi/progression", response_model=list[ProgressionCompetence])
def ma_progression(eleve: EleveCourant, session: SessionDB) -> list[ProgressionCompetence]:
    return progression_eleve(session, eleve)


@router.post("/seances", response_model=SeanceInfo, status_code=status.HTTP_201_CREATED)
def demarrer_seance(eleve: EleveCourant, session: SessionDB) -> models.Seance:
    seance = models.Seance(eleve=eleve, debut=_maintenant())
    session.add(seance)
    session.commit()
    return seance


def _seance_ouverte(session: SessionDB, seance_id: int, eleve: models.Eleve) -> models.Seance:
    seance = session.get(models.Seance, seance_id)
    if seance is None or seance.eleve_id != eleve.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Séance introuvable.")
    if seance.fin is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Cette séance est terminée.")
    return seance


@router.post("/seances/{seance_id}/fin", response_model=SeanceInfo)
def terminer_seance(seance_id: int, eleve: EleveCourant, session: SessionDB) -> models.Seance:
    seance = _seance_ouverte(session, seance_id, eleve)
    seance.fin = _maintenant()
    seance.question_courante = None
    seance.question_servie_le = None
    session.commit()
    return seance


@router.get(
    "/seances/{seance_id}/question",
    response_model=QuestionPublique,
    responses={204: {"description": "Plus aucune question disponible pour ce niveau."}},
)
def question_suivante(seance_id: int, eleve: EleveCourant, session: SessionDB):
    seance = _seance_ouverte(session, seance_id, eleve)
    if seance.question_courante is not None:
        return seance.question_courante

    candidates = {
        q.id: q
        for q in session.scalars(
            select(models.Question)
            .join(models.Competence)
            .join(models.Chapitre)
            .where(models.Chapitre.niveau == eleve.classe.niveau, models.Question.archivee.is_(False))
        )
    }
    choix = choisir_prochaine_question(
        [question_vers_domaine(q) for q in candidates.values()], historique_eleve(session, eleve.id)
    )
    if choix is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    question = candidates[choix.id]
    seance.question_courante = question
    seance.question_servie_le = _maintenant()
    session.commit()
    return question


@router.post("/seances/{seance_id}/reponses", response_model=ResultatReponse)
def repondre(seance_id: int, corps: SoumissionReponse, eleve: EleveCourant, session: SessionDB) -> ResultatReponse:
    seance = _seance_ouverte(session, seance_id, eleve)
    question = seance.question_courante
    if question is None or question.id != corps.question_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Cette question n'est pas la question en cours.")

    maintenant = _maintenant()
    correcte = corriger(question_vers_domaine(question), corps.reponse_donnee)
    session.add(
        models.Reponse(
            seance=seance,
            question=question,
            reponse_donnee=corps.reponse_donnee,
            correcte=correcte,
            duree_s=(maintenant - _utc(seance.question_servie_le)).total_seconds(),
            repondu_le=maintenant,
        )
    )
    seance.question_courante = None
    seance.question_servie_le = None
    session.commit()

    historique = historique_eleve(session, eleve.id)
    return ResultatReponse(
        correcte=correcte,
        solution=question.solution,
        maitrise=calculer_maitrise(historique, question.competence_id),
        maitrisee=est_maitrisee(historique, question.competence_id),
    )
