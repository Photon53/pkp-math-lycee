"""Correction d'une réponse d'élève.

- QCM : comparaison du libellé, sans tenir compte de la casse ni des espaces.
- Numérique : la valeur compte, pas l'écriture (`0,5` = `1/2` = `.5`).
- Expression : équivalence mathématique, vérifiée en évaluant les deux
  expressions en plusieurs points (`x(x+1)` = `x^2 + x`). Les deux doivent
  aussi avoir le même domaine de définition sur ces points (`2ln(x)` ≠ `ln(x²)`).
  La forme attendue (développée, factorisée…) n'est pas contrôlée.

Une saisie illisible de l'élève est simplement fausse. Une solution illisible
est une erreur de données et lève `ExpressionInvalide`.
"""

import math

from pkp_engine.domain import Question, TypeQuestion
from pkp_engine.expressions import ExpressionInvalide, HorsDomaine, analyser, evaluer, variables

TOLERANCE_RELATIVE = 1e-9
TOLERANCE_ABSOLUE = 1e-9

# Points d'évaluation choisis pour éviter les valeurs « faciles » (0, 1, entiers).
POINTS_TEST = (0.53, 1.71, -2.37, 3.13, -0.71, 2.93, 0.137, -1.29)
POINTS_VALIDES_MIN = 4


def corriger(question: Question, reponse_donnee: str) -> bool:
    """Indique si `reponse_donnee` est correcte pour `question`."""
    if question.type is TypeQuestion.QCM:
        return _normaliser_qcm(reponse_donnee) == _normaliser_qcm(question.solution)

    solution = analyser(question.solution)
    try:
        reponse = analyser(reponse_donnee)
    except ExpressionInvalide:
        return False

    if question.type is TypeQuestion.NUMERIQUE:
        if variables(reponse) or variables(solution):
            return False
        try:
            return _proches(evaluer(reponse, {}), evaluer(solution, {}))
        except HorsDomaine:
            return False

    return _equivalentes(reponse, solution)


def _normaliser_qcm(texte: str) -> str:
    return " ".join(texte.split()).casefold()


def _proches(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=TOLERANCE_RELATIVE, abs_tol=TOLERANCE_ABSOLUE)


def _equivalentes(reponse, solution) -> bool:
    noms = sorted(variables(reponse) | variables(solution))
    if not noms:
        try:
            return _proches(evaluer(reponse, {}), evaluer(solution, {}))
        except HorsDomaine:
            return False

    points_valides = 0
    for k in range(len(POINTS_TEST)):
        # Chaque variable reçoit une valeur différente au même point.
        valeurs = {nom: POINTS_TEST[(k + 3 * j) % len(POINTS_TEST)] for j, nom in enumerate(noms)}
        a, b = _evaluer_ou_none(reponse, valeurs), _evaluer_ou_none(solution, valeurs)
        if a is None and b is None:
            continue
        # Défini d'un côté seulement : domaines différents, donc pas équivalentes
        # (ex. ln(x²) et 2ln(x) pour x < 0).
        if a is None or b is None or not _proches(a, b):
            return False
        points_valides += 1
    return points_valides >= POINTS_VALIDES_MIN


def _evaluer_ou_none(arbre, valeurs) -> float | None:
    try:
        return evaluer(arbre, valeurs)
    except HorsDomaine:
        return None
