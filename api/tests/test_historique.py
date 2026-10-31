"""Historique des réponses (élève et professeur) et séance ciblée sur une compétence."""

from tests.conftest import connecter_admin, connecter_eleve, connecter_enseignant, entete


def _competence(client, h, code: str) -> int:
    return next(c["id"] for ch in client.get("/cours", headers=h).json() for c in ch["competences"] if c["code"] == code)


class TestHistorique:
    def test_eleve_revoit_ses_reponses_avec_correction(self, client):
        """Lina a répondu à 5 questions dans les données de démo, dont deux fausses."""
        page = client.get("/eleves/moi/historique", headers=connecter_eleve(client)).json()
        assert (page["total"], page["erreurs"]) == (5, 2)
        assert page["elements"][0]["repondu_le"] >= page["elements"][-1]["repondu_le"]  # plus récent d'abord
        assert {"enonce", "reponse_donnee", "solution", "correction", "competence"} <= set(page["elements"][0])

    def test_filtre_des_erreurs(self, client):
        page = client.get("/eleves/moi/historique?erreurs=true", headers=connecter_eleve(client)).json()
        assert [r["correcte"] for r in page["elements"]] == [False, False]

    def test_nouvelle_reponse_apparait(self, client):
        h = connecter_eleve(client, "Emma", "TLE-C-DEMO")
        assert client.get("/eleves/moi/historique", headers=h).json()["total"] == 0
        seance = client.post("/seances", headers=h).json()["id"]
        q = client.get(f"/seances/{seance}/question", headers=h).json()
        client.post(f"/seances/{seance}/reponses", headers=h, json={"question_id": q["id"], "reponse_donnee": "x"})
        [r] = client.get("/eleves/moi/historique", headers=h).json()["elements"]
        assert (r["question_id"], r["reponse_donnee"], r["correcte"]) == (q["id"], "x", False)

    def test_professeur_suit_son_eleve_seulement(self, client):
        h = connecter_enseignant(client)
        lina = next(e for c in client.get("/enseignants/classes", headers=h).json()
                    for e in client.get(f"/enseignants/classes/{c['id']}/eleves", headers=h).json() if e["prenom"] == "Lina")
        assert client.get(f"/enseignants/eleves/{lina['id']}/historique", headers=h).json()["total"] == 5
        admin = connecter_admin(client)
        cree = client.post("/admin/enseignants", headers=admin, json={"nom": "Autre", "email": "autre@lycee.fr"}).json()
        jeton = client.post("/enseignants/connexion", json={"email": "autre@lycee.fr", "mot_de_passe": cree["mot_de_passe_provisoire"]}).json()["jeton"]
        jeton = client.post("/enseignants/mot-de-passe", headers=entete(jeton),
                            json={"actuel": cree["mot_de_passe_provisoire"], "nouveau": "un-autre-mot-de-passe"}).json()["jeton"]
        assert client.get(f"/enseignants/eleves/{lina['id']}/historique", headers=entete(jeton)).status_code == 404


class TestSeanceCiblee:
    def test_seulement_les_questions_de_la_competence(self, client):
        h = connecter_eleve(client, "Hugo", "1RE-B-DEMO")
        competence = _competence(client, h, "1RE-SUI-TERME")
        seance = client.post("/seances", headers=h, json={"competence_ids": [competence]}).json()
        assert [c["id"] for c in seance["competences"]] == [competence]
        for _ in range(4):
            q = client.get(f"/seances/{seance['id']}/question", headers=h).json()
            assert q["competence_id"] == competence
            client.post(f"/seances/{seance['id']}/reponses", headers=h, json={"question_id": q["id"], "reponse_donnee": "0"})

    def test_competence_d_un_chapitre_ferme_refusee(self, client):
        h = connecter_eleve(client)  # Lina, Seconde : les compétences de Terminale ne sont pas ouvertes
        h_hugo = connecter_eleve(client, "Hugo", "1RE-B-DEMO")
        competence = _competence(client, h_hugo, "1RE-SUI-TERME")
        assert client.post("/seances", headers=h, json={"competence_ids": [competence]}).status_code == 422


class TestPartieDuCours:
    def test_resultat_indique_la_partie_du_cours(self, client):
        """Même sans correction détaillée, l'élève sait quelle compétence et quel résumé de cours utiliser."""
        h = connecter_eleve(client)
        seance = client.post("/seances", headers=h).json()["id"]
        q = client.get(f"/seances/{seance}/question", headers=h).json()
        r = client.post(f"/seances/{seance}/reponses", headers=h, json={"question_id": q["id"], "reponse_donnee": "x"}).json()
        assert r["competence"] and r["rappel"]

    def test_probabilites_conditionnelles_corrigees(self, client):
        h = connecter_eleve(client, "Hugo", "1RE-B-DEMO")
        competence = _competence(client, h, "1RE-COND")
        seance = client.post("/seances", headers=h, json={"competence_ids": [competence]}).json()["id"]
        q = client.get(f"/seances/{seance}/question", headers=h).json()
        r = client.post(f"/seances/{seance}/reponses", headers=h, json={"question_id": q["id"], "reponse_donnee": "0"}).json()
        assert r["correction"]["methode"] and r["correction"]["etapes"]


class TestMethodePKP:
    def test_seance_limitee_aux_niveaux_4_et_5(self, client):
        h = connecter_eleve(client, "Hugo", "1RE-B-DEMO")
        competence = _competence(client, h, "1RE-SD-CANON")
        seance = client.post(
            "/seances", headers=h, json={"competence_ids": [competence], "difficulte_min": 4, "difficulte_max": 5}
        ).json()
        assert (seance["difficulte_min"], seance["difficulte_max"]) == (4, 5)
        for _ in range(3):
            q = client.get(f"/seances/{seance['id']}/question", headers=h).json()
            assert q["difficulte"] >= 4
            client.post(f"/seances/{seance['id']}/reponses", headers=h, json={"question_id": q["id"], "reponse_donnee": "0"})

    def test_niveaux_incoherents_refuses(self, client):
        h = connecter_eleve(client, "Hugo", "1RE-B-DEMO")
        assert client.post("/seances", headers=h, json={"difficulte_min": 5, "difficulte_max": 2}).status_code == 422

    def test_avancement(self, client):
        h = connecter_eleve(client)  # Lina : 2 bonnes réponses en fractions (démo)
        competence = _competence(client, h, "2NDE-FRAC")
        av = client.get(f"/eleves/moi/competences/{competence}/avancement", headers=h).json()
        assert (av["objectif_bases"], av["objectif_avancees"]) == (3, 2)
        assert 0 <= av["maitrise"] <= 1 and av["reussies_bases"] <= av["reponses"]
        autre = _competence(client, connecter_eleve(client, "Hugo", "1RE-B-DEMO"), "1RE-SD-CANON")
        assert client.get(f"/eleves/moi/competences/{autre}/avancement", headers=h).status_code == 404
