"""Un même élève dans plusieurs parcours : le professeur relie ses inscriptions, l'élève bascule avec un seul code."""

import pytest

from app.db import models
from app.security import hacher_mot_de_passe
from tests.conftest import connecter_eleve, connecter_enseignant, entete, inscrire_eleves


def _classe(client, h, niveau, parcours) -> dict:
    r = client.post("/enseignants/classes", headers=h, json={"niveau": niveau, "parcours": parcours})
    assert r.status_code == 201, r.text
    return r.json()


def _eleve_id(client, h, classe_id, prenom) -> int:
    return next(e["id"] for e in client.get(f"/enseignants/classes/{classe_id}/eleves", headers=h).json() if e["prenom"] == prenom)


@pytest.fixture
def roiya(client):
    """Roiya, en spécialité (1RE-SPE-…) et en mise à niveau (1RE-MAN-…), deux codes au départ."""
    h = connecter_enseignant(client)
    spe, man = _classe(client, h, "1re", "specialite"), _classe(client, h, "1re", "mise-a-niveau")
    code_spe = inscrire_eleves(client, spe["code"], ["Roiya"])["Roiya"]
    code_man = inscrire_eleves(client, man["code"], ["Roiya"])["Roiya"]
    return {
        "h": h, "spe": spe, "man": man, "code_spe": code_spe, "code_man": code_man,
        "id_spe": _eleve_id(client, h, spe["id"], "Roiya"), "id_man": _eleve_id(client, h, man["id"], "Roiya"),
    }


def _relier(client, r):
    return client.post(f"/enseignants/eleves/{r['id_spe']}/liens", headers=r["h"], json={"eleve_id": r["id_man"]})


class TestCoteProfesseur:
    def test_suggestion_du_meme_prenom_puis_lien(self, client, roiya):
        liens = client.get(f"/enseignants/eleves/{roiya['id_spe']}/liens", headers=roiya["h"]).json()
        assert liens["liees"] == [] and [s["eleve_id"] for s in liens["suggestions"]] == [roiya["id_man"]]
        r = _relier(client, roiya)
        assert r.status_code == 200, r.text
        assert [i["code_classe"] for i in r.json()["liees"]] == [roiya["man"]["code"]] and r.json()["suggestions"] == []
        eleves = client.get(f"/enseignants/classes/{roiya['spe']['id']}/eleves", headers=roiya["h"]).json()
        assert next(e for e in eleves if e["prenom"] == "Roiya")["classes_liees"] == [roiya["man"]["code"]]

    def test_un_seul_code_pour_toutes_les_inscriptions(self, client, roiya):
        _relier(client, roiya)
        # Le code de la spécialité vaut désormais aussi en mise à niveau ; l'ancien code de mise à niveau ne vaut plus.
        connecter_eleve(client, "Roiya", roiya["man"]["code"], roiya["code_spe"])
        corps = {"prenom": "Roiya", "code_classe": roiya["man"]["code"], "code_personnel": roiya["code_man"]}
        assert client.post("/eleves/connexion", json=corps).status_code == 401
        # Un nouveau code généré vaut pour les deux inscriptions.
        nouveau = client.post(f"/enseignants/eleves/{roiya['id_man']}/code", headers=roiya["h"]).json()["code"]
        connecter_eleve(client, "Roiya", roiya["spe"]["code"], nouveau)

    def test_pas_deux_inscriptions_dans_la_meme_classe_ni_soi_meme(self, client, roiya):
        h = roiya["h"]
        assert client.post(f"/enseignants/eleves/{roiya['id_spe']}/liens", headers=h, json={"eleve_id": roiya["id_spe"]}).status_code == 422
        autre = inscrire_eleves(client, roiya["man"]["code"], ["Sami"]) and _eleve_id(client, h, roiya["man"]["id"], "Sami")
        assert _relier(client, roiya).status_code == 200
        r = client.post(f"/enseignants/eleves/{roiya['id_spe']}/liens", headers=h, json={"eleve_id": autre})
        assert r.status_code == 422 and "une inscription par classe" in r.json()["detail"]

    def test_classe_d_un_autre_professeur_refusee(self, client, fabrique, roiya):
        with fabrique() as s:
            s.add(models.Enseignant(nom="Autre", email="autre@pkp.test", mot_de_passe_hash=hacher_mot_de_passe("autre-mdp")))
            s.commit()
        h_autre = connecter_enseignant(client, "autre@pkp.test", "autre-mdp")
        classe = _classe(client, h_autre, "1re", "excellence")
        client.post(f"/enseignants/classes/{classe['id']}/eleves", headers=h_autre, json={"prenoms": ["Roiya"]})
        id_autre = _eleve_id(client, h_autre, classe["id"], "Roiya")
        # Ni lien vers l'élève d'un collègue, ni suggestion de ses classes.
        assert client.post(f"/enseignants/eleves/{roiya['id_spe']}/liens", headers=roiya["h"], json={"eleve_id": id_autre}).status_code == 404
        suggestions = client.get(f"/enseignants/eleves/{roiya['id_spe']}/liens", headers=roiya["h"]).json()["suggestions"]
        assert id_autre not in [s["eleve_id"] for s in suggestions]

    def test_delier_et_suppression(self, client, roiya):
        _relier(client, roiya)
        r = client.delete(f"/enseignants/eleves/{roiya['id_man']}/liens", headers=roiya["h"])
        assert r.status_code == 200 and r.json()["liees"] == []
        assert client.get(f"/enseignants/eleves/{roiya['id_spe']}/liens", headers=roiya["h"]).json()["liees"] == []
        _relier(client, roiya)
        assert client.delete(f"/enseignants/eleves/{roiya['id_spe']}", headers=roiya["h"]).status_code == 204
        assert client.get(f"/enseignants/eleves/{roiya['id_man']}/liens", headers=roiya["h"]).json()["liees"] == []


class TestCoteEleve:
    def test_bascule_entre_parcours_sans_ressaisir_de_code(self, client, roiya):
        _relier(client, roiya)
        h = connecter_eleve(client, "Roiya", roiya["spe"]["code"], roiya["code_spe"])
        parcours = client.get("/eleves/moi/parcours", headers=h).json()
        assert {(p["parcours"], p["actuelle"]) for p in parcours} == {("specialite", True), ("mise-a-niveau", False)}
        r = client.post(f"/eleves/moi/parcours/{roiya['id_man']}", headers=h)
        assert r.status_code == 200 and r.json()["eleve"]["parcours"] == "mise-a-niveau"
        h_man = entete(r.json()["jeton"])
        assert client.get("/eleves/moi", headers=h_man).json()["code_classe"] == roiya["man"]["code"]
        # Les cours servis sont ceux de la mise à niveau.
        assert all(ch["code"].startswith("1RE-MAN-") for ch in client.get("/cours", headers=h_man).json())

    def test_bascule_refusee_sans_lien(self, client, roiya):
        h = connecter_eleve(client, "Roiya", roiya["spe"]["code"], roiya["code_spe"])
        assert [p["actuelle"] for p in client.get("/eleves/moi/parcours", headers=h).json()] == [True]
        assert client.post(f"/eleves/moi/parcours/{roiya['id_man']}", headers=h).status_code == 404
        # Un autre élève de la démo n'est jamais accessible.
        assert client.post("/eleves/moi/parcours/1", headers=h).status_code == 404
