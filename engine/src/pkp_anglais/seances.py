"""Contrats de séances collectives de 90 minutes pour 4e et 3e.

Les packs renvoyés sont des structures de données, pas encore des fichiers PDF.
"""
from dataclasses import dataclass
from typing import Literal

Parcours = Literal["A", "B", "C"]
Niveau = Literal["4e", "3e"]


@dataclass(frozen=True)
class Etape:
    titre: str
    duree_minutes: int
    consigne_eleve: str
    consigne_animateur: str


@dataclass(frozen=True)
class Fiche:
    parcours: Parcours
    enonce: str
    corrige: str


@dataclass(frozen=True)
class Seance:
    code: str
    niveau: Niveau
    titre: str
    objectif: str
    etapes: tuple[Etape, ...]
    fiches: tuple[Fiche, ...]


def verifier_seance(seance: Seance) -> list[str]:
    """Renvoie toutes les erreurs de structure avant publication."""
    erreurs: list[str] = []
    if seance.niveau not in ("4e", "3e"):
        erreurs.append("Niveau non pris en charge par le MVP.")
    if not seance.code.strip() or not seance.titre.strip() or not seance.objectif.strip():
        erreurs.append("Code, titre et objectif sont obligatoires.")
    if not seance.etapes:
        erreurs.append("Au moins une étape est requise.")
    if any(e.duree_minutes <= 0 for e in seance.etapes):
        erreurs.append("Chaque étape doit avoir une durée strictement positive.")
    if sum(e.duree_minutes for e in seance.etapes) != 90:
        erreurs.append("La durée totale doit être de 90 minutes.")
    if any(not e.titre.strip() or not e.consigne_eleve.strip() or not e.consigne_animateur.strip() for e in seance.etapes):
        erreurs.append("Chaque étape doit posséder un titre et ses deux consignes.")
    parcours = [f.parcours for f in seance.fiches]
    if sorted(parcours) != ["A", "B", "C"]:
        erreurs.append("Il faut exactement une fiche pour chacun des parcours A, B et C.")
    if any(not f.enonce.strip() or not f.corrige.strip() for f in seance.fiches):
        erreurs.append("Les énoncés et corrigés ne peuvent pas être vides.")
    return erreurs


def _verifier_ou_refuser(seance: Seance) -> None:
    erreurs = verifier_seance(seance)
    if erreurs:
        raise ValueError("; ".join(erreurs))


def generer_pack_eleve(seance: Seance) -> dict:
    """Construit uniquement les informations destinées aux élèves.

    Les consignes animateur et les corrigés sont exclus par construction.
    """
    _verifier_ou_refuser(seance)
    return {
        "code": seance.code,
        "niveau": seance.niveau,
        "titre": seance.titre,
        "objectif": seance.objectif,
        "etapes": [
            {"titre": e.titre, "duree_minutes": e.duree_minutes, "consigne": e.consigne_eleve}
            for e in seance.etapes
        ],
        "fiches": [{"parcours": f.parcours, "enonce": f.enonce} for f in seance.fiches],
    }


def generer_pack_animateur(seance: Seance) -> dict:
    """Construit le déroulé et les corrigés réservés à l'animateur."""
    _verifier_ou_refuser(seance)
    return {
        **generer_pack_eleve(seance),
        "etapes": [
            {"titre": e.titre, "duree_minutes": e.duree_minutes,
             "consigne_eleve": e.consigne_eleve, "consigne_animateur": e.consigne_animateur}
            for e in seance.etapes
        ],
        "fiches": [
            {"parcours": f.parcours, "enonce": f.enonce, "corrige": f.corrige}
            for f in seance.fiches
        ],
    }
