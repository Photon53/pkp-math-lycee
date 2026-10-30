"""Statistiques globales du site pour le tableau de bord administrateur (EA3.20 à EA3.22).

Uniquement des agrégats : aucun prénom. Un taux portant sur moins de `SEUIL_ELEVES` élèves est
masqué. Les calculs sont des requêtes SQL groupées, mises en cache `DUREE_CACHE_S` secondes.
"""

import threading
import time
from datetime import date, datetime, timedelta

from sqlalchemy import case, distinct, func, select
from sqlalchemy.orm import Session

from app.db import models
from app.referentiel import StatutValidation, TypeRessource
from app.schemas_admin import (
    CouvertureNiveau,
    PointJour,
    PointReussiteJour,
    QuestionDifficile,
    Repartition,
    ReussiteChapitre,
    RessourceTop,
    Statistiques,
)

PERIODES = (7, 30, 365)
SEUIL_ELEVES = 5
REPONSES_MIN_QUESTION_DIFFICILE = 30
DUREE_CACHE_S = 600

_cache: dict[int, tuple[float, Statistiques]] = {}
_verrou = threading.Lock()


def vider_cache() -> None:
    with _verrou:
        _cache.clear()


def calculer(session: Session, periode: int, maintenant: datetime) -> Statistiques:
    with _verrou:
        en_cache = _cache.get(periode)
        if en_cache and time.monotonic() - en_cache[0] < DUREE_CACHE_S:
            return en_cache[1]
    resultat = _calculer(session, periode, maintenant)
    with _verrou:
        _cache[periode] = (time.monotonic(), resultat)
    return resultat


def _jour(valeur) -> date:
    # SQLite renvoie « AAAA-MM-JJ » (texte), PostgreSQL une date.
    return valeur if isinstance(valeur, date) else date.fromisoformat(str(valeur)[:10])


def _taux(correctes: int, total: int) -> float | None:
    return correctes / total if total else None


def _calculer(session: Session, periode: int, maintenant: datetime) -> Statistiques:
    debut = maintenant - timedelta(days=periode)
    correcte = func.sum(case((models.Reponse.correcte, 1), else_=0))
    sur_periode = models.Reponse.repondu_le >= debut

    professeurs_total = session.scalar(select(func.count(models.Enseignant.id)).where(models.Enseignant.actif))
    professeurs_actifs = session.scalar(
        select(func.count(models.Enseignant.id)).where(models.Enseignant.actif, models.Enseignant.derniere_connexion >= debut)
    )
    eleves_total = session.scalar(select(func.count(models.Eleve.id)))
    eleves_actifs = session.scalar(select(func.count(distinct(models.Seance.eleve_id))).where(models.Seance.debut >= debut))
    seances = session.scalar(select(func.count(models.Seance.id)).where(models.Seance.debut >= debut))
    nb_reponses, nb_correctes = session.execute(select(func.count(models.Reponse.id), correcte).where(sur_periode)).one()

    jour_seance = func.date(models.Seance.debut)
    seances_par_jour = [
        PointJour(jour=_jour(j), valeur=n)
        for j, n in session.execute(
            select(jour_seance, func.count()).where(models.Seance.debut >= debut).group_by(jour_seance).order_by(jour_seance)
        )
    ]
    jour_reponse = func.date(models.Reponse.repondu_le)
    reponses_par_jour = [
        PointReussiteJour(jour=_jour(j), reponses=n, correctes=c or 0)
        for j, n, c in session.execute(
            select(jour_reponse, func.count(), correcte).where(sur_periode).group_by(jour_reponse).order_by(jour_reponse)
        )
    ]

    reussite_par_chapitre = [
        ReussiteChapitre(
            chapitre_id=ch_id, titre=titre, niveau=niveau, reponses=n,
            taux_reussite=_taux(c or 0, n) if nb_eleves >= SEUIL_ELEVES else None,
        )
        for ch_id, titre, niveau, n, c, nb_eleves in session.execute(
            select(
                models.Chapitre.id, models.Chapitre.titre, models.Chapitre.niveau,
                func.count(models.Reponse.id), correcte, func.count(distinct(models.Seance.eleve_id)),
            )
            .select_from(models.Reponse)
            .join(models.Seance, models.Seance.id == models.Reponse.seance_id)
            .join(models.Question, models.Question.id == models.Reponse.question_id)
            .join(models.Competence, models.Competence.id == models.Question.competence_id)
            .join(models.Chapitre, models.Chapitre.id == models.Competence.chapitre_id)
            .where(sur_periode)
            .group_by(models.Chapitre.id, models.Chapitre.titre, models.Chapitre.niveau)
        )
    ]
    reussite_par_chapitre.sort(key=lambda r: (r.taux_reussite is None, r.taux_reussite or 0))

    nb_q = func.count(models.Reponse.id)
    questions_difficiles = [
        QuestionDifficile(question_id=q_id, code=code, enonce=enonce, chapitre=titre, reponses=n, taux_reussite=(c or 0) / n)
        for q_id, code, enonce, titre, n, c in session.execute(
            select(models.Question.id, models.Question.code, models.Question.enonce, models.Chapitre.titre, nb_q, correcte)
            .select_from(models.Reponse)
            .join(models.Question, models.Question.id == models.Reponse.question_id)
            .join(models.Competence, models.Competence.id == models.Question.competence_id)
            .join(models.Chapitre, models.Chapitre.id == models.Competence.chapitre_id)
            .where(sur_periode)
            .group_by(models.Question.id, models.Question.code, models.Question.enonce, models.Chapitre.titre)
            .having(nb_q >= REPONSES_MIN_QUESTION_DIFFICILE)
            .order_by((correcte * 1.0 / nb_q).asc())
            .limit(20)
        )
    ]

    couverture: dict = {}
    for niveau, statut, n in session.execute(
        select(models.Chapitre.niveau, models.Question.statut_validation, func.count(models.Question.id))
        .join(models.Competence, models.Competence.id == models.Question.competence_id)
        .join(models.Chapitre, models.Chapitre.id == models.Competence.chapitre_id)
        .where(models.Question.archivee.is_(False))
        .group_by(models.Chapitre.niveau, models.Question.statut_validation)
    ):
        couverture.setdefault(niveau, {s: 0 for s in StatutValidation})[statut] = n
    competences_sans_cours = session.scalar(
        select(func.count(models.Competence.id))
        .outerjoin(models.Lecon, models.Lecon.competence_id == models.Competence.id)
        .where(models.Lecon.id.is_(None), models.Competence.masque.is_(False))
    )
    valides = (
        select(models.Competence.chapitre_id)
        .join(models.Question, models.Question.competence_id == models.Competence.id)
        .where(models.Question.statut_validation == StatutValidation.VALIDEE, models.Question.archivee.is_(False))
    )
    chapitres_sans_validee = list(
        session.scalars(
            select(models.Chapitre.titre)
            .where(models.Chapitre.id.not_in(valides), models.Chapitre.masque.is_(False))
            .order_by(models.Chapitre.niveau, models.Chapitre.ordre)
        )
    )

    nb_eleves_classe = (
        select(models.Eleve.classe_id, func.count(models.Eleve.id).label("n")).group_by(models.Eleve.classe_id).subquery()
    )
    repartition = [
        Repartition(niveau=niveau, parcours=parcours, classes=nc, eleves=ne or 0)
        for niveau, parcours, nc, ne in session.execute(
            select(models.Classe.niveau, models.Classe.parcours, func.count(models.Classe.id), func.sum(nb_eleves_classe.c.n))
            .outerjoin(nb_eleves_classe, nb_eleves_classe.c.classe_id == models.Classe.id)
            .group_by(models.Classe.niveau, models.Classe.parcours)
            .order_by(models.Classe.niveau, models.Classe.parcours)
        )
    ]

    par_type = dict(
        session.execute(select(models.Ressource.type, func.count(models.Ressource.id)).group_by(models.Ressource.type)).all()
    )
    total_consult = func.sum(models.RessourceConsultation.nombre)
    ressources_consultees = [
        RessourceTop(ressource_id=r_id, titre=titre, type=type_.value, consultations=n)
        for r_id, titre, type_, n in session.execute(
            select(models.Ressource.id, models.Ressource.titre, models.Ressource.type, total_consult)
            .join(models.RessourceConsultation, models.RessourceConsultation.ressource_id == models.Ressource.id)
            .where(models.RessourceConsultation.jour >= debut.date())
            .group_by(models.Ressource.id, models.Ressource.titre, models.Ressource.type)
            .order_by(total_consult.desc())
            .limit(10)
        )
    ]

    return Statistiques(
        periode_jours=periode,
        calcule_le=maintenant,
        professeurs_actifs=professeurs_actifs,
        professeurs_total=professeurs_total,
        eleves_actifs=eleves_actifs,
        eleves_total=eleves_total,
        seances=seances,
        reponses=nb_reponses,
        taux_reussite=_taux(nb_correctes or 0, nb_reponses),
        seances_par_jour=seances_par_jour,
        reponses_par_jour=reponses_par_jour,
        reussite_par_chapitre=reussite_par_chapitre,
        questions_difficiles=questions_difficiles,
        couverture=[
            CouvertureNiveau(
                niveau=n,
                a_valider=c[StatutValidation.A_VALIDER],
                validees=c[StatutValidation.VALIDEE],
                a_corriger=c[StatutValidation.A_CORRIGER],
            )
            for n, c in couverture.items()
        ],
        competences_sans_cours=competences_sans_cours,
        chapitres_sans_question_validee=chapitres_sans_validee,
        repartition=repartition,
        ressources_liens=par_type.get(TypeRessource.LIEN, 0),
        ressources_pdf=par_type.get(TypeRessource.PDF, 0),
        ressources_consultees=ressources_consultees,
    )
