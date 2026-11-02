"""Questions à valeurs variables (« gabarits ») : le même exercice, avec d'autres nombres à chaque fois.

Un gabarit décrit des paramètres tirés au hasard, des valeurs calculées et des conditions :

    parametres: {a: {entre: [2, 9]}, x: {entre: [-6, 6], sauf: [0]}, s: {parmi: [-1, 1]}}
    calculs:    {b: "a*x - 3"}
    conditions: ["b != 0"]

Les textes (énoncé, solution, étapes de correction) citent les valeurs entre doubles crochets,
pour ne pas se confondre avec les accolades du LaTeX :

    [[a]]       la valeur : 3, -2, 5/4 (fraction exacte)
    [[b:+]]     un terme signé : « + 3 », « - 2 » (pour écrire « 2x [[b:+]] »)
    [[a:coef]]  un coefficient devant une lettre : « » pour 1, « - » pour -1, sinon la valeur
    [[c:frac]]  en LaTeX : \\dfrac{5}{4}, -\\dfrac{1}{2}, ou un entier

Les calculs sont exacts (fractions) : aucune erreur d'arrondi dans les solutions.
"""

import ast
import math
import operator
import random
import re
from fractions import Fraction

Valeur = Fraction

TIRAGES_MAX = 500  # au-delà, les conditions sont jugées impossibles à satisfaire


class GabaritInvalide(ValueError):
    """Gabarit mal écrit ou conditions impossibles à satisfaire."""


_OPERATEURS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
}
_COMPARAISONS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}
def _pgcd(a, b):
    if a.denominator != 1 or b.denominator != 1:
        raise GabaritInvalide("pgcd : entiers seulement")
    return math.gcd(int(a), int(b))


_FONCTIONS = {"abs": abs, "min": min, "max": max, "pgcd": _pgcd}


def evaluer(expression: str, valeurs: dict[str, Valeur]):
    """Évalue une expression arithmétique ou une condition, en fractions exactes. Pas d'eval Python :
    seuls les nombres, les noms de paramètres, + - * / ** % //, les comparaisons, and/or/not, abs/min/max/pgcd."""
    try:
        arbre = ast.parse(str(expression), mode="eval").body
    except SyntaxError as exc:
        raise GabaritInvalide(f"expression illisible « {expression} »") from exc
    return _noeud(arbre, valeurs, expression)


def _noeud(n, valeurs, source):
    if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
        return Fraction(str(n.value))
    if isinstance(n, ast.Name):
        if n.id not in valeurs:
            raise GabaritInvalide(f"« {n.id} » inconnu dans « {source} »")
        return valeurs[n.id]
    if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd, ast.Not)):
        v = _noeud(n.operand, valeurs, source)
        return -v if isinstance(n.op, ast.USub) else (not v if isinstance(n.op, ast.Not) else v)
    if isinstance(n, ast.BinOp) and type(n.op) in _OPERATEURS:
        gauche, droite = _noeud(n.left, valeurs, source), _noeud(n.right, valeurs, source)
        if isinstance(n.op, ast.Pow) and (droite.denominator != 1 or abs(droite) > 20):
            raise GabaritInvalide(f"puissance non entière ou trop grande dans « {source} »")
        try:
            resultat = _OPERATEURS[type(n.op)](gauche, droite)
        except ZeroDivisionError as exc:
            raise ZeroDivisionError(f"division par zéro dans « {source} »") from exc
        return Fraction(resultat)
    if isinstance(n, ast.Compare):
        gauche = _noeud(n.left, valeurs, source)
        for op, droite_n in zip(n.ops, n.comparators):
            if type(op) not in _COMPARAISONS:
                raise GabaritInvalide(f"comparaison non permise dans « {source} »")
            droite = _noeud(droite_n, valeurs, source)
            if not _COMPARAISONS[type(op)](gauche, droite):
                return False
            gauche = droite
        return True
    if isinstance(n, ast.BoolOp):
        resultats = (_noeud(v, valeurs, source) for v in n.values)
        return all(resultats) if isinstance(n.op, ast.And) else any(resultats)
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in _FONCTIONS and not n.keywords:
        return Fraction(_FONCTIONS[n.func.id](*(_noeud(a, valeurs, source) for a in n.args)))
    raise GabaritInvalide(f"élément non permis dans « {source} »")


def tirer(gabarit: dict, rng: random.Random | None = None) -> dict[str, str]:
    """Tire des valeurs qui respectent toutes les conditions. Renvoie {nom: "p/q" ou "n"} (sérialisable en JSON)."""
    rng = rng or random.Random()
    parametres = gabarit.get("parametres") or {}
    if not parametres:
        raise GabaritInvalide("aucun paramètre")
    for _ in range(TIRAGES_MAX):
        valeurs: dict[str, Valeur] = {}
        for nom, regle in parametres.items():
            valeurs[nom] = _tirer_un(nom, regle, rng)
        try:
            for nom, expression in (gabarit.get("calculs") or {}).items():
                valeurs[nom] = Fraction(evaluer(expression, valeurs))
            if all(evaluer(c, valeurs) for c in gabarit.get("conditions") or []):
                return {nom: str(v) for nom, v in valeurs.items()}
        except ZeroDivisionError:
            continue
    raise GabaritInvalide(f"conditions impossibles à satisfaire en {TIRAGES_MAX} tirages")


def _tirer_un(nom: str, regle: dict, rng: random.Random) -> Valeur:
    if "parmi" in regle:
        choix = [Fraction(str(v)) for v in regle["parmi"]]
    elif "entre" in regle:
        bas, haut = regle["entre"]
        pas = Fraction(str(regle.get("pas", 1)))
        n = int((Fraction(str(haut)) - Fraction(str(bas))) / pas)
        choix = [Fraction(str(bas)) + i * pas for i in range(n + 1)]
    else:
        raise GabaritInvalide(f"paramètre « {nom} » : préciser « entre » ou « parmi »")
    exclus = {Fraction(str(v)) for v in regle.get("sauf", [])}
    choix = [v for v in choix if v not in exclus]
    if not choix:
        raise GabaritInvalide(f"paramètre « {nom} » : aucune valeur possible")
    return rng.choice(choix)


def lire_tirage(tirage: dict[str, str]) -> dict[str, Valeur]:
    return {nom: Fraction(v) for nom, v in tirage.items()}


_MARQUE = re.compile(r"\[\[\s*([^\]:]+?)\s*(?::\s*(\+|coef|frac))?\s*\]\]")


def _ecrire(v: Valeur) -> str:
    return str(v.numerator) if v.denominator == 1 else f"{v.numerator}/{v.denominator}"


def _latex(v: Valeur) -> str:
    if v.denominator == 1:
        return str(v.numerator)
    signe = "-" if v < 0 else ""
    return f"{signe}\\dfrac{{{abs(v.numerator)}}}{{{v.denominator}}}"


def remplir(texte: str, tirage: dict[str, str]) -> str:
    """Remplace les marques [[…]] d'un texte par les valeurs tirées (expressions permises : [[a*x+1]])."""
    valeurs = lire_tirage(tirage)

    def remplacer(m: re.Match) -> str:
        v = Fraction(evaluer(m.group(1), valeurs))
        forme = m.group(2)
        if forme == "+":
            return f"{'-' if v < 0 else '+'} {_latex(abs(v))}"
        if forme == "coef":
            return "" if v == 1 else "-" if v == -1 else _latex(v)
        if forme == "frac":
            return _latex(v)
        return _ecrire(v)

    return _MARQUE.sub(remplacer, texte)


def remplir_correction(correction: dict | None, tirage: dict[str, str]) -> dict | None:
    """La correction avec les valeurs du tirage : chaque texte (méthode, étapes, résultat…) est rempli."""
    if correction is None:
        return None

    def parcourir(objet):
        if isinstance(objet, str):
            return remplir(objet, tirage)
        if isinstance(objet, list):
            return [parcourir(o) for o in objet]
        if isinstance(objet, dict):
            return {k: parcourir(v) for k, v in objet.items()}
        return objet

    return parcourir(correction)


def marques(texte: str) -> list[str]:
    """Expressions citées dans un texte (pour vérifier qu'elles ne citent que des paramètres connus)."""
    return [m.group(1) for m in _MARQUE.finditer(texte or "")]
