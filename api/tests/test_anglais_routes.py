"""Espace PKP Anglais : réservé aux professeurs d'anglais ; chaque code listé ouvre sa séance et ses PDF."""
from conftest import connecter_admin, connecter_enseignant, entete

from app.db.seed import EMAIL_ANGLAIS_DEMO


def connecter_anglais(client) -> dict[str, str]:
    return connecter_enseignant(client, email=EMAIL_ANGLAIS_DEMO)


def test_routes_reservees_aux_professeurs_d_anglais(client):
    assert client.get("/anglais/seances").status_code == 401
    # Le professeur de maths de démo n'a pas la discipline anglais : ni séances, ni corrigés, ni PDF.
    maths = connecter_enseignant(client)
    for chemin in ("/anglais/seances", "/anglais/seances/4E-01", "/anglais/seances/4E-01/pdf/animateur"):
        assert client.get(chemin, headers=maths).status_code == 403


def test_professeur_d_anglais_seul_n_ouvre_pas_l_espace_maths(client):
    connexion = client.post("/enseignants/connexion", json={"email": EMAIL_ANGLAIS_DEMO, "mot_de_passe": "demo-pkp-2026"}).json()
    assert connexion["enseigne_anglais"] is True and connexion["enseigne_maths"] is False
    assert client.get("/enseignants/classes", headers=entete(connexion["jeton"])).status_code == 403


def test_chaque_seance_listee_s_ouvre_et_produit_ses_pdf(client):
    h = connecter_anglais(client)
    liste = client.get("/anglais/seances", headers=h)
    assert liste.status_code == 200
    assert {s["niveau"] for s in liste.json()} == {"4e", "3e"}
    for item in liste.json():
        seance = client.get(f"/anglais/seances/{item['code']}", headers=h)
        assert seance.status_code == 200, item["code"]
        assert all("corrige" in f for f in seance.json()["fiches"])
        # Le même cours que le PDF : toutes les rubriques du cahier, pictogrammes compris.
        cahier = seance.json()["cahier"]
        assert {"vocab", "grammar", "listening", "model", "practice", "starters", "mission", "can_do"} <= cahier.keys()
        assert cahier["listening"]["url"].startswith("https://")
        assert all(v["image"].startswith("data:image/svg+xml;base64,") for v in cahier["visual"])
        for public in ("eleve", "animateur"):
            pdf = client.get(f"/anglais/seances/{item['code']}/pdf/{public}", headers=h)
            assert pdf.status_code == 200
            assert pdf.content.startswith(b"%PDF")


def test_chaque_objectif_du_referentiel_a_sa_seance():
    """Le programme 4e et 3e est couvert : chaque objectif du référentiel a une séance au catalogue, dans l'ordre."""
    import json

    from app.routes.anglais import CONTENU, SEANCES

    for niveau in ("4e", "3e"):
        referentiel = json.loads((CONTENU.parent / "referentiels" / niveau / "2026-2027.json").read_text(encoding="utf-8"))
        objectifs = [o["code"] for o in referentiel["objectives"]]
        assert objectifs == [code for code, (n, _) in SEANCES.items() if n == niveau]


def test_chaque_fichier_de_seance_est_au_catalogue():
    """Une séance déposée dans contenu/anglais/seances mais oubliée dans SEANCES n'apparaîtrait jamais."""
    from app.routes.anglais import CONTENU, SEANCES

    deposes = {(f.parent.name, f.name) for f in CONTENU.glob("*/*.json")}
    assert deposes == set(SEANCES.values())


def test_code_ou_pack_inconnu(client):
    h = connecter_anglais(client)
    assert client.get("/anglais/seances/5E-01", headers=h).status_code == 404
    assert client.get("/anglais/seances/4E-01/pdf/autre", headers=h).status_code == 404


def test_l_administrateur_coche_les_disciplines(client):
    h = connecter_admin(client)
    demo = next(e for e in client.get("/admin/enseignants", headers=h).json() if e["email"] == "demo@pkp.test")
    assert (demo["enseigne_maths"], demo["enseigne_anglais"]) == (True, False)
    corps = {"nom": demo["nom"], "email": demo["email"], "enseigne_maths": True, "enseigne_anglais": True}
    r = client.post(f"/admin/enseignants/{demo['id']}", headers=h, json=corps)
    assert r.status_code == 200 and r.json()["enseigne_anglais"] is True
    # La discipline est relue en base à chaque requête : pas besoin de se reconnecter.
    assert client.get("/anglais/seances", headers=connecter_enseignant(client)).status_code == 200

    aucune = {**corps, "enseigne_maths": False, "enseigne_anglais": False}
    assert client.post(f"/admin/enseignants/{demo['id']}", headers=h, json=aucune).status_code == 422


def test_pas_de_transfert_de_classes_vers_un_professeur_d_anglais_seul(client):
    h = connecter_admin(client)
    profs = client.get("/admin/enseignants", headers=h).json()
    demo = next(e for e in profs if e["email"] == "demo@pkp.test")
    anglais = next(e for e in profs if e["email"] == EMAIL_ANGLAIS_DEMO)
    r = client.post(f"/admin/enseignants/{demo['id']}/transfert", headers=h, json={"vers_enseignant_id": anglais["id"]})
    assert r.status_code == 422


def test_le_professeur_d_anglais_cree_ses_groupes_et_inscrit_ses_eleves(client):
    h = connecter_anglais(client)
    assert client.get("/anglais/groupes", headers=h).json() == []
    g3 = client.post("/anglais/groupes", headers=h, json={"nom": "3e A", "niveau": "3e"})
    g4 = client.post("/anglais/groupes", headers=h, json={"nom": "  4e   B mardi ", "niveau": "4e"})
    assert g3.status_code == g4.status_code == 201
    assert g4.json() == {"id": g4.json()["id"], "nom": "4e B mardi", "niveau": "4e", "eleves": []}

    r = client.post(f"/anglais/groupes/{g4.json()['id']}/eleves", headers=h, json={"prenoms": ["Yanis", "lina", "Yanis", " "]})
    assert r.status_code == 201
    assert [e["prenom"] for e in r.json()["groupe"]["eleves"]] == ["Lina", "Yanis"]
    r = client.post(f"/anglais/groupes/{g4.json()['id']}/eleves", headers=h, json={"prenoms": ["Lina", "Inès"]})
    assert r.json()["deja_presents"] == ["Lina"]
    assert [e["prenom"] for e in r.json()["groupe"]["eleves"]] == ["Inès", "Lina", "Yanis"]

    # 4e avant 3e, chacun avec ses élèves.
    groupes = client.get("/anglais/groupes", headers=h).json()
    assert [(g["niveau"], len(g["eleves"])) for g in groupes] == [("4e", 3), ("3e", 0)]

    lina = next(e for e in groupes[0]["eleves"] if e["prenom"] == "Lina")
    assert client.delete(f"/anglais/groupes/{g3.json()['id']}/eleves/{lina['id']}", headers=h).status_code == 404
    assert client.delete(f"/anglais/groupes/{g4.json()['id']}/eleves/{lina['id']}", headers=h).status_code == 204
    assert client.delete(f"/anglais/groupes/{g4.json()['id']}", headers=h).status_code == 204
    assert [g["nom"] for g in client.get("/anglais/groupes", headers=h).json()] == ["3e A"]


def test_groupes_valides_et_limites(client):
    h = connecter_anglais(client)
    assert client.post("/anglais/groupes", headers=h, json={"nom": "Lycée", "niveau": "2nde"}).status_code == 422
    assert client.post("/anglais/groupes", headers=h, json={"nom": "  ", "niveau": "4e"}).status_code == 422
    gid = client.post("/anglais/groupes", headers=h, json={"nom": "4e A", "niveau": "4e"}).json()["id"]
    assert client.post("/anglais/groupes", headers=h, json={"nom": "4E a", "niveau": "3e"}).status_code == 409
    assert client.post(f"/anglais/groupes/{gid}/eleves", headers=h, json={"prenoms": ["Lina Dupont 42"]}).status_code == 422
    trop = {"prenoms": [f"Élève {chr(65 + i // 26)}{chr(97 + i % 26)}" for i in range(31)]}
    r = client.post(f"/anglais/groupes/{gid}/eleves", headers=h, json=trop)
    assert r.status_code == 422 and "30" in r.json()["detail"]


def test_groupes_anglais_cloisonnes(client):
    h = connecter_anglais(client)
    gid = client.post("/anglais/groupes", headers=h, json={"nom": "4e A", "niveau": "4e"}).json()["id"]
    # Un professeur de maths n'y a pas accès ; un autre professeur d'anglais ne voit pas ce groupe.
    maths = connecter_enseignant(client)
    assert client.get("/anglais/groupes", headers=maths).status_code == 403
    admin = connecter_admin(client)
    demo = next(e for e in client.get("/admin/enseignants", headers=admin).json() if e["email"] == "demo@pkp.test")
    corps = {"nom": demo["nom"], "email": demo["email"], "enseigne_maths": True, "enseigne_anglais": True}
    assert client.post(f"/admin/enseignants/{demo['id']}", headers=admin, json=corps).status_code == 200
    autre = maths
    assert client.get("/anglais/groupes", headers=autre).json() == []
    assert client.post(f"/anglais/groupes/{gid}/eleves", headers=autre, json={"prenoms": ["Lina"]}).status_code == 404
    assert client.delete(f"/anglais/groupes/{gid}", headers=autre).status_code == 404
    # Les classes de maths ne voient pas les groupes d'anglais.
    assert all(c["niveau"] not in ("4e", "3e") for c in client.get("/enseignants/classes", headers=autre).json())


def test_un_professeur_avec_des_groupes_n_est_pas_supprime(client):
    h = connecter_anglais(client)
    client.post("/anglais/groupes", headers=h, json={"nom": "3e A", "niveau": "3e"})
    admin = connecter_admin(client)
    prof = next(e for e in client.get("/admin/enseignants", headers=admin).json() if e["email"] == EMAIL_ANGLAIS_DEMO)
    r = client.delete(f"/admin/enseignants/{prof['id']}", headers=admin, params={"confirmation": EMAIL_ANGLAIS_DEMO})
    assert r.status_code == 409 and "groupes d'anglais" in r.json()["detail"]


def _prof(client, admin, email):
    return next(e for e in client.get("/admin/enseignants", headers=admin).json() if e["email"] == email)


def test_l_administrateur_voit_et_gere_les_groupes_d_anglais(client):
    h = connecter_anglais(client)
    gid = client.post("/anglais/groupes", headers=h, json={"nom": "4e A", "niveau": "4e"}).json()["id"]
    client.post(f"/anglais/groupes/{gid}/eleves", headers=h, json={"prenoms": ["Lina", "Yanis"]})
    admin = connecter_admin(client)
    assert client.get("/admin/anglais/groupes", headers=h).status_code == 401  # jeton professeur refusé

    groupes = client.get("/admin/anglais/groupes", headers=admin).json()
    assert [(g["nom"], g["niveau"], [e["prenom"] for e in g["eleves"]]) for g in groupes] == [("4e A", "4e", ["Lina", "Yanis"])]
    prof = _prof(client, admin, EMAIL_ANGLAIS_DEMO)
    assert (prof["nb_groupes_anglais"], prof["nb_eleves_anglais"]) == (1, 2)

    # Transfert : seulement vers un professeur d'anglais.
    demo = _prof(client, admin, "demo@pkp.test")
    r = client.post(f"/admin/anglais/groupes/{gid}/transfert", headers=admin, json={"vers_enseignant_id": demo["id"]})
    assert r.status_code == 422 and "anglais" in r.json()["detail"]
    corps = {"nom": demo["nom"], "email": demo["email"], "enseigne_maths": True, "enseigne_anglais": True}
    client.post(f"/admin/enseignants/{demo['id']}", headers=admin, json=corps)
    r = client.post(f"/admin/anglais/groupes/{gid}/transfert", headers=admin, json={"vers_enseignant_id": demo["id"]})
    assert r.status_code == 200 and r.json()["enseignant_id"] == demo["id"]
    assert client.get("/anglais/groupes", headers=h).json() == []
    assert [g["nom"] for g in client.get("/anglais/groupes", headers=connecter_enseignant(client)).json()] == ["4e A"]

    # Effacement d'un élève puis du groupe, journalisés.
    lina = r.json()["eleves"][0]
    assert client.delete(f"/admin/anglais/eleves/{lina['id']}", headers=admin).status_code == 204
    assert client.delete(f"/admin/anglais/groupes/{gid}", headers=admin).status_code == 204
    assert client.get("/admin/anglais/groupes", headers=admin).json() == []
    journal = client.get("/admin/journal", headers=admin).json()["elements"]
    assert {(j["action"], j["objet"]) for j in journal} >= {
        ("transferer", "groupe_anglais"), ("supprimer", "eleve_anglais"), ("supprimer", "groupe_anglais"),
    }


def test_l_administrateur_consulte_les_seances_d_anglais(client):
    admin = connecter_admin(client)
    seances = client.get("/admin/anglais/seances", headers=admin).json()
    assert len(seances) == 20 and {s["code"] for s in seances} >= {"4E-01", "4E-10", "3E-01", "3E-10"}
    r = client.get("/admin/anglais/seances/3E-01/pdf/animateur", headers=admin)
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
