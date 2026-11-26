# Issue #171 — Candidatures de professeurs et demandes de partenariat (Claude)
"""Formulaire « Enseigner ou collaborer avec nous » et files d'« Accueil et demandes » (données fictives)."""

import base64
import os
import stat
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app import limitation
from app.config import settings
from app.db import models
from app.purge import purger
from tests import pdf_exemples
from tests.conftest import connecter_admin, connecter_eleve, connecter_enseignant


def b64(contenu: bytes) -> str:
    return base64.b64encode(contenu).decode()


def candidature(**champs) -> dict:
    return {
        "prenom": "Camille", "nom": "Fictif", "email": "camille.fictif@exemple.test", "telephone": "01 23 45 67 89",
        "matieres": ["maths"], "niveaux": ["2nde", "1re"], "disponibilites": "Mercredi après-midi",
        "message": "Professeure certifiée, je souhaite accompagner des lycéens.", "information_lue": True, **champs,
    }


def partenariat(**champs) -> dict:
    return {
        "prenom": "Dominique", "nom": "Essai", "email": "contact@association-fictive.test",
        "structure_nom": "Association Fictive", "structure_type": "association", "fonction": "Présidente",
        "partenariat": "Accompagnement scolaire de nos adhérents de collège.", "information_lue": True, **champs,
    }


@pytest.fixture
def ouvert(monkeypatch):
    monkeypatch.setattr(settings, "collaboration_active", True)
    monkeypatch.setattr(settings, "accueil_conservation_jours", {"candidature": 180, "partenariat": 180})
    # Les tests qui envoient beaucoup ne butent pas sur la limite ; TestAntiAbus la remet à sa valeur réelle.
    monkeypatch.setattr(limitation.collaboration_par_ip, "max_evenements", 1000)
    monkeypatch.setattr(limitation.collaboration_globale, "max_evenements", 1000)


def dossier() -> Path:
    return Path(settings.dossier_candidatures)


def deposer(client, **champs):
    return client.post("/collaboration/candidatures", json=candidature(**champs))


def fiche(client, admin, reference):
    for categorie in ("candidature", "partenariat"):
        for d in client.get(f"/admin/accueil/demandes?categorie={categorie}", headers=admin).json()["demandes"]:
            if d["reference"] == reference:
                return client.get(f"/admin/accueil/demandes/{d['id']}", headers=admin).json()
    return None


class TestFermeture:
    def test_ferme_par_defaut(self, client):
        assert client.get("/collaboration/etat").json()["ouvert"] is False
        assert deposer(client).status_code == 403
        assert client.post("/collaboration/partenariats", json=partenariat()).status_code == 403

    def test_production_exige_une_duree_de_conservation(self):
        from app.config import Settings

        reglages = dict(
            environnement="production", secret_key="x" * 40, cors_origins=["https://boussole.test"],
            database_url="postgresql+psycopg://u:p@db/pkp", servir_questions_non_validees=False,
        )
        with pytest.raises(ValueError, match="PKP_ACCUEIL_CONSERVATION_JOURS"):
            Settings(**reglages, collaboration_active=True)
        with pytest.raises(ValueError, match="PKP_ACCUEIL_CONSERVATION_JOURS"):
            Settings(**reglages, collaboration_active=True, accueil_conservation_jours={"candidature": 180})
        durees = {"candidature": 180, "partenariat": 365}
        assert Settings(**reglages, collaboration_active=True, accueil_conservation_jours=durees).collaboration_active

    def test_ferme_sans_duree_meme_active(self, client, monkeypatch):
        monkeypatch.setattr(settings, "collaboration_active", True)
        monkeypatch.setattr(settings, "accueil_conservation_jours", {"candidature": 180})
        assert client.get("/collaboration/etat").json()["ouvert"] is False
        assert deposer(client).status_code == 403


class TestCandidature:
    def test_avec_cv_dans_la_file_des_candidatures(self, client, session, ouvert):
        r = deposer(client, cv_base64=b64(pdf_exemples.ordinaire()))
        assert r.status_code == 201, r.text
        accuse = r.json()
        assert accuse["reference"].startswith("C-") and accuse["type"] == "candidature"
        admin = connecter_admin(client)
        file = client.get("/admin/accueil/demandes?categorie=candidature", headers=admin).json()
        assert [d["reference"] for d in file["demandes"]] == [accuse["reference"]] and file["demandes"][0]["a_un_cv"]
        assert client.get("/admin/accueil/demandes?categorie=partenariat", headers=admin).json()["total"] == 0
        stockee = session.scalar(select(models.DemandeAccueil))
        assert stockee.statut == "nouveau" and stockee.details["matieres"] == ["maths"] and stockee.details["niveaux"] == ["2nde", "1re"]
        # Nom serveur aléatoire, fichier privé, hors du dossier des ressources pédagogiques.
        chemin = dossier() / stockee.cv_fichier
        assert chemin.is_file() and len(stockee.cv_fichier) == 36 and "camille" not in stockee.cv_fichier.lower()
        assert Path(settings.dossier_fichiers).resolve() not in chemin.resolve().parents
        if os.name == "posix":
            assert stat.S_IMODE(chemin.stat().st_mode) == 0o600

    def test_aucun_compte_ni_habilitation_cree(self, client, session, ouvert):
        avant = {m: session.scalar(select(func.count()).select_from(m)) for m in (models.Enseignant, models.Habilitation, models.Parent)}
        assert deposer(client).status_code == 201
        assert client.post("/collaboration/partenariats", json=partenariat()).status_code == 201
        apres = {m: session.scalar(select(func.count()).select_from(m)) for m in avant}
        assert apres == avant

    def test_champs_obligatoires_minimises(self, client, ouvert):
        minimal = {"prenom": "Alex", "nom": "Fictif", "email": "alex@exemple.test", "matieres": ["anglais"],
                   "niveaux": ["6e"], "information_lue": True}
        assert client.post("/collaboration/candidatures", json=minimal).status_code == 201
        for manquant in ("prenom", "nom", "email", "matieres", "niveaux", "information_lue"):
            corps = {k: v for k, v in minimal.items() if k != manquant}
            assert client.post("/collaboration/candidatures", json=corps).status_code == 422, manquant

    @pytest.mark.parametrize("champs", [
        {"email": "pas-une-adresse"}, {"matieres": ["physique"]}, {"niveaux": ["CM2"]}, {"information_lue": False},
        {"prenom": "<script>"}, {"telephone": "appelez-moi"}, {"message": "x" * 3001},
    ])
    def test_validation(self, client, ouvert, champs):
        assert deposer(client, **champs).status_code == 422

    def test_corps_illisible(self, client, ouvert):
        r = client.post("/collaboration/candidatures", content=b"{pas du json", headers={"Content-Type": "application/json"})
        assert r.status_code == 422


class TestCvProtege:
    @pytest.mark.parametrize("contenu, motif", [
        (b"GIF89a....", "PDF"),
        (pdf_exemples.faux_entete(), ""),
        (pdf_exemples.javascript_a_l_ouverture(), "CV refusé"),
        (pdf_exemples.fichier_embarque(), "fichiers"),
        (pdf_exemples.chiffre(), "mot de passe"),
    ])
    def test_type_reel_verifie_et_rien_n_est_ecrit(self, client, session, ouvert, contenu, motif):
        r = deposer(client, cv_base64=b64(contenu))
        assert r.status_code == 422 and motif in r.json()["detail"]
        assert session.scalar(select(func.count()).select_from(models.DemandeAccueil)) == 0
        assert not dossier().exists() or not any(dossier().iterdir())

    def test_extension_trompeuse_refusee(self, client, ouvert):
        # Un fichier Word renommé en .pdf : l'en-tête réel est vérifié, pas le nom.
        assert deposer(client, cv_base64=b64(b"PK\x03\x04" + b"0" * 100)).status_code == 422

    def test_taille_maximale(self, client, ouvert, monkeypatch):
        monkeypatch.setattr(settings, "cv_taille_max_mo", 1)
        trop_gros = b"%PDF-1.4\n" + b"0" * (1024 * 1024)
        r = deposer(client, cv_base64=b64(trop_gros))
        assert r.status_code == 413 and "1 Mo" in r.json()["detail"]

    def test_base64_invalide(self, client, ouvert):
        assert deposer(client, cv_base64="pas du base64 !").status_code == 422

    def test_aucune_url_publique(self, client, session, ouvert):
        deposer(client, cv_base64=b64(pdf_exemples.ordinaire()))
        nom = session.scalar(select(models.DemandeAccueil.cv_fichier))
        for chemin in (f"/fichiers/{nom}", f"/candidatures/{nom}", f"/ressources/{nom}"):
            assert client.get(chemin).status_code == 404
        demande_id = session.scalar(select(models.DemandeAccueil.id))
        assert client.get(f"/admin/accueil/demandes/{demande_id}/cv").status_code == 401

    def test_telechargement_par_l_administrateur(self, client, session, ouvert):
        pdf = pdf_exemples.ordinaire()
        reference = deposer(client, cv_base64=b64(pdf)).json()["reference"]
        admin = connecter_admin(client)
        d = fiche(client, admin, reference)
        r = client.get(f"/admin/accueil/demandes/{d['id']}/cv", headers=admin)
        assert r.status_code == 200 and r.content == pdf
        assert r.headers["content-type"] == "application/pdf" and "attachment" in r.headers["content-disposition"]
        assert reference in r.headers["content-disposition"] and r.headers["cache-control"] == "private, no-store"
        journal = session.scalars(select(models.JournalAdmin).where(models.JournalAdmin.objet == "demande-accueil")).all()
        assert [j.action for j in journal] == ["telecharger-cv"]


class TestAccesCroise:
    """Aucun accès sans jeton administrateur : ni public, ni élève, ni professeur, ni validateur."""

    ROUTES = [
        ("get", "/admin/accueil/demandes?categorie=candidature"), ("get", "/admin/accueil/demandes/{id}"),
        ("post", "/admin/accueil/demandes/{id}"), ("get", "/admin/accueil/demandes/{id}/cv"),
        ("get", "/admin/accueil/contacts/{id}/export"), ("delete", "/admin/accueil/demandes/{id}"),
    ]

    def test_refus(self, client, session, ouvert):
        deposer(client, cv_base64=b64(pdf_exemples.ordinaire()))
        demande_id = session.scalar(select(models.DemandeAccueil.id))
        comptes = {"public": {}, "eleve": connecter_eleve(client), "professeur-validateur": connecter_enseignant(client)}
        for nom, h in comptes.items():
            for methode, chemin in self.ROUTES:
                kwargs = {"json": {"statut": "traite", "issue": "refus"}} if methode == "post" else {}
                r = getattr(client, methode)(chemin.format(id=demande_id), headers=h, **kwargs)
                assert r.status_code in (401, 403), (nom, chemin, r.status_code)
        assert session.scalar(select(func.count()).select_from(models.DemandeAccueil)) == 1

    def test_demande_inconnue(self, client, ouvert):
        admin = connecter_admin(client)
        assert client.get("/admin/accueil/demandes/999", headers=admin).status_code == 404
        assert client.get("/admin/accueil/demandes/999/cv", headers=admin).status_code == 404

    def test_partenariat_sans_cv(self, client, ouvert):
        reference = client.post("/collaboration/partenariats", json=partenariat()).json()["reference"]
        admin = connecter_admin(client)
        d = fiche(client, admin, reference)
        assert client.get(f"/admin/accueil/demandes/{d['id']}/cv", headers=admin).status_code == 404


class TestPartenariat:
    def test_dans_la_file_des_partenariats(self, client, ouvert):
        r = client.post("/collaboration/partenariats", json=partenariat())
        assert r.status_code == 201 and r.json()["reference"].startswith("P-")
        admin = connecter_admin(client)
        d = fiche(client, admin, r.json()["reference"])
        assert d["categorie"] == "partenariat" and d["organisation"] == "Association Fictive"
        assert d["details"] == {"structure_type": "association", "fonction": "Présidente"}
        assert d["message"].startswith("Accompagnement") and not d["a_un_cv"]
        assert client.get("/admin/accueil/demandes?categorie=candidature", headers=admin).json()["total"] == 0

    @pytest.mark.parametrize("champs", [{"structure_type": "entreprise"}, {"structure_nom": ""}, {"partenariat": "court"}])
    def test_validation(self, client, ouvert, champs):
        assert client.post("/collaboration/partenariats", json=partenariat(**champs)).status_code == 422

    def test_un_cv_n_est_pas_accepte(self, client, session, ouvert):
        r = client.post("/collaboration/partenariats", json=partenariat(cv_base64=b64(pdf_exemples.ordinaire())))
        assert r.status_code == 201
        assert session.scalar(select(models.DemandeAccueil.cv_fichier)) is None


class TestAntiAbus:
    @pytest.fixture(autouse=True)
    def limites_reelles(self, ouvert, monkeypatch):
        monkeypatch.setattr(limitation.collaboration_par_ip, "max_evenements", 5)
        monkeypatch.setattr(limitation.collaboration_globale, "max_evenements", 60)

    def test_piege_a_robots(self, client, session, ouvert):
        r = deposer(client, site_web="https://spam.test")
        assert r.status_code == 201  # rien ne trahit le piège…
        assert session.scalar(select(func.count()).select_from(models.DemandeAccueil)) == 0  # …rien n'est enregistré

    def test_limite_par_adresse(self, client, ouvert):
        for _ in range(5):
            assert deposer(client).status_code == 201
        r = client.post("/collaboration/partenariats", json=partenariat())
        assert r.status_code == 429 and "Retry-After" in r.headers

    def test_les_envois_refuses_comptent(self, client, ouvert):
        for _ in range(5):
            assert deposer(client, email="faux").status_code == 422
        assert deposer(client).status_code == 429

    def test_plafond_global(self, client, ouvert):
        for _ in range(limitation.collaboration_globale.max_evenements):
            limitation.collaboration_globale.enregistrer("toutes")
        assert deposer(client).status_code == 429

    def test_corps_trop_gros_coupe(self, client, ouvert, monkeypatch):
        monkeypatch.setattr(settings, "cv_taille_max_mo", 1)
        r = client.post("/collaboration/candidatures", content=b"{" + b" " * (3 * 1024 * 1024) + b"}",
                        headers={"Content-Type": "application/json"})
        assert r.status_code == 413


class TestTraitement:
    def test_statuts_issue_notes_et_journal_sans_contenu(self, client, session, ouvert):
        reference = deposer(client, cv_base64=b64(pdf_exemples.ordinaire())).json()["reference"]
        admin = connecter_admin(client)
        d = fiche(client, admin, reference)
        url = f"/admin/accueil/demandes/{d['id']}"
        moi = client.get("/admin/moi", headers=admin).json()
        assert client.post(url, headers=admin, json={"statut": "traite"}).status_code == 422  # issue exigée
        assert client.post(url, headers=admin, json={"statut": "a-traiter", "issue": "refus"}).status_code == 422
        r = client.post(url, headers=admin, json={"statut": "a-traiter", "notes_internes": "Rappeler mardi.", "responsable_id": moi["id"]})
        assert r.status_code == 200 and r.json()["notes_internes"] == "Rappeler mardi." and r.json()["responsable"]
        r = client.post(url, headers=admin, json={"statut": "traite", "issue": "suite-demandee"})
        assert r.json()["statut"] == "traite" and r.json()["issue"] == "suite-demandee"
        assert client.get("/admin/accueil/demandes?categorie=candidature&statut=traite", headers=admin).json()["total"] == 1
        r = client.post(url, headers=admin, json={"statut": "a-traiter"})  # rouverte : l'issue tombe
        assert r.json()["issue"] is None
        # Responsable : un administrateur seulement.
        prof = session.scalar(select(models.Enseignant).where(models.Enseignant.email == "demo@pkp.test"))
        assert client.post(url, headers=admin, json={"responsable_id": prof.id}).status_code == 422
        # Journal : traitement seulement, jamais coordonnées ni notes.
        for j in session.scalars(select(models.JournalAdmin).where(models.JournalAdmin.objet == "demande-accueil")):
            texte = repr((j.avant, j.apres))
            for donnee in ("Camille", "Fictif", "camille.fictif", "Rappeler", "01 23"):
                assert donnee not in texte

    def test_export(self, client, ouvert):
        reference = deposer(client).json()["reference"]
        admin = connecter_admin(client)
        d = fiche(client, admin, reference)
        r = client.get(f"/admin/accueil/contacts/{d['contact_id']}/export", headers=admin)
        export = r.json()
        assert r.status_code == 200 and export["contact"]["email"] == "camille.fictif@exemple.test"
        assert export["demandes"][0]["details"]["matieres"] == ["maths"]


class TestEffacementEtConservation:
    def test_suppression_inclut_le_cv(self, client, session, ouvert):
        reference = deposer(client, cv_base64=b64(pdf_exemples.ordinaire())).json()["reference"]
        nom = session.scalar(select(models.DemandeAccueil.cv_fichier))
        admin = connecter_admin(client)
        d = fiche(client, admin, reference)
        assert client.delete(f"/admin/accueil/demandes/{d['id']}", headers=admin).status_code == 204
        assert not (dossier() / nom).exists()
        assert session.scalar(select(func.count()).select_from(models.DemandeAccueil)) == 0

    def test_purge_apres_la_duree_decidee(self, client, session, ouvert):
        deposer(client, cv_base64=b64(pdf_exemples.ordinaire()))
        deposer(client, email="autre@exemple.test")
        ancienne, recente = session.scalars(select(models.DemandeAccueil).order_by(models.DemandeAccueil.id)).all()
        nom = ancienne.cv_fichier
        ancienne.maj_le = datetime.now(UTC) - timedelta(days=181)
        session.commit()
        purger(session, simulation=True)
        assert (dossier() / nom).exists()
        purger(session)
        restantes = session.scalars(select(models.DemandeAccueil.id)).all()
        assert restantes == [recente.id] and not (dossier() / nom).exists()

    def test_sans_duree_decidee_rien_n_est_purge(self, client, session, ouvert, monkeypatch):
        deposer(client)
        session.scalar(select(models.DemandeAccueil)).maj_le = datetime.now(UTC) - timedelta(days=3000)
        session.commit()
        monkeypatch.setattr(settings, "accueil_conservation_jours", {})
        purger(session)
        assert session.scalar(select(func.count()).select_from(models.DemandeAccueil)) == 1
