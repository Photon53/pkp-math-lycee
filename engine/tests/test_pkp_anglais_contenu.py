from pathlib import Path

from pkp_anglais.contenu import charger_seance, verifier_referentiel
from pkp_anglais.seances import generer_pack_eleve, generer_pack_animateur

RACINE = Path(__file__).resolve().parents[2] / "contenu" / "anglais"


def test_referentiels_pilotes():
    for niveau in ("4e", "3e"):
        chemin = RACINE / "referentiels" / niveau / "2026-2027.json"
        assert verifier_referentiel(chemin) == []


def test_seances_pilotes_90_minutes_et_packs_separes():
    # Chaque fichier déposé est contrôlé, sans liste à tenir à jour.
    fichiers = sorted((RACINE / "seances").glob("*/*.json"))
    assert len(fichiers) >= 4
    for chemin in fichiers:
        seance = charger_seance(chemin)
        assert seance.niveau == chemin.parent.name
        assert sum(e.duree_minutes for e in seance.etapes) == 90
        assert len(seance.fiches) == 3
        eleve = generer_pack_eleve(seance)
        animateur = generer_pack_animateur(seance)
        assert all("corrige" not in fiche for fiche in eleve["fiches"])
        assert all("consigne_animateur" not in etape for etape in eleve["etapes"])
        assert all("corrige" in fiche for fiche in animateur["fiches"])
