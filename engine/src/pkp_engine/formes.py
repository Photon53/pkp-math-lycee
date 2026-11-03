"""Forme d'écriture d'une expression : développée, factorisée ou réduite.

La correction vérifie d'abord la valeur (équivalence) ; pour « Développer », « Factoriser »
ou « Réduire », la forme compte aussi : recopier l'énoncé `(x+3)²` n'est pas développer.

Les règles portent sur l'arbre analysé (`expressions.analyser`) :
- développée : une somme de monômes, sans produit ni puissance d'une somme ;
- réduite : développée, et chaque monôme (même partie littérale) n'apparaît qu'une fois ;
- factorisée : un produit, un quotient ou une puissance au premier niveau, pas une somme.

Une sous-expression sans variable (`sqrt(2)`, `1/3`, `(2+3)`) compte comme un nombre.
"""

import ast
from collections import Counter

from pkp_engine.domain import Forme
from pkp_engine.expressions import CONSTANTES, FONCTIONS


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
            parties = [_partie_litterale(t) for t in _termes(corps)]
            if any(p is None for p in parties):
                return False
            return all(n == 1 for n in Counter(parties).values())
        case Forme.FACTORISEE:
            while isinstance(corps, ast.UnaryOp):
                corps = corps.operand
            return not (isinstance(corps, ast.BinOp) and isinstance(corps.op, (ast.Add, ast.Sub)))


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
