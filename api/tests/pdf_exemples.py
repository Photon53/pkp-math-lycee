# Issue #4 — Renforcer le contrôle des PDF (Claude)
"""PDF d'essai, fabriqués à la volée : ordinaires, malformés, chiffrés, ou porteurs d'un contenu actif."""

import io
import zlib

from pypdf import PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, NameObject, NumberObject, TextStringObject


def _octets(ecrivain: PdfWriter) -> bytes:
    tampon = io.BytesIO()
    ecrivain.write(tampon)
    return tampon.getvalue()


def _ecrivain(pages: int = 1) -> PdfWriter:
    ecrivain = PdfWriter()
    for _ in range(pages):
        ecrivain.add_blank_page(595, 842)
    return ecrivain


def ordinaire(pages: int = 1) -> bytes:
    return _octets(_ecrivain(pages))


def avec_texte_et_liens() -> bytes:
    """Cours ordinaire : texte, signet, lien interne et lien web https."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    tampon = io.BytesIO()
    c = canvas.Canvas(tampon, pagesize=A4)
    c.bookmarkPage("debut")
    c.addOutlineEntry("Début", "debut")
    c.drawString(72, 760, "Chapitre 1 — Fonctions affines")
    c.linkURL("https://eduscol.education.fr/", (72, 700, 300, 720))
    c.showPage()
    c.drawString(72, 760, "Page 2")
    c.linkAbsolute("Retour", "debut", (72, 700, 300, 720))
    c.showPage()
    c.save()
    return tampon.getvalue()


def _annotation_lien(action: dict) -> bytes:
    ecrivain = _ecrivain()
    action_obj = DictionaryObject({NameObject(k): v for k, v in action.items()})
    annotation = DictionaryObject({
        NameObject("/Type"): NameObject("/Annot"),
        NameObject("/Subtype"): NameObject("/Link"),
        NameObject("/Rect"): ArrayObject([NumberObject(0), NumberObject(0), NumberObject(100), NumberObject(100)]),
        NameObject("/A"): ecrivain._add_object(action_obj),
    })
    ecrivain.pages[0][NameObject("/Annots")] = ArrayObject([ecrivain._add_object(annotation)])
    return _octets(ecrivain)


def lien(uri: str) -> bytes:
    return _annotation_lien({"/S": NameObject("/URI"), "/URI": TextStringObject(uri)})


def lancement() -> bytes:
    return _annotation_lien({"/S": NameObject("/Launch"), "/F": TextStringObject("cmd.exe")})


def envoi_formulaire() -> bytes:
    return _annotation_lien({"/S": NameObject("/SubmitForm"), "/F": TextStringObject("https://exemple.test/")})


def javascript_nomme() -> bytes:
    """Script de document (arbre de noms /JavaScript), exécuté à l'ouverture par les lecteurs."""
    return _assembler([
        b"<< /Type /Catalog /Pages 2 0 R /Names << /JavaScript << /Names [(a) 4 0 R] >> >> >>",
        PAGES[1],
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >>",
        b"<< /S /JavaScript /JS (app.alert\\(1\\)) >>",
    ])


def javascript_a_l_ouverture() -> bytes:
    ecrivain = _ecrivain()
    action = DictionaryObject({
        NameObject("/S"): NameObject("/JavaScript"), NameObject("/JS"): TextStringObject("app.alert(1)"),
    })
    ecrivain._root_object[NameObject("/OpenAction")] = ecrivain._add_object(action)
    return _octets(ecrivain)


def ouverture_sur_une_page() -> bytes:
    """Action d'ouverture ordinaire : afficher la première page (destination)."""
    ecrivain = _ecrivain()
    ecrivain._root_object[NameObject("/OpenAction")] = ArrayObject(
        [ecrivain.pages[0].indirect_reference, NameObject("/Fit")]
    )
    return _octets(ecrivain)


def actions_automatiques() -> bytes:
    ecrivain = _ecrivain()
    action = DictionaryObject({NameObject("/S"): NameObject("/Named"), NameObject("/N"): NameObject("/NextPage")})
    ecrivain.pages[0][NameObject("/AA")] = DictionaryObject({NameObject("/O"): ecrivain._add_object(action)})
    return _octets(ecrivain)


def fichier_embarque() -> bytes:
    ecrivain = _ecrivain()
    ecrivain.add_attachment("charge.exe", b"MZ\x90\x00")
    return _octets(ecrivain)


def chiffre() -> bytes:
    ecrivain = _ecrivain()
    ecrivain.encrypt(user_password="", owner_password="secret")
    return _octets(ecrivain)


def tronque() -> bytes:
    return ordinaire()[:200]


def faux_entete() -> bytes:
    return b"%PDF-1.4 intrus"


def sans_page() -> bytes:
    return b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\ntrailer << /Root 1 0 R >>\n%%EOF\n"


def _assembler(objets: list[bytes]) -> bytes:
    """PDF écrit à la main : objets numérotés à partir de 1, table de références croisées exacte."""
    sortie = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    positions = []
    for numero, corps in enumerate(objets, start=1):
        positions.append(len(sortie))
        sortie += f"{numero} 0 obj\n".encode() + corps + b"\nendobj\n"
    debut_xref = len(sortie)
    sortie += f"xref\n0 {len(objets) + 1}\n0000000000 65535 f \n".encode()
    for position in positions:
        sortie += f"{position:010d} 00000 n \n".encode()
    sortie += f"trailer\n<< /Size {len(objets) + 1} /Root 1 0 R >>\nstartxref\n{debut_xref}\n%%EOF\n".encode()
    return bytes(sortie)


PAGES = [
    b"<< /Type /Catalog /Pages 2 0 R >>",
    b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
]


def javascript_nom_encode() -> bytes:
    """`/J#61vaScript` et `/J#53` : les noms encodés échappaient à la recherche de chaînes."""
    return _assembler([
        b"<< /Type /Catalog /Pages 2 0 R >>",
        PAGES[1],
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Annots [5 0 R] >>",
        b"<< /S /J#61vaScript /J#53 (app.alert\\(1\\)) >>",
        b"<< /Type /Annot /Subtype /Link /Rect [0 0 100 100] /A 4 0 R >>",
    ])


def javascript_dans_un_flux_d_objets() -> bytes:
    """Action JavaScript (objet 6) rangée dans un flux d'objets compressé et déclenchée par un lien : invisible dans
    les octets bruts, que voyait seule l'ancienne recherche de chaînes."""
    interne = b"<< /S /JavaScript /JS (app.alert\\(1\\)) >>"
    entete = b"6 0 "
    donnees = zlib.compress(entete + interne)
    flux = (
        f"<< /Type /ObjStm /N 1 /First {len(entete)} /Filter /FlateDecode /Length {len(donnees)} >>\nstream\n".encode()
        + donnees + b"\nendstream"
    )
    objets = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        PAGES[1],
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Annots [5 0 R] >>",
        flux,
        b"<< /Type /Annot /Subtype /Link /Rect [0 0 100 100] /A 6 0 R >>",
    ]
    sortie = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    positions = []
    for numero, corps in enumerate(objets, start=1):
        positions.append(len(sortie))
        sortie += f"{numero} 0 obj\n".encode() + corps + b"\nendobj\n"
    # Table de références croisées en flux (PDF 1.5) : type 1 = objet en clair, type 2 = objet 6 dans le flux 4.
    debut_xref = len(sortie)
    lignes = [bytes([0, 0, 0, 0xFF, 0xFF])]
    lignes += [bytes([1]) + position.to_bytes(3, "big") + b"\x00" for position in positions]
    lignes += [bytes([2, 0, 0, 4, 0]), bytes([1]) + debut_xref.to_bytes(3, "big") + b"\x00"]
    table = zlib.compress(b"".join(lignes))
    sortie += (
        f"7 0 obj\n<< /Type /XRef /Size 8 /W [1 3 1] /Root 1 0 R /Filter /FlateDecode /Length {len(table)} >>\n"
        "stream\n".encode() + table + b"\nendstream\nendobj\n"
        + f"startxref\n{debut_xref}\n%%EOF\n".encode()
    )
    assert b"JavaScript" not in sortie and b"/JS" not in sortie
    return bytes(sortie)


def structure_balisee() -> bytes:
    """PDF balisé (accessibilité) : `/S /P` désigne un paragraphe, pas une action."""
    return _assembler([
        b"<< /Type /Catalog /Pages 2 0 R /StructTreeRoot 4 0 R /MarkInfo << /Marked true >> >>",
        PAGES[1],
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Group << /S /Transparency /CS /DeviceRGB >> >>",
        b"<< /Type /StructTreeRoot /K 5 0 R >>",
        b"<< /S /P /P 4 0 R /Pg 3 0 R >>",
    ])


def javascript_orphelin() -> bytes:
    """Objet JavaScript non relié au document mais présent dans la table : analysé aussi."""
    return _assembler([
        b"<< /Type /Catalog /Pages 2 0 R >>",
        PAGES[1],
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >>",
        b"<< /S /JavaScript /JS (app.alert\\(1\\)) >>",
    ])
