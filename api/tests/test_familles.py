"""Familles : l'admin crée parent et enfants (une carte par enfant), le professeur inscrit les enfants dans ses
classes et groupes, l'enfant se connecte une fois et choisit sa matière, le parent suit et renouvelle l'accès."""

from sqlalchemy import select

from app.db import models
from app.db.seed import EMAIL_ANGLAIS_DEMO
from tests.conftest import connecter_admin, connecter_enseignant, entete


def _famille(client, admin, email="famille@x.test", enfants=None):
    enfants = enfants or [{"prenom": "Inès", "nom": "Martin", "niveau": "2nde"}, {"prenom": "Noé", "niveau": "4e"}]
    r = client.post("/admin/familles", headers=admin, json={"email": email, "enfants": enfants})
    assert r.status_code == 201, r.text
    return r.json()


def _carte(client, carte):
    r = client.post("/enfants/connexion", json={"identifiant": carte["identifiant"], "code_personnel": carte["code"]})
    assert r.status_code == 200, r.text
    return r.json()


def test_creation_de_famille_avec_cartes_et_mot_de_passe_provisoire(client, session):
    admin = connecter_admin(client)
    f = _famille(client, admin)
    assert f["mot_de_passe_provisoire"] and len(f["cartes"]) == 2
    assert {c["niveau"] for c in f["cartes"]} == {"2nde", "4e"}
    # Le parent change son mot de passe provisoire avant tout le reste.
    j = client.post("/parents/connexion", json={"email": "famille@x.test", "mot_de_passe": f["mot_de_passe_provisoire"]}).json()
    assert j["mdp_provisoire"] is True
    assert client.get("/parents/famille", headers=entete(j["jeton"])).status_code == 403
    r = client.post("/parents/mot-de-passe", headers=entete(j["jeton"]),
                    json={"actuel": f["mot_de_passe_provisoire"], "nouveau": "un-nouveau-mdp-2026"})
    assert r.status_code == 200, r.text
    suivi = client.get("/parents/famille", headers=entete(r.json()["jeton"])).json()
    assert [s["enfant"]["prenom"] for s in suivi] == ["Inès", "Noé"]
    assert [m["code"] for m in suivi[0]["matieres"]] == ["maths", "anglais", "francais"]
    assert [m["disponible"] for m in suivi[0]["matieres"]] == [True, True, False]
    # Même adresse : les nouveaux enfants rejoignent la famille, sans nouveau mot de passe.
    f2 = _famille(client, admin, enfants=[{"prenom": "Léa", "niveau": "6e"}])
    assert f2["parent_id"] == f["parent_id"] and f2["mot_de_passe_provisoire"] is None
    assert len(client.get(f"/admin/parents/{f['parent_id']}/famille", headers=admin).json()) == 3


def test_le_professeur_inscrit_l_enfant_dans_plusieurs_parcours_de_son_niveau(client, session):
    admin = connecter_admin(client)
    ines = next(c for c in _famille(client, admin)["cartes"] if c["prenom"] == "Inès")
    prof = connecter_enseignant(client)
    classes = {}
    for parcours in ("tronc-commun", "excellence", "mise-a-niveau"):
        r = client.post("/enseignants/classes", headers=prof, json={"niveau": "2nde", "parcours": parcours})
        classes[parcours] = r.json()["id"]
    # Recherche par prénom, limitée au niveau de la classe.
    trouves = client.get(f"/enseignants/classes/{classes['excellence']}/enfants?q=in", headers=prof).json()
    assert [t["identifiant"] for t in trouves] == [ines["identifiant"]]
    assert client.get(f"/enseignants/classes/{classes['excellence']}/enfants?q=n", headers=prof).status_code == 422
    for cid in classes.values():
        r = client.post(f"/enseignants/classes/{cid}/enfants", headers=prof, json={"enfant_ids": [ines["id"]]})
        assert r.json() == {"ajoutes": ["Inès Martin"], "refus": []}
    again = client.post(f"/enseignants/classes/{classes['excellence']}/enfants", headers=prof, json={"enfant_ids": [ines["id"]]})
    assert again.json()["ajoutes"] == [] and "déjà inscrit" in again.json()["refus"][0]
    # Niveau différent : refusé, avec une explication.
    noe = session.scalar(select(models.Enfant).where(models.Enfant.prenom == "Noé"))
    r = client.post(f"/enseignants/classes/{classes['excellence']}/enfants", headers=prof, json={"enfant_ids": [noe.id]})
    assert "4e" in r.json()["refus"][0]

    # L'enfant se connecte une fois, voit ses trois parcours et ouvre celui qu'il veut.
    connexion = _carte(client, ines)
    assert connexion["type"] == "enfant"
    espace = connexion["enfant"]
    assert sorted(m["parcours"] for m in espace["maths"]) == ["excellence", "mise-a-niveau", "tronc-commun"]
    h = entete(connexion["jeton"])
    excellence = next(m for m in espace["maths"] if m["parcours"] == "excellence")
    jeton = client.post(f"/enfants/moi/maths/{excellence['eleve_id']}", headers=h).json()["jeton"]
    moi = client.get("/eleves/moi", headers=entete(jeton)).json()
    assert moi["parcours"] == "excellence" and moi["identifiant"] == ines["identifiant"]
    assert len(client.get("/eleves/moi/parcours", headers=entete(jeton)).json()) == 3


def test_anglais_et_carte_unique(client, session):
    admin = connecter_admin(client)
    noe = next(c for c in _famille(client, admin)["cartes"] if c["prenom"] == "Noé")
    prof = connecter_enseignant(client, email=EMAIL_ANGLAIS_DEMO)
    groupe = next(g for g in client.get("/anglais/groupes", headers=prof).json() if g["niveau"] == "4e") if any(
        g["niveau"] == "4e" for g in client.get("/anglais/groupes", headers=prof).json()
    ) else client.post("/anglais/groupes", headers=prof, json={"nom": "Les explorateurs", "niveau": "4e"}).json()
    assert client.get(f"/anglais/groupes/{groupe['id']}/enfants?q=no", headers=prof).json()[0]["id"] == noe["id"]
    r = client.post(f"/anglais/groupes/{groupe['id']}/enfants", headers=prof, json={"enfant_ids": [noe["id"]]})
    assert r.json()["ajoutes"] == ["Noé"], r.text
    connexion = _carte(client, noe)
    assert len(connexion["enfant"]["anglais"]) == 1
    h = entete(connexion["jeton"])
    r = client.post(f"/enfants/moi/anglais/{connexion['enfant']['anglais'][0]['eleve_id']}", headers=h)
    assert r.status_code == 200 and client.get("/anglais/eleve/moi", headers=entete(r.json()["jeton"])).status_code == 200
    # L'ancienne page de connexion anglais ne connaît pas la carte d'un enfant de famille.
    assert client.post("/anglais/eleve/connexion", json={"identifiant": noe["identifiant"], "code_personnel": noe["code"]}).status_code == 401


def test_le_parent_renouvelle_l_acces_et_les_sessions_tombent(client, session):
    admin = connecter_admin(client)
    f = _famille(client, admin)
    ines = next(c for c in f["cartes"] if c["prenom"] == "Inès")
    prof = connecter_enseignant(client)
    cid = client.post("/enseignants/classes", headers=prof, json={"niveau": "2nde", "parcours": "tronc-commun"}).json()["id"]
    client.post(f"/enseignants/classes/{cid}/enfants", headers=prof, json={"enfant_ids": [ines["id"]]})
    connexion = _carte(client, ines)
    maths = client.post(f"/enfants/moi/maths/{connexion['enfant']['maths'][0]['eleve_id']}", headers=entete(connexion["jeton"])).json()

    j = client.post("/parents/connexion", json={"email": "famille@x.test", "mot_de_passe": f["mot_de_passe_provisoire"]}).json()
    hp = entete(client.post("/parents/mot-de-passe", headers=entete(j["jeton"]),
                            json={"actuel": f["mot_de_passe_provisoire"], "nouveau": "un-nouveau-mdp-2026"}).json()["jeton"])
    suivi = client.get(f"/parents/famille/{ines['id']}", headers=hp).json()
    assert suivi["maths"][0]["code_classe"] and suivi["enfant"]["maths"][0]["parcours"] == "tronc-commun"
    # Code tiré au hasard : renvoyé une fois ; l'ancien code et toutes les sessions cessent de fonctionner.
    nouveau = client.post(f"/parents/famille/{ines['id']}/acces", headers=hp, json={}).json()
    assert nouveau["identifiant"] == ines["identifiant"] and nouveau["code"]
    assert client.get("/enfants/moi", headers=entete(connexion["jeton"])).status_code == 401
    assert client.get("/eleves/moi", headers=entete(maths["jeton"])).status_code == 401
    assert client.post("/enfants/connexion", json={"identifiant": ines["identifiant"], "code_personnel": ines["code"]}).status_code == 401
    _carte(client, {"identifiant": ines["identifiant"], "code": nouveau["code"]})
    # Code choisi par le parent : mêmes règles que les autres codes choisis.
    assert client.post(f"/parents/famille/{ines['id']}/acces", headers=hp, json={"code": "abc"}).status_code == 422
    choisi = client.post(f"/parents/famille/{ines['id']}/acces", headers=hp, json={"code": "Soleil2026"}).json()
    assert choisi["code"] is None
    _carte(client, {"identifiant": ines["identifiant"], "code": "SOLEIL2026"})
    # Un parent ne voit pas les enfants des autres familles.
    autre = _famille(client, admin, email="autre@x.test", enfants=[{"prenom": "Sam", "niveau": "5e"}])
    assert client.get(f"/parents/famille/{autre['cartes'][0]['id']}", headers=hp).status_code == 404


def test_admin_cree_une_classe_inscrit_modifie_et_supprime(client, session):
    admin = connecter_admin(client)
    f = _famille(client, admin)
    ines = next(c for c in f["cartes"] if c["prenom"] == "Inès")
    prof_id = session.scalar(select(models.Enseignant.id).where(models.Enseignant.email == "demo@pkp.test"))
    r = client.post("/admin/classes", headers=admin, json={"niveau": "2nde", "parcours": "excellence", "enseignant_id": prof_id})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert client.post(f"/admin/classes/{cid}/enfants", headers=admin, json={"enfant_ids": [ines["id"]]}).json()["ajoutes"] == ["Inès Martin"]
    assert client.get(f"/admin/enfants?q=martin", headers=admin).json()[0]["maths"][0]["parcours"] == "excellence"
    # Passage au niveau supérieur ; nouvelle carte (identifiant conservé).
    assert client.patch(f"/admin/enfants/{ines['id']}", headers=admin, json={"niveau": "1re"}).json()["niveau"] == "1re"
    carte = client.post(f"/admin/enfants/{ines['id']}/carte", headers=admin).json()
    assert carte["identifiant"] == ines["identifiant"] and carte["code"] != ines["code"]
    # Suppression confirmée par l'identifiant : les inscriptions partent avec l'enfant.
    assert client.delete(f"/admin/enfants/{ines['id']}?confirmation=x", headers=admin).status_code == 422
    assert client.delete(f"/admin/enfants/{ines['id']}?confirmation={ines['identifiant']}", headers=admin).status_code == 204
    assert session.scalar(select(models.Eleve.id).where(models.Eleve.classe_id == cid)) is None
    # Le compte parent reste : il a encore un enfant (Noé).
    assert client.get(f"/admin/parents/{f['parent_id']}/famille", headers=admin).json()[0]["prenom"] == "Noé"


def test_deux_enfants_de_meme_prenom_dans_une_classe(client, session):
    admin = connecter_admin(client)
    a = _famille(client, admin, email="a@x.test", enfants=[{"prenom": "Lina", "nom": "Durand", "niveau": "2nde"}])["cartes"][0]
    b = _famille(client, admin, email="b@x.test", enfants=[{"prenom": "Lina", "nom": "Dupont", "niveau": "2nde"}])["cartes"][0]
    prof = connecter_enseignant(client)
    cid = client.post("/enseignants/classes", headers=prof, json={"niveau": "2nde", "parcours": "tronc-commun"}).json()["id"]
    r = client.post(f"/enseignants/classes/{cid}/enfants", headers=prof, json={"enfant_ids": [a["id"], b["id"]]}).json()
    assert r["refus"] == []
    prenoms = sorted(e["prenom"] for e in client.get(f"/enseignants/classes/{cid}/eleves", headers=prof).json())
    assert "Lina D." in prenoms


def test_ancienne_carte_eleve_par_la_connexion_unique(client):
    prof = connecter_enseignant(client)
    cid = client.post("/enseignants/classes", headers=prof, json={"niveau": "2nde", "parcours": "tronc-commun"}).json()["id"]
    cree = client.post(f"/enseignants/classes/{cid}/eleves", headers=prof, json={"prenoms": ["Zoé"]}).json()["crees"][0]
    r = client.post("/enfants/connexion", json={"identifiant": cree["identifiant"], "code_personnel": cree["code"]})
    assert r.status_code == 200 and r.json()["type"] == "eleve"
    assert client.get("/eleves/moi", headers=entete(r.json()["jeton"])).json()["prenom"] == "Zoé"
    assert client.post("/enfants/connexion", json={"identifiant": "inconnu-zzzz", "code_personnel": "ABCDEF"}).status_code == 401


def test_l_administrateur_gere_une_classe(client, session):
    """Élèves (ajout, retrait), chapitres ouverts, changement de professeur, suppression confirmée par le code."""
    admin = connecter_admin(client)
    ines = next(c for c in _famille(client, admin)["cartes"] if c["prenom"] == "Inès")
    prof = session.scalar(select(models.Enseignant).where(models.Enseignant.email == "demo@pkp.test"))
    remplacant = models.Enseignant(nom="Mme Remplaçante", email="remplacante@x.test", mot_de_passe_hash="x", enseigne_maths=True)
    session.add(remplacant)
    session.commit()
    classe = client.post("/admin/classes", headers=admin,
                         json={"niveau": "2nde", "parcours": "excellence", "enseignant_id": prof.id}).json()
    cid = classe["id"]

    # Recherche limitée au niveau de la classe, puis ajout.
    assert [t["identifiant"] for t in client.get(f"/admin/classes/{cid}/enfants?q=in", headers=admin).json()] == [ines["identifiant"]]
    assert client.post(f"/admin/classes/{cid}/enfants", headers=admin, json={"enfant_ids": [ines["id"]]}).json()["ajoutes"] == ["Inès Martin"]
    eleves = client.get(f"/admin/classes/{cid}/eleves", headers=admin).json()
    assert [(e["prenom"], e["identifiant"]) for e in eleves] == [("Inès", ines["identifiant"])]

    # Chapitres : on n'en garde qu'un ; un chapitre d'un autre programme est refusé.
    programme = client.get(f"/admin/classes/{cid}/chapitres", headers=admin).json()
    assert programme and all(c["propose"] for c in programme)
    r = client.put(f"/admin/classes/{cid}/chapitres", headers=admin, json={"chapitre_ids": [programme[0]["id"]]})
    assert [c["propose"] for c in r.json()].count(True) == 1
    autre = session.scalar(select(models.Chapitre).where(models.Chapitre.niveau != "2nde"))
    assert client.put(f"/admin/classes/{cid}/chapitres", headers=admin, json={"chapitre_ids": [autre.id]}).status_code == 422

    # Changement de professeur : la classe et ses élèves suivent ; un professeur d'anglais seul est refusé.
    r = client.patch(f"/admin/classes/{cid}", headers=admin, json={"enseignant_id": remplacant.id})
    assert r.json()["enseignant"] == "Mme Remplaçante" and r.json()["nb_eleves"] == 1
    anglais = session.scalar(select(models.Enseignant).where(models.Enseignant.email == EMAIL_ANGLAIS_DEMO))
    if not anglais.enseigne_maths:
        assert client.patch(f"/admin/classes/{cid}", headers=admin, json={"enseignant_id": anglais.id}).status_code == 422

    # Retrait d'un élève : l'enfant garde sa carte et sa famille.
    client.post(f"/admin/classes/{cid}/enfants", headers=admin, json={"enfant_ids": [ines["id"]]})
    eleve_id = client.get(f"/admin/classes/{cid}/eleves", headers=admin).json()[0]["id"]
    assert client.delete(f"/admin/eleves/{eleve_id}", headers=admin).status_code == 204
    assert client.get(f"/admin/classes/{cid}/eleves", headers=admin).json() == []
    assert _carte(client, ines)["type"] == "enfant"

    # Suppression : seulement avec le code de la classe.
    client.post(f"/admin/classes/{cid}/enfants", headers=admin, json={"enfant_ids": [ines["id"]]})
    assert client.delete(f"/admin/classes/{cid}?confirmation=MAUVAIS", headers=admin).status_code == 422
    assert client.delete(f"/admin/classes/{cid}?confirmation={classe['code'].lower()}", headers=admin).status_code == 204
    assert client.get(f"/admin/classes/{cid}", headers=admin).status_code == 404
    assert session.get(models.Enfant, ines["id"]) is not None
    # Un professeur ne passe pas par ces routes.
    assert client.get(f"/admin/classes/{programme[0]['id']}", headers=connecter_enseignant(client)).status_code in (401, 403)


def test_l_administrateur_voit_les_enfants_inscrits_nulle_part(client, session):
    admin = connecter_admin(client)
    cartes = _famille(client, admin)["cartes"]
    ines = next(c for c in cartes if c["prenom"] == "Inès")
    prof = connecter_enseignant(client)
    cid = client.post("/enseignants/classes", headers=prof, json={"niveau": "2nde", "parcours": "tronc-commun"}).json()["id"]
    client.post(f"/enseignants/classes/{cid}/enfants", headers=prof, json={"enfant_ids": [ines["id"]]})

    tous = {e["prenom"] for e in client.get("/admin/enfants", headers=admin).json()}
    assert {"Inès", "Noé"} <= tous
    sans = client.get("/admin/enfants?sans_classe=true", headers=admin).json()
    assert "Noé" in {e["prenom"] for e in sans} and "Inès" not in {e["prenom"] for e in sans}
    assert [e["prenom"] for e in client.get("/admin/enfants?sans_classe=true&niveau=4e", headers=admin).json()] == ["Noé"]
