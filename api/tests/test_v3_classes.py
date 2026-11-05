"""V3, Lot 3 : archivage des classes et des groupes en fin d'année, règle d'ouverture des domaines."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.db import models
from app.db.seed import EMAIL_ANGLAIS_DEMO
from tests.conftest import connecter_admin, connecter_enseignant, entete


def _famille(client, admin, email, enfants):
    r = client.post("/admin/familles", headers=admin, json={"email": email, "enfants": enfants})
    assert r.status_code == 201, r.text
    return r.json()["cartes"]


def _carte(client, carte):
    r = client.post("/enfants/connexion", json={"identifiant": carte["identifiant"], "code_personnel": carte["code"]})
    assert r.status_code == 200, r.text
    return r.json()


def _archiver(client, admin, chemin, ids, archiver=True, motif="Fin d'année 2025-2026"):
    r = client.post(chemin, headers=admin, json={"ids": ids, "archiver": archiver, "motif": motif})
    assert r.status_code == 200, r.text
    return r.json()["traites"]


def test_archiver_une_classe_garde_le_travail_et_ferme_l_acces(client, session):
    admin = connecter_admin(client)
    [ines] = _famille(client, admin, "arch@x.test", [{"prenom": "Inès", "niveau": "2nde"}])
    prof = connecter_enseignant(client)
    classe = client.post("/enseignants/classes", headers=prof, json={"niveau": "2nde", "parcours": "tronc-commun"}).json()
    client.post(f"/enseignants/classes/{classe['id']}/enfants", headers=prof, json={"enfant_ids": [ines["id"]]})
    eleve = session.scalar(select(models.Eleve).where(models.Eleve.enfant_id == ines["id"]))
    q = session.scalar(select(models.Question).limit(1))
    maintenant = datetime.now(UTC)
    seance = models.Seance(eleve_id=eleve.id, debut=maintenant, fin=maintenant + timedelta(minutes=5))
    session.add(seance)
    session.flush()
    session.add(models.Reponse(seance_id=seance.id, question_id=q.id, reponse_donnee="1", correcte=True, duree_s=2.0))
    session.commit()
    connexion = _carte(client, ines)
    jeton_maths = client.post(f"/enfants/moi/maths/{eleve.id}", headers=entete(connexion["jeton"])).json()["jeton"]

    assert _archiver(client, admin, "/admin/classes/archivage", [classe["id"]]) == 1
    # Rien n'est supprimé.
    assert session.scalar(select(func.count(models.Reponse.id)).where(models.Reponse.seance_id == seance.id)) == 1
    assert session.get(models.Eleve, eleve.id) is not None
    # L'élève ne la voit plus et ne peut plus y travailler, même avec un jeton déjà ouvert.
    espace = client.get("/enfants/moi", headers=entete(connexion["jeton"])).json()
    assert espace["maths"] == []
    assert client.post(f"/enfants/moi/maths/{eleve.id}", headers=entete(connexion["jeton"])).status_code == 403
    assert client.get("/eleves/moi", headers=entete(jeton_maths)).status_code == 401
    # Le professeur ne la voit plus ; plus d'inscription possible.
    assert classe["id"] not in [c["id"] for c in client.get("/enseignants/classes", headers=prof).json()]
    assert client.get(f"/enseignants/classes/{classe['id']}/eleves", headers=prof).status_code == 404
    r = client.post(f"/admin/classes/{classe['id']}/enfants", headers=admin, json={"enfant_ids": [ines["id"]]})
    assert "archivée" in " ".join(r.json()["refus"])
    # L'administrateur la retrouve parmi les archivées ; la fiche élève la montre, sans alerte.
    assert classe["id"] not in [c["id"] for c in client.get("/admin/classes", headers=admin).json()]
    archivee = next(c for c in client.get("/admin/classes?etat=archivees", headers=admin).json() if c["id"] == classe["id"])
    assert archivee["motif_archivage"] == "Fin d'année 2025-2026" and archivee["archivee_par"].endswith("Administrateur Démo")
    fiche = client.get(f"/admin/enfants/{ines['id']}/fiche", headers=admin).json()
    assert [(m["code_classe"], m["archivee"], m["reponses"]) for m in fiche["maths"]] == [(classe["code"], True, 1)]
    assert fiche["eleve"]["alertes"] == []
    sans_classe = client.get("/admin/repertoire?sans_classe=true", headers=admin).json()["elements"]
    assert ines["id"] in [e["id"] for e in sans_classe]
    assert client.get("/admin/journal?action=archiver", headers=admin).json()["elements"][0]["apres"]["ids"] == [classe["id"]]

    # Rétablir remet tout en service ; refaire l'opération ne change rien.
    assert _archiver(client, admin, "/admin/classes/archivage", [classe["id"]], archiver=False) == 1
    assert _archiver(client, admin, "/admin/classes/archivage", [classe["id"]], archiver=False) == 0
    assert [m["eleve_id"] for m in client.get("/enfants/moi", headers=entete(connexion["jeton"])).json()["maths"]] == [eleve.id]
    assert client.post(f"/enfants/moi/maths/{eleve.id}", headers=entete(connexion["jeton"])).status_code == 200


def test_archiver_un_groupe_d_anglais_libere_son_nom(client, session):
    admin = connecter_admin(client)
    [noe] = _famille(client, admin, "ang@x.test", [{"prenom": "Noé", "niveau": "4e"}])
    prof_id = session.scalar(select(models.Enseignant.id).where(models.Enseignant.email == EMAIL_ANGLAIS_DEMO))
    groupe = client.post("/admin/anglais/groupes", headers=admin, json={"nom": "4eB", "niveau": "4e", "enseignant_id": prof_id}).json()
    client.post(f"/admin/anglais/groupes/{groupe['id']}/enfants", headers=admin, json={"enfant_ids": [noe["id"]]})
    assert _archiver(client, admin, "/admin/anglais/groupes/archivage", [groupe["id"]]) == 1
    assert client.get("/enfants/moi", headers=entete(_carte(client, noe)["jeton"])).json()["anglais"] == []
    prof = connecter_enseignant(client, email=EMAIL_ANGLAIS_DEMO)
    assert groupe["id"] not in [g["id"] for g in client.get("/anglais/groupes", headers=prof).json()]
    # L'an prochain, le même nom est libre ; rétablir l'ancien groupe est alors refusé.
    nouveau = client.post("/anglais/groupes", headers=prof, json={"nom": "4eB", "niveau": "4e"})
    assert nouveau.status_code == 201, nouveau.text
    r = client.post("/admin/anglais/groupes/archivage", headers=admin, json={"ids": [groupe["id"]], "archiver": False})
    assert r.status_code == 409
    vues = client.get("/admin/anglais/groupes?etat=toutes", headers=admin).json()
    assert {g["id"]: g["archivee_le"] is not None for g in vues if g["nom"] == "4eB"} == {groupe["id"]: True, nouveau.json()["id"]: False}
    # Réservé à l'administrateur.
    assert client.post("/admin/classes/archivage", headers=prof, json={"ids": [1]}).status_code == 401


def test_un_domaine_sans_contenu_ne_peut_pas_ouvrir(client):
    admin = connecter_admin(client)
    domaines = {d["code"]: d for d in client.get("/admin/domaines", headers=admin).json()}
    assert domaines["maths-lycee"]["nb_contenus"] > 0 and domaines["francais-lycee"]["nb_contenus"] == 0
    r = client.post("/admin/domaines/francais-lycee", headers=admin, json={"actif": True, "public": True})
    assert r.status_code == 409 and "aucun contenu" in r.json()["detail"]
    # Activer pour l'équipe reste possible ; un domaine déjà public se règle sans nouveau contrôle.
    assert client.post("/admin/domaines/francais-lycee", headers=admin, json={"actif": True, "public": False}).status_code == 200
    assert client.post("/admin/domaines/maths-lycee", headers=admin, json={"actif": True, "public": True}).status_code == 200
