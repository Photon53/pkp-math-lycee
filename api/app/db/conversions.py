"""Passage des lignes de la base aux objets du moteur : le moteur ne voit jamais SQLAlchemy."""

from collections.abc import Iterable

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
        forme=q.forme,
    )


def historique_eleve(
    session: Session, eleve_id: int, competence_ids: Iterable[int] | None = None
) -> list[pkp_engine.Reponse]:
    """Réponses d'un élève, de la plus ancienne à la plus récente.

    Avec `competence_ids`, seulement celles de ces compétences (l'historique grandit toute l'année ;
    la maîtrise et le choix de la question n'utilisent que les compétences en jeu). La toute dernière
    réponse est alors ajoutée à la fin si elle porte sur une autre compétence : le choix de la question
    suivante a besoin de savoir quelle question vient d'être posée."""
    requete = (
        select(models.Reponse.question_id, models.Question.competence_id, models.Reponse.correcte, models.Reponse.duree_s)
        .join(models.Question, models.Reponse.question_id == models.Question.id)
        .join(models.Seance, models.Reponse.seance_id == models.Seance.id)
        .where(models.Seance.eleve_id == eleve_id)
    )
    ordre = (models.Reponse.repondu_le, models.Reponse.id)
    if competence_ids is None:
        return [pkp_engine.Reponse(*ligne) for ligne in session.execute(requete.order_by(*ordre))]

    competence_ids = set(competence_ids)
    historique = [
        pkp_engine.Reponse(*ligne)
        for ligne in session.execute(requete.where(models.Question.competence_id.in_(competence_ids)).order_by(*ordre))
    ]
    derniere = session.execute(requete.order_by(*(c.desc() for c in ordre)).limit(1)).first()
    if derniere is not None and derniere.competence_id not in competence_ids:
        historique.append(pkp_engine.Reponse(*derniere))
    return historique
