"""Contrôles de génération des quatre cahiers PKP Anglais."""
from pathlib import Path
import pytest
from pkp_anglais.contenu import charger_seance
from pkp_anglais.seances import generer_pack_eleve, generer_pack_animateur
from app.anglais_pdf import produire_pdf

ROOT = Path(__file__).resolve().parents[2] / "contenu" / "anglais" / "seances"
CASES = [
    ("4e", "4e-01-pilote.json"), ("4e", "4e-02-pilote.json"),
    ("3e", "3e-01-pilote.json"), ("3e", "3e-02-pilote.json"),
]

@pytest.mark.parametrize("niveau,filename", CASES)
def test_cahiers_complets(niveau, filename):
    seance = charger_seance(ROOT / niveau / filename)
    for public, pack in [
        ("eleve", generer_pack_eleve(seance)),
        ("animateur", generer_pack_animateur(seance)),
    ]:
        pdf = produire_pdf(pack, public)
        assert pdf.startswith(b"%PDF")
        assert len(pdf) > 3500

def test_public_inconnu_refuse():
    with pytest.raises(ValueError):
        produire_pdf({}, "inconnu")

def test_ressources_absentes_refusees():
    with pytest.raises(ValueError, match="Ressources pédagogiques"):
        produire_pdf({"code": "MISSING"}, "eleve")
