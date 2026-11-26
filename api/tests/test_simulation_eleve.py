# Issue #184 — Vue élève simulée (Claude)
"""Vue élève simulée (issue #184) : le professeur ou l'administrateur parcourt l'espace élève avec un élève fictif,
sans pouvoir d'adulte, sans toucher aux données réelles, et sans apparaître dans les listes et statistiques."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app import purge, simulation
from app.admin import creer_enseignant
from app.db import models
from app.db.simulation import INCLURE
from app.security import hacher_mot_de_passe
from tests.conftest import connecter_admin, connecter_eleve, connecter_enseignant, entete


def _classe_id(client, h, code="2NDE-A-DEMO") -> int:
    return next(c["classe_id"] for c in client.get("/enseignants/simulation/classes", headers=h).json()
                if c["code_classe"] == code)


def _ouvrir(client, h, classe_id: int, admin: bool = False) -> dict:
    r = client.post("/admin/simulation" if admin else "/enseignants/simulation", headers=h, json={"classe_id": classe_id})
    assert r.status_code == 200, r.text
    return r.json()


def _repondre(client, h) -> dict:
    s = client.post("/seances", headers=h)
    assert s.status_code == 201, s.text
    q = client.get(f"/seances/{s.json()['id']}/question", headers=h)
    assert q.status_code == 200, q.text
    assert "solution" not in q.json()  # ARCH-4 : aucune solution avant la réponse
    r = client.post(f"/seances/{s.json()['id']}/reponses", headers=h,
                    json={"question_id": q.json()["id"], "reponse_donnee": "42"})
    assert r.status_code == 200, r.text
    return r.json()


def _fictifs(session) -> int:
    return session.scalar(
        select(func.count(models.Eleve.id)).where(models.Eleve.simulation_par_id.is_not(None))
        .execution_options(**{INCLURE: True})
    )


@pytest.fixture
def prof(client):
    return connecter_enseignant(client)


@pytest.fixture
def sim(client, prof) -> dict:
    ouverte = _ouvrir(client, prof, _classe_id(client, prof))
    ouverte["h"] = entete(ouverte["jeton"])
    return ouverte


def test_le_professeur_choisit_parmi_ses_classes(client, prof):
    classes = client.get("/enseignants/simulation/classes", headers=prof).json()
    assert [c["code_classe"] for c in classes] == ["1RE-B-DEMO", "2NDE-A-DEMO", "TLE-C-DEMO"]
    assert all(c["matiere"] == "maths" and not c["en_cours"] for c in classes)


def test_le_professeur_parcourt_l_espace_eleve(client, sim):
    assert sim["simulation"]["role"] == "enseignant" and sim["simulation"]["code_classe"] == "2NDE-A-DEMO"
    moi = client.get("/eleves/moi", headers=sim["h"]).json()
    assert moi["prenom"].startswith("Élève fictif") and moi["identifiant"] is None
    assert client.get("/eleves/moi/simulation", headers=sim["h"]).json()["matiere"] == "maths"
    assert client.get("/eleves/moi/chapitres", headers=sim["h"]).json()  # mêmes chapitres que la classe
    resultat = _repondre(client, sim["h"])
    assert "solution" in resultat  # correction reçue après la réponse
    historique = client.get("/eleves/moi/historique", headers=sim["h"]).json()
    assert historique["total"] == 1
    assert client.get("/eleves/moi/progression", headers=sim["h"]).status_code == 200


def test_memes_chapitres_qu_un_vrai_eleve(client, sim):
    lina = connecter_eleve(client)
    assert client.get("/eleves/moi/chapitres", headers=sim["h"]).json() == client.get("/eleves/moi/chapitres", headers=lina).json()


def test_aucune_trace_dans_les_donnees_reelles(client, session, prof, sim):
    admin = connecter_admin(client)
    avant = client.get("/admin/statistiques?periode=30", headers=admin).json()
    classe_id = sim["simulation"]["classe_id"]
    _repondre(client, sim["h"])
    competence = session.scalars(select(models.Competence)).first()
    client.post("/eleves/moi/comprehension", headers=sim["h"], json={"competence_id": competence.id, "compris": False})

    eleves = client.get(f"/enseignants/classes/{classe_id}/eleves", headers=prof).json()
    assert [e["prenom"] for e in eleves] == ["Inès", "Lina", "Yanis"]
    direct = client.get("/enseignants/seance-en-direct", headers=prof).json()
    assert direct["demandes_cours"] == [] and "fictif" not in str(direct)
    apres = client.get("/admin/statistiques?periode=30", headers=admin).json()
    for cle in ("eleves_total", "eleves_actifs", "reponses", "seances"):
        assert apres[cle] == avant[cle], cle
    page = client.get("/admin/eleves", headers=admin).json()
    assert page["total"] == 5 and all("fictif" not in e["prenom"] for e in page["elements"])
    assert "fictif" not in client.get("/admin/recherche?q=fictif", headers=admin).text
    # La réponse existe bien en base, mais seulement pour la simulation.
    assert _fictifs(session) == 1
    assert session.scalar(select(func.count(models.Reponse.id))) == 7


def test_aucun_pouvoir_d_adulte(client, sim):
    for methode, chemin in [("get", "/enseignants/classes"), ("get", "/enseignants/simulation/classes"),
                            ("get", "/admin/eleves"), ("get", "/admin/simulation/classes"),
                            ("get", "/enseignants/seance-en-direct"), ("get", "/admin/statistiques")]:
        assert getattr(client, methode)(chemin, headers=sim["h"]).status_code in (401, 403), chemin
    # Ni rouvrir une simulation, ni ouvrir celle d'une autre classe avec le jeton élève.
    r = client.post("/enseignants/simulation", headers=sim["h"], json={"classe_id": sim["simulation"]["classe_id"]})
    assert r.status_code == 401


def test_connexion_impossible_avec_le_prenom_fictif(client, sim):
    r = client.post("/eleves/connexion", json={"prenom": sim["eleve"]["prenom"], "code_classe": "2NDE-A-DEMO",
                                                 "code_personnel": "AAAAAA"})
    assert r.status_code in (401, 422)


def test_autre_professeur_et_url_modifiee_refuses(client, session, prof):
    classe_id = _classe_id(client, prof)
    creer_enseignant(session, "autre@pkp.test", "Autre", "autre-mot-de-passe-1")
    autre = connecter_enseignant(client, "autre@pkp.test", "autre-mot-de-passe-1")
    assert client.get("/enseignants/simulation/classes", headers=autre).json() == []
    assert client.post("/enseignants/simulation", headers=autre, json={"classe_id": classe_id}).status_code == 404
    assert client.post("/enseignants/simulation", headers=prof, json={"classe_id": 999}).status_code == 404


def test_un_vrai_eleve_n_a_pas_de_simulation(client):
    lina = connecter_eleve(client)
    assert client.get("/eleves/moi/simulation", headers=lina).status_code == 404
    assert client.post("/eleves/moi/simulation/reinitialiser", headers=lina).status_code == 404
    assert client.post("/eleves/moi/simulation/fermer", headers=lina).status_code == 404


def test_l_administrateur_a_son_propre_eleve_fictif(client, session, prof, sim):
    admin = connecter_admin(client)
    classes = client.get("/admin/simulation/classes", headers=admin).json()
    assert {"1RE-B-DEMO", "2NDE-A-DEMO", "TLE-C-DEMO"} <= {c["code_classe"] for c in classes}
    ouverte = _ouvrir(client, admin, sim["simulation"]["classe_id"], admin=True)
    assert ouverte["simulation"]["role"] == "admin" and ouverte["eleve"]["id"] != sim["eleve"]["id"]
    h = entete(ouverte["jeton"])
    assert "solution" in _repondre(client, h)
    # Vue élève stricte : aucune route d'administration avec ce jeton.
    assert client.get("/admin/statistiques", headers=h).status_code == 401
    # Le travail de l'un n'apparaît pas chez l'autre.
    assert client.get("/eleves/moi/historique", headers=sim["h"]).json()["total"] == 0
    assert client.get("/eleves/moi/historique", headers=h).json()["total"] == 1
    assert _fictifs(session) == 2


def test_reprise_et_nouvel_onglet(client, prof, sim):
    _repondre(client, sim["h"])
    assert next(c for c in client.get("/enseignants/simulation/classes", headers=prof).json()
                if c["code_classe"] == "2NDE-A-DEMO")["en_cours"]
    reprise = _ouvrir(client, prof, sim["simulation"]["classe_id"])
    assert reprise["eleve"]["id"] == sim["eleve"]["id"]
    # L'ancien jeton (autre onglet) est révoqué ; le travail est conservé.
    assert client.get("/eleves/moi", headers=sim["h"]).status_code == 401
    assert client.get("/eleves/moi/historique", headers=entete(reprise["jeton"])).json()["total"] == 1


def test_reinitialisation(client, session, sim):
    _repondre(client, sim["h"])
    r = client.post("/eleves/moi/simulation/reinitialiser", headers=sim["h"])
    assert r.status_code == 200, r.text
    h = entete(r.json()["jeton"])
    assert client.get("/eleves/moi/historique", headers=h).json()["total"] == 0
    assert client.get("/eleves/moi", headers=sim["h"]).status_code == 401
    assert _fictifs(session) == 1
    assert session.scalar(select(func.count(models.Reponse.id)).execution_options(**{INCLURE: True})) == 7
    actions = [e.action for e in session.scalars(select(models.JournalAdmin).order_by(models.JournalAdmin.id))]
    assert actions[-2:] == ["simulation.ouverture", "simulation.reinitialisation"]


def test_retour_ferme_la_simulation(client, sim):
    assert client.post("/eleves/moi/simulation/fermer", headers=sim["h"]).status_code == 204
    assert client.get("/eleves/moi", headers=sim["h"]).status_code == 401


def test_revocation_par_l_acteur(client, session, sim):
    acteur = session.scalar(select(models.Enseignant).where(models.Enseignant.email == "demo@pkp.test"))
    acteur.mot_de_passe_hash = hacher_mot_de_passe("nouveau-mot-de-passe-1")
    session.commit()
    assert client.get("/eleves/moi", headers=sim["h"]).status_code == 401


def test_desactivation_du_professeur(client, session, sim):
    admin = connecter_admin(client)
    acteur = session.scalar(select(models.Enseignant).where(models.Enseignant.email == "demo@pkp.test"))
    r = client.post(f"/admin/enseignants/{acteur.id}/activation", headers=admin, json={"actif": False})
    assert r.status_code == 200, r.text
    assert client.get("/eleves/moi", headers=sim["h"]).status_code == 401


def test_classe_retiree_au_professeur(client, session, sim):
    autre = creer_enseignant(session, "repreneur@pkp.test", "Repreneur", "repreneur-mot-de-passe-1")
    classe = session.get(models.Classe, sim["simulation"]["classe_id"])
    classe.enseignant_id = autre.id
    session.commit()
    assert client.get("/eleves/moi", headers=sim["h"]).status_code == 401


def test_purge_des_eleves_fictifs(client, session, sim):
    _repondre(client, sim["h"])
    session.expire_all()
    purge.purger(session, retention_jours=10_000)
    assert _fictifs(session) == 1  # récent : conservé
    purge.purger(session, retention_jours=10_000, maintenant=datetime.now(UTC) + timedelta(days=simulation.JOURS_CONSERVATION + 1))
    assert _fictifs(session) == 0
    assert session.scalar(select(func.count(models.Eleve.id))) == 5  # aucun vrai élève touché


def test_domaine_ferme_comme_pour_un_vrai_eleve(client, prof, sim):
    admin = connecter_admin(client)
    assert client.post("/admin/domaines/maths-lycee", headers=admin, json={"actif": True, "public": False}).status_code == 200
    contexte = next(c for c in client.get("/enseignants/simulation/classes", headers=prof).json()
                    if c["code_classe"] == "2NDE-A-DEMO")
    assert not contexte["ouverte_aux_eleves"] and contexte["motif_fermeture"]
    lina = connecter_eleve(client)
    reel, fictif = client.post("/seances", headers=lina), client.post("/seances", headers=sim["h"])
    assert reel.status_code == fictif.status_code == 403
    assert reel.json() == fictif.json()


def test_filtre_global_sur_toutes_les_traces(client, session, sim):
    """Diagnostic, demandes d'aide et rédactions d'un élève fictif : invisibles de toute requête ordinaire."""
    eleve_id = sim["eleve"]["id"]
    question = session.scalars(select(models.Question)).first()
    session.add_all([
        models.DemandeAide(eleve_id=eleve_id, competence_id=question.competence_id, objet="cours", statut="ouverte"),
        models.ObservationDiagnostic(eleve_id=eleve_id, question_id=question.id, reponse_donnee="x",
                                     statut=models.StatutObservation.EN_ATTENTE),
        models.Redaction(eleve_id=eleve_id, question_id=question.id, texte="essai", statut="remise",
                         conserver_jusqu_au=datetime.now(UTC).date()),
        models.PassationDiagnostic(eleve_id=eleve_id),
    ])
    session.commit()
    session.expunge_all()
    for modele in (models.DemandeAide, models.ObservationDiagnostic, models.Redaction, models.PassationDiagnostic):
        assert session.scalars(select(modele)).all() == [], modele.__name__
        assert len(session.scalars(select(modele).execution_options(**{INCLURE: True})).all()) == 1
    classe = session.get(models.Classe, sim["simulation"]["classe_id"])
    assert all(e.simulation_par_id is None for e in classe.eleves)
