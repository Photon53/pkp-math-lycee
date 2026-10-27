"""Moteur pédagogique PKP Math Lycée.

Règle d'or : ce paquet n'importe jamais FastAPI, SQLAlchemy ni aucune
bibliothèque d'E/S. Il reçoit des objets du domaine et renvoie des objets du domaine.
"""

from pkp_engine.correction import corriger
from pkp_engine.domain import Niveau, Question, Reponse, TypeQuestion
from pkp_engine.expressions import ExpressionInvalide
from pkp_engine.maitrise import SEUIL_MAITRISE, calculer_maitrise, est_maitrisee
from pkp_engine.selection import choisir_prochaine_question

__all__ = [
    "SEUIL_MAITRISE",
    "ExpressionInvalide",
    "Niveau",
    "Question",
    "Reponse",
    "TypeQuestion",
    "calculer_maitrise",
    "choisir_prochaine_question",
    "corriger",
    "est_maitrisee",
]
