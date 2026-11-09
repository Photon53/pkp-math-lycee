"""Ticket #30 : remarques et suggestions, avec son nom ou anonymes, sans fuite d'identité."""

import typing
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.db import models
from app.purge import purger
from app.routes.remarques import Categorie
from tests.conftest import connecter_admin, connecter_eleve, connecter_enseignant
from tests.test_parents import connecter_parent

CATEGORIES = typing.get_args(Categorie)


def envoyer(client, h, anonyme: bool, categorie="bug", description="Le bouton Valider ne répond pas.", page="/admin/exercices"):
    return client.post("/remarques", headers=h, json={"categorie": categorie, "description": description, "page": page, "anonyme": anonyme})


@pytest.fixture
def comptes(client):
    return {"eleve": connecter_eleve(client), "parent": connecter_parent(client), "professeur": connecter_enseignant(client)}


@pytest.mark.parametrize("role", ["eleve", "parent", "professeur"])
@pytest.mark.parametrize("anonyme", [False, True])
def test_chaque_role_et_chaque_mode(client, session, comptes, role, anonyme):
    r = envoyer(client, comptes[role], anonyme)
    assert r.status_code == 201, r.text
    accuse = r.json()
    assert accuse["reference"].startswith("R-") and len(accuse["code_suivi"]) == 14 and accuse["statut"] == "recue"
    stockee = session.scalar(select(models.Remarque).where(models.Remarque.reference == accuse["reference"]))
    assert stockee.code_suivi_empreinte != accuse["code_suivi"]  # seule l'empreinte est conservée
    vue = next(x for x in client.get("/admin/remarques", headers=connecter_admin(client)).json() if x["reference"] == accuse["reference"])
    if anonyme:
        assert vue["auteur"] is None and stockee.auteur_role is None and stockee.auteur_id is None and stockee.auteur_nom is None
    else:
        assert vue["auteur"]["role"] == role and vue["auteur"]["nom"]


@pytest.mark.parametrize("categorie", CATEGORIES)
def test_chaque_categorie(client, categorie):
    assert envoyer(client, connecter_eleve(client), False, categorie=categorie).status_code == 201


def test_choix_du_mode_obligatoire_et_categorie_controlee(client):
    h = connecter_eleve(client)
    assert client.post("/remarques", headers=h, json={"categorie": "bug", "description": "Texte assez long"}).status_code == 422
    assert envoyer(client, h, False, categorie="spam").status_code == 422
    assert envoyer(client, h, False, description="  ").status_code == 422


def test_compte_obligatoire(client):
    assert envoyer(client, {}, True).status_code == 401


class TestAnonymat:
    def test_aucune_fuite_dans_l_api_l_export_et_le_journal(self, client, session):
        h = connecter_eleve(client)  # Lina, 2NDE-A-DEMO
        accuse = envoyer(client, h, True).json()
        admin = connecter_admin(client)
        liste = client.get("/admin/remarques", headers=admin).text
        export = client.get("/admin/remarques/export.csv", headers=admin).text
        for texte in (liste, export):
            assert "Lina" not in texte and "2NDE-A-DEMO" not in texte and "lina-demo" not in texte
        assert "Anonyme" in export
        rid = session.scalar(select(models.Remarque.id).where(models.Remarque.reference == accuse["reference"]))
        r = client.post(f"/admin/remarques/{rid}", headers=admin, json={"statut": "en-cours", "reponse": "Merci, corrigé."})
        assert r.status_code == 200 and r.json()["auteur"] is None
        traces = session.scalars(select(models.JournalAdmin).where(models.JournalAdmin.objet == "remarque")).all()
        assert traces and all("Lina" not in str(t.avant) + str(t.apres) for t in traces)
        # Une remarque anonyme n'apparaît pas dans « mes remarques » : elle n'est reliée à aucun compte.
        assert client.get("/remarques/miennes", headers=h).json() == []

    def test_suivi_par_code_confidentiel(self, client, session):
        accuse = envoyer(client, connecter_parent(client), True).json()
        admin = connecter_admin(client)
        rid = session.scalar(select(models.Remarque.id).where(models.Remarque.reference == accuse["reference"]))
        client.post(f"/admin/remarques/{rid}", headers=admin, json={"statut": "resolue", "reponse": "C'est réparé."})
        suivi = client.post("/remarques/suivi", json={"reference": accuse["reference"], "code": accuse["code_suivi"].lower()})
        assert suivi.status_code == 200 and suivi.json()["statut"] == "resolue" and suivi.json()["reponse"] == "C'est réparé."
        assert client.post("/remarques/suivi", json={"reference": accuse["reference"], "code": "AAAA-BBBB-CCCC"}).status_code == 404

    def test_references_imprevisibles(self, client):
        h = connecter_enseignant(client)
        refs = {envoyer(client, h, True).json()["reference"] for _ in range(5)}
        assert len(refs) == 5


class TestTraitement:
    def test_mes_remarques_avec_mon_nom(self, client):
        h = connecter_enseignant(client)
        accuse = envoyer(client, h, False).json()
        assert [r["reference"] for r in client.get("/remarques/miennes", headers=h).json()] == [accuse["reference"]]
        assert client.get("/remarques/miennes", headers=connecter_eleve(client)).json() == []

    def test_filtres_assignation_et_droits(self, client, session):
        envoyer(client, connecter_eleve(client), False, categorie="erreur-pedagogique")
        envoyer(client, connecter_eleve(client), True, categorie="question")
        admin = connecter_admin(client)
        assert {r["categorie"] for r in client.get("/admin/remarques?categorie=question", headers=admin).json()} == {"question"}
        rid = client.get("/admin/remarques?categorie=erreur-pedagogique", headers=admin).json()[0]["id"]
        admin_id = session.scalar(select(models.Enseignant.id).where(models.Enseignant.email == "admin@pkp.test"))
        prof_id = session.scalar(select(models.Enseignant.id).where(models.Enseignant.email == "demo@pkp.test"))
        r = client.post(f"/admin/remarques/{rid}", headers=admin, json={"priorite": "haute", "assignee_id": admin_id})
        assert r.json()["priorite"] == "haute" and r.json()["assignee"]
        assert client.post(f"/admin/remarques/{rid}", headers=admin, json={"assignee_id": prof_id}).status_code == 422
        assert client.get("/admin/remarques?priorite=haute", headers=admin).json()[0]["id"] == rid
        # Un professeur, un élève ou un parent n'accèdent pas à l'administration des remarques.
        assert client.get("/admin/remarques", headers=connecter_enseignant(client)).status_code in (401, 403)
        assert client.get("/admin/remarques", headers=connecter_eleve(client)).status_code == 401

    def test_anti_spam(self, client):
        h = connecter_eleve(client)
        codes = [envoyer(client, h, True).status_code for _ in range(11)]
        assert codes[:10] == [201] * 10 and codes[10] == 429

    def test_conservation_limitee(self, client, session):
        envoyer(client, connecter_eleve(client), True)
        r = session.scalars(select(models.Remarque)).one()
        r.maj_le = datetime.now(UTC) - timedelta(days=4000)
        session.commit()
        purger(session)
        assert session.scalars(select(models.Remarque)).all() == []
