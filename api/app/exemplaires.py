"""Questions à valeurs variables : l'exemplaire posé à l'élève, avec les nombres de son tirage.

Une question sans gabarit est son propre exemplaire (tirage `None`) : tout le reste de l'API
passe par ces fonctions sans avoir à distinguer les deux cas.
"""

from dataclasses import replace

from pkp_engine import Question, gabarits

from app.db import models
from app.db.conversions import question_vers_domaine


def nouveau_tirage(question: models.Question) -> dict[str, str] | None:
    return gabarits.tirer(question.gabarit) if question.gabarit else None


def enonce(question: models.Question, tirage: dict | None) -> str:
    return gabarits.remplir(question.enonce, tirage) if tirage else question.enonce


def solution(question: models.Question, tirage: dict | None) -> str:
    return gabarits.remplir(question.solution, tirage) if tirage else question.solution


def correction(question: models.Question, tirage: dict | None) -> dict | None:
    return gabarits.remplir_correction(question.correction, tirage) if tirage else question.correction


def domaine(question: models.Question, tirage: dict | None) -> Question:
    """Question du moteur, avec la solution de cet exemplaire : c'est elle que la correction compare."""
    return replace(question_vers_domaine(question), enonce=enonce(question, tirage), solution=solution(question, tirage))


def publique(question: models.Question, tirage: dict | None) -> dict:
    """Ce que voit l'élève avant de répondre (schéma QuestionPublique) : jamais la solution."""
    return {
        "id": question.id,
        "competence_id": question.competence_id,
        "enonce": enonce(question, tirage),
        "type": question.type,
        "difficulte": question.difficulte,
        "variable": question.gabarit is not None,
    }
