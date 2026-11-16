# Issues #114 et #115 — Comptes d'autrui hors de portée d'un professeur (Claude)
"""Un professeur ne prend la main ni sur un compte parent (#114) ni sur la carte d'un enfant de famille (#115)
qui ne relèvent pas de lui : scénarios de l'audit global de develop (C-1, C-2), rejoués en non-régression."""

import pytest
from sqlalchemy import select

from app.db import models
from app.db.seed import EMAIL_ANGLAIS_DEMO
from app.security import hacher_mot_de_passe
from tests.conftest import connecter_admin, connecter_enseignant
from tests.test_parents import EMAIL, NOUVEAU_MDP, connecter_parent

LINA = 1  # 2NDE-A-DEMO, professeur de démo


@pytest.fixture
def malveillant(client, fabrique):
    """Un autre professeur de maths, avec une classe de 2nde et un élève à lui."""
    with fabrique() as s:
        prof = models.Enseignant(nom="Autre", email="autre@pkp.test", mot_de_passe_hash=hacher_mot_de_passe("autre-mdp"))
        s.add(prof)
        s.commit()
    h = connecter_enseignant(client, "autre@pkp.test", "autre-mdp")
    classe = client.post("/enseignants/classes", headers=h, json={"niveau": "2nde", "parcours": "excellence"}).json()
    client.post(f"/enseignants/classes/{classe['id']}/eleves", headers=h, json={"prenoms": ["Leurre"]})
    eleve = client.get(f"/enseignants/classes/{classe['id']}/eleves", headers=h).json()[0]
    return {"h": h, "classe": classe, "eleve_id": eleve["id"]}


def _famille(client, email="famille@x.test", niveau="2nde") -> dict:
    r = client.post("/admin/familles", headers=connecter_admin(client),
                    json={"email": email, "enfants": [{"prenom": "Zélie", "niveau": niveau}]})
    assert r.status_code == 201, r.text
    return r.json()


def _connexion_carte(client, carte: dict, code: str | None = None) -> int:
    corps = {"identifiant": carte["identifiant"], "code_personnel": code or carte["code"]}
    return client.post("/enfants/connexion", json=corps).status_code


# --- #114 : compte parent ---------------------------------------------------------------------------------


class TestReinitialisationParent:
    def test_rattacher_puis_reinitialiser_le_parent_d_un_autre_eleve_refuse(self, client, malveillant):
        connecter_parent(client)  # parent de Lina, mot de passe choisi
        r = client.post(f"/enseignants/eleves/{malveillant['eleve_id']}/parents", headers=malveillant["h"], json={"email": EMAIL})
        parent_id = r.json()["parent"]["id"]
        r = client.post(f"/enseignants/parents/{parent_id}/mot-de-passe", headers=malveillant["h"])
        assert r.status_code == 403 and "administrateur" in r.json()["detail"]
        # Le mot de passe du parent n'a pas changé.
        assert client.post("/parents/connexion", json={"email": EMAIL, "mot_de_passe": NOUVEAU_MDP}).status_code == 200

    def test_le_professeur_de_tous_les_enfants_reinitialise_toujours(self, client):
        parent_id = client.post(f"/enseignants/eleves/{LINA}/parents", headers=connecter_enseignant(client),
                                json={"email": EMAIL}).json()["parent"]["id"]
        r = client.post(f"/enseignants/parents/{parent_id}/mot-de-passe", headers=connecter_enseignant(client))
        assert r.status_code == 200 and r.json()["mot_de_passe_provisoire"]

    def test_famille_dont_un_enfant_n_est_inscrit_nulle_part_refusee(self, client, malveillant, session):
        _famille(client)
        parent_id = client.post(f"/enseignants/eleves/{malveillant['eleve_id']}/parents", headers=malveillant["h"],
                                json={"email": "famille@x.test"}).json()["parent"]["id"]
        assert client.post(f"/enseignants/parents/{parent_id}/mot-de-passe", headers=malveillant["h"]).status_code == 403

    def test_famille_inscrite_seulement_chez_ce_professeur_acceptee(self, client, session):
        f = _famille(client)
        prof = connecter_enseignant(client)
        assert client.post("/enseignants/classes/1/enfants", headers=prof, json={"enfant_ids": [f["cartes"][0]["id"]]}).json()["ajoutes"]
        zelie = session.scalar(select(models.Eleve.id).where(models.Eleve.enfant_id == f["cartes"][0]["id"]))
        r = client.post(f"/enseignants/eleves/{zelie}/parents", headers=prof, json={"email": "famille@x.test"})
        parent_id = r.json()["parent"]["id"]
        assert client.post(f"/enseignants/parents/{parent_id}/mot-de-passe", headers=prof).status_code == 200


# --- #115 : carte d'un enfant de famille --------------------------------------------------------------------


def _inscrire_chez(client, malveillant, carte) -> int:
    r = client.post(f"/enseignants/classes/{malveillant['classe']['id']}/enfants", headers=malveillant["h"],
                    json={"enfant_ids": [carte["id"]]})
    assert r.json()["ajoutes"], r.text
    eleves = client.get(f"/enseignants/classes/{malveillant['classe']['id']}/eleves", headers=malveillant["h"]).json()
    return next(e["id"] for e in eleves if e["prenom"].startswith("Zélie"))


class TestCarteDeFamille:
    def test_nouveau_code_refuse_et_carte_intacte(self, client, malveillant):
        carte = _famille(client)["cartes"][0]
        eleve_id = _inscrire_chez(client, malveillant, carte)
        r = client.post(f"/enseignants/eleves/{eleve_id}/code", headers=malveillant["h"])
        assert r.status_code == 403 and "famille" in r.json()["detail"]
        assert _connexion_carte(client, carte) == 200

    def test_cartes_et_codes_de_classe_ignorent_les_enfants_de_famille(self, client, malveillant):
        carte = _famille(client)["cartes"][0]
        _inscrire_chez(client, malveillant, carte)
        cid = malveillant["classe"]["id"]
        cartes = client.post(f"/enseignants/classes/{cid}/cartes", headers=malveillant["h"]).json()
        assert [c["prenom"] for c in cartes] == ["Leurre"]
        assert client.post(f"/enseignants/classes/{cid}/codes-manquants", headers=malveillant["h"]).json() == []
        assert _connexion_carte(client, carte) == 200

    def test_relier_une_inscription_de_famille_refuse(self, client, malveillant):
        carte = _famille(client)["cartes"][0]
        eleve_id = _inscrire_chez(client, malveillant, carte)
        autre = client.post("/enseignants/classes", headers=malveillant["h"], json={"niveau": "2nde", "parcours": "mise-a-niveau"}).json()
        client.post(f"/enseignants/classes/{autre['id']}/eleves", headers=malveillant["h"], json={"prenoms": ["Zélie"]})
        libre = client.get(f"/enseignants/classes/{autre['id']}/eleves", headers=malveillant["h"]).json()[0]["id"]
        client.post(f"/enseignants/eleves/{libre}/code", headers=malveillant["h"])
        for a, b in ((libre, eleve_id), (eleve_id, libre)):
            r = client.post(f"/enseignants/eleves/{a}/liens", headers=malveillant["h"], json={"eleve_id": b})
            assert r.status_code == 422 and "carte de famille" in r.json()["detail"]
        assert _connexion_carte(client, carte) == 200

    def test_anglais_nouveau_code_refuse_et_groupe_ignore(self, client):
        carte = _famille(client, niveau="4e")["cartes"][0]
        h = connecter_enseignant(client, email=EMAIL_ANGLAIS_DEMO)
        gid = client.post("/anglais/groupes", headers=h, json={"nom": "Groupe 4e", "niveau": "4e"}).json()["id"]
        assert client.post(f"/anglais/groupes/{gid}/enfants", headers=h, json={"enfant_ids": [carte["id"]]}).json()["ajoutes"]
        eleve = client.get("/anglais/groupes", headers=h).json()[0]["eleves"][0]
        r = client.post(f"/anglais/groupes/{gid}/eleves/{eleve['id']}/code", headers=h)
        assert r.status_code == 403 and "famille" in r.json()["detail"]
        assert client.post(f"/anglais/groupes/{gid}/codes", headers=h, params={"tous": True}).json() == []
        assert _connexion_carte(client, carte) == 200

    def test_l_administrateur_renouvelle_toujours_la_carte(self, client):
        carte = _famille(client)["cartes"][0]
        r = client.post(f"/admin/enfants/{carte['id']}/carte", headers=connecter_admin(client))
        assert r.status_code == 200, r.text
        assert _connexion_carte(client, carte, r.json()["code"]) == 200
        assert _connexion_carte(client, carte) == 401
