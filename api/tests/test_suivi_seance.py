"""Ticket #28 : tableau de bord du professeur en séance et demandes « Je n'ai pas compris »."""

import pytest
from sqlalchemy import select

from app.admin import creer_enseignant
from app.db import models
from tests.conftest import connecter_eleve, connecter_enseignant

TABLEAU = "/enseignants/seance-en-direct"


def seance(client, h) -> int:
    r = client.post("/seances", headers=h)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def repondre(client, h, s, reponse="faux") -> dict:
    q = client.get(f"/seances/{s}/question", headers=h).json()
    client.post(f"/seances/{s}/reponses", headers=h, json={"question_id": q["id"], "reponse_donnee": reponse})
    return q


def competence_ouverte(session, prenom="Lina") -> int:
    eleve = session.scalars(select(models.Eleve).where(models.Eleve.prenom == prenom)).first()
    chapitre = next(c for c in eleve.classe.chapitres_proposes if not c.masque)
    return next(c.id for c in chapitre.competences if not c.masque)


@pytest.fixture
def autre_prof(client, fabrique):
    with fabrique() as s:
        creer_enseignant(s, "autre@pkp.test", "Autre", "autre-mot-de-passe")
    return connecter_enseignant(client, "autre@pkp.test", "autre-mot-de-passe")


class TestCours:
    def test_j_ai_compris_puis_change_d_avis(self, client, session):
        cid = competence_ouverte(session)
        h = connecter_eleve(client)
        assert client.get(f"/eleves/moi/comprehension/{cid}", headers=h).json()["compris"] is None
        assert client.post("/eleves/moi/comprehension", headers=h, json={"competence_id": cid, "compris": False}).json()["compris"] is False
        prof = connecter_enseignant(client)
        t = client.get(TABLEAU, headers=prof).json()
        assert [(d["eleve"], d["objet"]) for d in t["demandes_cours"]] == [("Lina", "cours")]
        assert t["compteurs"]["demandes_cours"] == 1
        # Changement d'avis : la demande disparaît du tableau, l'historique reste en base.
        client.post("/eleves/moi/comprehension", headers=h, json={"competence_id": cid, "compris": True})
        assert client.get(TABLEAU, headers=prof).json()["demandes_cours"] == []
        assert client.get(f"/eleves/moi/comprehension/{cid}", headers=h).json()["compris"] is True
        assert session.query(models.DemandeAide).filter_by(competence_id=cid).count() == 2

    def test_meme_avis_repete_n_ajoute_rien(self, client, session):
        cid = competence_ouverte(session)
        h = connecter_eleve(client)
        for _ in range(3):
            client.post("/eleves/moi/comprehension", headers=h, json={"competence_id": cid, "compris": False})
        assert session.query(models.DemandeAide).filter_by(competence_id=cid).count() == 1

    def test_cours_hors_classe_refuse(self, client, session):
        autre = competence_ouverte(session, "Hugo")  # compétence de 1re
        h = connecter_eleve(client)
        assert client.post("/eleves/moi/comprehension", headers=h, json={"competence_id": autre, "compris": False}).status_code == 404


class TestExercices:
    def test_erreurs_reussites_et_non_reponses(self, client):
        h = connecter_eleve(client, "Yanis")
        s = seance(client, h)
        q = repondre(client, h, s)
        prof = connecter_enseignant(client)
        t = client.get(TABLEAU, headers=prof).json()
        ligne = next(l for l in t["questions"] if l["question_id"] == q["id"])
        assert ligne["nb_erreurs"] == 1 and ligne["eleves_en_echec"] == ["Yanis"] and ligne["taux_erreur"] == 1.0
        assert ligne["solution"] and "enonce" in ligne
        # Question suivante affichée, sans réponse : non-réponse, pas une erreur.
        suivante = client.get(f"/seances/{s}/question", headers=h).json()
        t = client.get(TABLEAU, headers=prof).json()
        attente = next(l for l in t["questions"] if l["question_id"] == suivante["id"])
        assert attente["eleves_sans_reponse"] == ["Yanis"] and attente["nb_tentatives"] == 0
        assert t["compteurs"]["eleves_actifs"] == 1
        assert t["notions"] and t["notions"][0]["nb_eleves_en_difficulte"] == 1
        # « Erreurs uniquement » : la question sans tentative disparaît.
        filtre = client.get(f"{TABLEAU}?erreurs_uniquement=true", headers=prof).json()
        assert {l["question_id"] for l in filtre["questions"]} == {q["id"]}

    def test_demande_sur_exercice_et_corrige_puis_traitement(self, client):
        h = connecter_eleve(client)
        s = seance(client, h)
        q = repondre(client, h, s)
        r = client.post(f"/seances/{s}/aide", headers=h, json={"question_id": q["id"], "objet": "corrige"})
        assert r.status_code == 201 and r.json()["statut"] == "ouverte"
        # Doublon : la même demande en cours est renvoyée.
        assert client.post(f"/seances/{s}/aide", headers=h, json={"question_id": q["id"], "objet": "corrige"}).json()["id"] == r.json()["id"]
        prof = connecter_enseignant(client)
        t = client.get(TABLEAU, headers=prof).json()
        assert t["compteurs"]["demandes_corriges"] == 1 and t["demandes_exercices"][0]["question_id"] == q["id"]
        d = t["demandes_exercices"][0]["id"]
        assert client.post(f"/enseignants/demandes/{d}", headers=prof, json={"statut": "prise-en-charge"}).json()["statut"] == "prise-en-charge"
        assert client.post(f"/enseignants/demandes/{d}", headers=prof, json={"statut": "resolue"}).json()["traitee_par"] == "Enseignant Démo"
        t = client.get(TABLEAU, headers=prof).json()
        assert t["demandes_exercices"] == [] and t["compteurs"]["resolues"] == 1

    def test_aide_seulement_apres_une_reponse(self, client):
        h = connecter_eleve(client)
        s = seance(client, h)
        q = client.get(f"/seances/{s}/question", headers=h).json()
        assert client.post(f"/seances/{s}/aide", headers=h, json={"question_id": q["id"], "objet": "exercice"}).status_code == 409


class TestDroitsEtExport:
    def test_autre_professeur_ne_voit_rien(self, client, session, autre_prof):
        cid = competence_ouverte(session)
        h = connecter_eleve(client)
        client.post("/eleves/moi/comprehension", headers=h, json={"competence_id": cid, "compris": False})
        repondre(client, h, seance(client, h))
        t = client.get(TABLEAU, headers=autre_prof).json()
        assert t["questions"] == [] and t["demandes_cours"] == [] and t["compteurs"]["eleves_actifs"] == 0
        assert client.get(f"{TABLEAU}?classe_id=1", headers=autre_prof).status_code == 404
        d = session.scalars(select(models.DemandeAide)).first()
        assert client.post(f"/enseignants/demandes/{d.id}", headers=autre_prof, json={"statut": "resolue"}).status_code == 404
        assert client.get(TABLEAU, headers=h).status_code == 401

    def test_filtre_par_classe(self, client):
        repondre(client, (h := connecter_eleve(client, "Hugo", "1RE-B-DEMO")), seance(client, h))
        prof = connecter_enseignant(client)
        classes = {c["code"]: c["id"] for c in client.get("/enseignants/classes", headers=prof).json()}
        assert client.get(f"{TABLEAU}?classe_id={classes['2NDE-A-DEMO']}", headers=prof).json()["questions"] == []
        assert client.get(f"{TABLEAU}?classe_id={classes['1RE-B-DEMO']}", headers=prof).json()["questions"]

    def test_export_agrege_sans_prenom(self, client):
        h = connecter_eleve(client, "Yanis")
        repondre(client, h, seance(client, h))
        r = client.get(f"{TABLEAU}/export.csv", headers=connecter_enseignant(client))
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
        assert "Yanis" not in r.text and "Tentatives" in r.text

    def test_periode_vide(self, client):
        h = connecter_eleve(client, "Yanis")
        repondre(client, h, seance(client, h))
        t = client.get(f"{TABLEAU}?depuis=2020-01-01T00:00:00Z&jusqua=2020-01-02T00:00:00Z", headers=connecter_enseignant(client)).json()
        assert t["questions"] == [] and t["notions"] == []


def test_dates_avec_fuseau(client, session):
    """SQLite rend des dates sans fuseau : l'API les renvoie en UTC explicite (sinon le navigateur décale l'heure)."""
    h = connecter_eleve(client)
    cid = competence_ouverte(session)
    assert client.post("/eleves/moi/comprehension", headers=h, json={"competence_id": cid, "compris": False}).json()["le"].endswith("Z")
    t = client.get(TABLEAU, headers=connecter_enseignant(client)).json()
    assert t["demandes_cours"][0]["cree_le"].endswith("Z")
