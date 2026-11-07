"""Export des cartes d'accès en PDF A4 (ticket #23)."""

import json
import re
from io import BytesIO

from pypdf import PdfReader

from app.cartes_pdf import CarteAImprimer, generer
from tests.conftest import connecter_admin, connecter_enseignant
from tests.test_masse import _classeur, _importer

ORIGINE = "https://boussole.test"


def _lettres(i: int) -> str:
    return chr(65 + i // 26 % 26) + chr(97 + i % 26)


def _prenom(i: int) -> str:
    return f"Élève{_lettres(i)}"


def _importer_eleves(client, admin, nombre: int, niveau: str = "2nde", classe: str | None = "2NDE-A-DEMO", debut: int = 0):
    """`nombre` enfants, trois par famille ; renvoie les cartes créées (codes en clair)."""
    lignes = [(_prenom(i), f"Fam{_lettres(i // 3)}", niveau, f"fam{i // 3:03d}@x.test", None, classe, None) for i in range(debut, debut + nombre)]
    fait = _importer(client, admin, _classeur(client, admin, lignes), simulation=False).json()
    assert fait["nb_erreurs"] == 0, fait
    return fait["cartes"]


def _pages(contenu: bytes) -> list[str]:
    return [p.extract_text() for p in PdfReader(BytesIO(contenu)).pages]


def _connexion(client, identifiant, code):
    return client.post("/enfants/connexion", json={"identifiant": identifiant, "code_personnel": code}).status_code


def test_mise_en_page_4_6_8_cartes_par_page():
    cartes = [CarteAImprimer(f"Élève {i}", "2nde", f"eleve{i}", f"CODE{i:04d}") for i in range(90)]
    for par_page, attendu in ((8, 12), (6, 15), (4, 23)):
        assert len(_pages(generer(cartes, par_page, ORIGINE))) == attendu
    texte = _pages(generer(cartes[:8], 8, ORIGINE))[0]
    assert "eleve7" in texte and "CODE0007" in texte and "boussole.test/eleve" in texte and "Seconde" in texte


def test_reemission_de_90_cartes_en_12_pages(client):
    admin = connecter_admin(client)
    anciennes = _importer_eleves(client, admin, 90)
    eleves_avant = client.get("/admin/eleves?q=Fam", headers=admin).json()

    r = client.post("/admin/cartes/pdf", headers=admin,
                    json={"ids": [c["id"] for c in anciennes], "par_page": 8, "origine": ORIGINE, "nouveaux_codes": True})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf" and r.headers["cache-control"] == "no-store"
    pages = _pages(r.content)
    assert len(pages) == 12
    texte = "\n".join(pages)

    # Chaque carte est dans le PDF avec un nouveau code, qui fonctionne ; l'ancien ne fonctionne plus.
    for c in anciennes:
        assert c["identifiant"] in texte
    premiere = anciennes[0]
    nouveau = re.search(rf"{premiere['identifiant']}\s*Code\s*(\S+)", texte).group(1)
    assert nouveau != premiere["code"]
    assert _connexion(client, premiere["identifiant"], premiere["code"]) == 401
    assert _connexion(client, premiere["identifiant"], nouveau) == 200

    # Comptes et inscriptions inchangés ; journal sans aucun code.
    assert client.get("/admin/eleves?q=Fam", headers=admin).json()["total"] == eleves_avant["total"]
    journal = json.dumps(client.get("/admin/journal", headers=admin).json(), ensure_ascii=False)
    assert "reemettre-cartes" in journal and nouveau not in journal


def test_selection_par_niveau_ou_par_classe(client):
    admin = connecter_admin(client)
    _importer_eleves(client, admin, 5, niveau="3e", classe=None)
    r = client.post("/admin/cartes/pdf", headers=admin,
                    json={"niveau": "3e", "par_page": 4, "origine": ORIGINE, "nouveaux_codes": True})
    assert r.status_code == 200, r.text
    assert len(_pages(r.content)) == 2 and _prenom(4).casefold() in "".join(_pages(r.content)).casefold()

    classes = client.get("/admin/classes", headers=admin).json()
    classe = next(c for c in classes if c["code"] == "2NDE-A-DEMO")
    _importer_eleves(client, admin, 3, debut=100)
    r = client.post("/admin/cartes/pdf", headers=admin,
                    json={"classe_id": classe["id"], "origine": ORIGINE, "nouveaux_codes": True})
    assert r.status_code == 200, r.text
    assert _prenom(102).casefold() in "".join(_pages(r.content)).casefold()


def test_reemission_refusee_sans_confirmation_ou_selection(client):
    admin = connecter_admin(client)
    cartes = _importer_eleves(client, admin, 2)
    base = {"ids": [cartes[0]["id"]], "origine": ORIGINE}
    assert client.post("/admin/cartes/pdf", headers=admin, json=base).status_code == 422
    assert client.post("/admin/cartes/pdf", headers=admin, json={**base, "nouveaux_codes": True, "niveau": "2nde"}).status_code == 422
    assert client.post("/admin/cartes/pdf", headers=admin, json={**base, "nouveaux_codes": True, "par_page": 5}).status_code == 422
    r = client.post("/admin/cartes/pdf", headers=admin, json={**base, "nouveaux_codes": True, "origine": "javascript:alert(1)"})
    assert r.status_code == 422
    assert client.post("/admin/cartes/pdf", headers=admin, json={**base, "ids": [999999], "nouveaux_codes": True}).status_code == 404
    # Rien n'a changé.
    assert _connexion(client, cartes[0]["identifiant"], cartes[0]["code"]) == 200


def test_cartes_d_un_import_sans_changer_les_codes(client):
    admin = connecter_admin(client)
    cartes = _importer_eleves(client, admin, 10)
    corps = {"cartes": [{"id": c["id"], "code": c["code"]} for c in cartes], "par_page": 6, "origine": ORIGINE}
    r = client.post("/admin/cartes/pdf/connues", headers=admin, json=corps)
    assert r.status_code == 200, r.text
    assert len(_pages(r.content)) == 2 and cartes[9]["code"] in "".join(_pages(r.content))
    assert all(_connexion(client, c["identifiant"], c["code"]) == 200 for c in cartes[:3])

    # Un code faux (ou changé depuis) est refusé : on ne peut pas imprimer une carte inventée.
    faux = {**corps, "cartes": [{"id": cartes[0]["id"], "code": "AAAA-AAAA"}]}
    r = client.post("/admin/cartes/pdf/connues", headers=admin, json=faux)
    assert r.status_code == 422 and "nouveaux codes" in r.json()["detail"]


def test_reserve_a_l_administration(client):
    prof = connecter_enseignant(client)
    corps = {"niveau": "2nde", "origine": ORIGINE, "nouveaux_codes": True}
    assert client.post("/admin/cartes/pdf", headers=prof, json=corps).status_code == 401
    assert client.post("/admin/cartes/pdf", json=corps).status_code == 401
