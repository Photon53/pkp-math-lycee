"""PDF imprimables PKP Anglais : rendu serveur, sans contenu HTML."""
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether
from xml.sax.saxutils import escape


def produire_pdf(seance: dict, public: str) -> bytes:
    """Construit un PDF élève ou animateur à partir d'un pack validé."""
    if public not in ("eleve", "animateur"):
        raise ValueError("Public inconnu")
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=(21 * cm, 29.7 * cm), rightMargin=1.8 * cm,
                            leftMargin=1.8 * cm, topMargin=1.7 * cm, bottomMargin=1.7 * cm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="PKPSection", parent=styles["Heading2"], textColor=colors.HexColor("#17365D"), spaceBefore=13))
    styles.add(ParagraphStyle(name="PKPBody", parent=styles["BodyText"], leading=15, spaceAfter=7, alignment=TA_LEFT))
    story = []
    def para(texte, style="PKPBody"):
        story.append(Paragraph(escape(str(texte)).replace("\\n", "<br/>"), styles[style]))
    para(f"PKP Anglais - {seance['niveau']} - {public.capitalize()}", "Heading1")
    para(seance["titre"], "Heading2")
    para(f"Objectif : {seance['objectif']}")
    para("Durée : 90 minutes")
    for e in seance["etapes"]:
        para(f"{e['titre']} - {e['duree_minutes']} min", "PKPSection")
        para(e.get("consigne_eleve", e.get("consigne", "")))
        if public == "animateur":
            para("Animation : " + e["consigne_animateur"])
    for f in seance["fiches"]:
        para("Parcours " + f["parcours"], "PKPSection")
        para(f["enonce"])
        if public == "animateur":
            para("Corrigé / indications : " + f["corrige"])
    doc.build(story)
    return buf.getvalue()
