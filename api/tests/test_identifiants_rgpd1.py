"""Décision RGPD-1 (#87) : un enfant n'a aucun nom de famille ; les nouveaux comptes reçoivent un identifiant
prénom + numéro, sans séparateur (« Lina1 »), unique sur la plateforme, comparé sans casse ni accents, jamais
réattribué, de 40 caractères au plus. Les anciens identifiants (« lina-k7m4 ») restent valables."""
# Issue #87 — Retirer le nom des enfants : identifiant prénom + numéro (Claude)

import threading
from io import BytesIO

import pytest
from openpyxl import load_workbook
from sqlalchemy import select

from app import enfants
from app.db import models
from app.referentiel import Niveau
from app.schemas import EnfantSaisi
from app.security import base_identifiant, cle_identifiant
from tests.conftest import connecter_admin

MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _famille(client, admin, prenoms, email="rgpd1@x.test"):
    r = client.post("/admin/familles", headers=admin,
                    json={"email": email, "enfants": [{"prenom": p, "niveau": "2nde"} for p in prenoms]})
    assert r.status_code == 201, r.text
    return r.json()["cartes"]


def _connexion(client, identifiant, code):
    return client.post("/enfants/connexion", json={"identifiant": identifiant, "code_personnel": code})


# --- Base de l'identifiant ------------------------------------------------------------------------------------


@pytest.mark.parametrize("prenom, base", [
    ("Lina", "Lina"), ("Léa", "Lea"), ("Inès", "Ines"), ("Çağla", "Cagla"), ("Jean-Pierre", "JeanPierre"),
    ("N'Golo", "NGolo"), ("Anne Marie", "AnneMarie"), ("Ægir", "Aegir"), ("Søren", "Soren"), ("Ðaði", "Dadi"),
    ("Þóra", "Thora"), ("Maßen", "Massen"), ("Chloë", "Chloe"), ("Œdipe", "Oedipe"),
])
def test_base_sans_accents_lettres_d_origine_gardees(prenom, base):
    assert base_identifiant(prenom) == base


def test_comparaison_sans_casse_ni_accents():
    assert cle_identifiant("Léa1") == cle_identifiant("lea1") == cle_identifiant(" LEA1 ") == "lea1"
    assert cle_identifiant("lina-k7m4") == "lina-k7m4"  # ancien format inchangé


@pytest.mark.parametrize("prenom", ["-", "' -", "  ", "--'"])
def test_prenom_sans_lettre_refuse(prenom):
    with pytest.raises(ValueError):
        EnfantSaisi(prenom=prenom, niveau=Niveau.SECONDE)


def test_prenom_sans_lettre_refuse_par_l_api(client):
    admin = connecter_admin(client)
    r = client.post("/admin/familles", headers=admin, json={"email": "x@x.test", "enfants": [{"prenom": "- '", "niveau": "2nde"}]})
    assert r.status_code == 422


# --- Aucun nom de famille ------------------------------------------------------------------------------------


def test_aucun_nom_de_famille_dans_l_api(client):
    admin = connecter_admin(client)
    r = client.post("/admin/familles", headers=admin,
                    json={"email": "nom@x.test", "enfants": [{"prenom": "Lina", "nom": "Dupont", "niveau": "2nde"}]})
    assert r.status_code == 422 and "nom" in r.text  # refusé, pas ignoré en silence
    carte = _famille(client, admin, ["Lina"], email="nom@x.test")[0]
    assert "nom" not in carte
    fiche = client.get(f"/admin/parents/{client.get('/admin/parents?q=nom@', headers=admin).json()['elements'][0]['id']}/famille",
                       headers=admin).json()[0]
    assert "nom" not in fiche
    assert client.patch(f"/admin/enfants/{carte['id']}", headers=admin, json={"nom": "Dupont"}).status_code == 422
    assert "nom" not in models.Enfant.__table__.columns


def test_l_ancien_classeur_avec_des_noms_est_refuse(client):
    """Un classeur de l'ancien modèle dont la colonne « Nom » est remplie : rien n'est importé ni enregistré."""
    admin = connecter_admin(client)
    from openpyxl import Workbook

    classeur = Workbook()
    feuille = classeur.active
    feuille.title = "Élèves"
    feuille.append(["Prénom (obligatoire)", "Nom", "Niveau (obligatoire)", "E-mail du parent 1 (obligatoire)"])
    feuille.append(["Lina", "Dupont", "2nde", "ancien@x.test"])
    feuille.append(["Noé", "", "2nde", "ancien@x.test"])
    flux = BytesIO()
    classeur.save(flux)
    for simulation in ("true", "false"):
        r = client.post(f"/admin/import?simulation={simulation}", headers={**admin, "Content-Type": MIME_XLSX}, content=flux.getvalue())
        v = r.json()
        assert v["nb_erreurs"] == 1 and v["cartes"] == [], v
        assert any("Colonne « Nom » remplie" in e for ligne in v["lignes"] for e in ligne["erreurs"])
        assert "Dupont" not in r.text  # le nom n'est même pas renvoyé dans le rapport
    assert client.get("/admin/parents?q=ancien@", headers=admin).json()["total"] == 0


def test_le_modele_d_import_n_a_plus_de_colonne_nom(client):
    admin = connecter_admin(client)
    feuille = load_workbook(BytesIO(client.get("/admin/import/modele", headers=admin).content))["Élèves"]
    assert "Nom" not in [c.value for c in feuille[1]]


# --- Format, unicité, numéros jamais réattribués ---------------------------------------------------------------


def test_nouveau_format_et_compteur_partage_par_la_forme_normalisee(client):
    admin = connecter_admin(client)
    cartes = _famille(client, admin, ["Léa", "Lea", "Jean-Pierre", "Søren"])
    assert [c["identifiant"] for c in cartes] == ["Lea1", "Lea2", "JeanPierre1", "Soren1"]


def test_connexion_sans_casse_ni_accents_et_ancien_format(client, session):
    admin = connecter_admin(client)
    carte = _famille(client, admin, ["Léa"])[0]
    for saisi in ("Lea1", "lea1", "LÉA1", " léa1 "):
        assert _connexion(client, saisi, carte["code"]).status_code == 200, saisi
    # Ancien format : un enfant existant garde son identifiant et se connecte toujours.
    ancien = models.Enfant(prenom="Lina", niveau=Niveau.SECONDE, identifiant="lina-k7m4")
    code = enfants.nouveau_code(ancien)
    session.add(ancien)
    session.commit()
    assert _connexion(client, "LINA-K7M4", code).status_code == 200


def test_numero_jamais_reattribue_apres_suppression(client):
    admin = connecter_admin(client)
    lina = _famille(client, admin, ["Lina"], email="a@x.test")[0]
    assert lina["identifiant"] == "Lina1"
    r = client.delete(f"/admin/enfants/{lina['id']}?confirmation=lina1", headers=admin)  # confirmation sans casse
    assert r.status_code == 204, r.text
    assert _famille(client, admin, ["Lina"], email="b@x.test")[0]["identifiant"] == "Lina2"


def test_numero_jamais_reattribue_apres_purge(session):
    """La purge efface des lignes : un MAX(n) + 1 redonnerait le numéro ; le compteur, non."""
    for attendu in ("Zoe1", "Zoe2"):
        enfant, _ = enfants.creer(session, "Zoé", Niveau.SECONDE)
        assert enfant.identifiant == attendu
    session.commit()
    for e in session.scalars(select(models.Enfant).where(models.Enfant.prenom == "Zoé")):
        session.delete(e)
    session.commit()
    assert enfants.creer(session, "Zoé", Niveau.SECONDE)[0].identifiant == "Zoe3"


def test_identifiant_deja_pris_saute(session):
    """Un identifiant déjà présent (autre table, saisi à la main, casse différente) n'est jamais réattribué."""
    session.add(models.Enfant(prenom="Max", niveau=Niveau.SECONDE, identifiant="MAX1"))  # casse différente
    session.flush()
    assert enfants.creer(session, "Max", Niveau.SECONDE)[0].identifiant == "Max2"


def test_quarante_caracteres_au_plus(session):
    long = "Maximiliennebartholomeacassandrefrederique"  # 42 lettres
    premier = enfants.creer(session, long, Niveau.SECONDE)[0].identifiant
    assert premier == long[:39] + "1" and len(premier) == 40
    compteur = session.get(models.CompteurIdentifiant, long.lower()[:enfants.LONGUEUR_CLE_COMPTEUR])
    compteur.dernier = 9
    session.flush()
    dixieme = enfants.creer(session, long, Niveau.SECONDE)[0].identifiant
    assert dixieme == long[:38] + "10" and len(dixieme) == 40


def test_prenoms_longs_de_meme_debut_partagent_un_compteur(session):
    debut = "A" * 35
    a = enfants.creer(session, debut + "bcdefgh", Niveau.SECONDE)[0].identifiant
    b = enfants.creer(session, debut + "xyzuvw", Niveau.SECONDE)[0].identifiant
    assert a.endswith("1") and b.endswith("2") and cle_identifiant(a) != cle_identifiant(b)


def test_homonymes_de_classe_distingues_par_l_identifiant(client):
    admin = connecter_admin(client)
    a = _famille(client, admin, ["Inès"], email="i1@x.test")[0]
    b = _famille(client, admin, ["Inès"], email="i2@x.test")[0]
    cid = client.get("/admin/classes", headers=admin).json()
    cid = next(c["id"] for c in cid if c["code"] == "2NDE-A-DEMO")
    r = client.post(f"/admin/classes/{cid}/enfants", headers=admin, json={"enfant_ids": [a["id"], b["id"]]}).json()
    assert r["refus"] == [] and r["ajoutes"] == ["Inès", "Inès"]
    noms = {e["prenom"] for e in client.get(f"/admin/classes/{cid}/eleves", headers=admin).json()}
    assert {"Inès", "Ines2"} <= noms


# --- Concurrence ------------------------------------------------------------------------------------------------


def test_creations_simultanees_identifiants_distincts(fabrique):
    """Huit créations en parallèle, chacune dans sa transaction : jamais deux fois le même numéro."""
    obtenus, erreurs = [], []
    depart = threading.Barrier(8)

    def creer():
        try:
            with fabrique() as s:
                depart.wait()
                enfant, _ = enfants.creer(s, "Nina", Niveau.SECONDE)
                s.commit()
                obtenus.append(enfant.identifiant)
        except Exception as e:  # noqa: BLE001 — remonté par l'assertion
            erreurs.append(repr(e))

    fils = [threading.Thread(target=creer) for _ in range(8)]
    for f in fils:
        f.start()
    for f in fils:
        f.join()
    assert erreurs == []
    assert sorted(obtenus, key=lambda i: int(i[4:])) == [f"Nina{n}" for n in range(1, 9)]


# --- Limitation des tentatives (identifiants devinables) : constat documenté dans docs/audit/ ---------------------


def test_meme_reponse_que_l_identifiant_existe_ou_non(client):
    admin = connecter_admin(client)
    _famille(client, admin, ["Lina"])
    existe, absent = _connexion(client, "Lina1", "ABCDEF"), _connexion(client, "Lina999", "ABCDEF")
    assert existe.status_code == absent.status_code == 401
    assert existe.json() == absent.json()


def test_un_code_essaye_sur_des_identifiants_devinables_est_freine_par_adresse(client, session):
    """Balayage « Lina1, Lina2… » avec un même code depuis une adresse : chaque compte existe (codes_inconnus ne
    joue pas). SEC-D5 : au 61e échec depuis cette adresse, toute connexion élève y est refusée (429), y compris par
    une autre route de connexion élève."""
    from app import limitation
    from app.config import settings

    for _ in range(20):  # au plus 60 / 20 = 3 échecs par compte : le blocage par compte (5) ne joue pas
        enfants.creer(session, "Lina", Niveau.SECONDE)
    session.commit()
    maxi = settings.connexion_eleve_max_echecs_par_ip
    assert maxi == 60
    codes = [_connexion(client, f"Lina{(n % 20) + 1}", "ABCDEF").status_code for n in range(maxi + 1)]
    assert set(codes[:maxi]) == {401} and codes[-1] == 429
    autre_route = client.post("/eleves/connexion/identifiant", json={"identifiant": "Lina1", "code_personnel": "ABCDEF"})
    assert autre_route.status_code == 429
    # Par compte : 5 échecs, puis ce compte est bloqué même depuis une autre adresse (même clé de compte).
    limitation.echecs_eleve_par_ip.reinitialiser()
    statuts = [_connexion(client, "Lina1", "ABCDEF").status_code for _ in range(settings.connexion_eleve_max_echecs_code + 1)]
    assert statuts[-1] == 429


def test_une_classe_derriere_une_meme_adresse_n_est_pas_bloquee(client, session):
    """SEC-D5 : seuls les échecs comptent. 35 élèves qui se connectent depuis la même adresse, avec quelques fautes
    de frappe, passent tous."""
    cartes = []
    for _ in range(35):
        enfant, code = enfants.creer(session, "Eva", Niveau.SECONDE)
        cartes.append((enfant.identifiant, code))
    session.commit()
    for identifiant, code in cartes[:10]:  # dix fautes de frappe, puis tout le monde se connecte
        assert _connexion(client, identifiant, "ZZZZZZ").status_code == 401
    assert all(_connexion(client, identifiant, code).status_code == 200 for identifiant, code in cartes)


def test_prenom_d_une_lettre(client):
    admin = connecter_admin(client)
    carte = _famille(client, admin, ["A"])[0]
    assert carte["identifiant"] == "A1"
    assert _connexion(client, "a1", carte["code"]).status_code == 200
