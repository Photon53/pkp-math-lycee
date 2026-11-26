"""Export PDF d'un dossier de français (#217), réservé aux adultes habilités.

Deux exports, produits à partir des mêmes vues que l'écran :
- « eleve » : `francais.vue_eleve` seulement, sans aucun corrigé ni support professeur (ARCH-4) ;
- « professeur » : la partie élève, puis les supports professeur et les corrigés rapprochés de chaque question.

Une version non validée porte la mention NON VALIDÉ sur chaque page, comme les cahiers d'anglais.
"""
# Issue #217 — Export PDF des dossiers de français (Claude)

import re
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer

from app import francais, permissions
from app.db import models

PUBLICS = ("eleve", "professeur")
NAVY = colors.HexColor("#183153")
ROUGE = colors.HexColor("#B42318")

_styles = getSampleStyleSheet()
TITRE = ParagraphStyle("titre-fr", parent=_styles["Title"], textColor=NAVY, fontSize=18, leading=22)
H2 = ParagraphStyle("h2-fr", parent=_styles["Heading2"], textColor=NAVY, spaceBefore=10)
H3 = ParagraphStyle("h3-fr", parent=_styles["Heading3"], textColor=NAVY, spaceBefore=6)
CORPS = ParagraphStyle("corps-fr", parent=_styles["BodyText"], fontSize=10.5, leading=14)
DOUX = ParagraphStyle("doux-fr", parent=CORPS, textColor=colors.HexColor("#555555"), fontSize=9)
LIGNE = ParagraphStyle("ligne-fr", parent=CORPS, leftIndent=0.9 * cm, firstLineIndent=-0.9 * cm)
ALERTE = ParagraphStyle("alerte-fr", parent=CORPS, textColor=ROUGE, fontName="Helvetica-Bold")


def _inline(texte: str) -> str:
    """Markdown en ligne minimal (gras, italique) ; tout le reste est échappé."""
    t = escape(texte)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", t)
    return t


def _paragraphes(markdown: str, style: ParagraphStyle = CORPS) -> list[Paragraph]:
    blocs = [b.strip() for b in re.split(r"\n\s*\n", markdown or "") if b.strip()]
    return [Paragraph(_inline(b).replace("\n", "<br/>"), style) for b in blocs]


def _partie_eleve(e: dict) -> list:
    flux: list = []
    for p in e["presentation"]:
        flux += _paragraphes(p, DOUX)
    if e["objectifs"]:
        flux.append(Paragraph("Objectifs", H2))
        flux += [Paragraph("• " + _inline(o), CORPS) for o in e["objectifs"]]
    flux.append(Paragraph("Leçon", H2))
    for s in e["lecon"]:
        flux.append(Paragraph(_inline(s["titre"]), H3))
        flux += _paragraphes(s["markdown"])
    for t in e["textes"]:
        flux.append(Paragraph(f"{escape(t['code'])} — {_inline(t['titre'])}", H2))
        flux += [Paragraph(f"{i}&nbsp;&nbsp;{_inline(ligne)}", LIGNE) for i, ligne in enumerate(t["lignes"], 1)]
        if t.get("mention"):
            flux += _paragraphes(t["mention"], DOUX)
    flux.append(Paragraph("Questions", H2))
    for c in e["consignes_questions"]:
        flux += _paragraphes(c, DOUX)
    for q in e["questions"]:
        bloc = [Paragraph(f"<b>{escape(q['code'])}.</b> {_inline(q['consigne'])}", CORPS)]
        if q.get("coup_de_pouce"):
            bloc.append(Paragraph("Coup de pouce : " + _inline(q["coup_de_pouce"]), DOUX))
        bloc.append(Spacer(1, 1.6 * cm))  # place pour la réponse rédigée
        flux.append(KeepTogether(bloc))
    if e.get("quiz"):  # #217 : questions et choix seulement, jamais la bonne réponse (ARCH-4)
        flux.append(Paragraph("Quiz", H2))
        for i, q in enumerate(e["quiz"], 1):
            choix = "   ".join(f"{chr(64 + j)}) {_inline(c)}" for j, c in enumerate(q["choix"], 1))
            flux.append(KeepTogether([Paragraph(f"{i}. {_inline(q['question'])}", CORPS), Paragraph(choix, DOUX)]))
    if e.get("je_verifie"):
        flux.append(Paragraph("Je vérifie", H2))
        flux += _paragraphes(e["je_verifie"])
    return flux


def _partie_professeur(p: dict) -> list:
    flux: list = [PageBreak(), Paragraph("Supports professeur — réservés aux adultes", H2)]
    for ligne in p.get("presentation", []):
        flux += _paragraphes(ligne, DOUX)
    if d := p.get("deroulement"):
        flux.append(Paragraph(_inline(d["titre"]), H3))
        flux += [Paragraph(f"<b>{_inline(e['duree'])}</b> — {_inline(e['activite'])} ({_inline(e['observation'])})", CORPS)
                 for e in d.get("etapes", [])]
        for a in d.get("adaptations", []):
            flux += _paragraphes(a)
    flux.append(Paragraph("Corrigés expliqués", H3))
    if p.get("principes_correction"):
        flux += _paragraphes(p["principes_correction"])
    for q in p["questions"]:
        bloc = [Paragraph(f"<b>{escape(q['code'])}.</b> {_inline(q['consigne'])}", CORPS)]
        if q["corrige"].get("intitule"):
            bloc.append(Paragraph(_inline(q["corrige"]["intitule"]), DOUX))
        for para in q["corrige"]["paragraphes"]:
            bloc += _paragraphes(para)
        flux.append(KeepTogether(bloc))
    if p.get("quiz"):  # #217 : réponses du quiz, supports professeur seulement
        flux.append(Paragraph("Quiz : réponses", H3))
        for i, q in enumerate(p["quiz"], 1):
            bonne = f"{chr(65 + q['reponse'])}) {_inline(q['choix'][q['reponse']])}"
            flux.append(Paragraph(f"{i}. {bonne} — {_inline(q['explication'])}", CORPS))
    if g := p.get("grille"):
        flux.append(Paragraph(_inline(g["titre"]), H3))
        flux += [Paragraph(f"<b>{_inline(c['critere'])}</b> ({_inline(c['questions'])}) : {_inline(c['indice'])}", CORPS)
                 for c in g.get("criteres", [])]
        for c in g.get("consignes", []):
            flux += _paragraphes(c, DOUX)
    if p.get("controle_avant_utilisation"):
        flux.append(Paragraph("Contrôle avant utilisation", H3))
        flux += [Paragraph("• " + _inline(c), CORPS) for c in p["controle_avant_utilisation"]]
    for r in p.get("remarques", []):
        flux += _paragraphes(r, DOUX)
    if p.get("retour_seance"):
        flux.append(Paragraph("Retour de séance", H3))
        flux += _paragraphes(p["retour_seance"])
    return flux


def produire_pdf(dossier: models.DossierFrancais, version: models.DossierFrancaisVersion, public: str) -> bytes:
    if public not in PUBLICS:
        raise ValueError(f"export inconnu : {public}")
    validee = version.statut == "valide"
    mention = "" if validee else "NON VALIDÉ — "
    pied = f"{mention}{dossier.code} v{version.numero} · {'Élève' if public == 'eleve' else 'Professeur — corrigés'}"

    def _page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica-Bold" if not validee else "Helvetica", 8)
        canvas.setFillColor(ROUGE if not validee else colors.grey)
        canvas.drawString(1.5 * cm, 1 * cm, pied)
        canvas.drawRightString(19.5 * cm, 1 * cm, f"{doc.page}")
        canvas.restoreState()

    flux: list = [
        Paragraph(_inline(dossier.titre), TITRE),
        Paragraph(f"{escape(dossier.code)} · {escape(permissions.LIBELLES.get(dossier.domaine_code, dossier.domaine_code))} · {escape(dossier.niveau)} · "
                  f"version {version.numero}", DOUX),
    ]
    if not validee:
        flux.append(Paragraph("NON VALIDÉ : cette version n'a pas été validée ; elle n'est servie à aucun élève.", ALERTE))
    flux.append(Spacer(1, 0.3 * cm))
    flux += _partie_eleve(francais.vue_eleve(version))
    if public == "professeur":
        flux += _partie_professeur(francais.vue_professeur(version))
    tampon = BytesIO()
    doc = SimpleDocTemplate(tampon, title=f"{dossier.code} — {dossier.titre}", author="PKP Éducation",
                            leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.5 * cm, bottomMargin=1.8 * cm)
    doc.build(flux, onFirstPage=_page, onLaterPages=_page)
    return tampon.getvalue()

