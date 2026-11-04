"""Lot A du CDC V2, suite : domaine enregistré (EX.2), filtre par domaine (EA.2, recette 5), recherche globale
(EA.1), export des données d'une famille (EA.12) et permissions par compte (EX.7, EA.3)."""

from alembic import command
from sqlalchemy import select

from app.db import models
from app.db.seed import EMAIL_ANGLAIS_DEMO
from app.db.session import creer_moteur
from tests.conftest import config_alembic, connecter_admin, connecter_enseignant
from tests.test_parents import LINA

MATHS, ANGLAIS = "maths-lycee", "anglais-college"


class TestDomaineEnregistre:
    def test_la_migration_range_l_existant_dans_son_domaine(self, tmp_path):
        url = f"sqlite:///{tmp_path / 'v23.db'}"
        config = config_alembic(url)
        command.upgrade(config, "0023")
        moteur = creer_moteur(url)
        with moteur.begin() as c:
            c.exec_driver_sql(
                "insert into enseignant (id, nom, email, mot_de_passe_hash, role, enseigne_maths, enseigne_anglais, "
                "actif, mdp_provisoire, referent_anglais) values (1, 'E', 'e@x.test', 'h', 'enseignant', 1, 1, 1, 0, 0)"
            )
            c.exec_driver_sql("insert into classe (id, code, niveau, parcours, enseignant_id) values (1, 'C1', '2nde', 'tronc-commun', 1)")
            c.exec_driver_sql("insert into groupe_anglais (id, nom, niveau, enseignant_id) values (1, '4e A', '4e', 1)")
        command.upgrade(config, "head")
        with moteur.connect() as c:
            assert c.exec_driver_sql("select domaine_code from classe").scalar() == MATHS
            assert c.exec_driver_sql("select domaine_code from groupe_anglais").scalar() == ANGLAIS
            # La contrainte « 4e ou 3e » est remplacée par le contrôle de l'API sur les niveaux du domaine.
            c.exec_driver_sql("insert into groupe_anglais (id, nom, niveau, enseignant_id) values (2, '6e A', '6e', 1)")
        moteur.dispose()

    def test_contenus_et_espaces_de_demo(self, client, session):
        assert set(session.scalars(select(models.Classe.domaine_code))) == {MATHS}
        # Chaque chapitre est rangé dans le domaine de son niveau : collège ou lycée.
        domaines = {(c.niveau, c.domaine_code) for c in session.scalars(select(models.Chapitre))}
        assert {d for _, d in domaines} == {MATHS, "maths-college"}
        assert all(d == ("maths-college" if n.value in ("6e", "5e", "4e", "3e") else MATHS) for n, d in domaines)

    def test_un_groupe_prend_un_niveau_de_son_domaine(self, client):
        h = connecter_enseignant(client, EMAIL_ANGLAIS_DEMO)
        assert client.post("/anglais/groupes", headers=h, json={"nom": "6e A", "niveau": "6e"}).status_code == 201
        r = client.post("/anglais/groupes", headers=h, json={"nom": "2nde A", "niveau": "2nde"})
        assert r.status_code == 422
        assert "Anglais collège" in r.json()["detail"]


class TestFiltreDomaine:
    def test_chaque_liste_se_filtre(self, client):
        admin = connecter_admin(client)
        nb = lambda chemin, d: len(client.get(f"{chemin}{'&' if '?' in chemin else '?'}domaine={d}", headers=admin).json())  # noqa: E731
        for chemin in ["/admin/classes", "/admin/contenu", "/admin/ressources"]:
            assert nb(chemin, ANGLAIS) == 0, chemin
            tout = len(client.get(chemin, headers=admin).json())
            assert nb(chemin, MATHS) + nb(chemin, "maths-college") == tout, chemin
        assert client.get("/admin/eleves?domaine=anglais-college", headers=admin).json()["total"] == 0
        assert client.get("/admin/eleves?domaine=maths-lycee", headers=admin).json()["total"] > 0
        assert client.get("/admin/questions?domaine=anglais-college", headers=admin).json()["total"] == 0
        assert nb("/admin/anglais/seances", MATHS) == 0
        assert nb("/admin/anglais/seances", ANGLAIS) == 20
        equipe = {e["email"] for e in client.get("/admin/enseignants?domaine=anglais-college", headers=admin).json()}
        assert EMAIL_ANGLAIS_DEMO in equipe and "admin@pkp.test" not in equipe
        assert client.get("/admin/classes", headers=admin).json()[0]["domaine_code"] == MATHS

    def test_domaine_inconnu(self, client):
        admin = connecter_admin(client)
        assert client.get("/admin/classes?domaine=physique", headers=admin).status_code == 422

    def test_familles_du_domaine(self, client):
        admin = connecter_admin(client)
        client.post("/admin/parents", headers=admin, json={"email": "famille@exemple.fr", "eleve_id": LINA})
        r = lambda d: client.get(f"/admin/parents?q=famille&domaine={d}", headers=admin).json()["total"]  # noqa: E731
        assert (r(MATHS), r(ANGLAIS)) == (1, 0)


class TestRechercheGlobale:
    def test_trouve_eleves_comptes_et_contenus(self, client):
        admin = connecter_admin(client)
        types = lambda q, d="": {r["type"] for r in client.get(f"/admin/recherche?q={q}&domaine={d}", headers=admin).json()}  # noqa: E731
        assert "Élève" in types("lin")
        assert "Équipe" in types("demo")
        assert "Classe" in types("2nde-a")
        assert "Séance d'anglais" in types("4E-0")
        assert "Élève" not in types("lin", ANGLAIS)
        assert "Séance d'anglais" not in types("4E-0", MATHS)

    def test_chaque_resultat_ouvre_sa_page(self, client):
        admin = connecter_admin(client)
        eleve = next(r for r in client.get("/admin/recherche?q=lina", headers=admin).json() if r["type"] == "Élève")
        assert eleve["vers"] == "/admin/eleves?q=Lina"

    def test_familles_a_partir_de_trois_caracteres(self, client):
        admin = connecter_admin(client)
        client.post("/admin/parents", headers=admin, json={"email": "famille@exemple.fr", "eleve_id": LINA})
        familles = lambda q: [r for r in client.get(f"/admin/recherche?q={q}", headers=admin).json() if r["type"] == "Famille"]  # noqa: E731
        assert familles("fa") == []
        assert familles("famille")[0]["libelle"] == "famille@exemple.fr"

    def test_trop_court(self, client):
        assert client.get("/admin/recherche?q=a", headers=connecter_admin(client)).status_code == 422


class TestExportFamille:
    def test_export_complet_et_journalise(self, client):
        admin = connecter_admin(client)
        parent_id = client.post("/admin/parents", headers=admin, json={"email": "famille@exemple.fr", "eleve_id": LINA}).json()["famille"]["id"]
        r = client.get(f"/admin/parents/{parent_id}/export", headers=admin)
        assert r.status_code == 200
        assert "attachment" in r.headers["content-disposition"]
        donnees = r.json()
        assert donnees["parent"]["email"] == "famille@exemple.fr"
        assert [e["prenom"] for e in donnees["enfants"]] == ["Lina"]
        assert donnees["historique_des_rattachements"][0]["action"] == "ajout"
        journal = client.get("/admin/journal?objet=parent", headers=admin).json()["elements"]
        assert journal[0]["action"] == "exporter"


class TestPermissions:
    def test_l_admin_voit_tous_les_espaces_sans_valider_par_principe(self, client):
        moi = client.get("/admin/moi", headers=connecter_admin(client)).json()
        assert {"comptes.gerer", "parents.gerer", "pilotage.global", "configuration", "contenu.modifier"} <= set(moi["permissions"])
        # L'admin de démo valide parce qu'il est validateur de Maths lycée, pas parce qu'il est admin.
        assert "contenu.valider" in moi["permissions"]

    def test_permissions_par_domaine(self, client, session):
        from app import permissions

        prof = session.scalar(select(models.Enseignant).where(models.Enseignant.email == EMAIL_ANGLAIS_DEMO))
        assert "contenu.valider" in permissions.permissions_de(prof, ANGLAIS)
        assert "contenu.valider" not in permissions.permissions_de(prof, MATHS)
        assert "comptes.gerer" not in permissions.permissions_de(prof)
        assert permissions.exiger(prof, "configuration") is not None
