import re

import pytest

from app.db import models
from app.security import hacher_mot_de_passe
from tests.conftest import connecter_eleve, connecter_enseignant, corps_connexion, inscrire_eleves


@pytest.fixture
def autre_enseignant(client, fabrique):
    with fabrique() as s:
        s.add(models.Enseignant(nom="Autre", email="autre@pkp.test", mot_de_passe_hash=hacher_mot_de_passe("autre-mdp")))
        s.commit()
    return connecter_enseignant(client, "autre@pkp.test", "autre-mdp")


class TestConnexion:
    def test_ok_et_email_insensible_a_la_casse(self, client):
        r = client.post("/enseignants/connexion", json={"email": " Demo@PKP.test ", "mot_de_passe": "demo-pkp-2026"})
        assert r.status_code == 200 and r.json()["nom"] == "Enseignant Démo"

    @pytest.mark.parametrize(("email", "mdp"), [("demo@pkp.test", "mauvais"), ("inconnu@pkp.test", "demo-pkp-2026")])
    def test_refus_sans_reveler_si_le_compte_existe(self, client, email, mdp):
        r = client.post("/enseignants/connexion", json={"email": email, "mot_de_passe": mdp})
        assert r.status_code == 401
        assert r.json()["detail"] == "Email ou mot de passe incorrect."

    def test_jeton_eleve_refuse_cote_enseignant(self, client):
        assert client.get("/enseignants/classes", headers=connecter_eleve(client)).status_code == 401


class TestClasses:
    def test_mes_classes(self, client):
        classes = client.get("/enseignants/classes", headers=connecter_enseignant(client)).json()
        assert [(c["code"], c["nb_eleves"]) for c in classes] == [("1RE-B-DEMO", 1), ("2NDE-A-DEMO", 3), ("TLE-C-DEMO", 1)]

    def test_creer_une_classe(self, client):
        h = connecter_enseignant(client)
        classe = client.post("/enseignants/classes", headers=h, json={"niveau": "1re"}).json()
        assert re.fullmatch(r"1RE-[2-9A-HJKMNP-Z]{5}", classe["code"])
        assert classe["nb_eleves"] == 0
        codes = inscrire_eleves(client, classe["code"], ["Sam"])
        connecter_eleve(client, "Sam", classe["code"].lower(), codes["Sam"].lower())
        assert len(client.get("/enseignants/classes", headers=h).json()) == 4

    def test_tableau_de_bord(self, client):
        eleves = client.get("/enseignants/classes/1/eleves", headers=connecter_enseignant(client)).json()
        par_prenom = {e["prenom"]: e for e in eleves}
        assert list(par_prenom) == ["Inès", "Lina", "Yanis"]
        assert par_prenom["Lina"] == {
            "id": 1, "prenom": "Lina", "a_un_code": True, "nb_reponses": 5, "taux_reussite": 0.6,
            "competences_maitrisees": 0, "competences_total": 5,
        }
        assert par_prenom["Inès"]["taux_reussite"] is None

    def test_progression_d_un_eleve(self, client):
        progression = client.get("/enseignants/eleves/1/progression", headers=connecter_enseignant(client)).json()
        assert {p["code"]: p["nb_reponses"] for p in progression}["2NDE-DEV"] == 2


class TestCloisonnement:
    def test_ne_voit_pas_les_classes_des_autres(self, client, autre_enseignant):
        assert client.get("/enseignants/classes", headers=autre_enseignant).json() == []
        assert client.get("/enseignants/classes/1/eleves", headers=autre_enseignant).status_code == 404
        assert client.get("/enseignants/eleves/1/progression", headers=autre_enseignant).status_code == 404
        assert client.delete("/enseignants/eleves/1", headers=autre_enseignant).status_code == 404


class TestEffacementRgpd:
    def test_supprimer_un_eleve(self, client):
        h_eleve = connecter_eleve(client, "Lina")
        h = connecter_enseignant(client)
        assert client.delete("/enseignants/eleves/1", headers=h).status_code == 204
        assert [e["prenom"] for e in client.get("/enseignants/classes/1/eleves", headers=h).json()] == ["Inès", "Yanis"]
        # Son jeton et son code ne fonctionnent plus ; réinscrite, elle repart de zéro avec un nouveau code.
        assert client.get("/eleves/moi", headers=h_eleve).status_code == 401
        assert client.post("/eleves/connexion", json=corps_connexion("Lina")).status_code == 401
        nouveau_code = inscrire_eleves(client, "2NDE-A-DEMO", ["Lina"])["Lina"]
        nouveau = connecter_eleve(client, "Lina", code_personnel=nouveau_code)
        assert all(p["nb_reponses"] == 0 for p in client.get("/eleves/moi/progression", headers=nouveau).json())


class TestQuestions:
    def test_competences(self, client):
        competences = client.get("/enseignants/competences", headers=connecter_enseignant(client)).json()
        assert len(competences) == 17

    def test_liste_avec_solutions_sans_archivees(self, client):
        h = connecter_enseignant(client)
        actives = client.get("/enseignants/questions", headers=h).json()
        toutes = client.get("/enseignants/questions?archivees=true", headers=h).json()
        assert (len(actives), len(toutes)) == (79, 80)
        assert all("solution" in q for q in actives)

    def test_creer_une_question(self, client):
        h = connecter_enseignant(client)
        corps = {"competence_id": 3, "enonce": "Développer (x − 2)².", "type": "expression", "solution": "x² − 4x + 4", "difficulte": 2}
        r = client.post("/enseignants/questions", headers=h, json=corps)
        assert r.status_code == 201
        assert r.json()["archivee"] is False

    @pytest.mark.parametrize(
        ("corps", "code"),
        [
            ({"type": "expression", "solution": "x +"}, 422),
            ({"type": "numerique", "solution": "2x"}, 422),
            ({"difficulte": 6}, 422),
            ({"competence_id": 999}, 404),
        ],
    )
    def test_question_refusee(self, client, corps, code):
        base = {"competence_id": 3, "enonce": "?", "type": "numerique", "solution": "1", "difficulte": 2}
        r = client.post("/enseignants/questions", headers=connecter_enseignant(client), json={**base, **corps})
        assert r.status_code == code

    def test_archiver(self, client):
        h = connecter_enseignant(client)
        assert client.post("/enseignants/questions/1/archiver", headers=h).json()["archivee"] is True
        assert 1 not in {q["id"] for q in client.get("/enseignants/questions", headers=h).json()}
        assert client.post("/enseignants/questions/999/archiver", headers=h).status_code == 404
