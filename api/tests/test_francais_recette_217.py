"""Recette urgente du Français de bout en bout (#217) : import au déploiement, pilotage, habilitations, validation,
export PDF, ouverture, simulation et accès réels, rejoués par l'API comme sur l'instance."""
# Issue #217 — Recette du parcours complet du Français (Claude)

import os
import subprocess
import sys
from io import BytesIO

import pytest
from pypdf import PdfReader
from sqlalchemy import func, select

from app.db import models
from tests.conftest import RACINE_API, connecter_enseignant, entete
from tests.test_francais import CODE, DOMAINE, _activer, _corriges, _eleve_de, _importer
from tests.test_lot_a_habilitations import _creer

PROF_3E = [{"role": "professeur", "domaine": DOMAINE, "niveau": "3e"}]
VALIDATEUR_3E = [{"role": "validateur", "domaine": DOMAINE, "niveau": "3e"}]


def _texte_pdf(contenu: bytes) -> str:
    # Les retours à la ligne du PDF coupent les phrases : on compare sans espaces.
    return "".join("".join(p.extract_text() for p in PdfReader(BytesIO(contenu)).pages).split())


def _compact(texte: str) -> str:
    return "".join(texte.split())


# --- Import au déploiement : la cause de données de #212 ne peut plus se reproduire -----------------------------

def test_l_import_du_deploiement_charge_aussi_les_dossiers_de_francais(db_url, fabrique):
    """`python -m app.contenu importer`, rejoué par docker-compose et boussole-dev-sync, importe le dossier ;
    une seconde exécution ne crée rien et rien n'est validé ni ouvert aux élèves."""
    env = {**os.environ, "PKP_DATABASE_URL": db_url}
    sorties = []
    for _ in range(2):
        r = subprocess.run([sys.executable, "-m", "app.contenu", "importer"], cwd=RACINE_API, env=env,
                           capture_output=True, text=True, timeout=600)
        assert r.returncode == 0, r.stderr
        sorties.append(r.stdout)
    assert "Dossiers de français : 0 créé(s), 0 nouvelle(s) version(s), 1 inchangé(s)" in sorties[1]
    with fabrique() as s:
        assert s.scalar(select(func.count(models.DossierFrancais.id))) == 1
        statuts = s.scalars(select(models.DossierFrancaisVersion.statut)).all()
        assert statuts == ["soumis"]
        assert s.scalar(select(func.count()).select_from(models.OuvertureDossierFrancais)) == 0
        assert not s.get(models.DomainePedagogique, DOMAINE).public


def test_verifier_controle_aussi_les_dossiers_de_francais():
    r = subprocess.run([sys.executable, "-m", "app.contenu", "verifier"], cwd=RACINE_API,
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr
    assert "Dossiers de français valides : 1 dossier(s)" in r.stdout


# --- Parcours par rôle ----------------------------------------------------------------------------------------

@pytest.fixture
def recette(client, fabrique):
    """Instance prête : dossier importé, domaine actif fermé au public, comptes et classe pilote."""
    _importer(fabrique)
    from tests.conftest import connecter_admin

    admin = connecter_admin(client)
    assert _activer(client, admin).status_code == 200
    prof_info, prof = _creer(client, admin, "fr3@pkp.test", PROF_3E)
    _, validateur = _creer(client, admin, "val@pkp.test", PROF_3E + VALIDATEUR_3E)
    _, hors = _creer(client, admin, "fr6@pkp.test", [{"role": "professeur", "domaine": DOMAINE, "niveau": "6e"}])
    r = client.post("/admin/classes-pilotes", headers=admin, json={
        "matiere": "francais", "niveau": "3e", "enseignant_id": prof_info["id"], "motif": "Recette #217"})
    assert r.status_code == 201, r.text
    classe_id, code_classe = r.json()["classe_id"], r.json()["code"]
    eleve = _eleve_de(client, prof, classe_id, code_classe, "Lina")
    return {"admin": admin, "admin_prof": connecter_enseignant(client, email="admin@pkp.test"), "prof": prof,
            "validateur": validateur, "hors": hors, "classe_id": classe_id, "eleve": eleve}


def test_parcours_complet_par_role(client, recette):
    r_ = recette
    # Administrateur, professeur standard et validateur voient le dossier ; hors périmètre : liste vide, 404.
    for qui in ("admin_prof", "prof", "validateur"):
        assert [d["code"] for d in client.get("/francais/dossiers", headers=r_[qui]).json()] == [CODE], qui
    assert client.get("/francais/dossiers", headers=r_["hors"]).json() == []
    assert client.get(f"/francais/dossiers/{CODE}/pdf/professeur", headers=r_["hors"]).status_code == 404

    # Avant validation : rien n'est servi, même par adresse directe ; l'ouverture est refusée.
    assert client.get("/francais/eleve/dossiers", headers=r_["eleve"]).json() == []
    assert client.get(f"/francais/eleve/dossiers/{CODE}", headers=r_["eleve"]).status_code == 404
    assert client.put(f"/francais/dossiers/{CODE}/classes/{r_['classe_id']}", headers=r_["prof"]).status_code == 409

    # Le professeur standard ne décide pas ; le validateur et l'administrateur (#217, 23/11) voient la file.
    assert client.get("/francais/validation", headers=r_["prof"]).status_code == 403
    assert client.post(f"/francais/dossiers/{CODE}/valider", headers=r_["prof"]).status_code == 403
    for qui in ("admin", "admin_prof", "validateur"):
        assert [d["code"] for d in client.get("/francais/validation", headers=r_[qui]).json()] == [CODE], qui
    assert client.post(f"/francais/validation/{CODE}/valider", headers=r_["validateur"]).status_code == 200

    # Ouverture par le professeur, lecture par l'élève pilote, sans corrigé.
    assert client.put(f"/francais/dossiers/{CODE}/classes/{r_['classe_id']}", headers=r_["prof"]).status_code == 200
    [ligne] = client.get("/francais/eleve/dossiers", headers=r_["eleve"]).json()
    assert ligne["code"] == CODE
    lu = client.get(f"/francais/eleve/dossiers/{CODE}", headers=r_["eleve"])
    assert lu.status_code == 200
    assert not any(p in lu.text for p in _corriges() if len(p) >= 40)


def test_simulation_par_l_administrateur_et_le_professeur(client, recette):
    r_ = recette
    assert client.post(f"/francais/validation/{CODE}/valider", headers=r_["validateur"]).status_code == 200
    assert client.put(f"/francais/dossiers/{CODE}/classes/{r_['classe_id']}", headers=r_["prof"]).status_code == 200
    entrees = [("/enseignants/simulation", r_["prof"]), ("/admin/simulation", r_["admin"])]
    for route, h in entrees:
        r = client.post(route, headers=h, json={"classe_id": r_["classe_id"]})
        assert r.status_code == 200, (route, r.text)
        fictif = entete(r.json()["jeton"])
        assert [d["code"] for d in client.get("/francais/eleve/dossiers", headers=fictif).json()] == [CODE]
        assert client.get(f"/francais/eleve/dossiers/{CODE}", headers=fictif).status_code == 200
        # Jeton élève ordinaire : aucune route adulte.
        assert client.get("/francais/dossiers", headers=fictif).status_code == 401
    # Les élèves fictifs ne sont pas comptés parmi les élèves réels de la classe.
    eleves = client.get(f"/enseignants/classes/{r_['classe_id']}/eleves", headers=r_["prof"])
    assert eleves.status_code == 200
    assert [e["prenom"] for e in eleves.json()] == ["Lina"]


# --- Export PDF ---------------------------------------------------------------------------------------------

def test_export_pdf_eleve_sans_corrige_et_professeur_complet(client, recette):
    r_ = recette
    eleve = client.get(f"/francais/dossiers/{CODE}/pdf/eleve", headers=r_["prof"])
    prof = client.get(f"/francais/dossiers/{CODE}/pdf/professeur", headers=r_["prof"])
    for r in (eleve, prof):
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"
        assert r.headers["cache-control"] == "private, no-store"
        assert "NON-VALIDE" in r.headers["content-disposition"]
    texte_eleve, texte_prof = _texte_pdf(eleve.content), _texte_pdf(prof.content)
    assert _compact("NON VALIDÉ") in texte_eleve
    longs = [p for p in _corriges() if len(p) >= 40]
    assert longs and not any(_compact(p)[:60] in texte_eleve for p in longs)
    assert all(_compact(p)[:60] in texte_prof for p in longs)

    # Une fois validé, la mention disparaît.
    assert client.post(f"/francais/validation/{CODE}/valider", headers=r_["validateur"]).status_code == 200
    valide = client.get(f"/francais/dossiers/{CODE}/pdf/eleve", headers=r_["prof"])
    assert "NON-VALIDE" not in valide.headers["content-disposition"]
    assert _compact("NON VALIDÉ") not in _texte_pdf(valide.content)


def test_export_pdf_refuse_hors_des_adultes_habilites(client, recette):
    r_ = recette
    assert client.get(f"/francais/dossiers/{CODE}/pdf/corrige", headers=r_["prof"]).status_code == 404
    for h in (r_["eleve"], {}):
        assert client.get(f"/francais/dossiers/{CODE}/pdf/eleve", headers=h).status_code == 401
    for qui in ("admin", "admin_prof"):
        assert client.get(f"/francais/dossiers/{CODE}/pdf/eleve", headers=r_[qui]).status_code == 200
