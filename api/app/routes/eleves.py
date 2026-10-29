"""Parcours élève : connexion → séance → question → réponse → question…

Une séance n'a qu'une question en cours à la fois. Redemander la question
suivante renvoie la même tant qu'elle n'a pas reçu de réponse : impossible de
« passer » une question difficile, ou de répondre à une question non servie.
"""

from datetime import UTC, datetime
from functools import cache

from fastapi import APIRouter, HTTPException, Request, Response, status
from pkp_engine import calculer_maitrise, choisir_prochaine_question, corriger, est_maitrisee
from sqlalchemy import select

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
from app.security import (
    creer_jeton,
    generer_code_eleve,
    hacher_code_eleve,
    verifier_code_eleve,
    version_mot_de_passe,
)

router = APIRouter(tags=["élève"])


def _maintenant() -> datetime:
    return datetime.now(UTC)


def _utc(instant: datetime) -> datetime:
    # SQLite rend des dates sans fuseau : elles ont été enregistrées en UTC.
    return instant if instant.tzinfo else instant.replace(tzinfo=UTC)


def _info(eleve: models.Eleve) -> EleveInfo:
    return EleveInfo(id=eleve.id, prenom=eleve.prenom, code_classe=eleve.classe.code, niveau=eleve.classe.niveau)


ECHEC_CONNEXION = "Prénom, code classe ou code personnel incorrect."


@cache
def _code_leurre() -> str:
    return hacher_code_eleve(generer_code_eleve())


@router.post("/eleves/connexion", response_model=JetonEleve)
def connexion(corps: ConnexionEleve, request: Request, session: SessionDB) -> JetonEleve:
    """Prénom + code classe + code personnel (distribué par l'enseignant).

    Les comptes sont créés par l'enseignant : il n'y a plus de création à la première
    connexion (audit A-07 d). Un seul message d'échec, que l'erreur porte sur la classe,
    le prénom ou le code : on ne révèle pas quels élèves existent.
    """
    ip = limitation.adresse_ip(request)
    compte = f"eleve:{corps.code_classe}:{corps.prenom}"
    limitation.verifier(
        (limitation.par_ip, ip), (limitation.codes_inconnus, ip), (limitation.echecs_code_eleve, compte)
    )
    limitation.par_ip.enregistrer(ip)

    classe = session.scalar(select(models.Classe).where(models.Classe.code == corps.code_classe))
    if classe is None:
        limitation.codes_inconnus.enregistrer(ip)  # freine la recherche de codes classe
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, ECHEC_CONNEXION)
    eleve = session.scalar(
        select(models.Eleve).where(models.Eleve.classe_id == classe.id, models.Eleve.prenom == corps.prenom)
    )
    empreinte = eleve.code_hash if eleve and eleve.code_hash else _code_leurre()  # même durée dans tous les cas
    if not verifier_code_eleve(corps.code_personnel, empreinte) or not (eleve and eleve.code_hash):
        limitation.echecs_code_eleve.enregistrer(compte)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, ECHEC_CONNEXION)
    limitation.echecs_code_eleve.effacer(compte)
    version = version_mot_de_passe(eleve.code_hash)
    return JetonEleve(jeton=creer_jeton(ELEVE, eleve.id, settings.duree_jeton_eleve_h, version), eleve=_info(eleve))


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
