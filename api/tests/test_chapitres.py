"""Chapitres proposés par l'enseignant à sa classe, choisis par l'élève pour sa séance."""

from tests.conftest import connecter_eleve, connecter_enseignant

CLASSE = "1RE-B-DEMO"  # 1re spécialité : 10 chapitres, du second degré aux variables aléatoires


def _classe_id(client, h, code=CLASSE):
    return next(c["id"] for c in client.get("/enseignants/classes", headers=h).json() if c["code"] == code)


def _programme(client, h, classe_id):
    return client.get(f"/enseignants/classes/{classe_id}/chapitres", headers=h).json()


class TestCoteEnseignant:
    def test_tout_le_programme_est_ouvert_par_defaut(self, client):
        h = connecter_enseignant(client)
        programme = _programme(client, h, _classe_id(client, h))
        assert [c["code"] for c in programme][:2] == ["1RE-SECOND-DEGRE", "1RE-SUITES"]
        assert [c["ordre"] for c in programme] == list(range(1, 11))
        assert all(c["propose"] for c in programme)
        assert all(c["nb_questions"] > 0 and c["nb_competences"] > 0 for c in programme)

    def test_nouvelle_classe_ouverte_sur_son_programme(self, client):
        h = connecter_enseignant(client)
        classe = client.post("/enseignants/classes", headers=h, json={"niveau": "1re"}).json()
        assert all(c["propose"] for c in _programme(client, h, classe["id"]))

    def test_fermer_puis_rouvrir(self, client):
        h = connecter_enseignant(client)
        classe_id = _classe_id(client, h)
        suites = next(c["id"] for c in _programme(client, h, classe_id) if c["code"] == "1RE-SUITES")
        r = client.put(f"/enseignants/classes/{classe_id}/chapitres", headers=h, json={"chapitre_ids": [suites]})
        assert r.status_code == 200
        assert [c["code"] for c in r.json() if c["propose"]] == ["1RE-SUITES"]
        r = client.put(f"/enseignants/classes/{classe_id}/chapitres", headers=h, json={"chapitre_ids": []})
        assert not any(c["propose"] for c in r.json())

    def test_chapitre_hors_programme_refuse(self, client):
        h = connecter_enseignant(client)
        id_seconde = _programme(client, h, _classe_id(client, h, "2NDE-A-DEMO"))[0]["id"]
        r = client.put(f"/enseignants/classes/{_classe_id(client, h)}/chapitres", headers=h, json={"chapitre_ids": [id_seconde]})
        assert r.status_code == 422

    def test_classe_d_un_autre_enseignant_introuvable(self, client):
        h = connecter_enseignant(client)
        assert client.get("/enseignants/classes/99999/chapitres", headers=h).status_code == 404
        assert client.put("/enseignants/classes/99999/chapitres", headers=h, json={"chapitre_ids": []}).status_code == 404

    def test_reserve_aux_enseignants(self, client):
        assert client.get("/enseignants/classes/1/chapitres", headers=connecter_eleve(client, "Hugo", CLASSE)).status_code == 401


class TestCoteEleve:
    def _ne_garder_que(self, client, code_chapitre):
        h = connecter_enseignant(client)
        classe_id = _classe_id(client, h)
        garde = [c["id"] for c in _programme(client, h, classe_id) if c["code"] == code_chapitre]
        client.put(f"/enseignants/classes/{classe_id}/chapitres", headers=h, json={"chapitre_ids": garde})
        return garde[0] if garde else None

    def test_voit_les_chapitres_ouverts(self, client):
        h = connecter_eleve(client, "Hugo", CLASSE)
        chapitres = client.get("/eleves/moi/chapitres", headers=h).json()
        assert len(chapitres) == 10 and chapitres[0]["code"] == "1RE-SECOND-DEGRE"
        assert all(c["nb_questions"] > 0 for c in chapitres)

    def test_chapitre_ferme_disparait_du_cours_et_de_la_progression(self, client):
        self._ne_garder_que(client, "1RE-SUITES")
        h = connecter_eleve(client, "Hugo", CLASSE)
        assert [c["code"] for c in client.get("/eleves/moi/chapitres", headers=h).json()] == ["1RE-SUITES"]
        assert [c["code"] for c in client.get("/cours", headers=h).json()] == ["1RE-SUITES"]
        codes = {p["code"] for p in client.get("/eleves/moi/progression", headers=h).json()}
        assert codes and all(code.startswith("1RE-SUI") for code in codes)

    def test_seance_sur_un_chapitre_choisi(self, client):
        h = connecter_eleve(client, "Hugo", CLASSE)
        chapitres = {c["code"]: c["id"] for c in client.get("/eleves/moi/chapitres", headers=h).json()}
        r = client.post("/seances", headers=h, json={"chapitre_ids": [chapitres["1RE-SUITES"]]})
        assert r.status_code == 201
        assert [c["titre"] for c in r.json()["chapitres"]] == ["Suites numériques"]
        competences_suites = {
            comp["id"] for ch in client.get("/cours", headers=h).json() if ch["code"] == "1RE-SUITES" for comp in ch["competences"]
        }
        seance = r.json()["id"]
        for _ in range(5):  # toutes les questions servies viennent du chapitre choisi
            q = client.get(f"/seances/{seance}/question", headers=h).json()
            assert q["competence_id"] in competences_suites
            client.post(f"/seances/{seance}/reponses", headers=h, json={"question_id": q["id"], "reponse_donnee": "0"})

    def test_sans_choix_tous_les_chapitres_ouverts(self, client):
        h = connecter_eleve(client, "Hugo", CLASSE)
        r = client.post("/seances", headers=h)
        assert len(r.json()["chapitres"]) == 10

    def test_chapitre_non_propose_refuse(self, client):
        h = connecter_eleve(client, "Hugo", CLASSE)
        id_second_degre = client.get("/eleves/moi/chapitres", headers=h).json()[0]["id"]
        self._ne_garder_que(client, "1RE-SUITES")
        r = client.post("/seances", headers=h, json={"chapitre_ids": [id_second_degre]})
        assert r.status_code == 422

    def test_aucun_chapitre_ouvert(self, client):
        self._ne_garder_que(client, "INEXISTANT")
        h = connecter_eleve(client, "Hugo", CLASSE)
        assert client.get("/eleves/moi/chapitres", headers=h).json() == []
        r = client.post("/seances", headers=h)
        assert r.status_code == 409
        assert r.json()["detail"] == "Ton professeur n'a pas encore ouvert de chapitre."
