"""Comptes parents : création par le professeur, connexion, suivi, code choisi pour l'enfant, réinitialisation."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.db import models
from app.purge import purger
from app.security import hacher_mot_de_passe
from tests.conftest import CODES_DEMO, connecter_admin, connecter_eleve, connecter_enseignant, entete

LINA = 1  # 2NDE-A-DEMO, enseignant de démo
EMAIL = "parent.lina@exemple.fr"
NOUVEAU_MDP = "un-mot-de-passe-solide"


def creer_parent(client, eleve_id: int = LINA, email: str = EMAIL) -> dict:
    r = client.post(f"/enseignants/eleves/{eleve_id}/parents", headers=connecter_enseignant(client), json={"email": email})
    assert r.status_code == 201, r.text
    return r.json()


def connecter_parent(client, email: str = EMAIL, mot_de_passe: str | None = None) -> dict:
    """Crée le compte, change le mot de passe provisoire et renvoie l'en-tête d'un parent prêt."""
    provisoire = creer_parent(client, email=email)["mot_de_passe_provisoire"]
    jeton = client.post("/parents/connexion", json={"email": email, "mot_de_passe": provisoire}).json()["jeton"]
    r = client.post("/parents/mot-de-passe", headers=entete(jeton), json={"actuel": provisoire, "nouveau": NOUVEAU_MDP})
    assert r.status_code == 200, r.text
    return entete(r.json()["jeton"])


@pytest.fixture
def autre_enseignant(client, fabrique):
    with fabrique() as s:
        s.add(models.Enseignant(nom="Autre", email="autre@pkp.test", mot_de_passe_hash=hacher_mot_de_passe("autre-mdp")))
        s.commit()
    return connecter_enseignant(client, "autre@pkp.test", "autre-mdp")


class TestCreationParLeProfesseur:
    def test_creation_avec_mot_de_passe_provisoire(self, client):
        cree = creer_parent(client, email=" Parent.Lina@Exemple.FR ")
        assert cree["parent"]["email"] == EMAIL and cree["parent"]["mdp_provisoire"]
        assert cree["parent"]["enfants"] == ["Lina (2NDE-A-DEMO)"]
        assert len(cree["mot_de_passe_provisoire"]) == 16
        h = connecter_enseignant(client)
        assert [p["email"] for p in client.get(f"/enseignants/eleves/{LINA}/parents", headers=h).json()] == [EMAIL]

    def test_compte_existant_rattache_sans_nouveau_mot_de_passe(self, client, session):
        creer_parent(client)
        yanis = session.scalar(select(models.Eleve.id).where(models.Eleve.prenom == "Yanis"))
        second = creer_parent(client, eleve_id=yanis)
        assert second["mot_de_passe_provisoire"] is None
        assert sorted(second["parent"]["enfants"]) == ["Lina (2NDE-A-DEMO)", "Yanis (2NDE-A-DEMO)"]
        assert session.scalar(select(func.count(models.Parent.id))) == 1

    def test_email_invalide_refuse(self, client):
        h = connecter_enseignant(client)
        assert client.post(f"/enseignants/eleves/{LINA}/parents", headers=h, json={"email": "pas-un-email"}).status_code == 422

    def test_un_professeur_ne_gere_que_ses_eleves(self, client, autre_enseignant):
        parent_id = creer_parent(client)["parent"]["id"]
        assert client.post(f"/enseignants/eleves/{LINA}/parents", headers=autre_enseignant, json={"email": EMAIL}).status_code == 404
        assert client.get(f"/enseignants/eleves/{LINA}/parents", headers=autre_enseignant).status_code == 404
        assert client.post(f"/enseignants/parents/{parent_id}/mot-de-passe", headers=autre_enseignant).status_code == 404

    def test_detacher_le_dernier_enfant_supprime_le_compte(self, client, session):
        parent_id = creer_parent(client)["parent"]["id"]
        h = connecter_enseignant(client)
        assert client.delete(f"/enseignants/eleves/{LINA}/parents/{parent_id}", headers=h).json() == []
        assert session.get(models.Parent, parent_id) is None


class TestConnexion:
    def test_mot_de_passe_provisoire_a_changer_d_abord(self, client):
        provisoire = creer_parent(client)["mot_de_passe_provisoire"]
        r = client.post("/parents/connexion", json={"email": EMAIL, "mot_de_passe": provisoire})
        assert r.status_code == 200 and r.json()["mdp_provisoire"]
        assert client.get("/parents/enfants", headers=entete(r.json()["jeton"])).status_code == 403

    def test_mauvais_mot_de_passe(self, client):
        creer_parent(client)
        assert client.post("/parents/connexion", json={"email": EMAIL, "mot_de_passe": "faux"}).status_code == 401
        assert client.post("/parents/connexion", json={"email": "inconnu@x.fr", "mot_de_passe": "faux"}).status_code == 401

    def test_blocage_apres_plusieurs_echecs(self, client):
        creer_parent(client)
        for _ in range(5):
            client.post("/parents/connexion", json={"email": EMAIL, "mot_de_passe": "faux"})
        assert client.post("/parents/connexion", json={"email": EMAIL, "mot_de_passe": "faux"}).status_code == 429

    def test_un_jeton_eleve_ou_professeur_n_ouvre_pas_l_espace_parent(self, client):
        assert client.get("/parents/enfants", headers=connecter_eleve(client)).status_code == 401
        assert client.get("/parents/enfants", headers=connecter_enseignant(client)).status_code == 401

    def test_reinitialisation_par_le_professeur_ferme_les_sessions(self, client):
        h = connecter_parent(client)
        parent_id = client.get(f"/enseignants/eleves/{LINA}/parents", headers=connecter_enseignant(client)).json()[0]["id"]
        r = client.post(f"/enseignants/parents/{parent_id}/mot-de-passe", headers=connecter_enseignant(client))
        assert r.status_code == 200 and r.json()["parent"]["mdp_provisoire"]
        assert client.get("/parents/enfants", headers=h).status_code == 401
        nouveau = r.json()["mot_de_passe_provisoire"]
        assert client.post("/parents/connexion", json={"email": EMAIL, "mot_de_passe": nouveau}).status_code == 200

    def test_reinitialisation_par_un_administrateur_journalisee(self, client, session):
        connecter_parent(client)
        admin = connecter_admin(client)
        trouves = client.get("/admin/parents", headers=admin, params={"q": "lina@"}).json()["elements"]
        assert [p["email"] for p in trouves] == [EMAIL]
        r = client.post(f"/admin/parents/{trouves[0]['id']}/reinitialiser", headers=admin)
        assert r.status_code == 200 and r.json()["mot_de_passe_provisoire"]
        assert session.scalar(select(models.JournalAdmin).where(models.JournalAdmin.objet == "parent")) is not None

    def test_recherche_admin_exige_trois_caracteres(self, client):
        assert client.get("/admin/parents", headers=connecter_admin(client), params={"q": "a"}).status_code == 422


class TestSuivi:
    def test_liste_des_enfants(self, client):
        h = connecter_parent(client)
        enfants = client.get("/parents/enfants", headers=h).json()
        assert [e["prenom"] for e in enfants] == ["Lina"]
        lina = enfants[0]
        assert lina["code_classe"] == "2NDE-A-DEMO" and lina["nb_reponses"] > 0 and lina["competences_total"] > 0

    def test_tableau_de_bord(self, client):
        h = connecter_parent(client)
        t = client.get(f"/parents/enfants/{LINA}", headers=h).json()
        assert len(t["activite"]) == 14
        assert t["chapitres"] and t["progression"]
        assert sum(c["competences_total"] for c in t["chapitres"]) == len(t["progression"])

    def test_activite_et_temps_de_travail(self, client):
        h = connecter_parent(client)
        eleve = connecter_eleve(client)
        s = client.post("/seances", headers=eleve).json()["id"]
        q = client.get(f"/seances/{s}/question", headers=eleve).json()
        client.post(f"/seances/{s}/reponses", headers=eleve, json={"question_id": q["id"], "reponse_donnee": "1"})
        t = client.get(f"/parents/enfants/{LINA}", headers=h).json()
        aujourd_hui = datetime.now(UTC).date().isoformat()
        assert t["activite"][-1]["jour"] == aujourd_hui and t["activite"][-1]["nb_reponses"] >= 1
        assert t["seances_30_jours"] >= 1 and t["enfant"]["derniere_activite"]

    def test_historique(self, client):
        h = connecter_parent(client)
        page = client.get(f"/parents/enfants/{LINA}/historique", headers=h).json()
        assert page["total"] > 0 and page["elements"][0]["solution"]

    def test_pas_d_acces_aux_autres_eleves(self, client, session):
        h = connecter_parent(client)
        yanis = session.scalar(select(models.Eleve.id).where(models.Eleve.prenom == "Yanis"))
        assert client.get(f"/parents/enfants/{yanis}", headers=h).status_code == 404
        assert client.get(f"/parents/enfants/{yanis}/historique", headers=h).status_code == 404
        assert client.put(f"/parents/enfants/{yanis}/code", headers=h, json={"code": "MATHS2026X"}).status_code == 404

    def test_professeur_desactive_masque_l_enfant(self, client, session):
        h = connecter_parent(client)
        session.get(models.Eleve, LINA).classe.enseignant.actif = False
        session.commit()
        assert client.get("/parents/enfants", headers=h).json() == []


class TestCodeChoisi:
    def test_le_parent_choisit_le_code_de_l_enfant(self, client):
        h = connecter_parent(client)
        ancien = connecter_eleve(client)
        r = client.put(f"/parents/enfants/{LINA}/code", headers=h, json={"code": "maths-2026-k"})
        assert r.status_code == 200, r.text
        identifiant = r.json()["identifiant"]
        # L'ancien code et les sessions ouvertes de l'enfant cessent de fonctionner.
        assert client.get("/eleves/moi/progression", headers=ancien).status_code == 401
        assert client.post("/eleves/connexion", json={"prenom": "Lina", "code_classe": "2NDE-A-DEMO", "code_personnel": CODES_DEMO["Lina"]}).status_code == 401
        r = client.post("/eleves/connexion/identifiant", json={"identifiant": identifiant, "code_personnel": "MATHS2026K"})
        assert r.status_code == 200, r.text

    @pytest.mark.parametrize(
        "code",
        ["AB12", "ABCDEFGHIJKLMNOPQ9", "MATHSMATHS", "1234567890", "AAAA1111", "LINA2026XY", "MATHS2026É", "AZERTY123"],
    )
    def test_codes_refuses(self, client, code):
        h = connecter_parent(client)
        r = client.put(f"/parents/enfants/{LINA}/code", headers=h, json={"code": code})
        assert r.status_code == 422, code

    def test_le_code_vaut_pour_les_inscriptions_reliees(self, client, session):
        lina = session.get(models.Eleve, LINA)
        autre_classe = session.scalar(select(models.Classe).where(models.Classe.id != lina.classe_id, models.Classe.enseignant_id == lina.classe.enseignant_id))
        double = models.Eleve(prenom="Lina", classe=autre_classe, groupe_id=lina.id, code_hash=lina.code_hash)
        lina.groupe_id = lina.id
        session.add(double)
        session.commit()
        h = connecter_parent(client)
        assert {e["code_classe"] for e in client.get("/parents/enfants", headers=h).json()} == {"2NDE-A-DEMO", autre_classe.code}
        client.put(f"/parents/enfants/{LINA}/code", headers=h, json={"code": "MATHS2026K"})
        session.expire_all()
        assert session.get(models.Eleve, double.id).code_hash == session.get(models.Eleve, LINA).code_hash


class TestRgpd:
    def test_supprimer_l_eleve_supprime_le_compte_parent(self, client, session):
        parent_id = creer_parent(client)["parent"]["id"]
        assert client.delete(f"/enseignants/eleves/{LINA}", headers=connecter_enseignant(client)).status_code == 204
        session.expire_all()
        assert session.get(models.Parent, parent_id) is None

    def test_la_purge_supprime_les_comptes_parents_orphelins(self, client, session):
        parent_id = creer_parent(client)["parent"]["id"]
        purger(session, retention_jours=365, maintenant=datetime.now(UTC) + timedelta(days=400))
        assert session.get(models.Parent, parent_id) is None

    def test_un_parent_qui_suit_encore_un_enfant_est_garde(self, client, session):
        parent_id = creer_parent(client)["parent"]["id"]
        yanis = session.scalar(select(models.Eleve.id).where(models.Eleve.prenom == "Yanis"))
        creer_parent(client, eleve_id=yanis)
        assert client.delete(f"/enseignants/eleves/{LINA}", headers=connecter_enseignant(client)).status_code == 204
        session.expire_all()
        assert session.get(models.Parent, parent_id) is not None
