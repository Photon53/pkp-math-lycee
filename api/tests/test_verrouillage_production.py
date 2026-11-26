# Issue #116 — Verrouillage du mode production (Claude)
"""En production : ni démonstration, ni documentation interactive, ni origine non chiffrée ; la base est contrôlée
avant la mise en service (`python -m app.production verifier`)."""

import importlib

import pytest
from fastapi.testclient import TestClient

from app import production
from app.db import models
from app.config import settings
from app.db.seed import DemoInterdite, charger_demo
from tests.test_production import PROD_VALIDE, config

DOMAINE_FR = "francais-college"


@pytest.fixture
def en_production(monkeypatch):
    monkeypatch.setattr(settings, "environnement", "production")


def test_origine_non_chiffree_refusee():
    with pytest.raises(ValueError, match="https://"):
        config(**{**PROD_VALIDE, "cors_origins": ["http://maths.lycee.fr"]})


def test_la_demo_ne_se_charge_pas_en_production(en_production, session):
    with pytest.raises(DemoInterdite):
        charger_demo(session)
    assert production.problemes(session) == []  # rien n'a été écrit


def test_base_vierge_prete_pour_la_production(session):
    assert production.problemes(session) == []


def test_comptes_de_demonstration_detectes(client, fabrique):
    with fabrique() as s:
        trouves = production.problemes(s)
    assert len(trouves) == len(production.EMAILS_DEMO)
    assert all("démonstration" in t for t in trouves)


def test_commande_verifier_echoue_sur_une_base_de_demo(client, fabrique, monkeypatch, capsys):
    import app.db.session as module_session

    monkeypatch.setattr(module_session, "SessionLocale", fabrique)
    monkeypatch.setattr("sys.argv", ["app.production", "verifier"])
    with pytest.raises(SystemExit) as fin:
        production.main()
    assert fin.value.code == 1 and "REFUS" in capsys.readouterr().err


def test_documentation_interactive_fermee_en_production(en_production):
    import app.main as module_main

    try:
        prod = importlib.reload(module_main).app
        with TestClient(prod) as c:
            for chemin in ("/docs", "/openapi.json", "/redoc"):
                assert c.get(chemin).status_code == 404, chemin
            assert c.get("/health").status_code == 200
    finally:
        settings.environnement = "dev"
        importlib.reload(module_main)


def test_classe_d_un_domaine_ferme_hors_pilote_signalee(session):
    """SEC-D6 (#176) : une classe active d'un domaine fermé perd l'accès au contenu si elle n'est pas pilote."""
    prof = models.Enseignant(email="prof@lycee.test", nom="Prof", mot_de_passe_hash="x")
    session.add(prof)
    session.flush()
    domaine = session.get(models.DomainePedagogique, DOMAINE_FR)
    domaine.actif, domaine.public = True, False
    classe = models.Classe(code="FR5A", niveau=models.Niveau.CINQUIEME, enseignant_id=prof.id,
                           domaine_code=DOMAINE_FR)
    session.add(classe)
    session.commit()
    trouves = production.avertissements(session)
    assert len(trouves) == 1 and DOMAINE_FR in trouves[0] and "FR5A" not in trouves[0]

    session.add(models.ClassePilote(classe_id=classe.id, motif="Pilote"))
    session.commit()
    assert production.avertissements(session) == []
    assert production.problemes(session) == []  # un avertissement ne bloque pas la préparation
