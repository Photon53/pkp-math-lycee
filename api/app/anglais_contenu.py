"""Séances PKP Anglais en base : import depuis le dépôt, quiz corrigés et circuit de validation.

Le dépôt (contenu/anglais) fournit la première version de chaque séance ; ensuite tout se fait
dans l'application : édition par un administrateur, validation par un référent (CDC anglais V1.8).
"""
import json
from datetime import UTC, datetime
from pathlib import Path

from pkp_anglais.contenu import seance_depuis_dict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.anglais_pdf import charger_ressources, verifier_ressources
from app.anglais_pictos import image_svg
from app import permissions
from app.db import models

CONTENU = Path(__file__).resolve().parents[2] / "contenu" / "anglais"
# Un objectif du référentiel = une séance. Progression complète en 4e et 3e (10 chacune) ;
# 6e, 5e et lycée en cours (les premières séances, dans l'ordre du référentiel).
FICHIERS = {
    **{f"6E-{n:02d}": f"6e/6e-{n:02d}.json" for n in range(1, 3)},
    **{f"5E-{n:02d}": f"5e/5e-{n:02d}.json" for n in range(1, 3)},
    **{f"4E-{n:02d}": f"4e/4e-{n:02d}{'-pilote' if n <= 2 else ''}.json" for n in range(1, 11)},
    **{f"3E-{n:02d}": f"3e/3e-{n:02d}{'-pilote' if n <= 2 else ''}.json" for n in range(1, 11)},
    **{f"2NDE-{n:02d}": f"2nde/2nde-{n:02d}.json" for n in range(1, 3)},
    **{f"1RE-{n:02d}": f"1re/1re-{n:02d}.json" for n in range(1, 3)},
    **{f"TLE-{n:02d}": f"Tle/tle-{n:02d}.json" for n in range(1, 3)},
}
NIVEAU_DU_CODE = {n.upper(): n for n in models.NIVEAUX_ANGLAIS}  # "6E" -> "6e", "2NDE" -> "2nde"
NIVEAUX_I_CAN = ("non_observe", "avec_aide", "en_cours", "autonome")
QUESTIONS_VOCABULAIRE = 6


def _ordre(code: str) -> tuple[int, str]:
    """6e, 5e, 4e, 3e puis lycée, comme le programme."""
    return models.NIVEAUX_ANGLAIS.index(NIVEAU_DU_CODE[code.split("-")[0]]), code


def importer_seances(session: Session) -> int:
    """Ajoute les séances du dépôt absentes de la base, soumises à validation ; renvoie leur nombre.

    Une séance déjà en base n'est jamais écrasée : ses versions appartiennent à l'application.
    """
    presentes = set(session.scalars(select(models.SeanceAnglais.code)))
    manquantes = [c for c in FICHIERS if c not in presentes]
    if not manquantes:
        return 0
    cahiers = charger_ressources()
    quiz = json.loads((CONTENU / "quiz-grammaire.json").read_text(encoding="utf-8"))
    for code in manquantes:
        contenu = json.loads((CONTENU / "seances" / FICHIERS[code]).read_text(encoding="utf-8"))
        seance = models.SeanceAnglais(
            code=code, niveau=contenu["level"], domaine_code=permissions.domaine_anglais(contenu["level"]))
        seance.versions.append(models.SeanceAnglaisVersion(
            numero=1, contenu=contenu, cahier=cahiers[code], quiz=quiz.get(code, []), statut="soumis"))
        session.add(seance)
    session.commit()
    return len(manquantes)


def toutes(session: Session) -> list[models.SeanceAnglais]:
    importer_seances(session)
    return sorted(session.scalars(select(models.SeanceAnglais)), key=lambda s: _ordre(s.code))


def par_code(session: Session, code: str) -> models.SeanceAnglais | None:
    importer_seances(session)
    return session.scalar(select(models.SeanceAnglais).where(models.SeanceAnglais.code == code))


# --- Contrôle d'une version avant enregistrement -----------------------------

def verifier_quiz(quiz: list) -> list[str]:
    erreurs = []
    for i, q in enumerate(quiz, 1):
        choix = q.get("choix") if isinstance(q, dict) else None
        if not isinstance(choix, list) or not str(q.get("question", "")).strip() or len(choix) < 2:
            erreurs.append(f"QCM {i} : une question et au moins deux choix sont attendus")
        elif not isinstance(q.get("reponse"), int) or not 0 <= q["reponse"] < len(choix):
            erreurs.append(f"QCM {i} : la bonne réponse doit désigner un des choix")
        elif any(not str(c).strip() for c in choix):
            erreurs.append(f"QCM {i} : un choix est vide")
    return erreurs


def verifier_version(code: str, contenu: dict, cahier: dict, quiz: list) -> list[str]:
    """Toutes les erreurs qui empêcheraient de produire le cahier, le pack ou le quiz."""
    erreurs = []
    if contenu.get("code") != code:
        erreurs.append("Le code de la séance ne peut pas changer")
    try:
        seance_depuis_dict(contenu)
    except ValueError as exc:
        erreurs.append(str(exc))
    except (KeyError, TypeError):
        erreurs.append("Séance incomplète : étapes, fiches ou champs obligatoires manquants")
    try:
        erreurs += verifier_ressources(cahier)
    except (KeyError, TypeError, AttributeError):
        erreurs.append("Cahier incomplet")
    return erreurs + verifier_quiz(quiz)


# --- Quiz : QCM de grammaire rédigés + QCM de vocabulaire tirés du cahier -----

def quiz_complet(version: models.SeanceAnglaisVersion) -> list[dict]:
    """Questions avec leurs réponses ; le vocabulaire suit automatiquement les modifications du cahier.

    Les distracteurs sont choisis de façon déterministe : la correction retrouve exactement les mêmes choix.
    """
    vocab = [v for v in version.cahier.get("vocab", []) if len(v) >= 2]
    questions = []
    for i, (mot, sens, *_) in enumerate(vocab[:QUESTIONS_VOCABULAIRE]):
        autres = [vocab[(i + k) % len(vocab)][1] for k in (3, 7, 5, 1)]
        distracteurs = list(dict.fromkeys(a for a in autres if a != sens))[:2]
        if len(distracteurs) < 2:
            continue
        place = i % 3
        choix = distracteurs[:place] + [sens] + distracteurs[place:]
        questions.append({"question": f"« {mot} » means…", "choix": choix, "reponse": place,
                          "explication": f"{mot} = {sens}"})
    return questions + list(version.quiz)


def corriger(version: models.SeanceAnglaisVersion, reponses: list[int | None]) -> dict:
    quiz = quiz_complet(version)
    details = [
        {"juste": i < len(reponses) and reponses[i] == q["reponse"], "reponse": q["reponse"],
         "explication": q.get("explication", "")}
        for i, q in enumerate(quiz)
    ]
    cahier = version.cahier
    return {
        "score": sum(d["juste"] for d in details), "total": len(quiz), "details": details,
        # Réponses ouvertes : la correction est montrée après l'envoi, à comparer avec sa propre réponse.
        "practice_answers": cahier.get("practice_answers", []),
        "listening_answers": cahier.get("listening", {}).get("answers", []),
    }


# --- Ce que voit l'élève -----------------------------------------------------

def vue_eleve(version: models.SeanceAnglaisVersion) -> dict:
    """Cours, vocabulaire, écoute et exercices, sans consigne animateur ni corrigé."""
    contenu, cahier = version.contenu, version.cahier
    ecoute = {k: v for k, v in cahier["listening"].items() if k != "answers"}
    return {
        "code": contenu["code"], "niveau": contenu["level"], "titre": contenu["title"],
        "objectif": contenu["objective"],
        "etapes": [{"titre": e["title"], "duree_minutes": e["duration_minutes"], "consigne": e["student_instruction"]}
                   for e in contenu["steps"]],
        "fiches": [{"parcours": f["track"], "enonce": f["student_content"]} for f in contenu["sheets"]],
        "cahier": {
            **{k: v for k, v in cahier.items() if k not in ("practice_answers", "listening", "visual")},
            "listening": ecoute,
            "visual": [{**v, "image": image_svg(v["picto"])} for v in cahier["visual"]],
        },
        "quiz": [{"question": q["question"], "choix": q["choix"]} for q in quiz_complet(version)],
    }


# --- Circuit de validation ---------------------------------------------------

def enregistrer(seance: models.SeanceAnglais, auteur: models.Enseignant, contenu: dict, cahier: dict,
                quiz: list) -> models.SeanceAnglaisVersion:
    """Une version validée n'est jamais modifiée : on en crée une nouvelle, en brouillon.

    Un brouillon ou une version refusée est repris (statut remis à brouillon, motif effacé).
    Une version soumise repasse en brouillon : le référent ne valide pas un contenu qui bouge.
    """
    courante = seance.courante
    if courante.statut in ("valide", "archive"):
        courante = models.SeanceAnglaisVersion(numero=courante.numero + 1, contenu=contenu, cahier=cahier, quiz=quiz)
        seance.versions.append(courante)
    else:
        courante.contenu, courante.cahier, courante.quiz = contenu, cahier, quiz
    courante.statut, courante.auteur, courante.motif_refus = "brouillon", auteur, None
    courante.validateur, courante.decide_le = None, None
    return courante


def peut_decider(version: models.SeanceAnglaisVersion, qui: models.Enseignant) -> str | None:
    """Motif du refus d'agir, ou None : seul un contenu soumis se valide, jamais par son auteur."""
    if version.statut != "soumis":
        return "Seule une version soumise peut être validée ou refusée."
    if version.auteur_id == qui.id:
        return "Vous ne pouvez pas valider votre propre contenu : un autre référent doit le faire."
    return None


def valider(seance: models.SeanceAnglais, qui: models.Enseignant) -> None:
    for v in seance.versions[:-1]:
        if v.statut == "valide":
            v.statut = "archive"  # l'ancienne version validée est conservée, plus publiée
    courante = seance.courante
    courante.statut, courante.validateur, courante.decide_le = "valide", qui, datetime.now(UTC)


def refuser(seance: models.SeanceAnglais, qui: models.Enseignant, motif: str) -> None:
    courante = seance.courante
    courante.statut, courante.validateur, courante.decide_le = "refuse", qui, datetime.now(UTC)
    courante.motif_refus = motif


def resume(seance: models.SeanceAnglais) -> dict:
    """Ligne de catalogue : version courante, statut et version publiée."""
    c, p = seance.courante, seance.publiee
    return {
        "code": seance.code, "niveau": seance.niveau, "titre": c.contenu["title"], "objectif": c.contenu["objective"],
        "duree_minutes": 90, "version": c.numero, "statut": c.statut, "motif_refus": c.motif_refus,
        "auteur": c.auteur.nom if c.auteur else None, "validateur": c.validateur.nom if c.validateur else None,
        "version_publiee": p.numero if p else None,
    }


def historique(seance: models.SeanceAnglais) -> list[dict]:
    return [
        {"numero": v.numero, "statut": v.statut, "auteur": v.auteur.nom if v.auteur else "Import du dépôt",
         "cree_le": v.cree_le.isoformat() if v.cree_le else None,
         "validateur": v.validateur.nom if v.validateur else None,
         "decide_le": v.decide_le.isoformat() if v.decide_le else None, "motif_refus": v.motif_refus}
        for v in reversed(seance.versions)
    ]
