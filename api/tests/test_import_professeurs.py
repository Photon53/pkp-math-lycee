"""Création en masse des comptes professeurs par fichier Excel (ticket #22)."""

import json
from io import BytesIO

from openpyxl import load_workbook

from app.routes.masse import MIME_XLSX
from tests.conftest import connecter_admin, connecter_enseignant, entete


def _classeur(client, admin, lignes):
    r = client.get("/admin/import/professeurs/modele", headers=admin)
    assert r.status_code == 200 and r.headers["content-type"] == MIME_XLSX
    classeur = load_workbook(BytesIO(r.content))
    feuille = classeur["Professeurs"]
    for i, ligne in enumerate(lignes, start=2):
        for j, valeur in enumerate(ligne, start=1):
            feuille.cell(row=i, column=j, value=valeur)
    flux = BytesIO()
    classeur.save(flux)
    return flux.getvalue()


def _importer(client, admin, contenu, simulation):
    return client.post(
        f"/admin/import/professeurs?simulation={'true' if simulation else 'false'}",
        headers={**admin, "Content-Type": MIME_XLSX}, content=contenu,
    )


def test_import_verifie_puis_cree_les_professeurs(client):
    admin = connecter_admin(client)
    contenu = _classeur(client, admin, [
        ("Mme Lot", "Lot.Maths@x.test", None, None, None),       # maths par défaut
        ("M. Lot", "lot.anglais@x.test", "non", "oui", "oui"),  # anglais + référent
        ("Mme Deux", "lot.deux@x.test", "oui", "oui", None),
        ("M. Démo", "demo@pkp.test", "oui", None, None),        # déjà inscrit : ignoré
    ])
    v = _importer(client, admin, contenu, simulation=True).json()
    assert (v["nb_professeurs"], v["nb_deja_presents"], v["nb_erreurs"], v["comptes"]) == (3, 1, 0, [])
    assert [l["matieres"] for l in v["lignes"]][:3] == [["Maths"], ["Anglais", "Référent anglais"], ["Maths", "Anglais"]]
    assert not [p for p in client.get("/admin/enseignants", headers=admin).json() if p["email"].startswith("lot.")]

    fait = _importer(client, admin, contenu, simulation=False).json()
    assert fait["nb_erreurs"] == 0 and {c["email"] for c in fait["comptes"]} == {"lot.maths@x.test", "lot.anglais@x.test", "lot.deux@x.test"}
    profs = {p["email"]: p for p in client.get("/admin/enseignants", headers=admin).json()}
    assert (profs["lot.maths@x.test"]["enseigne_maths"], profs["lot.maths@x.test"]["enseigne_anglais"]) == (True, False)
    assert profs["lot.anglais@x.test"]["referent_anglais"] and not profs["lot.anglais@x.test"]["enseigne_maths"]
    assert all(profs[e]["mdp_provisoire"] and profs[e]["role"] == "enseignant" for e in ("lot.maths@x.test", "lot.deux@x.test"))
    # Le compte existant n'a pas été touché.
    assert not profs["demo@pkp.test"]["mdp_provisoire"]

    # Première connexion : changement de mot de passe obligatoire, puis accès à l'espace.
    mdp = next(c["mot_de_passe_provisoire"] for c in fait["comptes"] if c["email"] == "lot.maths@x.test")
    r = client.post("/enseignants/connexion", json={"email": "lot.maths@x.test", "mot_de_passe": mdp})
    assert r.status_code == 200, r.text
    assert client.get("/enseignants/classes", headers=entete(r.json()["jeton"])).status_code == 403
    r = client.post("/enseignants/mot-de-passe", headers=entete(r.json()["jeton"]),
                    json={"actuel": mdp, "nouveau": "secret-choisi-par-le-prof"})
    assert r.status_code == 200
    assert connecter_enseignant(client, "lot.maths@x.test", "secret-choisi-par-le-prof")

    # Journal : une entrée par compte, aucun mot de passe provisoire.
    journal = json.dumps(client.get("/admin/journal", headers=admin).json(), ensure_ascii=False)
    assert not [c for c in fait["comptes"] if c["mot_de_passe_provisoire"] in journal]

    # Réimporter : rien de nouveau.
    again = _importer(client, admin, contenu, simulation=False).json()
    assert (again["nb_professeurs"], again["nb_deja_presents"], again["comptes"]) == (0, 4, [])


def test_une_ligne_en_erreur_bloque_tout(client):
    admin = connecter_admin(client)
    contenu = _classeur(client, admin, [
        ("Mme Bonne", "bonne@x.test", None, None, None),
        ("", "sans.nom@x.test", None, None, None),
        ("M. Mail", "pas-une-adresse", None, None, None),
        ("Mme Double", "bonne@x.test", None, None, None),
        ("M. Peut-être", "pe@x.test", "peut-être", None, None),
        ("M. Référent", "ref@x.test", "oui", "non", "oui"),
        ("M. Rien", "rien@x.test", "non", "non", None),
    ])
    r = _importer(client, admin, contenu, simulation=False)
    assert r.status_code == 200, r.text
    v = r.json()
    erreurs = {l["ligne"]: l["erreurs"] for l in v["lignes"]}
    assert erreurs[2] == [] and v["nb_erreurs"] == 6 and v["comptes"] == []
    assert erreurs[3] == ["Nom manquant."]
    assert "invalide" in erreurs[4][0]
    assert "plus haut" in erreurs[5][0]
    assert "oui ou non" in erreurs[6][0]
    assert "référent" in erreurs[7][0].lower()
    assert "discipline" in erreurs[8][0]
    assert not [p for p in client.get("/admin/enseignants", headers=admin).json() if p["email"] == "bonne@x.test"]


def test_fichier_invalide_et_acces_reserve(client):
    admin = connecter_admin(client)
    r = _importer(client, admin, b"pas un classeur", simulation=True)
    assert r.status_code == 422 and "Excel" in r.json()["detail"]
    prof = connecter_enseignant(client)
    assert client.get("/admin/import/professeurs/modele", headers=prof).status_code == 401
    assert client.post("/admin/import/professeurs", headers={**prof, "Content-Type": MIME_XLSX}, content=b"x").status_code == 401
