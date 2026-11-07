"""Ticket #22 : lot multi-rôles de bout en bout, une connexion par rôle, pas de secret au journal."""

import json

from tests.conftest import connecter_admin, entete
from tests.test_masse import _classeur, _importer


def test_lot_complet_et_connexion_par_role(client):
    admin = connecter_admin(client)

    # 1. L'administrateur crée deux professeurs (maths, anglais) : mot de passe provisoire.
    r = client.post("/admin/enseignants", headers=admin, json={"nom": "M. Audit", "email": "audit.maths@x.test"})
    assert r.status_code == 201, r.text
    mdp_maths = r.json()["mot_de_passe_provisoire"]
    r = client.post("/admin/enseignants", headers=admin, json={
        "nom": "Mme Audit", "email": "audit.anglais@x.test", "enseigne_maths": False, "enseigne_anglais": True})
    assert r.status_code == 201, r.text
    prof_anglais = r.json()["enseignant"]

    # 2. Première connexion du professeur : bloqué tant que le mot de passe provisoire n'est pas changé.
    r = client.post("/enseignants/connexion", json={"email": "audit.maths@x.test", "mot_de_passe": mdp_maths})
    assert r.status_code == 200, r.text
    jeton_prov = entete(r.json()["jeton"])
    assert client.get("/enseignants/classes", headers=jeton_prov).status_code == 403
    r = client.post("/enseignants/mot-de-passe", headers=jeton_prov,
                    json={"actuel": mdp_maths, "nouveau": "nouveau-secret-prof-2026"})
    assert r.status_code == 200, r.text
    prof = entete(r.json()["jeton"])
    assert client.get("/enseignants/classes", headers=jeton_prov).status_code == 401  # ancien jeton invalidé

    # 3. Le professeur crée sa classe ; l'admin crée le groupe d'anglais.
    r = client.post("/enseignants/classes", headers=prof, json={"niveau": "2nde"})
    assert r.status_code == 201, r.text
    classe = r.json()
    r = client.post("/admin/anglais/groupes", headers=admin,
                    json={"nom": "3e Audit", "niveau": "3e", "enseignant_id": prof_anglais["id"]})
    assert r.status_code == 201, r.text

    # 4. Import de 8 enfants, 5 familles, des seconds parents, élèves sans e-mail propre.
    lignes = [
        ("Adam", "Martin", "2nde", "martin@x.test", "martin.mere@x.test", classe["code"], None),
        ("Léa", "Martin", "3e", "martin@x.test", "martin.mere@x.test", None, "3e Audit · Mme Audit"),
        ("Noé", "Petit", "2nde", "petit@x.test", None, classe["code"], None),
        ("Lina", "Roux", "2nde", "roux@x.test", None, classe["code"], None),
        ("Sami", "Roux", "3e", "roux@x.test", None, None, "3e Audit · Mme Audit"),
        ("Emma", "Bernard", "6e", "bernard@x.test", "bernard2@x.test", None, None),
        ("Yanis", "Leroy", "Tle", "leroy@x.test", None, None, None),
        ("Jade", "Leroy", "1re", "leroy@x.test", None, None, None),
    ]
    contenu = _classeur(client, admin, lignes)
    sim = _importer(client, admin, contenu, simulation=True).json()
    assert (sim["nb_enfants"], sim["nb_comptes_nouveaux"], sim["nb_erreurs"]) == (8, 7, 0), sim
    fait = _importer(client, admin, contenu, simulation=False).json()
    assert len(fait["cartes"]) == 8 and len(fait["comptes"]) == 7

    # 5. Le professeur voit ses 3 élèves (et leurs parents).
    eleves = client.get(f"/enseignants/classes/{classe['id']}/eleves", headers=prof).json()
    assert sorted(e["prenom"] for e in eleves) == ["Adam", "Lina", "Noé"]

    # 6. Connexion enfant avec sa carte, puis ouverture de sa matière.
    adam = next(c for c in fait["cartes"] if c["prenom"] == "Adam")
    r = client.post("/enfants/connexion", json={"identifiant": adam["identifiant"], "code_personnel": adam["code"]})
    assert r.status_code == 200, r.text
    enfant = entete(r.json()["jeton"])
    espace = client.get("/enfants/moi", headers=enfant).json()
    eleve_id = espace["maths"][0]["eleve_id"]
    assert eleve_id, espace
    assert client.post(f"/enfants/moi/maths/{eleve_id}", headers=enfant).status_code == 200

    # 7. Parent : provisoire → bloqué, changement → voit ses deux enfants ; le parent 2 aussi.
    mdp = next(c["mot_de_passe_provisoire"] for c in fait["comptes"] if c["email"] == "martin@x.test")
    r = client.post("/parents/connexion", json={"email": "martin@x.test", "mot_de_passe": mdp})
    assert r.status_code == 200, r.text
    prov = entete(r.json()["jeton"])
    assert client.get("/parents/enfants", headers=prov).status_code == 403
    r = client.post("/parents/mot-de-passe", headers=prov, json={"actuel": mdp, "nouveau": "nouveau-secret-parent-26"})
    assert r.status_code == 200, r.text
    famille = client.get("/parents/famille", headers=entete(r.json()["jeton"])).json()
    assert sorted(e["enfant"]["prenom"] for e in famille) == ["Adam", "Léa"], famille
    mdp2 = next(c["mot_de_passe_provisoire"] for c in fait["comptes"] if c["email"] == "martin.mere@x.test")
    r = client.post("/parents/connexion", json={"email": "martin.mere@x.test", "mot_de_passe": mdp2})
    assert r.status_code == 200, r.text

    # 8. Aucun secret (mots de passe provisoires, codes de carte) dans le journal d'administration.
    page = json.dumps(client.get("/admin/journal", headers=admin).json(), ensure_ascii=False)
    secrets_emis = [mdp_maths, *(c["mot_de_passe_provisoire"] for c in fait["comptes"]), *(c["code"] for c in fait["cartes"])]
    assert not [s for s in secrets_emis if s in page]
