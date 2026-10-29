"""Phase 6 : droits RGPD (accès, effacement), purge automatique, comptes enseignant."""

from datetime import UTC, datetime, timedelta
from urllib.parse import unquote

import pytest
from sqlalchemy import func, select, update

from app.admin import ErreurAdmin, changer_mot_de_passe, creer_enseignant
from app.db import models
from app.purge import purger
from app.security import hacher_mot_de_passe
from tests.conftest import connecter_eleve, connecter_enseignant


def compter(session, modele) -> int:
    return session.scalar(select(func.count()).select_from(modele))


@pytest.fixture
def autre_enseignant(client, fabrique):
    with fabrique() as s:
        s.add(models.Enseignant(nom="Autre", email="autre@pkp.test", mot_de_passe_hash=hacher_mot_de_passe("autre-mot-de-passe")))
        s.commit()
    return connecter_enseignant(client, "autre@pkp.test", "autre-mot-de-passe")


class TestExport:
    def test_contenu_complet(self, client):
        r = client.get("/enseignants/eleves/1/export", headers=connecter_enseignant(client))
        assert r.status_code == 200
        assert unquote(r.headers["content-disposition"]) == "attachment; filename*=UTF-8''pkp-2NDE-A-DEMO-Lina.json"
        donnees = r.json()
        assert donnees["eleve"]["prenom"] == "Lina"
        assert donnees["eleve"]["classe"] == "2NDE-A-DEMO"
        reponses = [rep for s in donnees["seances"] for rep in s["reponses"]]
        assert len(reponses) == 5
        assert reponses[0] == {**reponses[0], "question": "Calculer 1/2 + 1/3.", "reponse_donnee": "5/6", "correcte": True}
        assert len(donnees["progression"]) == 5

    def test_accent_dans_le_nom_de_fichier(self, client):
        r = client.get("/enseignants/eleves/3/export", headers=connecter_enseignant(client))
        assert "Inès" in unquote(r.headers["content-disposition"])

    def test_reserve_a_l_enseignant_de_la_classe(self, client, autre_enseignant):
        assert client.get("/enseignants/eleves/1/export", headers=autre_enseignant).status_code == 404
        assert client.get("/enseignants/eleves/1/export", headers=connecter_eleve(client)).status_code == 401


class TestSuppressionClasse:
    def test_supprime_eleves_et_historique(self, client, session):
        jeton_lina = connecter_eleve(client, "Lina")
        h = connecter_enseignant(client)
        assert client.delete("/enseignants/classes/1", headers=h).status_code == 204
        assert [c["code"] for c in client.get("/enseignants/classes", headers=h).json()] == ["1RE-B-DEMO", "TLE-C-DEMO"]
        assert compter(session, models.Eleve) == 2
        assert compter(session, models.Reponse) == 0
        assert compter(session, models.Question) == 80  # la banque de questions reste
        assert client.get("/eleves/moi", headers=jeton_lina).status_code == 401

    def test_reserve_a_son_enseignant(self, client, autre_enseignant):
        assert client.delete("/enseignants/classes/1", headers=autre_enseignant).status_code == 404


class TestPurge:
    def test_rien_a_purger_juste_apres_l_activite(self, client, session):
        assert purger(session, retention_jours=365) == []
        assert compter(session, models.Eleve) == 5

    def test_tous_purges_apres_la_duree_de_conservation(self, client, session):
        dans_400_jours = datetime.now(UTC) + timedelta(days=400)
        purges = purger(session, retention_jours=365, maintenant=dans_400_jours)
        assert sorted(e.prenom for e in purges) == ["Emma", "Hugo", "Inès", "Lina", "Yanis"]
        assert compter(session, models.Eleve) == 0
        assert compter(session, models.Seance) == 0
        assert compter(session, models.Reponse) == 0
        assert compter(session, models.Classe) == 3  # les classes restent à l'enseignant

    def test_seule_la_derniere_activite_compte(self, client, session):
        # Lina : seule séance il y a 2 ans. Les autres : actifs récemment.
        lina = session.scalar(select(models.Eleve).where(models.Eleve.prenom == "Lina"))
        il_y_a_2_ans = datetime.now(UTC) - timedelta(days=730)
        session.execute(update(models.Seance).where(models.Seance.eleve_id == lina.id).values(debut=il_y_a_2_ans))
        session.execute(update(models.Eleve).where(models.Eleve.id == lina.id).values(cree_le=il_y_a_2_ans))
        session.commit()
        purges = purger(session, retention_jours=365)
        assert [e.prenom for e in purges] == ["Lina"]
        assert purges[0].derniere_activite.year == il_y_a_2_ans.year

    def test_une_seance_recente_protege_un_eleve_ancien(self, client, session):
        lina = session.scalar(select(models.Eleve).where(models.Eleve.prenom == "Lina"))
        session.execute(update(models.Eleve).where(models.Eleve.id == lina.id).values(cree_le=datetime.now(UTC) - timedelta(days=730)))
        session.commit()
        assert purger(session, retention_jours=365) == []

    def test_simulation_ne_supprime_rien(self, client, session):
        purges = purger(session, retention_jours=0, maintenant=datetime.now(UTC) + timedelta(days=1), simulation=True)
        assert len(purges) == 5
        assert compter(session, models.Eleve) == 5


class TestComptesEnseignant:
    def test_creer_puis_se_connecter(self, client, session):
        creer_enseignant(session, " Prof@Lycee.FR ", "Mme Martin", "un-mot-de-passe-long")
        r = client.post("/enseignants/connexion", json={"email": "prof@lycee.fr", "mot_de_passe": "un-mot-de-passe-long"})
        assert r.status_code == 200 and r.json()["nom"] == "Mme Martin"

    def test_refus(self, client, session):
        with pytest.raises(ErreurAdmin, match="12 caractères"):
            creer_enseignant(session, "a@b.fr", "A", "court")
        with pytest.raises(ErreurAdmin, match="existe déjà"):
            creer_enseignant(session, "demo@pkp.test", "Doublon", "un-mot-de-passe-long")

    def test_changer_le_mot_de_passe(self, client, session):
        changer_mot_de_passe(session, "demo@pkp.test", "nouveau-mot-de-passe")
        assert client.post("/enseignants/connexion", json={"email": "demo@pkp.test", "mot_de_passe": "demo-pkp-2026"}).status_code == 401
        connecter_enseignant(client, mot_de_passe="nouveau-mot-de-passe")
