"""V3, Lot 1 : répertoire des élèves (un élève = un enfant), fiche élève, responsables et tuteur légal."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db import models
from tests.conftest import connecter_admin, connecter_enseignant


def _famille(client, admin, email, enfants, nom="", prenom=""):
    r = client.post("/admin/familles", headers=admin, json={"email": email, "nom": nom, "prenom": prenom, "enfants": enfants})
    assert r.status_code == 201, r.text
    return r.json()


def _repertoire(client, admin, **params):
    r = client.get("/admin/repertoire", headers=admin, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _classe(client, prof, niveau, parcours):
    r = client.post("/enseignants/classes", headers=prof, json={"niveau": niveau, "parcours": parcours})
    assert r.status_code == 201, r.text
    return r.json()


def test_repertoire_recherche_filtres_et_points_a_verifier(client, session):
    admin = connecter_admin(client)
    f = _famille(client, admin, "martin@x.test", [{"prenom": "Inès", "nom": "Martin", "niveau": "2nde"},
                                                  {"prenom": "Noé", "nom": "Martin", "niveau": "4e"}],
                 nom="Martin", prenom="Claire")
    ines = next(c for c in f["cartes"] if c["prenom"] == "Inès")
    prof = connecter_enseignant(client)
    excellence = _classe(client, prof, "2nde", "excellence")
    client.post(f"/enseignants/classes/{excellence['id']}/enfants", headers=prof, json={"enfant_ids": [ines["id"]]})

    tous = _repertoire(client, admin)
    assert tous["total"] >= 2 and len(tous["elements"]) <= 50
    ligne = next(e for e in _repertoire(client, admin, q="inès martin")["elements"] if e["id"] == ines["id"])
    assert [r["email"] for r in ligne["responsables"]] == ["martin@x.test"]
    assert ligne["responsables"][0]["nom"] == "Martin" and ligne["responsables"][0]["prenom"] == "Claire"
    # Seulement en excellence (une option) : pas de parcours principal.
    assert ligne["maths"][0]["principal"] is False
    assert ligne["alertes"] == ["Pas de parcours principal en maths"]
    # Recherche par code de classe, par e-mail du responsable ; filtres.
    assert [e["id"] for e in _repertoire(client, admin, q=excellence["code"])["elements"]] == [ines["id"]]
    assert {e["id"] for e in _repertoire(client, admin, q="martin@x")["elements"]} == {c["id"] for c in f["cartes"]}
    assert ines["id"] in [e["id"] for e in _repertoire(client, admin, a_verifier="true")["elements"]]
    assert all(e["niveau"] == "4e" for e in _repertoire(client, admin, niveau="4e")["elements"])
    assert [e["id"] for e in _repertoire(client, admin, classe_id=excellence["id"])["elements"]] == [ines["id"]]

    # Avec un parcours principal en plus, l'alerte disparaît ; deux principaux la font revenir autrement.
    tronc = _classe(client, prof, "2nde", "tronc-commun")
    client.post(f"/enseignants/classes/{tronc['id']}/enfants", headers=prof, json={"enfant_ids": [ines["id"]]})
    assert ines["id"] not in [e["id"] for e in _repertoire(client, admin, a_verifier="true")["elements"]]

    # Réservé à l'administrateur.
    assert client.get("/admin/repertoire", headers=prof).status_code == 401


def test_eleve_sans_responsable_puis_rattache(client, session):
    admin = connecter_admin(client)
    f = _famille(client, admin, "seul@x.test", [{"prenom": "Lou", "niveau": "6e"}])
    lou = f["cartes"][0]
    parent_id = f["parent_id"]
    # Détacher le dernier responsable : l'élève reste, le compte sans enfant est supprimé (RGPD).
    r = client.delete(f"/admin/enfants/{lou['id']}/responsables/{parent_id}", headers=admin)
    assert r.status_code == 200 and r.json()["eleve"]["responsables"] == []
    assert session.get(models.Parent, parent_id) is None
    assert lou["id"] in [e["id"] for e in _repertoire(client, admin, sans_responsable="true")["elements"]]

    # Nouveau responsable : compte créé avec un mot de passe provisoire.
    r = client.post(f"/admin/enfants/{lou['id']}/responsables", headers=admin,
                    json={"email": "Tuteur@X.test", "nom": "Durand", "prenom": "Paul"})
    assert r.status_code == 200, r.text
    assert r.json()["cree"] and r.json()["mot_de_passe_provisoire"]
    assert r.json()["responsable"]["email"] == "tuteur@x.test"
    # Compte existant : rattaché sans nouveau mot de passe ; en double : refusé.
    _famille(client, admin, "autre@x.test", [{"prenom": "Zoé", "niveau": "3e"}])
    r = client.post(f"/admin/enfants/{lou['id']}/responsables", headers=admin, json={"email": "autre@x.test"})
    assert r.json()["cree"] is False and r.json()["mot_de_passe_provisoire"] is None
    assert client.post(f"/admin/enfants/{lou['id']}/responsables", headers=admin, json={"email": "autre@x.test"}).status_code == 409
    # Un troisième responsable demande une confirmation.
    _famille(client, admin, "trois@x.test", [{"prenom": "Max", "niveau": "3e"}])
    assert client.post(f"/admin/enfants/{lou['id']}/responsables", headers=admin, json={"email": "trois@x.test"}).status_code == 409
    r = client.post(f"/admin/enfants/{lou['id']}/responsables?confirmer=true", headers=admin, json={"email": "trois@x.test"})
    assert r.status_code == 200
    fiche = client.get(f"/admin/enfants/{lou['id']}/fiche", headers=admin).json()
    assert len(fiche["eleve"]["responsables"]) == 3
    assert [h["action"] for h in fiche["historique"]][:3] == ["rattacher-enfant"] * 3


def test_fiche_eleve_progression_archives_et_historique(client, session):
    admin = connecter_admin(client)
    ines = _famille(client, admin, "fiche@x.test", [{"prenom": "Inès", "niveau": "2nde"}])["cartes"][0]
    prof = connecter_enseignant(client)
    tronc = _classe(client, prof, "2nde", "tronc-commun")
    excellence = _classe(client, prof, "2nde", "excellence")
    for c in (tronc, excellence):
        client.post(f"/enseignants/classes/{c['id']}/enfants", headers=prof, json={"enfant_ids": [ines["id"]]})
    eleve = session.scalar(select(models.Eleve).where(models.Eleve.enfant_id == ines["id"], models.Eleve.classe_id == tronc["id"]))
    q = session.scalars(select(models.Question).limit(2)).all()
    maintenant = datetime.now(UTC)
    seance = models.Seance(eleve_id=eleve.id, debut=maintenant, fin=maintenant + timedelta(minutes=5))
    session.add(seance)
    session.flush()
    for question, juste in zip(q, (True, False)):
        session.add(models.Reponse(seance_id=seance.id, question_id=question.id, reponse_donnee="1", correcte=juste, duree_s=3.0))
    session.commit()
    client.delete(f"/enseignants/classes/{excellence['id']}", headers=prof)  # archivée
    client.post("/admin/enfants/blocage", headers=admin, json={"ids": [ines["id"]], "bloque": True})

    fiche = client.get(f"/admin/enfants/{ines['id']}/fiche", headers=admin).json()
    assert fiche["eleve"]["bloque"] is True
    [maths] = fiche["maths"]
    assert (maths["code_classe"], maths["principal"], maths["seances"], maths["reponses"], maths["taux_reussite"]) == (
        tronc["code"], True, 1, 2, 0.5)
    assert [a["cours"] for a in fiche["archives"]] == [excellence["code"]]
    assert "bloquer" in [h["action"] for h in fiche["historique"]]
    assert client.get("/admin/enfants/999999/fiche", headers=admin).status_code == 404


def test_changement_de_niveau_en_masse(client, session):
    admin = connecter_admin(client)
    cartes = _famille(client, admin, "niveau@x.test", [{"prenom": "Ana", "niveau": "2nde"}, {"prenom": "Léo", "niveau": "2nde"}])["cartes"]
    prof = connecter_enseignant(client)
    tronc = _classe(client, prof, "2nde", "tronc-commun")
    client.post(f"/enseignants/classes/{tronc['id']}/enfants", headers=prof, json={"enfant_ids": [cartes[0]["id"]]})
    r = client.post("/admin/enfants/niveau", headers=admin, json={"ids": [c["id"] for c in cartes], "niveau": "1re"})
    assert r.status_code == 200, r.text
    assert {e["niveau"] for e in r.json()["elements"]} == {"1re"}
    ana = next(e for e in r.json()["elements"] if e["id"] == cartes[0]["id"])
    assert "Inscrit dans une classe d'un autre niveau" in ana["alertes"]
    journal = client.get("/admin/journal?action=changer-niveau", headers=admin).json()
    assert journal["elements"][0]["apres"]["niveau"] == "1re"


def test_tuteur_legal_nom_prenom_recherche_et_modification(client, session):
    admin = connecter_admin(client)
    f = _famille(client, admin, "dupont@x.test", [{"prenom": "Jade", "niveau": "5e"}], nom="Dupont", prenom="Anne")
    trouve = client.get("/admin/parents?q=dupont", headers=admin).json()["elements"]
    assert [(p["email"], p["nom"], p["prenom"]) for p in trouve] == [("dupont@x.test", "Dupont", "Anne")]
    assert client.get("/admin/parents?q=anne", headers=admin).json()["total"] == 1
    r = client.patch(f"/admin/parents/{f['parent_id']}", headers=admin, json={"email": "dupont@x.test", "prenom": "Anne-Marie"})
    assert r.status_code == 200 and (r.json()["nom"], r.json()["prenom"]) == ("Dupont", "Anne-Marie")
    assert client.patch(f"/admin/parents/{f['parent_id']}", headers=admin, json={"email": "dupont@x.test", "nom": "D4"}).status_code == 422
    # Sans nom : le compte reste utilisable, les champs sont vides.
    g = _famille(client, admin, "anonyme@x.test", [{"prenom": "Tom", "niveau": "5e"}])
    p = session.get(models.Parent, g["parent_id"])
    assert (p.nom, p.prenom) == ("", "")
