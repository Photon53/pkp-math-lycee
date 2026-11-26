# Issue #172 — Accueil et demandes : contacts adultes et demandes (Claude)
"""Socle « Accueil et demandes » : files, rattachement prudent, traitement, droits, effacement et purge (données fictives)."""

import base64
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app import accueil, limitation
from app.config import settings
from app.db import models
from app.purge import purger
from tests import pdf_exemples
from tests.conftest import connecter_admin, connecter_eleve, connecter_enseignant
from tests.test_parents import connecter_parent

DUREES = {"famille": 30, "information": 60, "candidature": 180, "partenariat": 365}


@pytest.fixture
def durees(monkeypatch):
    monkeypatch.setattr(settings, "accueil_conservation_jours", dict(DUREES))
    monkeypatch.setattr(settings, "collaboration_active", True)
    monkeypatch.setattr(limitation.collaboration_par_ip, "max_evenements", 1000)


@pytest.fixture
def admin(client):
    return connecter_admin(client)


def saisir(client, admin, categorie="famille", email="parent.fictif@exemple.test", **champs):
    corps = {"categorie": categorie, "prenom": "Sacha", "nom": "Fictif", "email": email,
             "message": "Souhaite un bilan pour son enfant en 4e.", **champs}
    return client.post("/admin/accueil/demandes", headers=admin, json=corps)


def compter(session, modele) -> int:
    return session.scalar(select(func.count()).select_from(modele))


class TestFiles:
    def test_quatre_files_et_durees(self, client, admin, durees):
        saisir(client, admin, "famille")
        saisir(client, admin, "information", email="autre@exemple.test")
        files = {f["categorie"]: f for f in client.get("/admin/accueil/files", headers=admin).json()}
        assert list(files) == ["famille", "information", "candidature", "partenariat"]
        assert files["famille"]["nouvelles"] == 1 and files["information"]["nouvelles"] == 1 and files["candidature"]["nouvelles"] == 0
        assert files["partenariat"]["conservation_jours"] == 365

    def test_chaque_demande_dans_sa_file(self, client, admin, durees):
        saisir(client, admin, "famille")
        saisir(client, admin, "information")
        for categorie in ("famille", "information"):
            page = client.get(f"/admin/accueil/demandes?categorie={categorie}", headers=admin).json()
            assert page["total"] == 1 and page["demandes"][0]["categorie"] == categorie
        assert client.get("/admin/accueil/demandes?categorie=candidature", headers=admin).json()["total"] == 0

    def test_sans_duree_decidee_rien_n_est_enregistre(self, client, session, admin, monkeypatch):
        monkeypatch.setattr(settings, "accueil_conservation_jours", {"information": 60})
        r = saisir(client, admin, "famille")
        assert r.status_code == 409 and "durée de conservation" in r.json()["detail"]
        assert compter(session, models.DemandeAccueil) == 0 and compter(session, models.ContactAdulte) == 0
        assert saisir(client, admin, "information").status_code == 201

    @pytest.mark.parametrize("categorie", ["candidature", "partenariat", "eleve"])
    def test_saisie_reservee_aux_familles_et_informations(self, client, admin, durees, categorie):
        assert saisir(client, admin, categorie).status_code == 422

    def test_aucun_compte_ni_inscription(self, client, session, admin, durees):
        avant = {m: compter(session, m) for m in (models.Parent, models.Enfant, models.Eleve, models.Enseignant, models.Habilitation)}
        saisir(client, admin, "famille")
        r = client.post(f"/admin/accueil/demandes/{saisir(client, admin, 'famille', email='x@exemple.test').json()['id']}",
                        headers=admin, json={"statut": "traite", "issue": "inscription-effective"})
        assert r.status_code == 200
        assert {m: compter(session, m) for m in avant} == avant  # l'issue est notée, rien n'est créé


class TestRattachementPrudent:
    def test_meme_email_normalise_meme_contact_sans_ecraser(self, client, session, admin, durees):
        premiere = saisir(client, admin, "famille", email="Parent.Fictif@Exemple.test").json()
        seconde = saisir(client, admin, "information", email="  parent.fictif@exemple.TEST ", prenom="Autre", nom="Nom",
                         telephone="0600000000").json()
        assert seconde["contact_id"] == premiere["contact_id"]
        assert [d["reference"] for d in seconde["autres_demandes"]] == [premiere["reference"]]
        contact = session.get(models.ContactAdulte, premiere["contact_id"])
        assert (contact.prenom, contact.nom, contact.telephone) == ("Sacha", "Fictif", None)  # rien d'écrasé
        assert (seconde["prenom"], seconde["telephone"]) == ("Autre", "0600000000")  # saisie gardée sur la demande
        # Les catégories et l'historique restent distincts.
        assert {seconde["categorie"], seconde["autres_demandes"][0]["categorie"]} == {"famille", "information"}

    @pytest.mark.parametrize("voisin", ["parent.fictif+1@exemple.test", "parentfictif@exemple.test", "parent.fictif@exemple.fr"])
    def test_email_ressemblant_jamais_rattache(self, client, admin, durees, voisin):
        a = saisir(client, admin, email="parent.fictif@exemple.test").json()
        b = saisir(client, admin, email=voisin).json()
        assert a["contact_id"] != b["contact_id"] and b["autres_demandes"] == []

    def test_detacher_une_demande_rattachee_a_tort(self, client, session, admin, durees):
        a = saisir(client, admin, email="commun@exemple.test").json()
        b = saisir(client, admin, "information", email="commun@exemple.test", prenom="Dominique").json()
        r = client.post(f"/admin/accueil/demandes/{b['id']}/detacher", headers=admin)
        assert r.status_code == 200 and r.json()["contact_id"] != a["contact_id"]
        assert r.json()["contact_fiche"]["prenom"] == "Dominique" and r.json()["autres_demandes"] == []
        assert compter(session, models.ContactAdulte) == 2
        # La dernière demande d'un contact ne se détache pas.
        assert client.post(f"/admin/accueil/demandes/{a['id']}/detacher", headers=admin).status_code == 422

    def test_le_contact_ne_relie_aucun_compte(self, client, session, admin, durees):
        """Un e-mail identique à celui d'un compte parent ne rattache ni enfant ni compte, et ne donne aucun accès."""
        connecter_parent(client)
        parent = session.scalar(select(models.Parent))
        d = saisir(client, admin, email=parent.email).json()
        assert set(d["contact_fiche"]) == {"id", "prenom", "nom", "email", "telephone", "cree_le"}
        assert len(session.get(models.Parent, parent.id).enfants) == len(parent.enfants)


class TestTraitement:
    def test_issues_par_file(self, client, admin, durees):
        famille = saisir(client, admin, "famille").json()
        information = saisir(client, admin, "information", email="i@exemple.test").json()
        url = "/admin/accueil/demandes/{}"
        assert client.post(url.format(famille["id"]), headers=admin, json={"statut": "traite", "issue": "inscription-effective"}).status_code == 200
        r = client.post(url.format(information["id"]), headers=admin, json={"statut": "traite", "issue": "inscription-effective"})
        assert r.status_code == 422 and "file" in r.json()["detail"]
        assert client.post(url.format(information["id"]), headers=admin, json={"statut": "traite", "issue": "refus"}).status_code == 422
        assert client.post(url.format(information["id"]), headers=admin, json={"statut": "traite", "issue": "cloture"}).status_code == 200

    def test_statuts_notes_responsable(self, client, session, admin, durees):
        d = saisir(client, admin).json()
        url = f"/admin/accueil/demandes/{d['id']}"
        moi = client.get("/admin/moi", headers=admin).json()
        assert client.post(url, headers=admin, json={"statut": "traite"}).status_code == 422  # issue exigée
        r = client.post(url, headers=admin, json={"statut": "a-traiter", "notes_internes": "Rappeler jeudi.", "responsable_id": moi["id"]})
        assert r.json()["statut"] == "a-traiter" and r.json()["notes_internes"] == "Rappeler jeudi." and r.json()["responsable"]
        prof = session.scalar(select(models.Enseignant).where(models.Enseignant.email == "demo@pkp.test"))
        assert client.post(url, headers=admin, json={"responsable_id": prof.id}).status_code == 422

    def test_journal_sans_contenu_personnel(self, client, session, admin, durees):
        d = saisir(client, admin, telephone="0611111111").json()
        client.post(f"/admin/accueil/demandes/{d['id']}", headers=admin, json={"notes_internes": "Très motivée."})
        client.get(f"/admin/accueil/contacts/{d['contact_id']}/export", headers=admin)
        client.delete(f"/admin/accueil/contacts/{d['contact_id']}", headers=admin)
        lignes = session.scalars(select(models.JournalAdmin).where(models.JournalAdmin.objet.in_(["demande-accueil", "contact-accueil"]))).all()
        assert [j.action for j in lignes] == ["saisir", "traiter", "exporter", "supprimer"]
        for j in lignes:
            texte = repr((j.avant, j.apres))
            for donnee in ("Sacha", "Fictif", "parent.fictif", "0611", "bilan", "motivée"):
                assert donnee not in texte

    def test_recherche_filtres_et_pagination(self, client, session, admin, durees):
        contact = models.ContactAdulte(prenom="Essai", nom="Lot", email="lot@exemple.test", cree_le=datetime.now(UTC))
        for i in range(55):
            session.add(models.DemandeAccueil(
                reference=f"F-ESSAI{i:03d}", contact=contact, categorie="famille", origine="saisie-admin", prenom="Essai",
                nom=f"Numero{i}", email="lot@exemple.test", statut="traite" if i % 5 == 0 else "nouveau",
                issue="cloture" if i % 5 == 0 else None, details={},
                cree_le=datetime(2026, 11, 1, tzinfo=UTC) + timedelta(hours=i), maj_le=datetime.now(UTC),
            ))
        session.commit()
        base = "/admin/accueil/demandes?categorie=famille"
        p1, p2 = (client.get(f"{base}&page={n}", headers=admin).json() for n in (1, 2))
        assert p1["total"] == 55 and len(p1["demandes"]) == 50 and len(p2["demandes"]) == 5
        assert p1["demandes"][0]["reference"] == "F-ESSAI054"
        assert client.get(f"{base}&q=numero7", headers=admin).json()["total"] == 1
        assert client.get(f"{base}&statut=traite", headers=admin).json()["total"] == 11
        assert client.get(f"{base}&depuis=2026-11-03T00:00:00Z", headers=admin).json()["total"] == 7
        assert client.get("/admin/accueil/demandes?page=0", headers=admin).status_code == 422


class TestDroits:
    ROUTES = [
        ("get", "/admin/accueil/files"), ("get", "/admin/accueil/demandes"), ("post", "/admin/accueil/demandes"),
        ("get", "/admin/accueil/demandes/{id}"), ("post", "/admin/accueil/demandes/{id}"),
        ("post", "/admin/accueil/demandes/{id}/detacher"), ("delete", "/admin/accueil/demandes/{id}"),
        ("get", "/admin/accueil/contacts/{contact}/export"), ("delete", "/admin/accueil/contacts/{contact}"),
    ]

    def test_aucun_acces_hors_administrateurs(self, client, session, admin, durees):
        d = saisir(client, admin).json()
        comptes = {
            "public": {}, "eleve": connecter_eleve(client), "parent": connecter_parent(client),
            "professeur-validateur": connecter_enseignant(client),
        }
        for nom, h in comptes.items():
            for methode, chemin in self.ROUTES:
                kwargs = {"json": {"categorie": "famille", "statut": "a-traiter"}} if methode == "post" else {}
                r = getattr(client, methode)(chemin.format(id=d["id"], contact=d["contact_id"]), headers=h, **kwargs)
                assert r.status_code in (401, 403), (nom, chemin, r.status_code)
        assert compter(session, models.DemandeAccueil) == 1

    def test_introuvables(self, client, admin):
        for chemin in ("/admin/accueil/demandes/999", "/admin/accueil/contacts/999/export"):
            assert client.get(chemin, headers=admin).status_code == 404


class TestEffacementEtPurge:
    def _candidature(self, client, email):
        corps = {"prenom": "Camille", "nom": "Fictif", "email": email, "matieres": ["maths"], "niveaux": ["Tle"],
                 "information_lue": True, "cv_base64": base64.b64encode(pdf_exemples.ordinaire()).decode()}
        assert client.post("/collaboration/candidatures", json=corps).status_code == 201

    def test_supprimer_le_contact_efface_toutes_ses_demandes_et_ses_cv(self, client, session, admin, durees):
        self._candidature(client, "camille@exemple.test")
        d = saisir(client, admin, "information", email="camille@exemple.test").json()
        cv = session.scalar(select(models.DemandeAccueil.cv_fichier).where(models.DemandeAccueil.cv_fichier.is_not(None)))
        assert len(d["autres_demandes"]) == 1 and (Path(settings.dossier_candidatures) / cv).exists()
        assert client.delete(f"/admin/accueil/contacts/{d['contact_id']}", headers=admin).status_code == 204
        assert compter(session, models.DemandeAccueil) == 0 and compter(session, models.ContactAdulte) == 0
        assert not (Path(settings.dossier_candidatures) / cv).exists()

    def test_la_derniere_demande_emporte_le_contact(self, client, session, admin, durees):
        a = saisir(client, admin).json()
        b = saisir(client, admin, "information").json()
        client.delete(f"/admin/accueil/demandes/{a['id']}", headers=admin)
        assert compter(session, models.ContactAdulte) == 1
        client.delete(f"/admin/accueil/demandes/{b['id']}", headers=admin)
        assert compter(session, models.ContactAdulte) == 0

    def test_purge_file_par_file(self, client, session, admin, durees):
        famille = saisir(client, admin, "famille").json()  # 30 jours
        information = saisir(client, admin, "information").json()  # 60 jours, même contact
        self._candidature(client, "c@exemple.test")  # 180 jours
        il_y_a_45_jours = datetime.now(UTC) - timedelta(days=45)
        for d in session.scalars(select(models.DemandeAccueil)):
            d.maj_le = il_y_a_45_jours
        session.commit()
        cv = session.scalar(select(models.DemandeAccueil.cv_fichier).where(models.DemandeAccueil.cv_fichier.is_not(None)))
        assert accueil.purger(session, simulation=True) == 1
        purger(session)
        restantes = set(session.scalars(select(models.DemandeAccueil.reference)))
        assert famille["reference"] not in restantes and information["reference"] in restantes and len(restantes) == 2
        assert (Path(settings.dossier_candidatures) / cv).exists()
        # Plus tard : tout est échu ; contacts et CV partent avec.
        purger(session, maintenant=datetime.now(UTC) + timedelta(days=400))
        assert compter(session, models.DemandeAccueil) == 0 and compter(session, models.ContactAdulte) == 0
        assert not (Path(settings.dossier_candidatures) / cv).exists()

    def test_file_sans_duree_jamais_purgee(self, client, session, admin, durees, monkeypatch):
        saisir(client, admin, "famille")
        monkeypatch.setattr(settings, "accueil_conservation_jours", {"information": 60})
        purger(session, maintenant=datetime.now(UTC) + timedelta(days=3000))
        assert compter(session, models.DemandeAccueil) == 1


class TestMigration:
    """0047 reprend les demandes de 0046 (#171, déjà publiée) dans le socle, et 0046 se retrouve au retour arrière."""

    def test_reprise_des_demandes_de_collaboration(self, db_url):
        from alembic import command

        from app.db.session import creer_moteur
        from tests.conftest import config_alembic

        config = config_alembic(db_url)
        command.downgrade(config, "0046")
        moteur = creer_moteur(db_url)
        with moteur.begin() as c:
            for ref, type_, email, extra in (
                ("C-AAAA2222", "candidature", "Camille@Exemple.test", "matieres, niveaux, disponibilites, cv_fichier, cv_taille_octets, statut, issue"),
                ("P-BBBB3333", "partenariat", "camille@exemple.test ", "structure_nom, structure_type, fonction, statut"),
            ):
                valeurs = {
                    "candidature": "'maths,francais', '2nde,Tle', 'mercredi', 'abc.pdf', 1234, 'traite', 'suite-demandee'",
                    "partenariat": "'Association Fictive', 'association', 'Présidente', 'a-traiter'",
                }[type_]
                c.exec_driver_sql(
                    f"insert into demande_collaboration (reference, type, prenom, nom, email, message, cree_le, maj_le, {extra}) "
                    f"values ('{ref}', '{type_}', 'Camille', 'Fictif', '{email}', 'Bonjour', '2026-11-19 08:00:00', "
                    f"'2026-11-19 09:00:00', {valeurs})"
                )
        moteur.dispose()

        command.upgrade(config, "head")
        moteur = creer_moteur(db_url)
        with moteur.connect() as c:
            assert c.exec_driver_sql("select count(*) from contact_adulte").scalar() == 1  # même e-mail normalisé
            lignes = {r.reference: r for r in c.exec_driver_sql(
                "select reference, categorie, origine, email, organisation, details, cv_fichier, statut, issue from demande_accueil"
            )}
            assert "demande_collaboration" not in sa_tables(moteur)
        moteur.dispose()
        cand, part = lignes["C-AAAA2222"], lignes["P-BBBB3333"]
        assert (cand.categorie, cand.origine, cand.email, cand.cv_fichier, cand.statut, cand.issue) == (
            "candidature", "formulaire-collaboration", "camille@exemple.test", "abc.pdf", "traite", "suite-demandee")
        assert json.loads(cand.details) == {"matieres": ["maths", "francais"], "niveaux": ["2nde", "Tle"], "disponibilites": "mercredi"}
        assert part.organisation == "Association Fictive" and json.loads(part.details) == {"structure_type": "association", "fonction": "Présidente"}

        command.downgrade(config, "0046")
        moteur = creer_moteur(db_url)
        with moteur.connect() as c:
            retour = {r.reference: r for r in c.exec_driver_sql("select reference, type, matieres, structure_nom, cv_fichier, issue from demande_collaboration")}
        moteur.dispose()
        assert retour["C-AAAA2222"].matieres == "maths,francais" and retour["C-AAAA2222"].cv_fichier == "abc.pdf"
        assert retour["C-AAAA2222"].issue == "suite-demandee" and retour["P-BBBB3333"].structure_nom == "Association Fictive"


def sa_tables(moteur) -> set[str]:
    from sqlalchemy import inspect

    return set(inspect(moteur).get_table_names())
