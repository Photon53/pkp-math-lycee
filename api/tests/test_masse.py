"""Inscription en masse par fichier Excel, blocage temporaire et suppression de plusieurs comptes ou cours."""

from io import BytesIO

from openpyxl import load_workbook

from app.routes.masse import MIME_XLSX
from tests.conftest import connecter_admin, connecter_enseignant, entete


def _classeur(client, admin, lignes):
    """Le modèle téléchargé, rempli avec `lignes` (prénom, nom, niveau, e-mail 1, e-mail 2, classes, groupe)."""
    r = client.get("/admin/import/modele", headers=admin)
    assert r.status_code == 200 and r.headers["content-type"] == MIME_XLSX
    classeur = load_workbook(BytesIO(r.content))
    feuille = classeur["Élèves"]
    for i, ligne in enumerate(lignes, start=2):
        for j, valeur in enumerate(ligne, start=1):
            feuille.cell(row=i, column=j, value=valeur)
    flux = BytesIO()
    classeur.save(flux)
    return flux.getvalue()


def _importer(client, admin, contenu, simulation):
    return client.post(
        f"/admin/import?simulation={'true' if simulation else 'false'}", headers={**admin, "Content-Type": MIME_XLSX},
        content=contenu,
    )


def _groupe_4e(client, admin):
    profs = client.get("/admin/enseignants", headers=admin).json()
    prof = next(p for p in profs if p["enseigne_anglais"] and p["actif"])
    r = client.post("/admin/anglais/groupes", headers=admin, json={"nom": "4e Import", "niveau": "4e", "enseignant_id": prof["id"]})
    assert r.status_code == 201, r.text
    return r.json(), prof


def test_le_modele_liste_les_classes_et_les_groupes(client):
    admin = connecter_admin(client)
    _, prof = _groupe_4e(client, admin)
    classeur = load_workbook(BytesIO(client.get("/admin/import/modele", headers=admin).content))
    assert classeur.sheetnames == ["Élèves", "Listes", "Mode d'emploi"]
    assert [c.value for c in classeur["Élèves"][1]][:4] == ["Prénom (obligatoire)", "Nom", "Niveau (obligatoire)", "E-mail du parent 1 (obligatoire)"]
    listes = classeur["Listes"]
    assert "2NDE-A-DEMO" in [c.value for c in listes["B"]]
    assert f"4e Import · {prof['nom']}" in [c.value for c in listes["D"]]
    assert client.get("/admin/import/modele", headers=connecter_enseignant(client)).status_code == 401


def test_import_en_masse_verifie_puis_cree_familles_cartes_et_inscriptions(client):
    admin = connecter_admin(client)
    groupe, prof = _groupe_4e(client, admin)
    contenu = _classeur(client, admin, [
        ("Inès", "Durand", "seconde", "durand@x.test", "durand2@x.test", "2NDE-A-DEMO", None),
        ("Hugo", "Durand", "4e", "DURAND@x.test", None, None, f"4e Import · {prof['nom']}"),
        ("Zoé", "", "1ère", "zoe@x.test", None, None, None),
    ])
    # Vérification : rien n'est écrit.
    r = _importer(client, admin, contenu, simulation=True)
    assert r.status_code == 200, r.text
    v = r.json()
    assert (v["nb_enfants"], v["nb_comptes_nouveaux"], v["nb_erreurs"], v["cartes"]) == (3, 3, 0, [])
    assert client.get("/admin/parents?q=durand", headers=admin).json()["total"] == 0

    r = _importer(client, admin, contenu, simulation=False)
    assert r.status_code == 200, r.text
    fait = r.json()
    assert len(fait["cartes"]) == 3 and {c["email"] for c in fait["comptes"]} == {"durand@x.test", "durand2@x.test", "zoe@x.test"}
    # Une famille pour les deux enfants Durand (même e-mail, casse comprise), suivie aussi par le parent 2.
    durand = client.get("/admin/parents?q=durand@", headers=admin).json()["elements"][0]
    assert sorted(durand["famille"]) == ["Hugo Durand (4e)", "Inès Durand (2nde)"]
    second = client.get("/admin/parents?q=durand2", headers=admin).json()["elements"][0]
    assert second["famille"] == ["Inès Durand (2nde)"]
    ines = next(c for c in fait["cartes"] if c["prenom"] == "Inès")
    assert [m["code_classe"] for m in client.get(f"/admin/enfants/{ines['id']}", headers=admin).json()["maths"]] == ["2NDE-A-DEMO"]
    groupes = client.get("/admin/anglais/groupes", headers=admin).json()
    assert [e["prenom"] for g in groupes if g["id"] == groupe["id"] for e in g["eleves"]] == ["Hugo"]
    # La carte fonctionne ; le mot de passe provisoire aussi.
    assert client.post("/enfants/connexion", json={"identifiant": ines["identifiant"], "code_personnel": ines["code"]}).status_code == 200
    mdp = next(c["mot_de_passe_provisoire"] for c in fait["comptes"] if c["email"] == "zoe@x.test")
    assert client.post("/parents/connexion", json={"email": "zoe@x.test", "mot_de_passe": mdp}).status_code == 200

    # Réimporter le même fichier ne crée pas de doublon.
    again = _importer(client, admin, contenu, simulation=False).json()
    assert (again["nb_enfants"], again["nb_deja_presents"], again["cartes"]) == (0, 3, [])


def test_une_ligne_en_erreur_bloque_tout_l_import(client):
    admin = connecter_admin(client)
    contenu = _classeur(client, admin, [
        ("Léo", "Petit", "2nde", "petit@x.test", None, None, None),
        ("Léa", "Petit", "CM2", "petit@x.test", None, None, None),
        ("Max", "", "4e", "pas-une-adresse", None, "2NDE-A-DEMO", None),
        ("", "Sans", "", "", None, "INCONNUE", "Groupe fantôme"),
    ])
    r = _importer(client, admin, contenu, simulation=False)
    assert r.status_code == 200, r.text
    rapport = r.json()
    assert rapport["nb_erreurs"] == 3 and rapport["cartes"] == []
    erreurs = {l["ligne"]: " ".join(l["erreurs"]) for l in rapport["lignes"]}
    assert erreurs[2] == ""
    assert "Niveau « CM2 » inconnu" in erreurs[3]
    assert "Adresse e-mail invalide" in erreurs[4] and "pas de 4e" in erreurs[4]
    assert all(m in erreurs[5] for m in ("Prénom manquant", "Niveau manquant", "E-mail du parent 1 manquant", "INCONNUE", "fantôme"))
    assert client.get("/admin/parents?q=petit", headers=admin).json()["total"] == 0


def test_fichier_qui_n_est_pas_un_classeur(client):
    admin = connecter_admin(client)
    r = _importer(client, admin, b"prenom;nom\nInes;Martin", simulation=True)
    assert r.status_code == 422 and "xlsx" in r.json()["detail"]


def test_blocage_temporaire_d_un_enfant_et_d_une_famille(client):
    admin = connecter_admin(client)
    r = client.post("/admin/familles", headers=admin, json={"email": "bloc@x.test", "enfants": [{"prenom": "Inès", "niveau": "2nde"}]})
    famille = r.json()
    carte = famille["cartes"][0]
    connexion = {"identifiant": carte["identifiant"], "code_personnel": carte["code"]}
    jeton = client.post("/enfants/connexion", json=connexion).json()["jeton"]

    assert client.post("/admin/enfants/blocage", headers=admin, json={"ids": [carte["id"]], "bloque": True}).json() == {"traites": 1}
    assert client.get(f"/admin/enfants/{carte['id']}", headers=admin).json()["bloque"] is True
    assert client.get("/enfants/moi", headers=entete(jeton)).status_code == 401  # session ouverte fermée
    r = client.post("/enfants/connexion", json=connexion)
    assert r.status_code == 403 and "suspendu" in r.json()["detail"]
    client.post("/admin/enfants/blocage", headers=admin, json={"ids": [carte["id"]], "bloque": False})
    assert client.post("/enfants/connexion", json=connexion).status_code == 200

    mdp = famille["mot_de_passe_provisoire"]
    client.post("/admin/parents/blocage", headers=admin, json={"ids": [famille["parent_id"]], "bloque": True})
    assert client.get("/admin/parents?q=bloc@", headers=admin).json()["elements"][0]["bloque"] is True
    r = client.post("/parents/connexion", json={"email": "bloc@x.test", "mot_de_passe": mdp})
    assert r.status_code == 403 and "suspendu" in r.json()["detail"]
    assert client.post("/enfants/connexion", json=connexion).status_code == 200  # la carte de l'enfant reste valable
    client.post("/admin/parents/blocage", headers=admin, json={"ids": [famille["parent_id"]], "bloque": False})
    assert client.post("/parents/connexion", json={"email": "bloc@x.test", "mot_de_passe": mdp}).status_code == 200


def test_suppression_en_masse_avec_confirmation(client):
    admin = connecter_admin(client)
    f1 = client.post("/admin/familles", headers=admin, json={"email": "un@x.test", "enfants": [{"prenom": "Anna", "niveau": "6e"}]}).json()
    f2 = client.post("/admin/familles", headers=admin, json={"email": "deux@x.test", "enfants": [{"prenom": "Bob", "niveau": "6e"}]}).json()
    f3 = client.post("/admin/familles", headers=admin, json={"email": "trois@x.test", "enfants": [{"prenom": "Chloé", "niveau": "5e"}]}).json()
    ids = [f1["parent_id"], f2["parent_id"]]

    r = client.post("/admin/parents/suppression", headers=admin, json={"ids": ids, "confirmation": "oui"})
    assert r.status_code == 422
    # Familles supprimées avec leurs enfants (qui n'ont pas d'autre parent).
    r = client.post("/admin/parents/suppression", headers=admin, json={"ids": ids, "confirmation": "supprimer", "avec_enfants": True})
    assert r.json() == {"traites": 2}
    assert client.get(f"/admin/enfants/{f1['cartes'][0]['id']}", headers=admin).status_code == 404
    # Enfants supprimés : le compte parent devenu vide disparaît aussi.
    r = client.post("/admin/enfants/suppression", headers=admin, json={"ids": [f3["cartes"][0]["id"]], "confirmation": "SUPPRIMER"})
    assert r.json() == {"traites": 1}
    assert client.get(f"/admin/parents/{f3['parent_id']}", headers=admin).status_code == 404

    # Classes et groupes d'anglais.
    profs = client.get("/admin/enseignants", headers=admin).json()
    maths = next(p for p in profs if p["enseigne_maths"] and p["actif"])
    classes = [client.post("/admin/classes", headers=admin, json={"niveau": "2nde", "parcours": "tronc-commun", "enseignant_id": maths["id"]}).json()["id"]
               for _ in range(2)]
    r = client.post("/admin/classes/suppression", headers=admin, json={"ids": classes, "confirmation": "SUPPRIMER"})
    assert r.json() == {"traites": 2}
    assert client.get(f"/admin/classes/{classes[0]}", headers=admin).status_code == 404
    groupe, _ = _groupe_4e(client, admin)
    r = client.post("/admin/anglais/groupes/suppression", headers=admin, json={"ids": [groupe["id"]], "confirmation": "SUPPRIMER"})
    assert r.json() == {"traites": 1}
    assert all(g["id"] != groupe["id"] for g in client.get("/admin/anglais/groupes", headers=admin).json())
    r = client.post("/admin/anglais/groupes/suppression", headers=admin, json={"ids": [groupe["id"]], "confirmation": "SUPPRIMER"})
    assert r.status_code == 404
