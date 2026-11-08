"""Ticket #25 : parcours « voie professionnelle » en seconde (seconde préparant au bac pro).

Distinct de la seconde générale (tronc commun) et de la voie technologique ; les classes et progressions
existantes ne changent pas.
"""

from sqlalchemy import select

from app import matrice, programmes
from app.config import settings
from app.contenu import charger, importer
from app.db import models
from app.referentiel import PARCOURS_PAR_NIVEAU, Niveau, Parcours, est_principal, parcours_par_defaut
from tests.conftest import connecter_admin, connecter_enseignant, entete
from tests.test_contenu import ecrire, erreurs
from tests.test_familles import _carte, _famille

CHAPITRE_PRO = """
chapitre: {code: 2PRO-TEST, niveau: 2nde, parcours: professionnel, ordre: 9, titre: Chapitre de test}
competences:
  - code: 2PRO-TEST-MOY
    libelle: Calculer une moyenne
    questions:
      - {code: 2PRO-TEST-MOY-01, difficulte: 1, type: numerique, enonce: "Moyenne de 8 et 12 ?", solution: "10"}
"""
DOSSIER_PRO = "2nde/professionnel/09-test.yaml"


def importer_chapitre_pro(session, tmp_path) -> models.Chapitre:
    ecrire(tmp_path, CHAPITRE_PRO, DOSSIER_PRO)
    importer(session, charger(tmp_path), archiver_absentes=False)
    session.commit()
    return session.scalar(select(models.Chapitre).where(models.Chapitre.code == "2PRO-TEST"))


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
        ecrire(tmp_path, CHAPITRE_PRO.replace("niveau: 2nde", "niveau: 1re"), "1re/professionnel/09-test.yaml")
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
        assert "2PRO-TEST" in [c.code for c in classe.chapitres_proposes]
        # Critère 1 : aucun chapitre de seconde générale dans le programme de la classe.
        assert all(c.parcours is Parcours.PROFESSIONNEL for c in classe.chapitres_proposes)

    def test_classe_de_seconde_generale_sans_chapitre_pro(self, client, session, tmp_path):
        importer_chapitre_pro(session, tmp_path)
        r = client.post("/enseignants/classes", headers=connecter_enseignant(client), json={"niveau": "2nde"})
        assert r.status_code == 201
        classe = session.get(models.Classe, r.json()["id"])
        assert classe.parcours is Parcours.TRONC_COMMUN
        assert classe.chapitres_proposes and "2PRO-TEST" not in [c.code for c in classe.chapitres_proposes]

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


class TestProgrammeOfficiel:
    """Référentiel 2NDE-PRO-2019 (BO spécial n° 5 du 11 avril 2019) et première séquence."""

    def test_referentiel_trace_jusqu_au_bo(self):
        r = programmes.charger()
        p = r.programmes["2NDE-PRO-2019"]
        assert p.niveau is Niveau.SECONDE and p.parcours is Parcours.PROFESSIONNEL
        assert r.sources[p.source].bulletin == "BO spécial n° 5 du 11 avril 2019"
        themes = {t.code for t, _ in r.du_programme("2NDE-PRO-2019")}
        # Six modules des domaines de connaissances, et les trois modules transversaux.
        assert themes == {"STAT", "PROBA", "DEGRE1", "FONC", "CCF", "GEOM", "ALGO", "AUTO", "LOGIQUE"}
        assert all(a.page for _, a in r.du_programme("2NDE-PRO-2019"))

    def test_calculs_commerciaux_reserves_aux_specialites_sans_physique_chimie(self):
        r = programmes.charger()
        [titre] = {t.titre for t, _ in r.du_programme("2NDE-PRO-2019") if t.code == "CCF"}
        assert "ne comportant pas d’enseignement de physique-chimie" in titre

    def test_sequence_statistique_couvre_le_module(self):
        r = programmes.charger()
        fichiers = charger(codes_attendus=set(r.attendus))
        lignes = [l for l in matrice.couverture(r, fichiers, "2NDE-PRO-2019") if l.theme.code == "STAT"]
        exigibles = [l for l in lignes if l.attendu.obligatoire]
        assert exigibles and all(l.explique and l.questions >= 5 for l in exigibles)
        assert all(set(l.difficultes) == {1, 2, 3, 4, 5} for l in exigibles)

    def test_sequence_a_valider_par_un_humain(self):
        """Brouillon : aucune question n'est validée d'office, et l'auteur n'est pas le relecteur."""
        [(_, f)] = [(c, f) for c, f in charger() if f.chapitre.code == "2PRO-STAT"]
        questions = [q for c in f.competences for q in c.questions]
        assert questions and all(q.validation.statut.value == "a-valider" and q.correction for q in questions)

    def test_brouillons_non_servis_quand_la_validation_est_exigee(self, client, session, tmp_path, monkeypatch):
        h = TestEnfant()._enfant_en_classe(client, session, tmp_path, "professionnel")
        stat = next(c for c in client.get("/pkp-math/catalogue", headers=h).json() if c["code"] == "2PRO-STAT")
        assert stat["nb_questions"] > 0  # bêta : brouillons servis, document marqué NON VALIDÉ
        assert stat["valide"] is False
        monkeypatch.setattr(settings, "servir_questions_non_validees", False)
        stat = next(c for c in client.get("/pkp-math/catalogue", headers=h).json() if c["code"] == "2PRO-STAT")
        assert stat["nb_questions"] == 0
