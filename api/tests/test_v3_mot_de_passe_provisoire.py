"""V3, Lot 0 : le mot de passe provisoire d'un parent (aléatoire, ~92 bits) est haché à coût modéré pour que
l'import en masse reste rapide ; il passe au coût complet dès la première connexion."""

from sqlalchemy import select

from app import security
from app.db import models
from tests.conftest import connecter_admin


def _cout(empreinte: str) -> int:
    return int(empreinte.split("$")[1])


def test_provisoire_hache_a_cout_modere_puis_rehache_a_la_connexion(client, session, monkeypatch):
    monkeypatch.setattr(security, "_N", 2**14)  # le coût complet reste supérieur au coût modéré (2^12)
    admin = connecter_admin(client)
    r = client.post("/admin/familles", headers=admin, json={"email": "rapide@x.test", "enfants": [{"prenom": "Léo", "niveau": "6e"}]})
    provisoire = r.json()["mot_de_passe_provisoire"]
    parent = session.scalar(select(models.Parent).where(models.Parent.email == "rapide@x.test"))
    assert _cout(parent.mot_de_passe_hash) == security._N_CODE
    assert security.doit_rehacher(parent.mot_de_passe_hash)

    assert client.post("/parents/connexion", json={"email": "rapide@x.test", "mot_de_passe": provisoire}).status_code == 200
    session.expire_all()
    assert _cout(session.get(models.Parent, parent.id).mot_de_passe_hash) == 2**14
