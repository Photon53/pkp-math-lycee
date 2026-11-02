"""Cahiers PKP Anglais : contenu concret, lexique, compréhension et exercices."""
from io import BytesIO
from pathlib import Path
import json
from urllib.parse import quote
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.graphics.shapes import Drawing, Rect, String

RESSOURCES = Path(__file__).resolve().parents[2] / "contenu" / "anglais" / "ressources-pedagogiques.json"
NAVY = colors.HexColor("#183153")
BLUE = colors.HexColor("#2666A2")
PALE = colors.HexColor("#EAF3FA")
TEAL = colors.HexColor("#087D75")


def produire_pdf(seance: dict, public: str) -> bytes:
    if public not in ("eleve", "animateur"):
        raise ValueError("Public inconnu")
    code = seance.get("code", "")
    ressources = json.loads(RESSOURCES.read_text(encoding="utf-8"))
    if code not in ressources:
        raise ValueError("Ressources pédagogiques manquantes pour " + code)
    r = ressources[code]
    if not r.get("vocab") or not r.get("model") or not r.get("practice") or not r.get("listening"):
        raise ValueError("Pack incomplet")
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=(21*cm, 29.7*cm), leftMargin=1.65*cm, rightMargin=1.65*cm,
                            topMargin=1.65*cm, bottomMargin=1.65*cm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="PKPTitle", fontName="Helvetica-Bold", fontSize=19, leading=24, textColor=NAVY, spaceAfter=10))
    styles.add(ParagraphStyle(name="PKPHeading", fontName="Helvetica-Bold", fontSize=13, leading=17, textColor=BLUE, spaceBefore=12, spaceAfter=7))
    styles.add(ParagraphStyle(name="PKPText", fontName="Helvetica", fontSize=10, leading=15, spaceAfter=7))
    styles.add(ParagraphStyle(name="PKPSmall", fontName="Helvetica", fontSize=8.5, leading=12, spaceAfter=5))
    story = []
    def p(s, style="PKPText"):
        story.append(Paragraph(escape(str(s)).replace("\n","<br/>"), styles[style]))
    def heading(s):
        p(s, "PKPHeading")
    def space(n=8):
        story.append(Spacer(1,n))
    def rulebox(text):
        t=Table([[Paragraph(escape(text),styles["PKPText"])]],colWidths=[17.4*cm])
        t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),PALE),("BOX",(0,0),(-1,-1),0.6,BLUE),("LEFTPADDING",(0,0),(-1,-1),11),("RIGHTPADDING",(0,0),(-1,-1),11),("TOPPADDING",(0,0),(-1,-1),9),("BOTTOMPADDING",(0,0),(-1,-1),8)]))
        story.append(t)
    def lined(n=3):
        for _ in range(n):
            p("________________________________________________________________________________","PKPSmall")
    p("PKP ANGLAIS  /  "+seance["niveau"].upper()+"  /  "+("CAHIER ELEVE" if public=="eleve" else "GUIDE ANIMATEUR"),"PKPSmall")
    p(seance["titre"],"PKPTitle")
    rulebox(r["hook"]+"  |  90 MIN  |  "+seance["objectif"])
    space(14)
    heading("1. GET CURIOUS - Choose your idea")
    d=Drawing(490,80)
    palette=["#DCEFFC","#DFF4E9","#FFF0D5","#F4E3F5"]
    for i,label in enumerate(r["visual"]):
        x=i*123
        d.add(Rect(x,4,117,70,rx=10,ry=10,fillColor=colors.HexColor(palette[i]),strokeColor=colors.HexColor("#C6D3DF")))
        d.add(String(x+58,39,label,fontName="Helvetica-Bold",fontSize=10,textAnchor="middle",fillColor=NAVY))
    story.append(d)
    p("Which one interests you most? Explain your choice to a partner.")
    lined(2)
    heading("2. WORD POWER - Learn and remember")
    cells=[[Paragraph("<b>English</b>",styles["PKPSmall"]),Paragraph("<b>Français</b>",styles["PKPSmall"])]]
    for en,fr in r["vocab"]:
        cells.append([Paragraph(escape(en),styles["PKPSmall"]),Paragraph(escape(fr),styles["PKPSmall"])])
    tab=Table(cells,colWidths=[8.7*cm,8.7*cm],repeatRows=1,hAlign="LEFT")
    tab.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),PALE),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#F7FAFD")]),("LINEBELOW",(0,0),(-1,-1),0.25,colors.HexColor("#D8E2E9")),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),10),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)]))
    story.append(tab)
    p("Memory challenge: cover the French column and recall at least five meanings.","PKPSmall")
    story.append(PageBreak())
    heading("3. LISTEN AND NOTICE")
    listen=r["listening"]
    p(listen["title"])
    if listen.get("url"):
        p("Listening resource: "+listen["url"],"PKPSmall")
        p("Open the link before class. If unavailable, the volunteer reads the backup script twice.","PKPSmall")
    else:
        p("Original PKP listening: the volunteer reads the script twice.","PKPSmall")
    for i,q in enumerate(listen["questions"],1):
        p(str(i)+". "+q)
        lined(1)
    heading("4. READ THE MODEL")
    rulebox(r["model"])
    p("Highlight useful expressions. Find one sentence you can reuse.")
    lined(2)
    heading("5. PRACTISE - Try it yourself")
    for i,q in enumerate(r["practice"],1):
        p(str(i)+". "+q)
        lined(2)
    story.append(PageBreak())
    heading("6. CHOOSE YOUR CHALLENGE - A / B / C")
    for f in seance["fiches"]:
        heading("Track "+f["parcours"])
        p(f["enonce"])
        lined(3)
    heading("7. FINAL MISSION")
    rulebox(r["mission"])
    lined(5)
    heading("8. REMEMBER FOR NEXT TIME")
    p(r["memory"])
    lined(3)
    if public=="animateur":
        story.append(PageBreak())
        p("GUIDE ANIMATEUR - RESERVE AUX ADULTES","PKPTitle")
        heading("Timing: 90 minutes")
        for e in seance["etapes"]:
            p(e["titre"]+" - "+str(e["duree_minutes"])+" min")
            p(e.get("consigne_animateur",e.get("consigne","")),"PKPSmall")
        heading("Listening: backup script and answers")
        p(listen["fallback"])
        for i,a in enumerate(listen["answers"],1):
            p(str(i)+". "+a)
        heading("Practice: suggested answers")
        for i,a in enumerate(r["practice_answers"],1):
            p(str(i)+". "+a)
        heading("Tracks: correction guidance")
        for f in seance["fiches"]:
            p(f["parcours"]+": "+f.get("corrige","Réponse ouverte"))
        heading("Observation: quick grid")
        p("For each student: task / organisation / language / interaction: 1-4 or NO (not observed).")
        heading("Validation")
        p("BROUILLON - Validation par un professeur d'anglais obligatoire avant diffusion au bénévole.")
    def footer(canvas,document):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#CAD9E5"))
        canvas.line(1.65*cm,1.35*cm,19.35*cm,1.35*cm)
        canvas.setFont("Helvetica",8)
        canvas.setFillColor(NAVY)
        canvas.drawString(1.65*cm,1.05*cm,"PKP ANGLAIS | "+code+" | Brouillon - validation professeur requise")
        canvas.drawRightString(19.35*cm,1.05*cm,str(document.page))
        canvas.restoreState()
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return buf.getvalue()
