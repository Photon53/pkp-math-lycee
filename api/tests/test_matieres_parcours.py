"""Ajout d'une matière (#215) : configuration cohérente, circuit de validation commun et refus attendus par rôle.

Le Français sert de premier cas : il réutilise les domaines, les habilitations, les classes pilotes (SEC-D6) et le
circuit versionné de l'anglais. Les parcours propres à chaque rôle sont décrits dans docs/MATIERES.md.
"""
# Issue #215 — Standardiser l'ajout d'une matière (Claude)

from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app import anglais_contenu, circuit_validation, francais, permissions
from app.db import models
from app.db.seed import EMAIL_ANGLAIS_DEMO
from app.referentiel import NIVEAUX_COLLEGE, Niveau, domaine_de
from tests.conftest import connecter_eleve, connecter_enseignant
from tests.test_francais import CODE, DOMAINE, _creer, circuit, prepare  # noqa: F401 (fixtures)
from tests.test_parents import connecter_parent


# --- Configuration d'une matière : une seule déclaration, reprise partout ---------------------------------------

def test_chaque_domaine_declare_existe_en_base_avec_ses_niveaux(session):
    for d in permissions.DOMAINES:
        ligne = session.get(models.DomainePedagogique, d.code)
        assert ligne is not None, f"{d.code} : déclaré dans permissions.DOMAINES mais absent de la base (migration)"
        assert list(ligne.niveaux) == d.niveaux and ligne.libelle == d.libelle
        assert permissions.MATIERES[d.code] == d.matiere and d.code.startswith(d.matiere + "-")


@pytest.mark.parametrize("matiere", ["maths", "francais"])
def test_le_domaine_d_une_classe_est_un_domaine_declare(matiere):
    for niveau in Niveau:
        if matiere == "francais" and niveau.value not in {n for d in permissions.DOMAINES if d.matiere == "francais" for n in d.niveaux}:
            continue
        code = domaine_de(matiere, niveau)
        assert code in permissions.MATIERES, (matiere, niveau)
        assert niveau.value in next(d.niveaux for d in permissions.DOMAINES if d.code == code)
    assert domaine_de("francais", NIVEAUX_COLLEGE[0]) == "francais-college"


# --- Circuit de validation commun (anglais, français) ---------------------------------------------------------

def _contenu(*statuts, auteur_id=None):
    versions = [SimpleNamespace(statut=s, auteur_id=auteur_id, validateur=None, decide_le=None, motif_refus=None)
                for s in statuts]
    return SimpleNamespace(versions=versions, courante=versions[-1])


def test_les_deux_matieres_partagent_le_meme_circuit():
    for module in (anglais_contenu, francais):
        assert module.peut_decider is circuit_validation.peut_decider
        assert module.valider is circuit_validation.valider
        assert module.refuser is circuit_validation.refuser


def test_regles_du_circuit():
    qui, auteur = SimpleNamespace(id=1), SimpleNamespace(id=2)
    c = _contenu("valide", "soumis", auteur_id=2)
    assert circuit_validation.peut_decider(c.courante, auteur) == circuit_validation.AUTO_VALIDATION
    assert circuit_validation.peut_decider(c.versions[0], qui) is not None  # déjà validée : rien à décider
    assert circuit_validation.peut_decider(c.courante, qui) is None
    circuit_validation.refuser(c, qui, "À revoir")
    assert circuit_validation.diffusee(c) is c.versions[0]  # le refus ne retire pas la version diffusée
    c.versions.append(SimpleNamespace(statut="soumis", auteur_id=None, validateur=None, decide_le=None, motif_refus=None))
    c.courante = c.versions[-1]
    circuit_validation.valider(c, qui)
    assert [v.statut for v in c.versions] == ["archive", "refuse", "valide"]
    assert circuit_validation.diffusee(c) is c.courante and c.courante.validateur is qui


# --- Refus attendus par rôle, sur le cas Français --------------------------------------------------------------

def test_validateur_hors_niveau_ne_relit_pas(client, circuit):
    _, val6 = _creer(client, circuit["admin"], "val6@pkp.test", [{"role": "validateur", "domaine": DOMAINE, "niveau": "6e"}])
    assert client.get("/francais/validation", headers=val6).json() == []
    assert client.get(f"/francais/validation/{CODE}", headers=val6).status_code == 404
    assert client.post(f"/francais/validation/{CODE}/valider", headers=val6).status_code == 404


def test_professeur_hors_perimetre_ne_voit_ni_n_ouvre(client, circuit):
    # Professeur de maths seul : l'espace Français lui est fermé, adresse directe comprise.
    prof_maths = connecter_enseignant(client)
    assert client.get("/francais/dossiers", headers=prof_maths).status_code == 403
    assert client.get(f"/francais/dossiers/{CODE}/classes", headers=prof_maths).status_code == 403
    assert client.put(f"/francais/dossiers/{CODE}/classes/{circuit['pilote'][0]}", headers=prof_maths).status_code == 403


def test_revocation_de_la_classe_pilote_coupe_l_acces_au_dossier(client, circuit):
    classe, lina = circuit["pilote"]
    client.post(f"/francais/validation/{CODE}/valider", headers=circuit["val"])
    assert client.put(f"/francais/dossiers/{CODE}/classes/{classe}", headers=circuit["prof"]).status_code == 200
    assert client.get(f"/francais/eleve/dossiers/{CODE}", headers=lina).status_code == 200
    assert client.delete(f"/admin/classes-pilotes/{classe}", headers=circuit["admin"]).status_code == 204
    assert client.get("/francais/eleve/dossiers", headers=lina).json() == []
    r = client.get(f"/francais/eleve/dossiers/{CODE}", headers=lina)
    assert r.status_code == 403 and "pas ouvert à ta classe" in r.json()["detail"]
    # Rien n'est supprimé : l'ouverture est conservée, le professeur la voit toujours.
    lignes = client.get(f"/francais/dossiers/{CODE}/classes", headers=circuit["prof"]).json()
    ligne = next(c for c in lignes if c["id"] == classe)
    assert ligne["ouvert"] is True and ligne["acces_eleves"] is False


def test_parent_et_enfant_n_accedent_a_aucun_contenu_pilote(client, circuit):
    """SEC-D6 : l'accès par niveau (enfant de famille, parent) ne vaut que pour les domaines publics."""
    client.post(f"/francais/validation/{CODE}/valider", headers=circuit["val"])
    client.put(f"/francais/dossiers/{CODE}/classes/{circuit['pilote'][0]}", headers=circuit["prof"])
    parent = connecter_parent(client)
    for route in ("/francais/eleve/dossiers", f"/francais/eleve/dossiers/{CODE}", "/francais/dossiers",
                  f"/francais/dossiers/{CODE}/professeur", f"/francais/validation/{CODE}"):
        assert client.get(route, headers=parent).status_code == 401, route


def test_non_regression_maths_et_anglais(client, circuit):
    assert client.get("/enseignants/classes", headers=connecter_enseignant(client)).status_code == 200
    assert client.get("/eleves/moi/chapitres", headers=connecter_eleve(client)).status_code == 200
    prof_anglais = connecter_enseignant(client, email=EMAIL_ANGLAIS_DEMO)
    assert client.get("/anglais/seances", headers=prof_anglais).status_code == 200
