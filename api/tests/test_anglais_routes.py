"""Parcours de l'écran PKP Anglais : chaque code listé doit ouvrir sa séance et ses PDF."""
from conftest import connecter_enseignant


def test_routes_reservees_aux_enseignants(client):
    assert client.get("/anglais/seances").status_code == 401


def test_chaque_seance_listee_s_ouvre_et_produit_ses_pdf(client):
    h = connecter_enseignant(client)
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
    h = connecter_enseignant(client)
    assert client.get("/anglais/seances/5E-01", headers=h).status_code == 404
    assert client.get("/anglais/seances/4E-01/pdf/autre", headers=h).status_code == 404
