"""Maths collège : niveaux 6e à 3e, dans leur propre domaine (fermé tant que le contenu n'est pas validé)."""

from app import permissions
from app.db import models
from app.referentiel import PARCOURS_PAR_NIVEAU, Niveau, Parcours, domaine_maths
from tests.conftest import connecter_admin, connecter_enseignant


def test_domaine_selon_le_niveau():
    assert [domaine_maths(n) for n in Niveau] == ["maths-college"] * 4 + ["maths-lycee"] * 3
    assert Parcours.EXAMENS in PARCOURS_PAR_NIVEAU[Niveau.TROISIEME]
    assert Parcours.EXAMENS not in PARCOURS_PAR_NIVEAU[Niveau.SIXIEME]


def test_classe_de_college_refusee_tant_que_le_domaine_est_ferme_puis_rangee_dans_son_domaine(client, session):
    prof = connecter_enseignant(client)
    corps = {"niveau": "5e", "parcours": "tronc-commun"}
    assert client.post("/enseignants/classes", headers=prof, json=corps).status_code == 403
    admin = connecter_admin(client)
    assert client.post("/admin/domaines/maths-college", headers=admin, json={"actif": True, "public": True}).status_code == 200
    r = client.post("/enseignants/classes", headers=prof, json=corps)
    assert r.status_code == 201, r.text
    assert r.json()["code"].startswith("5E-")
    assert session.get(models.Classe, r.json()["id"]).domaine_code == "maths-college"
    assert client.post("/enseignants/classes", headers=prof, json={"niveau": "6e", "parcours": "specialite"}).status_code == 422


def test_un_professeur_de_maths_college_a_l_espace_des_classes(client, session):
    admin = connecter_admin(client)
    client.post("/admin/domaines/maths-college", headers=admin, json={"actif": True, "public": False})
    enseignant = models.Enseignant(nom="P", email="p@x.test", mot_de_passe_hash="h")
    session.add(enseignant)
    permissions.appliquer(session, enseignant, [permissions.Portee(permissions.PROFESSEUR, permissions.MATHS_COLLEGE)], None)
    assert enseignant.enseigne_maths


def test_referentiels_du_college():
    from app import programmes

    r = programmes.charger()
    niveaux = {code: r.programmes[code].niveau.value for code in ("6E-2025", "5E-2026", "4E-2020", "3E-2020")}
    assert niveaux == {"6E-2025": "6e", "5E-2026": "5e", "4E-2020": "4e", "3E-2020": "3e"}
    for code in niveaux:
        types = {a.type.value for _, a in r.du_programme(code)}
        assert "capacite" in types, code
    assert any(a.type.value == "automatisme" for _, a in r.du_programme("6E-2025"))
