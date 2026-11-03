"""Chargement et contrôle des contenus pilotes anglais (sans API ni BDD)."""
import json
from pathlib import Path

from .seances import Etape, Fiche, Seance, verifier_seance


def charger_seance(chemin: str | Path) -> Seance:
    return seance_depuis_dict(json.loads(Path(chemin).read_text(encoding="utf-8")))


def seance_depuis_dict(data: dict) -> Seance:
    """Séance au format des fichiers JSON (aussi stockée telle quelle en base) ; refusée si incomplète."""
    seance = Seance(
        code=data["code"],
        niveau=data["level"],
        titre=data["title"],
        objectif=data["objective"],
        etapes=tuple(
            Etape(e["title"], e["duration_minutes"], e["student_instruction"], e["facilitator_instruction"])
            for e in data["steps"]
        ),
        fiches=tuple(
            Fiche(f["track"], f["student_content"], f["facilitator_correction"])
            for f in data["sheets"]
        ),
    )
    erreurs = verifier_seance(seance)
    if erreurs:
        raise ValueError("; ".join(erreurs))
    return seance


def verifier_referentiel(chemin: str | Path) -> list[str]:
    data = json.loads(Path(chemin).read_text(encoding="utf-8"))
    erreurs = []
    if data.get("level") not in ("4e", "3e"):
        erreurs.append("Niveau inconnu")
    if not data.get("school_year") or not data.get("program"):
        erreurs.append("Version du programme manquante")
    codes = [o.get("code") for o in data.get("objectives", [])]
    if len(codes) != 10 or len(set(codes)) != 10:
        erreurs.append("Le référentiel pilote doit avoir dix objectifs distincts")
    for obj in data.get("objectives", []):
        if not all(obj.get(k) for k in ("code", "activity", "observable", "theme")):
            erreurs.append("Objectif incomplet")
    return erreurs
