"""Moteur pédagogique PKP Math Lycée.

Règle d'or : ce paquet n'importe jamais FastAPI, SQLAlchemy ni aucune
bibliothèque d'E/S. Il reçoit des objets du domaine et renvoie des objets du domaine.
"""

from pkp_engine.correction import Verdict, corriger, reponse_modele, reponses_acceptees, verifier
from pkp_engine.domain import Forme, Niveau, Question, Reponse, TypeQuestion
from pkp_engine.expressions import ExpressionInvalide
from pkp_engine.maitrise import SEUIL_MAITRISE, calculer_maitrise, est_maitrisee
from pkp_engine.selection import choisir_prochaine_question

__all__ = [
    "SEUIL_MAITRISE",
    "ExpressionInvalide",
    "Forme",
    "Niveau",
    "Question",
    "Reponse",
    "TypeQuestion",
    "Verdict",
    "calculer_maitrise",
    "choisir_prochaine_question",
    "corriger",
    "est_maitrisee",
    "reponse_modele",
    "reponses_acceptees",
    "verifier",
]
