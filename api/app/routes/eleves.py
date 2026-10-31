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

from app import inscriptions, limitation
from app.auth import ELEVE, EleveCourant, SessionDB
from app.config import settings
from app.db import models
from app.db.conversions import historique_eleve, question_vers_domaine
from app.progression import (
    filtre_validation,
    avancement_competence,
    historique_reponses,
    ids_ouverts,
    nb_questions_servables,
    progression_eleve,
)
from app.schemas import (
    AvancementCompetence,
    ChapitreOuvert,
    ConnexionEleve,
    PageHistorique,
    EleveInfo,
    InscriptionLiee,
    JetonEleve,
    ProgressionCompetence,
    QuestionPublique,
    ResultatReponse,
    SeanceCreation,
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
    return EleveInfo(
        id=eleve.id,
        prenom=eleve.prenom,
        code_classe=eleve.classe.code,
        niveau=eleve.classe.niveau,
        parcours=eleve.classe.parcours,
    )


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
    if not classe.enseignant.actif:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Le compte de ton professeur est suspendu.")
    version = version_mot_de_passe(eleve.code_hash)
    return JetonEleve(jeton=creer_jeton(ELEVE, eleve.id, settings.duree_jeton_eleve_h, version), eleve=_info(eleve))


@router.get("/eleves/moi", response_model=EleveInfo)
def moi(eleve: EleveCourant) -> EleveInfo:
    return _info(eleve)


@router.get("/eleves/moi/parcours", response_model=list[InscriptionLiee])
def mes_parcours(eleve: EleveCourant, session: SessionDB) -> list[InscriptionLiee]:
    """Toutes les inscriptions de l'élève (celle-ci comprise), reliées par son professeur."""
    autres = inscriptions.liees(session, eleve)
    return [inscriptions.decrire(e, actuelle=e.id == eleve.id) for e in sorted([eleve, *autres], key=lambda e: e.id)]


@router.post("/eleves/moi/parcours/{eleve_id}", response_model=JetonEleve)
def changer_de_parcours(eleve_id: int, eleve: EleveCourant, session: SessionDB) -> JetonEleve:
    """Passe à une autre inscription du même élève : vérifié côté serveur (lien posé par le professeur)."""
    cible = next((e for e in inscriptions.liees(session, eleve) if e.id == eleve_id), None)
    if cible is None or cible.code_hash is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Parcours introuvable.")
    if not cible.classe.enseignant.actif:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Le compte du professeur de cette classe est suspendu.")
    version = version_mot_de_passe(cible.code_hash)
    return JetonEleve(jeton=creer_jeton(ELEVE, cible.id, settings.duree_jeton_eleve_h, version), eleve=_info(cible))


@router.get("/eleves/moi/progression", response_model=list[ProgressionCompetence])
def ma_progression(eleve: EleveCourant, session: SessionDB) -> list[ProgressionCompetence]:
    return progression_eleve(session, eleve)


@router.get("/eleves/moi/chapitres", response_model=list[ChapitreOuvert])
def mes_chapitres(eleve: EleveCourant, session: SessionDB) -> list[ChapitreOuvert]:
    """Chapitres ouverts par l'enseignant, avec le nombre de questions disponibles."""
    chapitres = sorted((c for c in eleve.classe.chapitres_proposes if not c.masque), key=lambda c: c.ordre)
    nb = nb_questions_servables(session, [c.id for c in chapitres])
    return [ChapitreOuvert(id=c.id, code=c.code, titre=c.titre, nb_questions=nb.get(c.id, 0)) for c in chapitres]


@router.get("/eleves/moi/historique", response_model=PageHistorique)
def mon_historique(
    eleve: EleveCourant, session: SessionDB, page: int = 1, erreurs: bool = False, competence_id: int | None = None
) -> PageHistorique:
    """Ce que l'élève a déjà fait : questions, réponses, corrections (questions déjà répondues uniquement)."""
    return historique_reponses(session, eleve, page, erreurs, competence_id)


@router.get("/eleves/moi/competences/{competence_id}/avancement", response_model=AvancementCompetence)
def mon_avancement(competence_id: int, eleve: EleveCourant, session: SessionDB) -> AvancementCompetence:
    """Avancement dans la méthode PKP pour une compétence d'un chapitre ouvert."""
    competence = session.get(models.Competence, competence_id)
    if competence is None or competence.masque or competence.chapitre_id not in ids_ouverts(eleve.classe):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Compétence introuvable.")
    return avancement_competence(session, eleve, competence)


@router.post("/seances", response_model=SeanceInfo, status_code=status.HTTP_201_CREATED)
def demarrer_seance(eleve: EleveCourant, session: SessionDB, corps: SeanceCreation | None = None) -> models.Seance:
    """Démarre une séance sur les chapitres choisis (tous les chapitres ouverts si aucun choix)."""
    ouverts = {c.id: c for c in eleve.classe.chapitres_proposes if not c.masque}
    if not ouverts:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ton professeur n'a pas encore ouvert de chapitre.")
    competences = []
    if corps and corps.competence_ids:
        # Séance ciblée depuis une leçon : les chapitres sont ceux des compétences demandées.
        competences = [session.get(models.Competence, i) for i in dict.fromkeys(corps.competence_ids)]
        if any(c is None or c.masque or c.chapitre_id not in ouverts for c in competences):
            raise HTTPException(422, "Cette compétence n'est pas proposée par ton professeur.")
        choisis = list(dict.fromkeys(c.chapitre_id for c in competences))
    else:
        choisis = list(dict.fromkeys(corps.chapitre_ids)) if corps and corps.chapitre_ids else list(ouverts)
    if any(i not in ouverts for i in choisis):
        raise HTTPException(422, "Ce chapitre n'est pas proposé par ton professeur.")
    seance = models.Seance(
        eleve=eleve, debut=_maintenant(), chapitres=[ouverts[i] for i in choisis], competences=competences,
        difficulte_min=corps.difficulte_min if corps else None, difficulte_max=corps.difficulte_max if corps else None,
    )
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
    responses={204: {"description": "Aucune question disponible dans les chapitres de la séance."}},
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
            .where(
                # Chapitres choisis pour la séance ; séances antérieures : tous les chapitres ouverts.
                models.Chapitre.id.in_([c.id for c in seance.chapitres] or ids_ouverts(eleve.classe)),
                models.Question.archivee.is_(False),
                *filtre_validation(),
                *([models.Question.competence_id.in_([c.id for c in seance.competences])] if seance.competences else []),
                *([models.Question.difficulte >= seance.difficulte_min] if seance.difficulte_min else []),
                *([models.Question.difficulte <= seance.difficulte_max] if seance.difficulte_max else []),
            )
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
        correction=question.correction,
        competence=question.competence.libelle,
        rappel=question.competence.lecon.resume if question.competence.lecon else None,
        maitrise=calculer_maitrise(historique, question.competence_id),
        maitrisee=est_maitrisee(historique, question.competence_id),
    )
