"""Passage des lignes de la base aux objets du moteur : le moteur ne voit jamais SQLAlchemy."""

import pkp_engine
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models


def question_vers_domaine(q: models.Question) -> pkp_engine.Question:
    return pkp_engine.Question(
        id=q.id,
        competence_id=q.competence_id,
        enonce=q.enonce,
        type=q.type,
        solution=q.solution,
        difficulte=q.difficulte,
        archivee=q.archivee,
    )


def historique_eleve(session: Session, eleve_id: int) -> list[pkp_engine.Reponse]:
    """Toutes les réponses d'un élève, de la plus ancienne à la plus récente."""
    lignes = session.execute(
        select(models.Reponse.question_id, models.Question.competence_id, models.Reponse.correcte, models.Reponse.duree_s)
        .join(models.Question, models.Reponse.question_id == models.Question.id)
        .join(models.Seance, models.Reponse.seance_id == models.Seance.id)
        .where(models.Seance.eleve_id == eleve_id)
        .order_by(models.Reponse.repondu_le, models.Reponse.id)
    )
    return [pkp_engine.Reponse(*ligne) for ligne in lignes]
