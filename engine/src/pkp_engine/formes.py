"""Forme d'écriture d'une expression : développée, factorisée ou réduite.

La correction vérifie d'abord la valeur (équivalence) ; pour « Développer », « Factoriser »
ou « Réduire », la forme compte aussi : recopier l'énoncé `(x+3)²` n'est pas développer.

Les règles portent sur l'arbre analysé (`expressions.analyser`) :
- développée : une somme de monômes, sans produit ni puissance d'une somme ;
- réduite : développée, chaque monôme (même partie littérale) n'apparaît qu'une fois et son
  coefficient est calculé (`(3+3)x` ou `2·3x` ne sont pas réduits ; `3x/2` l'est) ;
- factorisée : un produit d'au moins deux facteurs contenant la variable, une puissance d'une
  somme, ou un nombre autre que ±1 fois une somme ; `1(9x²-25)` ou `(9x²-25)/1` ne comptent pas.

Une sous-expression sans variable (`sqrt(2)`, `1/3`, `(2+3)`) compte comme un nombre.
"""

import ast
from collections import Counter

from pkp_engine.domain import Forme
from pkp_engine.expressions import CONSTANTES, FONCTIONS, HorsDomaine, evaluer


LIBELLES = {
    Forme.DEVELOPPEE: "développée",
    Forme.FACTORISEE: "factorisée",
    Forme.REDUITE: "développée et réduite",
}


def respecte(arbre: ast.Expression, forme: Forme) -> bool:
    corps = arbre.body
    match forme:
        case Forme.DEVELOPPEE:
            return all(_partie_litterale(t) is not None for t in _termes(corps))
        case Forme.REDUITE:
            termes = _termes(corps)
            parties = [_partie_litterale(t) for t in termes]
            if any(p is None for p in parties) or not all(_coefficient_calcule(t) for t in termes):
                return False
            return all(n == 1 for n in Counter(parties).values())
        case Forme.FACTORISEE:
            return _factorisee(corps)


def _facteurs(noeud: ast.AST, numerateur: bool = True) -> list[tuple[ast.AST, bool]]:
    """Facteurs d'un produit ou d'un quotient, avec leur place (numérateur ou dénominateur) ;
    les signes ne comptent pas."""
    match noeud:
        case ast.UnaryOp(operand=o):
            return _facteurs(o, numerateur)
        case ast.BinOp(op=ast.Mult(), left=g, right=d):
            return _facteurs(g, numerateur) + _facteurs(d, numerateur)
        case ast.BinOp(op=ast.Div(), left=g, right=d):
            return _facteurs(g, numerateur) + _facteurs(d, not numerateur)
    return [(noeud, numerateur)]


def _est_somme(noeud: ast.AST) -> bool:
    while isinstance(noeud, ast.UnaryOp):
        noeud = noeud.operand
    return isinstance(noeud, ast.BinOp) and isinstance(noeud.op, (ast.Add, ast.Sub))


def _factorisee(corps: ast.AST) -> bool:
    facteurs = _facteurs(corps)
    litteraux = [f for f, _ in facteurs if not _sans_variable(f)]
    if len(litteraux) != 1:
        return True  # au moins deux facteurs avec la variable, ou un nombre
    seul = litteraux[0]
    if isinstance(seul, ast.BinOp) and isinstance(seul.op, ast.Pow) and _est_somme(seul.left):
        exposant = _nombre(seul.right)
        if exposant is not None and exposant >= 2:
            return True  # (x+1)²
        seul = seul.left
    if not _est_somme(seul):
        return True  # un monôme est déjà sous forme factorisée
    # Une somme multipliée par un nombre : factorisée seulement si ce nombre n'est pas ±1.
    coefficient = 1.0
    for f, numerateur in facteurs:
        if _sans_variable(f):
            try:
                v = evaluer(ast.Expression(body=f), {})
            except HorsDomaine:
                return False
            coefficient = coefficient * v if numerateur else coefficient / v
    return abs(abs(coefficient) - 1) > 1e-12


def _coefficient_calcule(terme: ast.AST) -> bool:
    """Au plus un nombre au numérateur et un au dénominateur, chacun déjà calculé."""
    constantes = [(f, n) for f, n in _facteurs(terme) if _sans_variable(f)]
    if sum(n for _, n in constantes) > 1 or sum(not n for _, n in constantes) > 1:
        return False
    return all(_nombre_simple(f) for f, _ in constantes)


def _nombre_simple(noeud: ast.AST) -> bool:
    """`3`, `pi`, `sqrt(2)` : pas une opération entre nombres restée à calculer (`3+3`, `2^3`)."""
    for n in ast.walk(noeud):
        if isinstance(n, ast.BinOp) and not (isinstance(n.op, ast.Pow) and isinstance(n.left, ast.Name)):
            return False
    return True


def _termes(noeud: ast.AST) -> list[ast.AST]:
    """Termes d'une somme : `a - b + c` -> [a, b, c] (les signes ne comptent pas pour la forme)."""
    if isinstance(noeud, ast.BinOp) and isinstance(noeud.op, (ast.Add, ast.Sub)):
        return _termes(noeud.left) + _termes(noeud.right)
    if isinstance(noeud, ast.UnaryOp):
        return _termes(noeud.operand)
    return [noeud]


def _sans_variable(noeud: ast.AST) -> bool:
    return not any(isinstance(n, ast.Name) and n.id not in CONSTANTES and n.id not in FONCTIONS for n in ast.walk(noeud))


def _partie_litterale(noeud: ast.AST) -> tuple[tuple[str, float], ...] | None:
    """Partie littérale d'un monôme (`3x²y` -> (("x", 2), ("y", 1))), `()` pour un nombre,
    None si le terme n'est pas un monôme (produit d'une somme, fonction d'une variable…)."""
    exposants = _exposants(noeud)
    if exposants is None:
        return None
    return tuple(sorted((v, e) for v, e in exposants.items() if e != 0))


def _exposants(noeud: ast.AST) -> Counter | None:
    if _sans_variable(noeud):
        return Counter()
    match noeud:
        case ast.Name(id=nom):
            return Counter({nom: 1})
        case ast.UnaryOp(operand=o):
            return _exposants(o)
        case ast.BinOp(op=ast.Mult(), left=g, right=d):
            a, b = _exposants(g), _exposants(d)
            return None if a is None or b is None else _ajouter(a, b, 1)
        case ast.BinOp(op=ast.Div(), left=g, right=d):
            a, b = _exposants(g), _exposants(d)
            return None if a is None or b is None else _ajouter(a, b, -1)
        case ast.BinOp(op=ast.Pow(), left=base, right=exposant) if _sans_variable(exposant):
            valeur = _nombre(exposant)
            b = _exposants(base) if isinstance(base, (ast.Name, ast.Constant)) else None
            if b is None or valeur is None:
                return None
            return Counter({v: e * valeur for v, e in b.items()})
    return None


def _ajouter(a: Counter, b: Counter, signe: int) -> Counter:
    total = Counter(a)
    for v, e in b.items():
        total[v] += signe * e
    return total


def _nombre(noeud: ast.AST) -> float | None:
    match noeud:
        case ast.Constant(value=v) if isinstance(v, (int, float)):
            return float(v)
        case ast.UnaryOp(op=ast.USub(), operand=o):
            v = _nombre(o)
            return None if v is None else -v
    return None
