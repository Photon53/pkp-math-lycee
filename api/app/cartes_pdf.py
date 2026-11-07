"""Cartes d'accès des enfants en PDF A4 (ticket #23) : 4, 6 ou 8 cartes par feuille, lignes de découpe.

Chaque carte porte le nom, le niveau, l'identifiant, le code personnel, l'adresse de connexion et un QR code
qui ouvre la session directement (même lien que les cartes imprimées depuis le navigateur : `lienCarte`).

Les codes n'étant conservés que sous forme d'empreinte, le PDF ne peut être produit qu'avec des codes en
clair : ceux qu'un import vient de créer (vérifiés contre l'empreinte), ou des codes réémis à l'export.
"""

from dataclasses import dataclass
from io import BytesIO

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas

GRILLES = {4: (2, 2), 6: (2, 3), 8: (2, 4)}  # cartes par page → (colonnes, lignes)
MARGE = 1 * cm
MARGE_CARTE = 0.45 * cm
NAVY = colors.HexColor("#183153")
GRIS = colors.HexColor("#9AA5B1")
NOMS_NIVEAUX = {"6e": "6e", "5e": "5e", "4e": "4e", "3e": "3e", "2nde": "Seconde", "1re": "Première", "Tle": "Terminale"}


@dataclass(frozen=True)
class CarteAImprimer:
    nom: str
    niveau: str
    identifiant: str
    code: str


def lien(origine: str, identifiant: str, code: str) -> str:
    return f"{origine.rstrip('/')}/eleve#carte={identifiant}.{code}"


def _ajuster(texte: str, police: str, taille: float, largeur: float) -> str:
    """Coupe le texte (avec « … ») pour qu'il tienne dans `largeur`."""
    if stringWidth(texte, police, taille) <= largeur:
        return texte
    while texte and stringWidth(texte + "…", police, taille) > largeur:
        texte = texte[:-1]
    return texte + "…"


def _qr(donnees: str, taille: float) -> Drawing:
    """QR code carré de `taille` points (marge blanche de 2 modules comprise)."""
    dessin = Drawing(taille, taille)
    dessin.add(QrCodeWidget(donnees, barLevel="M", barBorder=2, barWidth=taille, barHeight=taille))
    return dessin


def _carte(c: Canvas, carte: CarteAImprimer, x: float, y: float, l: float, h: float, origine: str) -> None:
    c.saveState()  # couleurs et repère propres à chaque carte (le QR code les modifie)
    try:
        _contenu(c, carte, x, y, l, h, origine)
    finally:
        c.restoreState()


def _nom(c: Canvas, nom: str, x: float, y: float, largeur: float, k: float) -> None:
    """Le nom en entier si possible : taille réduite, sinon coupé avec « … »."""
    for taille in (13 * k, 11 * k, 9.5 * k):
        if stringWidth(nom, "Helvetica-Bold", taille) <= largeur:
            break
    c.setFont("Helvetica-Bold", taille)
    c.drawString(x, y, _ajuster(nom, "Helvetica-Bold", taille, largeur))


def _contenu(c: Canvas, carte: CarteAImprimer, x: float, y: float, l: float, h: float, origine: str) -> None:
    interieur_l, interieur_h = l - 2 * MARGE_CARTE, h - 2 * MARGE_CARTE
    gauche, haut = x + MARGE_CARTE, y + h - MARGE_CARTE
    k = max(0.85, min(1.2, h / (6.9 * cm), l / (9.5 * cm) * 1.1))  # texte un peu plus grand sur les grandes cartes
    verticale = h > 1.1 * l  # 4 par page : texte en haut, grand QR code en dessous
    if verticale:
        texte_l = interieur_l
        qr = min(interieur_l * 0.75, interieur_h - 140 * k, 7 * cm)
        qr_x, qr_y = x + (l - qr) / 2, y + MARGE_CARTE + 24 * k
    else:  # QR code à droite du texte, au-dessus des deux lignes du bas
        bas = 22 * k
        qr = min(interieur_h - bas, interieur_l * 0.42, 5.5 * cm)
        texte_l = interieur_l - qr - 0.4 * cm
        qr_x, qr_y = x + l - MARGE_CARTE - qr, y + MARGE_CARTE + bas + (interieur_h - bas - qr) / 2

    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 8 * k)
    c.drawString(gauche, haut - 8 * k, "BOUSSOLE · CARTE D'ACCÈS")
    c.setStrokeColor(NAVY)
    c.setLineWidth(0.8)
    c.line(gauche, haut - 11 * k, gauche + texte_l, haut - 11 * k)

    lignes = haut - 11 * k
    c.setFillColor(colors.black)
    lignes -= 18 * k
    _nom(c, carte.nom, gauche, lignes, texte_l, k)
    c.setFont("Helvetica", 9.5 * k)
    lignes -= 13 * k
    c.drawString(gauche, lignes, NOMS_NIVEAUX.get(carte.niveau, carte.niveau))

    for libelle, valeur in (("Identifiant", carte.identifiant), ("Code", carte.code)):
        lignes -= 15 * k
        c.setFont("Helvetica", 8 * k)
        c.drawString(gauche, lignes, libelle)
        lignes -= 13 * k
        c.setFont("Courier-Bold", 12.5 * k)
        c.drawString(gauche, lignes, _ajuster(valeur, "Courier-Bold", 12.5 * k, texte_l))

    # L'adresse, sur toute la largeur de la carte : elle doit rester lisible en entier.
    adresse = f"{origine.rstrip('/')}/eleve"
    taille = 7.5 * k
    while taille > 5.5 and stringWidth(adresse, "Helvetica", taille) > interieur_l:
        taille -= 0.25
    c.setFont("Helvetica", taille)
    c.drawString(gauche, y + MARGE_CARTE + 9 * k, _ajuster(adresse, "Helvetica", taille, interieur_l))
    c.setFillColor(GRIS)
    c.setFont("Helvetica", 7 * k)
    c.drawString(gauche, y + MARGE_CARTE, "Scanne le QR code, ou saisis ton identifiant et ton code.")

    renderPDF.draw(_qr(lien(origine, carte.identifiant, carte.code), qr), c, qr_x, qr_y)


def _decoupe(c: Canvas, colonnes: int, rangees: int, l: float, h: float) -> None:
    largeur, hauteur = A4
    c.saveState()
    c.setStrokeColor(GRIS)
    c.setLineWidth(0.4)
    c.setDash(3, 3)
    for i in range(colonnes + 1):
        x = MARGE + i * l
        c.line(x, MARGE / 3, x, hauteur - MARGE / 3)
    for j in range(rangees + 1):
        y = MARGE + j * h
        c.line(MARGE / 3, y, largeur - MARGE / 3, y)
    c.restoreState()


def generer(cartes: list[CarteAImprimer], par_page: int, origine: str, titre: str = "Cartes d'accès") -> bytes:
    if par_page not in GRILLES:
        raise ValueError("4, 6 ou 8 cartes par page.")
    colonnes, rangees = GRILLES[par_page]
    largeur, hauteur = A4
    l, h = (largeur - 2 * MARGE) / colonnes, (hauteur - 2 * MARGE) / rangees
    flux = BytesIO()
    c = Canvas(flux, pagesize=A4, pageCompression=1)
    c.setTitle(titre)
    c.setAuthor("Boussole")
    for debut in range(0, len(cartes), par_page):
        _decoupe(c, colonnes, rangees, l, h)
        for i, carte in enumerate(cartes[debut:debut + par_page]):
            col, rang = i % colonnes, i // colonnes
            _carte(c, carte, MARGE + col * l, hauteur - MARGE - (rang + 1) * h, l, h, origine)
        c.showPage()
    c.save()
    return flux.getvalue()
