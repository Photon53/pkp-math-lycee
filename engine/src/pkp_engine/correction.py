"""Correction d'une réponse d'élève.

- QCM : comparaison du libellé, sans tenir compte de la casse ni des espaces.
- Numérique : la valeur compte, pas l'écriture (`0,5` = `1/2` = `.5`).
- Expression : équivalence mathématique, vérifiée en évaluant les deux
  expressions en plusieurs points (`x(x+1)` = `x^2 + x`). Les deux doivent
  aussi avoir le même domaine de définition sur ces points (`2ln(x)` ≠ `ln(x²)`).
  Aux points fixes s'ajoutent des points pseudo-aléatoires tirés à partir de la solution
  et de la saisie (une expression construite pour s'annuler aux points fixes ne passe
  donc pas, et une même réponse reçoit toujours le même verdict) et des
  entiers proches de 0, où se cachent les valeurs interdites (`x²/x` ≠ `x` en 0).
  Si la question exige une forme (`Question.forme`), elle est contrôlée ensuite :
  recopier `(x+3)²` ne répond pas à « Développer (x+3)² » (voir `formes`).

- Texte (réponse courte) : la solution liste les réponses acceptées, séparées par « | »
  (`finissent | ils finissent`). La casse, les espaces en trop, la forme des apostrophes et des
  tirets et la ponctuation finale ne comptent pas ; **les accents comptent** (« a » ≠ « à »).

Une saisie illisible de l'élève est simplement fausse. Une solution illisible
est une erreur de données et lève `ExpressionInvalide`.
"""

import math
import random
import re
import unicodedata
from enum import Enum

from pkp_engine import formes
from pkp_engine.domain import Question, TypeQuestion
from pkp_engine.expressions import ExpressionInvalide, HorsDomaine, analyser, evaluer, variables

TOLERANCE_RELATIVE = 1e-9
TOLERANCE_ABSOLUE = 1e-9

# Points d'évaluation choisis pour éviter les valeurs « faciles » (0, 1, entiers).
POINTS_TEST = (0.53, 1.71, -2.37, 3.13, -0.71, 2.93, 0.137, -1.29)
# Valeurs interdites les plus fréquentes au lycée : ne comptent que si elles révèlent un écart.
POINTS_DOMAINE = (0.0, 1.0, -1.0, 2.0, -2.0, 3.0, -3.0)
NB_POINTS_ALEATOIRES = 8
POINTS_VALIDES_MIN = 4


class Verdict(str, Enum):
    JUSTE = "juste"
    FAUX = "faux"
    # Valeur juste mais forme demandée non respectée : l'élève doit le savoir.
    FORME = "forme"


def corriger(question: Question, reponse_donnee: str) -> bool:
    """Indique si `reponse_donnee` est correcte pour `question`."""
    return verifier(question, reponse_donnee) is Verdict.JUSTE


def verifier(question: Question, reponse_donnee: str) -> Verdict:
    """Verdict détaillé : juste, faux, ou juste en valeur mais pas sous la forme demandée."""
    if question.type is TypeQuestion.QCM:
        return _verdict(_normaliser_qcm(reponse_donnee) == _normaliser_qcm(question.solution))
    if question.type is TypeQuestion.TEXTE:
        saisie = normaliser_texte(reponse_donnee)
        return _verdict(bool(saisie) and saisie in {normaliser_texte(r) for r in reponses_acceptees(question.solution)})

    solution = analyser(question.solution)
    try:
        reponse = analyser(reponse_donnee)
    except ExpressionInvalide:
        return Verdict.FAUX

    if question.type is TypeQuestion.NUMERIQUE:
        if variables(reponse) or variables(solution):
            return Verdict.FAUX
        try:
            return _verdict(_proches(evaluer(reponse, {}), evaluer(solution, {})))
        except HorsDomaine:
            return Verdict.FAUX

    if not _equivalentes(reponse, solution, graine=f"{question.solution}|{reponse_donnee}"):
        return Verdict.FAUX
    if question.forme is not None and not formes.respecte(reponse, question.forme):
        return Verdict.FORME
    return Verdict.JUSTE


def _verdict(juste: bool) -> Verdict:
    return Verdict.JUSTE if juste else Verdict.FAUX


SEPARATEUR_REPONSES = "|"
_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "ʼ": "'", "`": "'", "´": "'", "‐": "-", "‑": "-", "–": "-", "—": "-"})


def reponses_acceptees(solution: str) -> list[str]:
    """Les réponses acceptées d'une question « texte », dans l'ordre (la première est la réponse modèle)."""
    return [r.strip() for r in solution.split(SEPARATEUR_REPONSES) if r.strip()]


def reponse_modele(question: Question) -> str:
    """La réponse modèle : la solution telle quelle, ou la première réponse acceptée d'une question « texte »."""
    if question.type is TypeQuestion.TEXTE:
        return next(iter(reponses_acceptees(question.solution)), "")
    return question.solution


def normaliser_texte(texte: str) -> str:
    """Forme de comparaison d'une réponse courte : casse, espaces, apostrophes, tirets et ponctuation
    finale neutralisés ; accents et cédilles conservés (forme Unicode composée)."""
    texte = unicodedata.normalize("NFC", texte).translate(_APOSTROPHES).casefold()
    texte = re.sub(r"\s*([-'])\s*", r"\1", " ".join(texte.split()))  # « l ' arbre » = « l'arbre »
    return texte.rstrip(" .!?;:…")


def _normaliser_qcm(texte: str) -> str:
    return " ".join(texte.split()).casefold()


def _proches(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=TOLERANCE_RELATIVE, abs_tol=TOLERANCE_ABSOLUE)


def _equivalentes(reponse, solution, graine: str = "") -> bool:
    noms = sorted(variables(reponse) | variables(solution))
    if not noms:
        try:
            return _proches(evaluer(reponse, {}), evaluer(solution, {}))
        except HorsDomaine:
            return False

    points_valides = 0
    for valeurs in _points(noms, graine):
        a, b = _evaluer_ou_none(reponse, valeurs), _evaluer_ou_none(solution, valeurs)
        if a is None and b is None:
            continue
        # Défini d'un côté seulement : domaines différents, donc pas équivalentes
        # (ex. ln(x²) et 2ln(x) pour x < 0).
        if a is None or b is None or not _proches(a, b):
            return False
        points_valides += 1
    return points_valides >= POINTS_VALIDES_MIN


def _points(noms: list[str], graine: str) -> list[dict[str, float]]:
    """Points fixes, entiers proches de 0 et points pseudo-aléatoires (reproductibles : une
    graine texte donne toujours le même tirage) ; chaque variable reçoit une valeur différente
    au même point."""
    hasard = random.Random(graine)
    series = (
        POINTS_TEST,
        POINTS_DOMAINE,
        tuple(hasard.choice((-1, 1)) * hasard.uniform(0.2, 3.4) for _ in range(NB_POINTS_ALEATOIRES)),
    )
    return [
        {nom: serie[(k + 3 * j) % len(serie)] for j, nom in enumerate(noms)}
        for serie in series
        for k in range(len(serie))
    ]


def _evaluer_ou_none(arbre, valeurs) -> float | None:
    try:
        return evaluer(arbre, valeurs)
    except HorsDomaine:
        return None
