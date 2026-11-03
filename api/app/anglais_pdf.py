"""Cahiers PKP Anglais : pictogrammes, lexique en contexte, écoutes en ligne par QR code, exercices.

Le cahier reste autosuffisant sur papier (cahier des charges V1.8) : chaque écoute en ligne a un script
de secours, lu par le bénévole, qui répond aux mêmes questions.
"""
import json
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.anglais_pictos import PICTOS, dessin, groupe

RESSOURCES = Path(__file__).resolve().parents[2] / "contenu" / "anglais" / "ressources-pedagogiques.json"
NAVY = colors.HexColor("#183153")
BLUE = colors.HexColor("#2666A2")
PALE = colors.HexColor("#EAF3FA")
TEAL = colors.HexColor("#087D75")
LARGEUR = 17.7 * cm

# Couleur de bandeau et icône de chaque rubrique.
RUBRIQUES = {
    "curious": (colors.HexColor("#2666A2"), "ampoule"),
    "words": (colors.HexColor("#087D75"), "livre"),
    "grammar": (colors.HexColor("#8E6CC9"), "crayon"),
    "listen": (colors.HexColor("#D9534F"), "casque"),
    "model": (colors.HexColor("#2666A2"), "bulles"),
    "practise": (colors.HexColor("#087D75"), "crayon"),
    "challenge": (colors.HexColor("#E67E22"), "etoile"),
    "mission": (colors.HexColor("#D9534F"), "cible"),
    "can_do": (colors.HexColor("#2E9E5B"), "valide"),
    "remember": (colors.HexColor("#8E6CC9"), "ampoule"),
    "further": (colors.HexColor("#2666A2"), "globe"),
}
CARTES = ["#DCEFFC", "#DFF4E9", "#FFF0D5", "#F4E3F5"]
CHAMPS = ("hook", "visual", "vocab", "grammar", "pronunciation", "did_you_know", "model", "listening",
          "go_further", "practice", "practice_answers", "starters", "mission", "can_do", "memory")
CHAMPS_ECOUTE = ("title", "source", "level", "media", "url", "verified_on", "questions", "answers", "fallback")


def charger_ressources() -> dict:
    return json.loads(RESSOURCES.read_text(encoding="utf-8"))


def verifier_ressources(r: dict) -> list[str]:
    """Erreurs de structure d'une fiche de ressources ; vide si le cahier peut être produit."""
    erreurs = [f"Champ manquant : {c}" for c in CHAMPS if c not in r]
    if erreurs:
        return erreurs
    if len(r["visual"]) != 4 or any(v.get("picto") not in PICTOS for v in r["visual"]):
        erreurs.append("Quatre visuels avec un pictogramme connu sont attendus")
    ecoute = r["listening"]
    erreurs += [f"Écoute : champ manquant {c}" for c in CHAMPS_ECOUTE if c not in ecoute]
    if not erreurs and len(ecoute["questions"]) != len(ecoute["answers"]):
        erreurs.append("Écoute : une réponse par question")
    for res in [ecoute, *r["go_further"]]:
        if res.get("url") and not res["url"].startswith("https://"):
            erreurs.append(f"Lien non sécurisé : {res['url']}")
        if res.get("url") and not res.get("verified_on"):
            erreurs.append(f"Lien sans date de vérification : {res['url']}")
    if len(r["practice"]) != len(r["practice_answers"]):
        erreurs.append("Exercices : une réponse par exercice")
    return erreurs


def _qr(url: str, taille: float) -> Drawing:
    code = QrCodeWidget(url, barBorder=1)
    x0, y0, x1, y1 = code.getBounds()
    d = Drawing(taille, taille, transform=[taille / (x1 - x0), 0, 0, taille / (y1 - y0), 0, 0])
    d.add(code)
    return d


def _case(taille=11):
    d = Drawing(taille, taille)
    d.add(Rect(0, 0, taille, taille, rx=2, ry=2, fillColor=colors.white, strokeColor=NAVY, strokeWidth=1))
    return d


def produire_pdf(seance: dict, public: str) -> bytes:
    if public not in ("eleve", "animateur"):
        raise ValueError("Public inconnu")
    code = seance.get("code", "")
    ressources = charger_ressources()
    if code not in ressources:
        raise ValueError("Ressources pédagogiques manquantes pour " + code)
    r = ressources[code]
    erreurs = verifier_ressources(r)
    if erreurs:
        raise ValueError("Pack incomplet : " + "; ".join(erreurs))

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=(21 * cm, 29.7 * cm), leftMargin=1.65 * cm, rightMargin=1.65 * cm,
                            topMargin=1.3 * cm, bottomMargin=1.45 * cm,
                            title=f"PKP Anglais {code} - {seance['titre']}", author="PKP Anglais")
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="PKPTitle", fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=NAVY, spaceAfter=5))
    styles.add(ParagraphStyle(name="PKPBand", fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=colors.white))
    styles.add(ParagraphStyle(name="PKPHook", fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=colors.white))
    styles.add(ParagraphStyle(name="PKPText", fontName="Helvetica", fontSize=9.5, leading=12.5, spaceAfter=3))
    styles.add(ParagraphStyle(name="PKPSmall", fontName="Helvetica", fontSize=8, leading=10.5, spaceAfter=2))
    styles.add(ParagraphStyle(name="PKPBubble", fontName="Helvetica", fontSize=9.5, leading=12))
    styles.add(ParagraphStyle(name="PKPCell", fontName="Helvetica", fontSize=8.5, leading=10.5))
    story = []
    numero = [0]

    def html(s):
        return escape(str(s)).replace("\n", "<br/>")

    def para(s, style="PKPText"):
        return Paragraph(html(s), styles[style])

    def p(s, style="PKPText"):
        story.append(para(s, style))

    def space(n=8):
        story.append(Spacer(1, n))

    def lien(url, texte=None):
        return f'<a href={quoteattr(url)} color="#2666A2"><u>{escape(texte or url)}</u></a>'

    def bandeau(rubrique, titre, numerote=True):
        couleur, icone = RUBRIQUES[rubrique]
        if numerote:
            numero[0] += 1
            titre = f"{numero[0]}. {titre}"
        t = Table([[dessin(icone, 15), Paragraph(escape(titre), styles["PKPBand"])]], colWidths=[0.95 * cm, LARGEUR - 0.95 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), couleur), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (0, 0), 6), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        return t

    def section(rubrique, titre, *contenu, numerote=True):
        # Le bandeau ne reste jamais seul en bas de page.
        # Un KeepTogether imbriqué annonce une hauteur démesurée pour forcer sa propre coupure : on le déplie,
        # sinon la rubrique partait toujours à la page suivante en laissant une demi-page vide.
        premier = list(contenu[0]._content) if contenu and isinstance(contenu[0], KeepTogether) else list(contenu[:1])
        story.append(Spacer(1, 5))
        story.append(KeepTogether([bandeau(rubrique, titre, numerote), Spacer(1, 4), *premier]))
        story.extend(contenu[1:])

    def encadre(elements, fond, bord, titre=None, largeur=LARGEUR):
        lignes = [[Paragraph(f"<b>{escape(titre)}</b>", styles["PKPText"])]] if titre else []
        lignes += [[e if not isinstance(e, str) else para(e)] for e in elements]
        t = Table(lignes, colWidths=[largeur])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), fond), ("BOX", (0, 0), (-1, -1), 0.8, bord),
            ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        t.spaceAfter = 4
        return t

    def lignes(n=3):
        return [para("_" * 92, "PKPSmall") for _ in range(n)]

    def question(texte, n):
        # Une consigne n'est jamais séparée de ses lignes de réponse par un saut de page.
        return KeepTogether([para(texte), *lignes(n)])

    def bulles(texte):
        """Dialogue « Nom: réplique » en bulles alternées gauche / droite ; un texte suivi reste un encadré."""
        repliques = [ligne.split(":", 1) for ligne in texte.split("\n")]
        if len(repliques) < 2 or any(len(x) != 2 or len(x[0]) > 15 for x in repliques):
            return [encadre([texte], PALE, BLUE)]
        noms = list(dict.fromkeys(nom.strip() for nom, _ in repliques))
        elements = []
        for nom, replique in repliques:
            gauche = noms.index(nom.strip()) % 2 == 0
            bulle = Table([[Paragraph(f"<b>{escape(nom.strip())}:</b>  {escape(replique.strip())}", styles["PKPBubble"])]],
                          colWidths=[LARGEUR * 0.78])
            bulle.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#DCEFFC" if gauche else "#FFF0D5")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#9DB7CC")),
                ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            bulle.hAlign = "LEFT" if gauche else "RIGHT"
            elements += [bulle, Spacer(1, 2)]
        return elements

    def ressource_en_ligne(res, consigne):
        media = {"audio": "Audio", "video": "Video", "text": "Text"}.get(res.get("media"), "Online")
        texte = [
            Paragraph(f"<b>{escape(res['title'])}</b>", styles["PKPText"]),
            Paragraph(f"{escape(media)} · {escape(res.get('level', ''))} · {escape(res.get('source', ''))}", styles["PKPSmall"]),
            Paragraph(consigne, styles["PKPSmall"]),
            Paragraph(lien(res["url"]), styles["PKPSmall"]),
        ]
        t = Table([[_qr(res["url"], 2.1 * cm), texte]], colWidths=[2.6 * cm, LARGEUR - 2.6 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF5F4")), ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#E8A49C")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        t.spaceAfter = 7
        return t

    # --- Couverture -----------------------------------------------------------------------
    p("PKP ANGLAIS  /  " + seance["niveau"].upper() + "  /  " + ("CAHIER ÉLÈVE" if public == "eleve" else "GUIDE ANIMATEUR"), "PKPSmall")
    p(seance["titre"], "PKPTitle")
    accroche = Table([[Paragraph(escape(r["hook"]), styles["PKPHook"])],
                      [Paragraph(f"90 MIN  ·  {escape(seance['objectif'])}", ParagraphStyle(
                          "PKPHookSub", parent=styles["PKPSmall"], textColor=colors.white, fontSize=9.5, leading=13))]],
                     colWidths=[LARGEUR])
    accroche.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NAVY), ("LEFTPADDING", (0, 0), (-1, -1), 14),
                                  ("TOPPADDING", (0, 0), (0, 0), 10), ("BOTTOMPADDING", (0, -1), (-1, -1), 10)]))
    story.append(accroche)

    cartes = Drawing(LARGEUR, 74)
    largeur_carte = (LARGEUR - 3 * 10) / 4
    for i, visuel in enumerate(r["visual"]):
        x = i * (largeur_carte + 10)
        cartes.add(Rect(x, 2, largeur_carte, 70, rx=10, ry=10, fillColor=colors.HexColor(CARTES[i]),
                        strokeColor=colors.HexColor("#C6D3DF")))
        cartes.add(groupe(visuel["picto"], 40, x + (largeur_carte - 40) / 2, 26))
        cartes.add(String(x + largeur_carte / 2, 11, visuel["label"], fontName="Helvetica-Bold", fontSize=10,
                          textAnchor="middle", fillColor=NAVY))
    section("curious", "GET CURIOUS - Choose your idea", cartes, Spacer(1, 6),
            para("Which one interests you most? Explain your choice to a partner."), *lignes(1))

    cellules = [[Paragraph(f"<b>{t}</b>", styles["PKPCell"]) for t in ("English", "Français", "In a sentence")]]
    for mot in r["vocab"]:
        en, fr, *exemple = mot
        cellules.append([Paragraph(f"<b>{escape(en)}</b>", styles["PKPCell"]), para(fr, "PKPCell"),
                         Paragraph(f"<i>{escape(exemple[0])}</i>" if exemple else "", styles["PKPCell"])])
    tab = Table(cellules, colWidths=[4.2 * cm, 4.2 * cm, LARGEUR - 8.4 * cm], repeatRows=1, hAlign="LEFT")
    tab.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DFF4E9")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5FBF8")]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#D0E4DA")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    section("words", "WORD POWER - Learn and remember", tab,
            para("Memory challenge: cover the French column and recall at least five meanings.", "PKPSmall"),
            encadre([r["pronunciation"]], colors.HexColor("#F3EEFB"), colors.HexColor("#B9A5DE"), "Say it right!"))

    grammaire = r["grammar"]
    section("grammar", "GRAMMAR FOCUS - " + grammaire["title"],
            encadre([grammaire["rule"], *("→  " + e for e in grammaire["examples"])],
                    colors.HexColor("#FFF8E1"), colors.HexColor("#E8C547")))

    ecoute = r["listening"]
    consigne = ("Scan the QR code or open the link. Listen or watch twice, then answer. "
                "No internet? The volunteer reads the script.")
    section("listen", "LISTEN AND WATCH", ressource_en_ligne(ecoute, consigne),
            *[question(f"{i}. {q}", 1) for i, q in enumerate(ecoute["questions"], 1)])

    section("model", "READ THE MODEL", *bulles(r["model"]),
            para("Highlight useful expressions. Find one sentence you can reuse."), *lignes(1))
    story.append(Spacer(1, 6))
    story.append(KeepTogether(encadre([r["did_you_know"]], colors.HexColor("#FFF0D5"), colors.HexColor("#F2994A"), "Did you know?")))

    section("practise", "PRACTISE - Try it yourself",
            *[question(f"{i}. {q}", 2) for i, q in enumerate(r["practice"], 1)])

    pistes = []
    for f in seance["fiches"]:
        piste = [Paragraph(f"<b>Track {escape(f['parcours'])}</b>", styles["PKPText"]), para(f["enonce"])]
        if f["parcours"] == "A":
            piste.append(encadre(["  /  ".join(r["starters"])], colors.HexColor("#EAF3FA"), BLUE, "Need help? Start with:"))
        pistes.append(KeepTogether(piste + lignes(2)))
    section("challenge", "CHOOSE YOUR CHALLENGE - A / B / C", *pistes)
    section("mission", "FINAL MISSION", encadre([r["mission"]], PALE, BLUE), *lignes(3))

    grille = [[Paragraph("<b>I can...</b>", styles["PKPCell"])] +
              [Paragraph(f"<b>{t}</b>", styles["PKPCell"]) for t in ("Not yet", "Almost", "Yes!")]]
    grille += [[para(c, "PKPCell"), _case(), _case(), _case()] for c in r["can_do"]]
    tab = Table(grille, colWidths=[LARGEUR - 6 * cm, 2 * cm, 2 * cm, 2 * cm])
    tab.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DFF4E9")), ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#D0E4DA")),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    section("can_do", "CHECK YOURSELF - I can...", tab)
    section("remember", "REMEMBER FOR NEXT TIME", para(r["memory"]), *lignes(1))
    if r["go_further"]:
        section("further", "GO FURTHER AT HOME", *[
            x for res in r["go_further"] for x in (ressource_en_ligne(res, escape(res["task"])), Spacer(1, 5))
        ], numerote=False)

    if public == "animateur":
        story.append(PageBreak())
        p("GUIDE ANIMATEUR - RÉSERVÉ AUX ADULTES", "PKPTitle")
        section("model", "Timing: 90 minutes", *[
            x for e in seance["etapes"] for x in (
                Paragraph(f"<b>{escape(e['titre'])}</b> - {e['duree_minutes']} min", styles["PKPText"]),
                para(e.get("consigne_animateur", e.get("consigne", "")), "PKPSmall"))
        ], numerote=False)
        section("listen", "Listening: before class", Paragraph(
            f"Open and test the resource before the session: {lien(ecoute['url'])} "
            f"(checked on {escape(ecoute['verified_on'])}). Plan a phone or computer with sound.", styles["PKPText"]),
            Paragraph("<b>No internet? Read this backup script twice. It answers the same questions.</b>", styles["PKPText"]),
            *bulles(ecoute["fallback"]),
            *[para(f"{i}. {a}") for i, a in enumerate(ecoute["answers"], 1)], numerote=False)
        section("practise", "Practice: suggested answers", *[para(f"{i}. {a}") for i, a in enumerate(r["practice_answers"], 1)],
                numerote=False)
        section("challenge", "Tracks: correction guidance",
                *[para(f["parcours"] + ": " + f.get("corrige", "Réponse ouverte")) for f in seance["fiches"]], numerote=False)
        section("can_do", "Observation: quick grid",
                para("For each student: task / organisation / language / interaction: 1-4 or NO (not observed)."), numerote=False)
        section("remember", "Validation",
                para("BROUILLON - Validation par un professeur d'anglais obligatoire avant diffusion au bénévole. "
                     "Vérifier aussi que chaque lien fonctionne encore."), numerote=False)

    def footer(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#CAD9E5"))
        canvas.line(1.65 * cm, 1.35 * cm, 19.35 * cm, 1.35 * cm)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(NAVY)
        canvas.drawString(1.65 * cm, 1.05 * cm, "PKP ANGLAIS | " + code + " | Brouillon - validation professeur requise")
        canvas.drawRightString(19.35 * cm, 1.05 * cm, str(document.page))
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
