import time
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app import limitation, security
from app.db.seed import CODES_DEMO, charger_demo
from app.db.session import creer_moteur, get_session
from app.main import app

RACINE_API = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def scrypt_rapide(monkeypatch):
    """Coût scrypt minimal en test : les paramètres sont stockés dans l'empreinte."""
    monkeypatch.setattr(security, "_N", 2**8)


@pytest.fixture(autouse=True)
def limiteurs_vierges():
    """Les compteurs de tentatives sont globaux au processus : on repart de zéro."""
    for limiteur in limitation.TOUS:
        limiteur.reinitialiser()
        limiteur.horloge = time.monotonic
    yield


def config_alembic(url: str) -> Config:
    config = Config(str(RACINE_API / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    config.attributes["configure_logger"] = False
    return config


@pytest.fixture
def db_url(tmp_path) -> str:
    """Base SQLite vierge, migrée jusqu'à la dernière version."""
    url = f"sqlite:///{tmp_path / 'test.db'}"
    command.upgrade(config_alembic(url), "head")
    return url


@pytest.fixture
def fabrique(db_url):
    moteur = creer_moteur(db_url)
    yield sessionmaker(bind=moteur, expire_on_commit=False)
    moteur.dispose()


@pytest.fixture
def session(fabrique) -> Session:
    with fabrique() as s:
        yield s


@pytest.fixture
def client(fabrique):
    """Client HTTP sur une base migrée et chargée avec les données de démo."""
    with fabrique() as s:
        charger_demo(s)

    def _session():
        with fabrique() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def entete(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def corps_connexion(prenom: str = "Lina", code: str = "2NDE-A-DEMO", code_personnel: str | None = None) -> dict:
    """Corps de POST /eleves/connexion ; par défaut, le code personnel de démo de l'élève."""
    return {"prenom": prenom, "code_classe": code, "code_personnel": code_personnel or CODES_DEMO.get(prenom, "XXXXXX")}


def connecter_eleve(client, prenom: str = "Lina", code: str = "2NDE-A-DEMO", code_personnel: str | None = None) -> dict[str, str]:
    r = client.post("/eleves/connexion", json=corps_connexion(prenom, code, code_personnel))
    assert r.status_code == 200, r.text
    return entete(r.json()["jeton"])


def inscrire_eleves(client, classe_code: str, prenoms: list[str]) -> dict[str, str]:
    """Inscrit des élèves comme le fait l'enseignant de démo ; renvoie {prénom: code personnel}."""
    h = connecter_enseignant(client)
    classe_id = next(c["id"] for c in client.get("/enseignants/classes", headers=h).json() if c["code"] == classe_code.upper())
    r = client.post(f"/enseignants/classes/{classe_id}/eleves", headers=h, json={"prenoms": prenoms})
    assert r.status_code == 201, r.text
    return {e["prenom"]: e["code"] for e in r.json()["crees"]}


def connecter_enseignant(client, email: str = "demo@pkp.test", mot_de_passe: str = "demo-pkp-2026") -> dict[str, str]:
    r = client.post("/enseignants/connexion", json={"email": email, "mot_de_passe": mot_de_passe})
    assert r.status_code == 200, r.text
    return entete(r.json()["jeton"])
