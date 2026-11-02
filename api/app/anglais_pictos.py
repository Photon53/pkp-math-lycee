"""Pictogrammes vectoriels des cahiers PKP Anglais : dessinés ici, donc sans droits d'image ni fichier à télécharger.

Chaque pictogramme est tracé dans un carré de 60 × 60 puis mis à l'échelle ; les noms sont ceux du champ
« picto » de contenu/anglais/ressources-pedagogiques.json.
"""
from base64 import b64encode
from math import cos, pi, sin

from reportlab.graphics import renderSVG
from reportlab.graphics.shapes import Circle, Drawing, Ellipse, Group, Line, PolyLine, Polygon, Rect, Wedge
from reportlab.lib import colors

ENCRE = colors.HexColor("#183153")
BLANC = colors.white
VERT = colors.HexColor("#2E9E5B")
VERT_CLAIR = colors.HexColor("#7BC67E")
ORANGE = colors.HexColor("#F2994A")
JAUNE = colors.HexColor("#F6C945")
BLEU = colors.HexColor("#2666A2")
BLEU_CLAIR = colors.HexColor("#8EC5F0")
ROUGE = colors.HexColor("#E05A47")
VIOLET = colors.HexColor("#8E6CC9")
BRUN = colors.HexColor("#9C6B3F")


def _trait(points, couleur=ENCRE, epaisseur=2.5):
    return PolyLine(points, strokeColor=couleur, strokeWidth=epaisseur, strokeLineCap=1, strokeLineJoin=1)


def _ballon():
    g = [Circle(30, 30, 24, fillColor=BLANC, strokeColor=ENCRE, strokeWidth=2.5)]
    points = []
    for k in range(5):
        a = pi / 2 + k * 2 * pi / 5
        points += [30 + 9 * cos(a), 30 + 9 * sin(a)]
    g.append(Polygon(points, fillColor=ENCRE, strokeColor=ENCRE))
    for k in range(5):
        a = pi / 2 + k * 2 * pi / 5
        g.append(Line(30 + 9 * cos(a), 30 + 9 * sin(a), 30 + 24 * cos(a), 30 + 24 * sin(a), strokeColor=ENCRE, strokeWidth=1.8))
    return g


def _livre():
    return [
        Polygon([30, 14, 6, 18, 6, 48, 30, 44], fillColor=BLEU_CLAIR, strokeColor=ENCRE, strokeWidth=2),
        Polygon([30, 14, 54, 18, 54, 48, 30, 44], fillColor=BLANC, strokeColor=ENCRE, strokeWidth=2),
        Line(30, 14, 30, 44, strokeColor=ENCRE, strokeWidth=2),
        *[Line(35, y, 49, y + 1, strokeColor=BLEU, strokeWidth=1.5) for y in (24, 30, 36)],
    ]


def _musique():
    return [
        Ellipse(17, 16, 7, 5, fillColor=VIOLET, strokeColor=VIOLET),
        Ellipse(43, 22, 7, 5, fillColor=VIOLET, strokeColor=VIOLET),
        Line(23, 16, 23, 48, strokeColor=VIOLET, strokeWidth=3),
        Line(49, 22, 49, 54, strokeColor=VIOLET, strokeWidth=3),
        Polygon([23, 48, 49, 54, 49, 47, 23, 41], fillColor=VIOLET, strokeColor=VIOLET),
    ]


def _manette():
    return [
        Rect(4, 14, 52, 30, rx=13, ry=13, fillColor=BLEU_CLAIR, strokeColor=ENCRE, strokeWidth=2.5),
        Rect(12, 26, 14, 5, fillColor=ENCRE, strokeColor=ENCRE),
        Rect(16.5, 21.5, 5, 14, fillColor=ENCRE, strokeColor=ENCRE),
        Circle(40, 32, 3.5, fillColor=ROUGE, strokeColor=ROUGE),
        Circle(47, 25, 3.5, fillColor=VERT, strokeColor=VERT),
    ]


def _cinema():
    g = [
        Rect(8, 8, 44, 28, fillColor=ENCRE, strokeColor=ENCRE),
        Polygon([8, 38, 52, 38, 52, 48, 8, 48], fillColor=BLANC, strokeColor=ENCRE, strokeWidth=2),
    ]
    for x in (8, 22, 36):
        g.append(Polygon([x, 38, x + 7, 38, x + 14, 48, x + 7, 48], fillColor=ENCRE, strokeColor=ENCRE))
    g.append(Polygon([25, 15, 25, 29, 37, 22], fillColor=JAUNE, strokeColor=JAUNE))
    return g


def _arbre():
    return [
        Rect(27, 6, 6, 20, fillColor=BRUN, strokeColor=BRUN),
        Circle(20, 32, 11, fillColor=VERT, strokeColor=VERT),
        Circle(40, 32, 11, fillColor=VERT, strokeColor=VERT),
        Circle(30, 43, 13, fillColor=VERT_CLAIR, strokeColor=VERT_CLAIR),
    ]


def _musee():
    g = [
        Polygon([6, 40, 54, 40, 30, 54], fillColor=JAUNE, strokeColor=ENCRE, strokeWidth=2),
        Rect(6, 8, 48, 5, fillColor=ENCRE, strokeColor=ENCRE),
        Rect(8, 36, 44, 4, fillColor=ENCRE, strokeColor=ENCRE),
    ]
    g += [Rect(x, 13, 5, 23, fillColor=BLANC, strokeColor=ENCRE, strokeWidth=1.8) for x in (12, 22, 33, 43)]
    return g


def _bowling():
    return [
        Ellipse(42, 30, 7, 18, fillColor=BLANC, strokeColor=ENCRE, strokeWidth=2),
        Rect(36, 34, 12, 3, fillColor=ROUGE, strokeColor=ROUGE),
        Circle(20, 20, 14, fillColor=BLEU, strokeColor=ENCRE, strokeWidth=2),
        Circle(16, 25, 2, fillColor=ENCRE, strokeColor=ENCRE),
        Circle(22, 27, 2, fillColor=ENCRE, strokeColor=ENCRE),
        Circle(20, 21, 2, fillColor=ENCRE, strokeColor=ENCRE),
    ]


def _plante():
    return [
        Polygon([16, 6, 44, 6, 48, 22, 12, 22], fillColor=ORANGE, strokeColor=ENCRE, strokeWidth=2),
        Line(30, 22, 30, 46, strokeColor=VERT, strokeWidth=3),
        Polygon([30, 34, 16, 40, 10, 52, 22, 48], fillColor=VERT_CLAIR, strokeColor=VERT, strokeWidth=1.5),
        Polygon([30, 40, 44, 46, 52, 56, 38, 54], fillColor=VERT_CLAIR, strokeColor=VERT, strokeWidth=1.5),
    ]


def _recyclage():
    g = []
    for k in range(3):
        a0 = pi / 2 + k * 2 * pi / 3 + 0.35
        a1 = a0 + 2 * pi / 3 - 0.7
        arc = []
        for i in range(9):
            a = a0 + (a1 - a0) * i / 8
            arc += [30 + 20 * cos(a), 30 + 20 * sin(a)]
        g.append(_trait(arc, VERT, 5))
        x, y = 30 + 20 * cos(a1), 30 + 20 * sin(a1)
        dx, dy = -sin(a1), cos(a1)
        g.append(Polygon([x + 6 * dx, y + 6 * dy, x + 6 * cos(a1), y + 6 * sin(a1), x - 6 * cos(a1), y - 6 * sin(a1)],
                         fillColor=VERT, strokeColor=VERT))
    return g


def _bulles():
    return [
        Rect(4, 26, 32, 22, rx=8, ry=8, fillColor=BLEU_CLAIR, strokeColor=ENCRE, strokeWidth=2),
        Polygon([12, 27, 10, 18, 20, 27], fillColor=BLEU_CLAIR, strokeColor=ENCRE, strokeWidth=2),
        Rect(24, 8, 32, 20, rx=8, ry=8, fillColor=JAUNE, strokeColor=ENCRE, strokeWidth=2),
        Polygon([46, 9, 50, 2, 40, 9], fillColor=JAUNE, strokeColor=ENCRE, strokeWidth=2),
    ]


def _ampoule():
    g = [
        Circle(30, 34, 15, fillColor=JAUNE, strokeColor=ENCRE, strokeWidth=2),
        Rect(24, 12, 12, 9, fillColor=BLANC, strokeColor=ENCRE, strokeWidth=2),
        Line(24, 16, 36, 16, strokeColor=ENCRE, strokeWidth=1.5),
    ]
    for a in (pi / 6, pi / 2, 5 * pi / 6, pi / 3 - 0.2, 2 * pi / 3 + 0.2):
        g.append(Line(30 + 19 * cos(a), 34 + 19 * sin(a), 30 + 25 * cos(a), 34 + 25 * sin(a), strokeColor=ORANGE, strokeWidth=2))
    return g


def _equipe():
    g = []
    for x, couleur in ((14, BLEU), (46, VERT), (30, ORANGE)):
        g.append(Wedge(x, 8, 12, 0, 180, fillColor=couleur, strokeColor=couleur))
        g.append(Circle(x, 26, 7, fillColor=couleur, strokeColor=BLANC, strokeWidth=1.5))
    return g


def _valide():
    return [Circle(30, 30, 24, fillColor=VERT, strokeColor=VERT), _trait([18, 31, 27, 21, 43, 39], BLANC, 5)]


def _casque():
    arc = []
    for i in range(13):
        a = pi * i / 12
        arc += [30 + 20 * cos(a), 26 + 20 * sin(a)]
    return [
        _trait(arc, ENCRE, 4),
        Rect(6, 12, 10, 18, rx=4, ry=4, fillColor=BLEU, strokeColor=ENCRE, strokeWidth=1.5),
        Rect(44, 12, 10, 18, rx=4, ry=4, fillColor=BLEU, strokeColor=ENCRE, strokeWidth=1.5),
    ]


def _crayon():
    return [
        Polygon([10, 14, 42, 46, 50, 38, 18, 6], fillColor=JAUNE, strokeColor=ENCRE, strokeWidth=2),
        Polygon([10, 14, 18, 6, 6, 2], fillColor=BRUN, strokeColor=ENCRE, strokeWidth=1.5),
        Polygon([42, 46, 50, 38, 54, 42, 46, 50], fillColor=ROUGE, strokeColor=ENCRE, strokeWidth=1.5),
    ]


def _cible():
    return [
        Circle(30, 30, 24, fillColor=ROUGE, strokeColor=ROUGE),
        Circle(30, 30, 16, fillColor=BLANC, strokeColor=BLANC),
        Circle(30, 30, 8, fillColor=ROUGE, strokeColor=ROUGE),
    ]


def _etoile():
    points = []
    for k in range(10):
        a = pi / 2 + k * pi / 5
        r = 24 if k % 2 == 0 else 10
        points += [30 + r * cos(a), 28 + r * sin(a)]
    return [Polygon(points, fillColor=JAUNE, strokeColor=ORANGE, strokeWidth=2)]


def _globe():
    return [
        Circle(30, 30, 23, fillColor=BLEU_CLAIR, strokeColor=ENCRE, strokeWidth=2),
        Ellipse(30, 30, 10, 23, fillColor=None, strokeColor=ENCRE, strokeWidth=1.5),
        Line(7, 30, 53, 30, strokeColor=ENCRE, strokeWidth=1.5),
        Line(11, 42, 49, 42, strokeColor=ENCRE, strokeWidth=1.2),
        Line(11, 18, 49, 18, strokeColor=ENCRE, strokeWidth=1.2),
    ]


PICTOS = {
    "ballon": _ballon, "livre": _livre, "musique": _musique, "manette": _manette, "cinema": _cinema,
    "arbre": _arbre, "musee": _musee, "bowling": _bowling, "plante": _plante, "recyclage": _recyclage,
    "bulles": _bulles, "ampoule": _ampoule, "equipe": _equipe, "valide": _valide,
    # Icônes des rubriques du cahier.
    "casque": _casque, "crayon": _crayon, "cible": _cible, "etoile": _etoile, "globe": _globe,
}


def groupe(nom: str, taille: float, x: float = 0, y: float = 0) -> Group:
    """Le pictogramme `nom`, de `taille` points de côté, posé en (x, y)."""
    g = Group(*PICTOS[nom]())
    s = taille / 60
    g.transform = (s, 0, 0, s, x, y)
    return g


def dessin(nom: str, taille: float) -> Drawing:
    d = Drawing(taille, taille)
    d.add(groupe(nom, taille))
    return d


def image_svg(nom: str, taille: float = 64) -> str:
    """Le même pictogramme pour l'écran web, en image data: (une balise <img> n'exécute rien)."""
    svg = renderSVG.drawToString(dessin(nom, taille))
    return "data:image/svg+xml;base64," + b64encode(svg.encode("utf-8")).decode("ascii")
