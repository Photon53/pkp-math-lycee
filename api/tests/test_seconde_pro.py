"""Ticket #25 : parcours « voie professionnelle » en seconde (seconde préparant au bac pro).

Distinct de la seconde générale (tronc commun) et de la voie technologique ; les classes et progressions
existantes ne changent pas.
"""

from sqlalchemy import select

from app.contenu import charger, importer
from app.db import models
from app.referentiel import PARCOURS_PAR_NIVEAU, Niveau, Parcours, est_principal, parcours_par_defaut
from tests.conftest import connecter_admin, connecter_enseignant, entete
from tests.test_contenu import ecrire, erreurs
from tests.test_familles import _carte, _famille

CHAPITRE_PRO = """
chapitre: {code: 2PRO-STAT, niveau: 2nde, parcours: professionnel, ordre: 1, titre: Statistique à une variable}
competences:
  - code: 2PRO-STAT-MOY
    libelle: Calculer une moyenne
    questions:
      - {code: 2PRO-STAT-MOY-01, difficulte: 1, type: numerique, enonce: "Moyenne de 8 et 12 ?", solution: "10"}
"""
DOSSIER_PRO = "2nde/professionnel/01-statistique.yaml"


def importer_chapitre_pro(session, tmp_path) -> models.Chapitre:
    ecrire(tmp_path, CHAPITRE_PRO, DOSSIER_PRO)
    importer(session, charger(tmp_path), archiver_absentes=False)
    session.commit()
    return session.scalar(select(models.Chapitre).where(models.Chapitre.code == "2PRO-STAT"))


class TestReferentiel:
    def test_parcours_principal_de_seconde_seulement(self):
        assert Parcours.PROFESSIONNEL in PARCOURS_PAR_NIVEAU[Niveau.SECONDE]
        assert est_principal(Parcours.PROFESSIONNEL)
        for niveau, permis in PARCOURS_PAR_NIVEAU.items():
            if niveau is not Niveau.SECONDE:
                assert Parcours.PROFESSIONNEL not in permis
        # Jamais attribué par défaut : la seconde générale reste le parcours d'une classe sans choix.
        assert parcours_par_defaut(Niveau.SECONDE) is Parcours.TRONC_COMMUN

    def test_distinct_de_la_voie_technologique(self):
        assert Parcours.PROFESSIONNEL is not Parcours.TECHNOLOGIQUE
        assert Parcours.TECHNOLOGIQUE not in PARCOURS_PAR_NIVEAU[Niveau.SECONDE]


class TestContenu:
    def test_chapitre_range_sous_2nde_professionnel(self, tmp_path):
        ecrire(tmp_path, CHAPITRE_PRO, DOSSIER_PRO)
        [(_, fichier)] = charger(tmp_path)
        assert fichier.chapitre.parcours is Parcours.PROFESSIONNEL

    def test_refuse_hors_seconde(self, tmp_path):
        ecrire(tmp_path, CHAPITRE_PRO.replace("niveau: 2nde", "niveau: 1re"), "1re/professionnel/01-statistique.yaml")
        assert "parcours « professionnel » impossible en 1re" in erreurs(tmp_path)


class TestClasses:
    def test_classe_de_seconde_pro_avec_son_seul_programme(self, client, session, tmp_path):
        importer_chapitre_pro(session, tmp_path)
        prof = connecter_enseignant(client)
        r = client.post("/enseignants/classes", headers=prof, json={"niveau": "2nde", "parcours": "professionnel"})
        assert r.status_code == 201, r.text
        assert r.json()["code"].startswith("2NDE-PRO-")
        classe = session.get(models.Classe, r.json()["id"])
        assert classe.domaine_code == "maths-lycee"
        assert [c.code for c in classe.chapitres_proposes] == ["2PRO-STAT"]
        # Critère 1 : aucun chapitre de seconde générale dans le programme de la classe.
        assert all(c.parcours is Parcours.PROFESSIONNEL for c in classe.chapitres_proposes)

    def test_classe_de_seconde_generale_sans_chapitre_pro(self, client, session, tmp_path):
        importer_chapitre_pro(session, tmp_path)
        r = client.post("/enseignants/classes", headers=connecter_enseignant(client), json={"niveau": "2nde"})
        assert r.status_code == 201
        classe = session.get(models.Classe, r.json()["id"])
        assert classe.parcours is Parcours.TRONC_COMMUN
        assert classe.chapitres_proposes and "2PRO-STAT" not in [c.code for c in classe.chapitres_proposes]

    def test_refusee_hors_seconde(self, client):
        r = client.post("/enseignants/classes", headers=connecter_enseignant(client),
                        json={"niveau": "1re", "parcours": "professionnel"})
        assert r.status_code == 422

    def test_classes_existantes_inchangees(self, client, session):
        """La démo n'a aucune classe de voie professionnelle : rien n'a été converti."""
        assert session.scalar(select(models.Classe).where(models.Classe.parcours == Parcours.PROFESSIONNEL)) is None


class TestEnfant:
    def _enfant_en_classe(self, client, session, tmp_path, parcours: str):
        importer_chapitre_pro(session, tmp_path)
        admin = connecter_admin(client)
        ines = next(c for c in _famille(client, admin)["cartes"] if c["prenom"] == "Inès")
        prof = connecter_enseignant(client)
        cid = client.post("/enseignants/classes", headers=prof, json={"niveau": "2nde", "parcours": parcours}).json()["id"]
        client.post(f"/enseignants/classes/{cid}/enfants", headers=prof, json={"enfant_ids": [ines["id"]]})
        return entete(_carte(client, ines)["jeton"])

    def test_enfant_de_seconde_pro_ne_voit_pas_la_seconde_generale(self, client, session, tmp_path):
        h = self._enfant_en_classe(client, session, tmp_path, "professionnel")
        parcours = {c["parcours"] for c in client.get("/pkp-math/catalogue", headers=h).json()}
        assert "professionnel" in parcours and "tronc-commun" not in parcours
        general = session.scalar(select(models.Chapitre).where(
            models.Chapitre.niveau == Niveau.SECONDE, models.Chapitre.parcours == Parcours.TRONC_COMMUN))
        assert client.get(f"/pkp-math/chapitres/{general.id}", headers=h).status_code == 404

    def test_enfant_de_seconde_generale_ne_voit_pas_la_voie_pro(self, client, session, tmp_path):
        h = self._enfant_en_classe(client, session, tmp_path, "tronc-commun")
        parcours = {c["parcours"] for c in client.get("/pkp-math/catalogue", headers=h).json()}
        assert "tronc-commun" in parcours and "professionnel" not in parcours
