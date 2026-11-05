"""Route publique de la page d'accueil : l'état de chaque parcours, sans connexion ni donnée personnelle."""

from app.db import models
from tests.conftest import connecter_admin

CHAMPS = {"code", "matiere", "cycle", "libelle", "niveaux", "etat"}


def _etats(client) -> dict[str, str]:
    r = client.get("/domaines/publics")
    assert r.status_code == 200
    return {d["code"]: d["etat"] for d in r.json()}


def test_sans_connexion_les_six_domaines_dans_l_ordre(client):
    r = client.get("/domaines/publics")
    assert r.status_code == 200
    domaines = r.json()
    assert [d["code"] for d in domaines] == [
        "maths-college", "maths-lycee", "anglais-college", "anglais-lycee", "francais-college", "francais-lycee",
    ]
    # Seulement la description du parcours : ni compteur de comptes, ni habilitation.
    assert all(set(d) == CHAMPS for d in domaines)
    assert domaines[1]["libelle"] == "Maths lycée"
    assert domaines[1]["niveaux"] == ["2nde", "1re", "Tle"]


def test_etat_tire_des_reglages_du_domaine(client):
    assert _etats(client) == {
        "maths-college": "en_chantier",
        "maths-lycee": "ouvert",
        "anglais-college": "ouvert",
        "anglais-lycee": "en_chantier",
        "francais-college": "en_chantier",
        "francais-lycee": "en_chantier",
    }


def test_suit_l_ouverture_par_l_administrateur(client):
    admin = connecter_admin(client)
    assert client.post("/admin/domaines/maths-college", headers=admin, json={"actif": True, "public": False}).status_code == 200
    assert _etats(client)["maths-college"] == "en_preparation"
    assert client.post("/admin/domaines/maths-college", headers=admin, json={"actif": True, "public": True}).status_code == 200
    assert _etats(client)["maths-college"] == "ouvert"


def test_lecture_seule(client):
    assert client.post("/domaines/publics", json={}).status_code == 405


def test_etat_du_domaine():
    from app.routes.domaines import etat_du_domaine

    d = models.DomainePedagogique(code="x", matiere="m", cycle="c", libelle="X", niveaux=[], ordre=1, actif=False, public=False)
    assert etat_du_domaine(d) == "en_chantier"
    d.actif = True
    assert etat_du_domaine(d) == "en_preparation"
    d.public = True
    assert etat_du_domaine(d) == "ouvert"
