"""Lecture et évaluation sûres des expressions saisies par les élèves.

On n'utilise jamais `eval` : l'expression est normalisée, analysée par `ast`,
puis évaluée nœud par nœud avec une liste blanche d'opérations.

Notations acceptées : `0,5`, `1 000`, `2x`, `x(x+1)`, `x^2`, `x²`, `3×4`,
`sqrt(2)`, `racine(2)`, `ln`, `log` (base 10), `exp`, `sin`, `cos`, `tan`,
`abs`, `pi` / `π`, `e`.
"""

import ast
import math
import re
from collections.abc import Mapping

LONGUEUR_MAX = 200

FONCTIONS = {
    "sqrt": math.sqrt,
    "racine": math.sqrt,
    "ln": math.log,
    "log": math.log10,
    "exp": math.exp,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "abs": abs,
}
CONSTANTES = {"pi": math.pi, "e": math.e}

_REMPLACEMENTS = {
    ",": ".",
    "×": "*",
    "·": "*",
    "÷": "/",
    "−": "-",
    "^": "**",
    "²": "**2",
    "³": "**3",
    "π": " pi ",  # espaces : « 2πx » ne doit pas devenir l'identifiant « pix »
    "√(": "sqrt(",
}
_JETON = re.compile(r"(\d+(?:\.\d*)?|\.\d+)|([a-zA-Z]+)|(\*\*|[-+*/()])")


class ExpressionInvalide(ValueError):
    """La saisie n'est pas une expression mathématique reconnue."""


class HorsDomaine(ValueError):
    """L'expression est valide mais non définie en ce point (division par 0, ln(-1)…)."""


def analyser(texte: str) -> ast.Expression:
    """Transforme une saisie libre en arbre syntaxique Python validé."""
    if not texte or not texte.strip():
        raise ExpressionInvalide("saisie vide")
    if len(texte) > LONGUEUR_MAX:
        raise ExpressionInvalide("saisie trop longue")
    try:
        arbre = ast.parse(_normaliser(texte), mode="eval")
    except SyntaxError as exc:
        raise ExpressionInvalide(str(exc)) from exc
    noms_de_fonction = set()
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, _NOEUDS_AUTORISES):
            raise ExpressionInvalide(f"élément non autorisé : {type(noeud).__name__}")
        if isinstance(noeud, ast.Call):
            if not (
                isinstance(noeud.func, ast.Name)
                and noeud.func.id in FONCTIONS
                and len(noeud.args) == 1
                and not noeud.keywords
            ):
                raise ExpressionInvalide("appel de fonction invalide")
            noms_de_fonction.add(id(noeud.func))
        elif isinstance(noeud, ast.Name) and noeud.id in FONCTIONS and id(noeud) not in noms_de_fonction:
            raise ExpressionInvalide(f"{noeud.id} doit être suivi de parenthèses")
    return arbre


def variables(arbre: ast.Expression) -> set[str]:
    return {
        n.id
        for n in ast.walk(arbre)
        if isinstance(n, ast.Name) and n.id not in CONSTANTES and n.id not in FONCTIONS
    }


def evaluer(arbre: ast.Expression, valeurs: Mapping[str, float]) -> float:
    try:
        resultat = _evaluer(arbre.body, valeurs)
    except (ZeroDivisionError, OverflowError, ValueError) as exc:
        if isinstance(exc, ExpressionInvalide):
            raise
        raise HorsDomaine(str(exc)) from exc
    if isinstance(resultat, complex) or not math.isfinite(resultat):
        raise HorsDomaine("résultat non réel ou infini")
    return resultat


def _normaliser(texte: str) -> str:
    texte = re.sub(r"(?<=\d)\s+(?=\d)", "", texte.strip())  # « 1 000 » -> « 1000 »
    for ancien, nouveau in _REMPLACEMENTS.items():
        texte = texte.replace(ancien, nouveau)

    jetons: list[tuple[str, str]] = []
    position = 0
    for m in _JETON.finditer(texte):
        if texte[position : m.start()].strip():
            raise ExpressionInvalide(f"caractère inattendu : {texte[position:m.start()]!r}")
        position = m.end()
        nombre, identifiant, operateur = m.groups()
        if nombre:
            jetons.append(("nombre", nombre))
        elif operateur:
            jetons.append(("op", operateur))
        elif identifiant in FONCTIONS:
            jetons.append(("fonction", identifiant))
        elif identifiant in CONSTANTES:
            jetons.append(("valeur", identifiant))
        elif identifiant[:-1] in FONCTIONS:
            # « lnx », « cosx » : une fonction collée à une seule lettre.
            jetons += [("fonction", identifiant[:-1]), ("valeur", identifiant[-1])]
        else:
            # « xy » signifie x*y : les variables n'ont qu'une lettre.
            jetons.extend(("valeur", lettre) for lettre in identifiant)
    if texte[position:].strip():
        raise ExpressionInvalide(f"caractère inattendu : {texte[position:]!r}")

    jetons = _arguments_sans_parentheses(jetons)

    # Multiplication implicite : 2x, 2(x+1), x(x+1), (x+1)(x-1), 2sqrt(3)…
    morceaux: list[str] = []
    precedent: tuple[str, str] | None = None
    for genre, valeur in jetons:
        if precedent is not None:
            fin_de_terme = precedent[0] in ("nombre", "valeur") or precedent == ("op", ")")
            debut_de_terme = genre in ("nombre", "valeur", "fonction") or (genre, valeur) == ("op", "(")
            if fin_de_terme and debut_de_terme:
                morceaux.append("*")
        morceaux.append(valeur)
        precedent = (genre, valeur)
    return "".join(morceaux)


def _arguments_sans_parentheses(jetons: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """« ln5 », « 2ln2 », « ln x + 1 » : la fonction s'applique au seul nombre ou à la
    seule lettre qui suit. Si la suite est ambiguë (« ln2x », « ln x^2 », « ln 2/3 »),
    la saisie est refusée plutôt que devinée."""
    resultat: list[tuple[str, str]] = []
    i = 0
    while i < len(jetons):
        genre, valeur = jetons[i]
        resultat.append(jetons[i])
        if genre == "fonction" and i + 1 < len(jetons) and jetons[i + 1][0] in ("nombre", "valeur"):
            suivant = jetons[i + 2] if i + 2 < len(jetons) else None
            if suivant is not None and suivant not in (("op", "+"), ("op", "-"), ("op", ")")):
                raise ExpressionInvalide(f"parenthèses nécessaires après {valeur} : écrire {valeur}(…)")
            resultat += [("op", "("), jetons[i + 1], ("op", ")")]
            i += 2
            continue
        i += 1
    return resultat


_NOEUDS_AUTORISES = (
    ast.Expression,
    ast.Constant,
    ast.Name,
    ast.Load,
    ast.UnaryOp,
    ast.UAdd,
    ast.USub,
    ast.BinOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.Call,
)


def _evaluer(noeud: ast.AST, valeurs: Mapping[str, float]) -> float:
    match noeud:
        case ast.Constant(value=v) if isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v)
        case ast.Name(id=nom):
            if nom in CONSTANTES:
                return CONSTANTES[nom]
            if nom in valeurs:
                return float(valeurs[nom])
            raise ExpressionInvalide(f"nom inconnu : {nom}")
        case ast.UnaryOp(op=ast.USub(), operand=o):
            return -_evaluer(o, valeurs)
        case ast.UnaryOp(op=ast.UAdd(), operand=o):
            return _evaluer(o, valeurs)
        case ast.BinOp(left=g, op=op, right=d):
            a, b = _evaluer(g, valeurs), _evaluer(d, valeurs)
            match op:
                case ast.Add():
                    return a + b
                case ast.Sub():
                    return a - b
                case ast.Mult():
                    return a * b
                case ast.Div():
                    return a / b
                case ast.Pow():
                    return a**b
        case ast.Call(func=ast.Name(id=nom), args=[argument], keywords=[]) if nom in FONCTIONS:
            return FONCTIONS[nom](_evaluer(argument, valeurs))
    raise ExpressionInvalide(f"expression non reconnue : {ast.dump(noeud)}")
