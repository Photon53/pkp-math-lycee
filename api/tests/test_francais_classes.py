"""PKP Français (F1) : chapitres et classes de français, rangés dans leur domaine, à côté des maths."""

from sqlalchemy import select

from app import permissions
from app.contenu import charger, importer
from app.db import models
from app.referentiel import Niveau, domaine_de
from tests.conftest import connecter_admin, connecter_enseignant
from tests.test_contenu import ecrire, erreurs

CHAPITRE_FR = """
chapitre: {code: FR5-CH, matiere: francais, niveau: 5e, parcours: tronc-commun, ordre: 1, titre: Le présent}
competences:
  - code: FR5-PRES
    libelle: Conjuguer au présent
    questions:
      - {code: FR5-PRES-01, difficulte: 1, type: texte, enonce: "finir, ils (présent) ?", solution: "finissent | ils finissent"}
"""
DOSSIER_FR = "francais/5e/tronc-commun/01-present.yaml"


def importer_chapitre_fr(session, tmp_path) -> None:
    ecrire(tmp_path, CHAPITRE_FR, DOSSIER_FR)
    importer(session, charger(tmp_path), archiver_absentes=False)
    session.commit()


def ouvrir_domaine(client, public: bool = True) -> None:
    """Un domaine ne devient public qu'avec du contenu prêt : importer le chapitre avant."""
    r = client.post("/admin/domaines/francais-college", headers=connecter_admin(client), json={"actif": True, "public": public})
    assert r.status_code == 200, r.text


def ouvrir_francais(client, session, email: str = "demo@pkp.test") -> models.Enseignant:
    """Domaine Français collège ouvert, et le professeur habilité à l'enseigner."""
    ouvrir_domaine(client)
    session.expire_all()
    prof = session.scalar(select(models.Enseignant).where(models.Enseignant.email == email))
    voulues = [*permissions.portees(prof), permissions.Portee(permissions.PROFESSEUR, "francais-college")]
    permissions.appliquer(session, prof, voulues, None)
    session.commit()
    return prof


def test_domaine_selon_la_matiere():
    assert domaine_de("francais", Niveau.SIXIEME) == "francais-college"
    assert domaine_de("francais", Niveau.PREMIERE) == "francais-lycee"
    assert domaine_de("maths", Niveau.PREMIERE) == "maths-lycee"


class TestContenu:
    def test_chapitre_de_francais_range_sous_francais(self, tmp_path):
        ecrire(tmp_path, CHAPITRE_FR, DOSSIER_FR)
        [(_, fichier)] = charger(tmp_path)
        assert fichier.chapitre.matiere == "francais"

    def test_mal_range(self, tmp_path):
        ecrire(tmp_path, CHAPITRE_FR, "5e/tronc-commun/01-present.yaml")
        assert "à ranger dans contenu/francais/5e/tronc-commun/" in erreurs(tmp_path)

    def test_pas_de_francais_en_terminale_ni_hors_tronc_commun(self, tmp_path):
        ecrire(tmp_path, CHAPITRE_FR.replace("niveau: 5e", "niveau: Tle"), "francais/tle/tronc-commun/01-present.yaml")
        assert "pas enseigné en Tle" in erreurs(tmp_path)
        ecrire(tmp_path, CHAPITRE_FR.replace("tronc-commun", "excellence"), "francais/tle/tronc-commun/01-present.yaml")
        assert "suit le tronc commun" in erreurs(tmp_path)

    def test_premiere_tronc_commun_permise_en_francais(self, tmp_path):
        texte = CHAPITRE_FR.replace("niveau: 5e", "niveau: 1re").replace("FR5", "FR1")
        ecrire(tmp_path, texte, "francais/1re/tronc-commun/01-present.yaml")
        assert charger(tmp_path)[0][1].chapitre.niveau is Niveau.PREMIERE

    def test_meme_rang_qu_un_chapitre_de_maths(self, client, tmp_path, session):
        """Le chapitre de français n°1 de 5e cohabite avec le chapitre de maths n°1 de 5e."""
        ecrire(tmp_path, CHAPITRE_FR, DOSSIER_FR)
        importer(session, charger(tmp_path), archiver_absentes=False)
        session.commit()
        ch = session.scalar(select(models.Chapitre).where(models.Chapitre.code == "FR5-CH"))
        assert ch.domaine_code == "francais-college"
        maths = session.scalar(select(models.Chapitre).where(
            models.Chapitre.niveau == Niveau.CINQUIEME, models.Chapitre.ordre == 1, models.Chapitre.domaine_code == "maths-college"))
        assert maths is not None


class TestClasses:
    CORPS = {"matiere": "francais", "niveau": "5e"}

    def test_refusee_tant_que_le_domaine_est_ferme(self, client):
        r = client.post("/enseignants/classes", headers=connecter_enseignant(client), json=self.CORPS)
        assert r.status_code == 403 and "Français collège est fermé" in r.json()["detail"]

    def test_refusee_sans_habilitation(self, client, session, tmp_path):
        importer_chapitre_fr(session, tmp_path)
        ouvrir_domaine(client)
        r = client.post("/enseignants/classes", headers=connecter_enseignant(client), json=self.CORPS)
        assert r.status_code == 403 and "pas le français en 5e" in r.json()["detail"]

    def test_classe_de_francais_avec_son_seul_programme(self, client, session, tmp_path):
        importer_chapitre_fr(session, tmp_path)
        ouvrir_francais(client, session)
        prof = connecter_enseignant(client)
        r = client.post("/enseignants/classes", headers=prof, json=self.CORPS)
        assert r.status_code == 201, r.text
        assert r.json()["code"].startswith("5E-FR-") and r.json()["matiere"] == "francais"
        classe = session.get(models.Classe, r.json()["id"])
        assert classe.domaine_code == "francais-college" and classe.parcours.value == "tronc-commun"
        assert [c.code for c in classe.chapitres_proposes] == ["FR5-CH"]
        # La classe de maths du même niveau ne reçoit pas le chapitre de français.
        client.post("/admin/domaines/maths-college", headers=connecter_admin(client), json={"actif": True, "public": True})
        r = client.post("/enseignants/classes", headers=prof, json={"niveau": "5e"})
        assert r.status_code == 201 and r.json()["matiere"] == "maths"
        assert "FR5-CH" not in [c.code for c in session.get(models.Classe, r.json()["id"]).chapitres_proposes]

    def test_niveaux_et_parcours(self, client):
        prof = connecter_enseignant(client)
        assert client.post("/enseignants/classes", headers=prof, json={"matiere": "francais", "niveau": "Tle"}).status_code == 422
        corps = {"matiere": "francais", "niveau": "1re", "parcours": "specialite"}
        assert client.post("/enseignants/classes", headers=prof, json=corps).status_code == 422
        assert client.post("/enseignants/classes", headers=prof, json={"matiere": "svt", "niveau": "5e"}).status_code == 422

    def test_professeur_de_francais_seul(self, client, session):
        """Il a l'espace des classes, mais n'y ouvre pas de classe de maths."""
        ouvrir_domaine(client, public=False)
        prof = models.Enseignant(nom="Mme Lettres", email="lettres@pkp.test", mot_de_passe_hash="h")
        session.add(prof)
        permissions.appliquer(session, prof, [permissions.Portee(permissions.PROFESSEUR, "francais-college")], None)
        session.commit()
        assert not prof.enseigne_maths and permissions.enseigne_francais(prof)
        assert permissions.refus_matiere_enseignee(prof, "maths", "maths-lycee", "2nde") == "Vous n'enseignez pas les mathématiques."
        assert permissions.refus_matiere_enseignee(prof, "francais", "francais-college", "6e") is None
        assert permissions.refus_matiere_enseignee(prof, "francais", "francais-lycee", "2nde") is not None


class TestEspaceEnfant:
    def test_maths_et_francais_separes(self, client, session, tmp_path):
        from tests.conftest import entete
        from tests.test_familles import _carte, _famille

        importer_chapitre_fr(session, tmp_path)
        admin = connecter_admin(client)
        carte = _famille(client, admin, enfants=[{"prenom": "Inès", "nom": "Martin", "niveau": "5e"}])["cartes"][0]
        avant = _carte(client, carte)["enfant"]
        assert next(m for m in avant["matieres"] if m["code"] == "francais")["disponible"] is False

        ouvrir_francais(client, session)
        client.post("/admin/domaines/maths-college", headers=admin, json={"actif": True, "public": True})
        prof = connecter_enseignant(client)
        ids = {}
        for corps in ({"matiere": "francais", "niveau": "5e"}, {"niveau": "5e"}):
            r = client.post("/enseignants/classes", headers=prof, json=corps)
            ids[r.json()["matiere"]] = r.json()["id"]
            r = client.post(f"/enseignants/classes/{r.json()['id']}/enfants", headers=prof, json={"enfant_ids": [carte["id"]]})
            assert r.json()["ajoutes"] == ["Inès Martin"], r.text

        espace = _carte(client, carte)["enfant"]
        assert next(m for m in espace["matieres"] if m["code"] == "francais")["disponible"] is True
        assert [m["code_classe"][:5] for m in espace["francais"]] == ["5E-FR"]
        assert len(espace["maths"]) == 1 and not espace["maths"][0]["code_classe"].startswith("5E-FR")
        assert espace["francais"][0]["libelle_parcours"] == "Français"

        # La classe de français s'ouvre dans l'espace élève habituel, avec son seul programme.
        h = entete(_carte(client, carte)["jeton"])
        jeton = client.post(f"/enfants/moi/maths/{espace['francais'][0]['eleve_id']}", headers=h).json()
        assert jeton["eleve"]["matiere"] == "francais"
        he = entete(jeton["jeton"])
        assert [c["code"] for c in client.get("/eleves/moi/chapitres", headers=he).json()] == ["FR5-CH"]
        # Les parcours liés restent dans la matière : pas de bascule vers la classe de maths.
        assert [p["code_classe"][:5] for p in client.get("/eleves/moi/parcours", headers=he).json()] == ["5E-FR"]

        # Le répertoire ne voit pas deux parcours principaux en maths.
        enfant = session.get(models.Enfant, carte["id"])
        session.refresh(enfant)
        from app import repertoire
        assert repertoire.DEUX_PRINCIPAUX not in repertoire.alertes(enfant)
