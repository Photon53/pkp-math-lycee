"""V3, Lot 0 : supprimer une classe, un groupe ou une inscription ne fait plus disparaître le travail d'un enfant
de famille (copie archivée sur sa fiche) ; l'effacement de l'enfant efface ses archives ; les statistiques
comptent chaque élève une fois."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app import purge
from app.db import models
from app.db.seed import EMAIL_ANGLAIS_DEMO
from tests.conftest import connecter_admin, connecter_enseignant


def _famille(client, admin):
    r = client.post("/admin/familles", headers=admin, json={
        "email": "archives@x.test",
        "enfants": [{"prenom": "Inès", "nom": "Martin", "niveau": "2nde"}, {"prenom": "Noé", "niveau": "4e"}],
    })
    assert r.status_code == 201, r.text
    return {c["prenom"]: c for c in r.json()["cartes"]}


def _travail_maths(session, eleve_id, debut=None):
    """Une séance de deux réponses (une juste) pour l'inscription `eleve_id`."""
    debut = debut or datetime.now(UTC)
    questions = session.scalars(select(models.Question).limit(2)).all()
    seance = models.Seance(eleve_id=eleve_id, debut=debut, fin=debut + timedelta(minutes=10))
    session.add(seance)
    session.flush()
    for q, juste in zip(questions, (True, False)):
        session.add(models.Reponse(seance_id=seance.id, question_id=q.id, reponse_donnee="42", correcte=juste,
                                   duree_s=12.0, repondu_le=debut + timedelta(minutes=1)))
    session.commit()


def _inscription(session, enfant_id, classe_id):
    return session.scalar(select(models.Eleve).where(models.Eleve.enfant_id == enfant_id, models.Eleve.classe_id == classe_id))


def _nb_archives(session):
    session.expire_all()
    return session.scalar(select(func.count(models.ArchiveInscription.id)))


def test_supprimer_une_classe_archive_le_travail_de_l_enfant(client, session):
    admin = connecter_admin(client)
    ines = _famille(client, admin)["Inès"]
    prof = connecter_enseignant(client)
    cid = client.post("/enseignants/classes", headers=prof, json={"niveau": "2nde", "parcours": "excellence"}).json()["id"]
    assert client.post(f"/enseignants/classes/{cid}/enfants", headers=prof, json={"enfant_ids": [ines["id"]]}).json()["ajoutes"]
    eleve = _inscription(session, ines["id"], cid)
    _travail_maths(session, eleve.id)

    assert client.delete(f"/enseignants/classes/{cid}", headers=prof).status_code == 204
    session.expire_all()
    assert session.get(models.Classe, cid) is None  # la classe et l'inscription disparaissent comme avant

    archives = client.get(f"/admin/enfants/{ines['id']}/archives", headers=admin).json()
    assert len(archives) == 1
    a = archives[0]
    assert (a["matiere"], a["niveau"], a["parcours"], a["motif"]) == ("maths", "2nde", "excellence", "classe supprimée")
    assert a["par"].startswith("Professeur : ") and a["resume"]["seances"] == 1
    assert (a["resume"]["reponses"], a["resume"]["correctes"]) == (2, 1)
    detail = client.get(f"/admin/archives/{a['id']}", headers=admin).json()
    assert len(detail["contenu"]["seances"][0]["reponses"]) == 2
    # Réservé à l'administrateur.
    assert client.get(f"/admin/enfants/{ines['id']}/archives", headers=prof).status_code == 401


def test_retirer_une_inscription_ou_un_groupe_d_anglais_archive_aussi(client, session):
    admin = connecter_admin(client)
    cartes = _famille(client, admin)
    ines, noe = cartes["Inès"], cartes["Noé"]
    prof_id = session.scalar(select(models.Enseignant.id).where(models.Enseignant.email == "demo@pkp.test"))
    cid = client.post("/admin/classes", headers=admin, json={"niveau": "2nde", "parcours": "tronc-commun", "enseignant_id": prof_id}).json()["id"]
    client.post(f"/admin/classes/{cid}/enfants", headers=admin, json={"enfant_ids": [ines["id"]]})
    eleve = _inscription(session, ines["id"], cid)
    _travail_maths(session, eleve.id)
    assert client.delete(f"/admin/eleves/{eleve.id}", headers=admin).status_code == 204
    retrait = client.get(f"/admin/enfants/{ines['id']}/archives", headers=admin).json()
    assert [(a["motif"], a["par"].split(" : ")[0]) for a in retrait] == [("inscription retirée", "Administrateur")]

    anglais = session.scalar(select(models.Enseignant.id).where(models.Enseignant.email == EMAIL_ANGLAIS_DEMO))
    gid = client.post("/admin/anglais/groupes", headers=admin, json={"nom": "4e Archive", "niveau": "4e", "enseignant_id": anglais}).json()["id"]
    client.post(f"/admin/anglais/groupes/{gid}/enfants", headers=admin, json={"enfant_ids": [noe["id"]]})
    inscrit = session.scalar(select(models.EleveAnglais).where(models.EleveAnglais.enfant_id == noe["id"]))
    session.add(models.ProgressionAnglais(eleve_id=inscrit.id, code="S01", meilleur_score=8, total=10, tentatives=2, i_can=["a"]))
    session.commit()
    assert client.delete(f"/admin/anglais/groupes/{gid}", headers=admin).status_code == 204
    a = client.get(f"/admin/enfants/{noe['id']}/archives", headers=admin).json()
    assert [(x["matiere"], x["cours"], x["motif"]) for x in a] == [("anglais", "4e Archive", "groupe supprimé")]
    detail = client.get(f"/admin/archives/{a[0]['id']}", headers=admin).json()
    assert detail["contenu"]["progression"][0]["meilleur_score"] == 8


def test_effacer_l_enfant_efface_ses_archives(client, session):
    admin = connecter_admin(client)
    ines = _famille(client, admin)["Inès"]
    prof = connecter_enseignant(client)
    cid = client.post("/enseignants/classes", headers=prof, json={"niveau": "2nde", "parcours": "excellence"}).json()["id"]
    client.post(f"/enseignants/classes/{cid}/enfants", headers=prof, json={"enfant_ids": [ines["id"]]})
    client.delete(f"/enseignants/classes/{cid}", headers=prof)
    assert _nb_archives(session) == 1
    r = client.delete(f"/admin/enfants/{ines['id']}?confirmation={ines['identifiant']}", headers=admin)
    assert r.status_code == 204
    assert _nb_archives(session) == 0


def test_une_inscription_sans_enfant_reste_effacee_sans_archive(client, session):
    """Ancien modèle (élève sans fiche enfant) : le retrait reste le droit à l'effacement."""
    prof = connecter_enseignant(client)
    classe = session.scalar(select(models.Classe).where(models.Classe.code == "2NDE-A-DEMO"))
    eleve = models.Eleve(prenom="Sansfiche", classe_id=classe.id)
    session.add(eleve)
    session.commit()
    eleve_id = eleve.id
    _travail_maths(session, eleve_id)
    assert client.delete(f"/enseignants/eleves/{eleve_id}", headers=prof).status_code == 204
    assert _nb_archives(session) == 0
    assert session.scalar(select(func.count(models.Seance.id)).where(models.Seance.eleve_id == eleve_id)) == 0


def test_la_purge_rgpd_supprime_les_archives_echues(client, session):
    admin = connecter_admin(client)
    ines = _famille(client, admin)["Inès"]
    prof = connecter_enseignant(client)
    cid = client.post("/enseignants/classes", headers=prof, json={"niveau": "2nde", "parcours": "excellence"}).json()["id"]
    client.post(f"/enseignants/classes/{cid}/enfants", headers=prof, json={"enfant_ids": [ines["id"]]})
    client.delete(f"/enseignants/classes/{cid}", headers=prof)
    session.expire_all()
    purge.purger(session, retention_jours=30, maintenant=datetime.now(UTC) + timedelta(days=10))
    assert _nb_archives(session) == 1  # pas encore échue
    purge.purger(session, retention_jours=30, maintenant=datetime.now(UTC) + timedelta(days=31))
    assert _nb_archives(session) == 0


def test_un_enfant_inscrit_dans_deux_parcours_compte_pour_un_eleve(client, session):
    admin = connecter_admin(client)
    avant = client.get("/admin/statistiques?periode=30", headers=admin).json()
    ines = _famille(client, admin)["Inès"]
    prof = connecter_enseignant(client)
    for parcours in ("tronc-commun", "excellence"):
        cid = client.post("/enseignants/classes", headers=prof, json={"niveau": "2nde", "parcours": parcours}).json()["id"]
        client.post(f"/enseignants/classes/{cid}/enfants", headers=prof, json={"enfant_ids": [ines["id"]]})
        _travail_maths(session, _inscription(session, ines["id"], cid).id)
    from app import statistiques

    statistiques.vider_cache()
    apres = client.get("/admin/statistiques?periode=30", headers=admin).json()
    assert apres["eleves_total"] == avant["eleves_total"] + 2  # Inès et Noé, une fois chacun
    assert apres["eleves_actifs"] == avant["eleves_actifs"] + 1  # Inès, active dans deux parcours
