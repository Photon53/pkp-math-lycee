"""Tests du rendu PDF sans connexion ni base de données."""
from app.anglais_pdf import produire_pdf


def test_pdf_eleve_et_animateur():
    base = {
        "niveau": "4e", "titre": "Daily life", "objectif": "Speak about routines",
        "etapes": [{"titre": "Warm-up", "duree_minutes": 90, "consigne": "Talk about routines"}],
        "fiches": [{"parcours": "A", "enonce": "I usually read"}],
    }
    pdf_eleve = produire_pdf(base, "eleve")
    assert pdf_eleve.startswith(b"%PDF")
    assert len(pdf_eleve) > 500

    animateur = {
        **base,
        "etapes": [{"titre": "Warm-up", "duree_minutes": 90,
                    "consigne_eleve": "Talk about routines", "consigne_animateur": "Ask questions"}],
        "fiches": [{"parcours": "A", "enonce": "I usually read", "corrige": "Example answer"}],
    }
    pdf_animateur = produire_pdf(animateur, "animateur")
    assert pdf_animateur.startswith(b"%PDF")


def test_public_inconnu_refuse():
    import pytest
    with pytest.raises(ValueError):
        produire_pdf({}, "inconnu")
