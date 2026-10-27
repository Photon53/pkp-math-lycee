import pytest

from app.security import creer_jeton
from tests.conftest import connecter_eleve, connecter_enseignant, entete


def solutions(client) -> dict[int, str]:
    r = client.get("/enseignants/questions?archivees=true", headers=connecter_enseignant(client))
    return {q["id"]: q["solution"] for q in r.json()}


def nouvelle_seance(client, h) -> int:
    r = client.post("/seances", headers=h)
    assert r.status_code == 201
    return r.json()["id"]


class TestConnexion:
    def test_eleve_existant(self, client):
        r = client.post("/eleves/connexion", json={"prenom": "Lina", "code_classe": "2NDE-A-DEMO"})
        assert r.status_code == 200
        assert r.json()["eleve"] == {"id": 1, "prenom": "Lina", "code_classe": "2NDE-A-DEMO", "niveau": "2nde"}

    @pytest.mark.parametrize(("prenom", "code"), [("  lina ", "2nde-a-demo"), ("LINA", " 2NDE-A-DEMO ")])
    def test_saisie_normalisee(self, client, prenom, code):
        r = client.post("/eleves/connexion", json={"prenom": prenom, "code_classe": code})
        assert r.json()["eleve"]["id"] == 1

    def test_nouveau_prenom_cree_l_eleve_une_seule_fois(self, client):
        premier = client.post("/eleves/connexion", json={"prenom": "jean-paul", "code_classe": "2NDE-A-DEMO"}).json()
        second = client.post("/eleves/connexion", json={"prenom": "Jean-Paul", "code_classe": "2NDE-A-DEMO"}).json()
        assert premier["eleve"]["prenom"] == "Jean-Paul"
        assert premier["eleve"]["id"] == second["eleve"]["id"]

    def test_code_inconnu(self, client):
        r = client.post("/eleves/connexion", json={"prenom": "Lina", "code_classe": "NOPE"})
        assert r.status_code == 404

    @pytest.mark.parametrize("prenom", ["", "   ", "R2D2", "<script>", "a" * 51])
    def test_prenom_invalide(self, client, prenom):
        r = client.post("/eleves/connexion", json={"prenom": prenom, "code_classe": "2NDE-A-DEMO"})
        assert r.status_code == 422


class TestAuthentification:
    def test_sans_jeton(self, client):
        assert client.get("/eleves/moi").status_code == 401

    @pytest.mark.parametrize("jeton", ["n'importe quoi", "abc.def", ""])
    def test_jeton_invalide(self, client, jeton):
        assert client.get("/eleves/moi", headers=entete(jeton)).status_code == 401

    def test_jeton_falsifie(self, client):
        charge, signature = connecter_eleve(client)["Authorization"].removeprefix("Bearer ").split(".")
        autre = creer_jeton("eleve", 2, 1).split(".")[0]
        assert client.get("/eleves/moi", headers=entete(f"{autre}.{signature}")).status_code == 401

    def test_jeton_expire(self, client):
        assert client.get("/eleves/moi", headers=entete(creer_jeton("eleve", 1, -1))).status_code == 401

    def test_jeton_enseignant_refuse_cote_eleve(self, client):
        assert client.get("/eleves/moi", headers=connecter_enseignant(client)).status_code == 401

    def test_moi(self, client):
        assert client.get("/eleves/moi", headers=connecter_eleve(client, "Hugo", "1RE-B-DEMO")).json()["niveau"] == "1re"


class TestParcours:
    def test_question_publique_sans_solution(self, client):
        h = connecter_eleve(client)
        q = client.get(f"/seances/{nouvelle_seance(client, h)}/question", headers=h).json()
        assert set(q) == {"id", "enonce", "type", "difficulte"}

    def test_redemander_renvoie_la_meme_question(self, client):
        h = connecter_eleve(client)
        s = nouvelle_seance(client, h)
        ids = {client.get(f"/seances/{s}/question", headers=h).json()["id"] for _ in range(3)}
        assert len(ids) == 1

    def test_bonne_reponse(self, client):
        sol = solutions(client)
        h = connecter_eleve(client, "Inès")
        s = nouvelle_seance(client, h)
        q = client.get(f"/seances/{s}/question", headers=h).json()
        r = client.post(f"/seances/{s}/reponses", headers=h, json={"question_id": q["id"], "reponse_donnee": sol[q["id"]]})
        assert r.status_code == 200
        corps = r.json()
        assert corps["correcte"] is True
        assert corps["solution"] == sol[q["id"]]
        assert corps["maitrise"] == pytest.approx(0.5)
        assert corps["maitrisee"] is False

    def test_mauvaise_reponse_revele_la_solution(self, client):
        h = connecter_eleve(client, "Inès")
        s = nouvelle_seance(client, h)
        q = client.get(f"/seances/{s}/question", headers=h).json()
        corps = client.post(f"/seances/{s}/reponses", headers=h, json={"question_id": q["id"], "reponse_donnee": "faux"}).json()
        assert corps["correcte"] is False and corps["solution"] and corps["maitrise"] == 0.0

    def test_repondre_sans_question_servie(self, client):
        h = connecter_eleve(client)
        s = nouvelle_seance(client, h)
        r = client.post(f"/seances/{s}/reponses", headers=h, json={"question_id": 1, "reponse_donnee": "5/6"})
        assert r.status_code == 409

    def test_repondre_a_une_autre_question(self, client):
        h = connecter_eleve(client)
        s = nouvelle_seance(client, h)
        q = client.get(f"/seances/{s}/question", headers=h).json()
        r = client.post(f"/seances/{s}/reponses", headers=h, json={"question_id": q["id"] + 1, "reponse_donnee": "1"})
        assert r.status_code == 409

    def test_pas_deux_reponses_a_la_meme_question(self, client):
        h = connecter_eleve(client)
        s = nouvelle_seance(client, h)
        q = client.get(f"/seances/{s}/question", headers=h).json()
        corps = {"question_id": q["id"], "reponse_donnee": "1"}
        assert client.post(f"/seances/{s}/reponses", headers=h, json=corps).status_code == 200
        assert client.post(f"/seances/{s}/reponses", headers=h, json=corps).status_code == 409

    def test_reponse_trop_longue(self, client):
        h = connecter_eleve(client)
        s = nouvelle_seance(client, h)
        q = client.get(f"/seances/{s}/question", headers=h).json()
        r = client.post(f"/seances/{s}/reponses", headers=h, json={"question_id": q["id"], "reponse_donnee": "1" * 201})
        assert r.status_code == 422

    def test_seance_d_un_autre_eleve(self, client):
        s = nouvelle_seance(client, connecter_eleve(client, "Lina"))
        assert client.get(f"/seances/{s}/question", headers=connecter_eleve(client, "Yanis")).status_code == 404

    def test_seance_terminee(self, client):
        h = connecter_eleve(client)
        s = nouvelle_seance(client, h)
        assert client.post(f"/seances/{s}/fin", headers=h).json()["fin"] is not None
        assert client.get(f"/seances/{s}/question", headers=h).status_code == 409

    def test_questions_du_niveau_et_jamais_archivees(self, client):
        archivees = {q["id"] for q in client.get("/enseignants/questions?archivees=true", headers=connecter_enseignant(client)).json() if q["archivee"]}
        h = connecter_eleve(client, "Hugo", "1RE-B-DEMO")
        s = nouvelle_seance(client, h)
        vues = set()
        for _ in range(6):
            q = client.get(f"/seances/{s}/question", headers=h).json()
            vues.add(q["id"])
            client.post(f"/seances/{s}/reponses", headers=h, json={"question_id": q["id"], "reponse_donnee": "x"})
        assert vues == {14, 15}  # les 2 questions de 1re
        assert not vues & archivees

    def test_aucune_question_pour_le_niveau(self, client):
        code = client.post("/enseignants/classes", headers=connecter_enseignant(client), json={"niveau": "Tle"}).json()["code"]
        h = connecter_eleve(client, "Zoé", code)
        assert client.get(f"/seances/{nouvelle_seance(client, h)}/question", headers=h).status_code == 204

    def test_progression(self, client):
        h = connecter_eleve(client)
        progression = {p["code"]: p for p in client.get("/eleves/moi/progression", headers=h).json()}
        assert list(progression) == ["2NDE-FRAC", "2NDE-PUIS", "2NDE-DEV", "2NDE-EQ1"]
        assert progression["2NDE-FRAC"]["nb_reponses"] == 2
        assert progression["2NDE-PUIS"] == {**progression["2NDE-PUIS"], "nb_reponses": 0, "maitrise": 0.0, "maitrisee": False}
