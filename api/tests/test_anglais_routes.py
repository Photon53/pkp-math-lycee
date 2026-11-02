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
        for public in ("eleve", "animateur"):
            pdf = client.get(f"/anglais/seances/{item['code']}/pdf/{public}", headers=h)
            assert pdf.status_code == 200
            assert pdf.content.startswith(b"%PDF")


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
