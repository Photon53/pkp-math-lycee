"""Lot A du CDC V2 : domaines pédagogiques, habilitations par matière, gestion des familles par l'administration."""

from alembic import command
from pkp_engine import Niveau
from sqlalchemy import select

from app.db import models
from app.db.seed import EMAIL_ANGLAIS_DEMO
from app.db.session import creer_moteur
from tests.conftest import config_alembic, connecter_admin, connecter_eleve, connecter_enseignant, entete
from tests.test_parents import EMAIL, LINA, connecter_parent

MDP = "un-mot-de-passe-solide"


def _compte(client, admin, email):
    return next(e for e in client.get("/admin/enseignants", headers=admin).json() if e["email"] == email)


def _creer(client, admin, email, habilitations, role="enseignant"):
    """Crée un compte habilité, change son mot de passe provisoire et renvoie son en-tête enseignant."""
    r = client.post("/admin/enseignants", headers=admin, json={
        "nom": email.split("@")[0], "email": email, "role": role, "habilitations": habilitations,
    })
    assert r.status_code == 201, r.text
    provisoire = r.json()["mot_de_passe_provisoire"]
    jeton = client.post("/enseignants/connexion", json={"email": email, "mot_de_passe": provisoire}).json()["jeton"]
    r2 = client.post("/enseignants/mot-de-passe", headers=entete(jeton), json={"actuel": provisoire, "nouveau": MDP})
    assert r2.status_code == 200, r2.text
    return r.json()["enseignant"], entete(r2.json()["jeton"])


def _question(session, niveau: Niveau) -> int:
    return session.scalar(
        select(models.Question.id).join(models.Competence).join(models.Chapitre)
        .where(models.Chapitre.niveau == niveau, models.Question.archivee.is_(False)).limit(1)
    )


def _soumettre_anglais(client, admin, code="4E-02"):
    """Une modification de l'administrateur, soumise : il en devient l'auteur."""
    seance = client.get(f"/admin/anglais/seances/{code}", headers=admin).json()
    corps = {"contenu": {**seance["contenu"], "title": "Révisé"}, "cahier": seance["cahier"], "quiz": seance["quiz"]}
    assert client.put(f"/admin/anglais/seances/{code}", headers=admin, json=corps).status_code == 200
    assert client.post(f"/admin/anglais/seances/{code}/soumettre", headers=admin).json()["statut"] == "soumis"


class TestMigration:
    def test_les_droits_existants_deviennent_des_habilitations(self, tmp_path):
        url = f"sqlite:///{tmp_path / 'v1.db'}"
        config = config_alembic(url)
        command.upgrade(config, "0022")
        moteur = creer_moteur(url)
        with moteur.begin() as c:
            c.exec_driver_sql(
                "insert into enseignant (id, nom, email, mot_de_passe_hash, role, enseigne_maths, enseigne_anglais, "
                "actif, mdp_provisoire, referent_anglais) values "
                "(1, 'Admin', 'a@x.test', 'h', 'admin', 1, 0, 1, 0, 0), "
                "(2, 'Anglais', 'b@x.test', 'h', 'enseignant', 0, 1, 1, 0, 1)"
            )
            c.exec_driver_sql("insert into classe (id, code, niveau, parcours, enseignant_id) values (1, 'C1', '2nde', 'tronc-commun', 1)")
            c.exec_driver_sql("insert into eleve (id, prenom, classe_id, cree_le) values (1, 'Lina', 1, '2026-01-01')")
            c.exec_driver_sql("insert into parent (id, email, mot_de_passe_hash, cree_le) values (1, 'p@x.test', 'h', '2026-01-02')")
            c.exec_driver_sql("insert into parent_eleve values (1, 1)")
        command.upgrade(config, "head")
        with moteur.connect() as c:
            habilitations = set(c.exec_driver_sql("select enseignant_id, role, domaine_code, niveau from habilitation").all())
            assert habilitations == {
                (1, "professeur", "maths-lycee", None), (1, "validateur", "maths-lycee", None),
                (2, "professeur", "anglais-college", None), (2, "validateur", "anglais-college", None),
            }
            publics = {code for code, in c.exec_driver_sql("select code from domaine_pedagogique where public").all()}
            assert publics == {"maths-lycee", "anglais-college"}
            assert c.exec_driver_sql("select parent_id, eleve_id, action from rattachement_parent").all() == [(1, 1, "ajout")]
        moteur.dispose()

    def test_comptes_de_demo(self, client):
        admin = connecter_admin(client)
        vues = {e["email"]: {(h["role"], h["domaine"]) for h in e["habilitations"]} for e in client.get("/admin/enseignants", headers=admin).json()}
        assert vues["admin@pkp.test"] == {("professeur", "maths-lycee"), ("validateur", "maths-lycee")}
        assert vues[EMAIL_ANGLAIS_DEMO] == {("professeur", "anglais-college"), ("validateur", "anglais-college")}
        assert vues["demo@pkp.test"] == {("professeur", "maths-lycee")}


class TestHabilitations:
    def test_creation_avec_plusieurs_matieres(self, client, session):
        admin = connecter_admin(client)
        compte, h = _creer(client, admin, "bi@pkp.test", [
            {"role": "professeur", "domaine": "maths-lycee"},
            {"role": "validateur", "domaine": "maths-lycee", "niveau": "Tle"},
            {"role": "validateur", "domaine": "anglais-college"},
        ])
        assert (compte["enseigne_maths"], compte["enseigne_anglais"], compte["referent_anglais"]) == (True, False, True)
        assert {(x["role"], x["domaine"], x["niveau"]) for x in compte["habilitations"]} == {
            ("professeur", "maths-lycee", None), ("validateur", "maths-lycee", "Tle"), ("validateur", "anglais-college", None),
        }
        # Il enseigne les maths et valide l'anglais sans l'enseigner : la qualification suffit.
        assert client.get("/enseignants/classes", headers=h).status_code == 200
        assert client.get("/anglais/validation", headers=h).status_code == 200
        journal = client.get("/admin/journal", headers=admin, params={"objet": "enseignant", "action": "creer"}).json()
        assert "validateur anglais-college" in journal["elements"][0]["apres"]["habilitations"]

    def test_un_niveau_dans_tout_le_domaine_est_absorbe(self, client):
        admin = connecter_admin(client)
        compte, _ = _creer(client, admin, "x@pkp.test", [
            {"role": "validateur", "domaine": "maths-lycee"}, {"role": "validateur", "domaine": "maths-lycee", "niveau": "1re"},
            {"role": "validateur", "domaine": "maths-lycee"},
        ])
        assert [(x["role"], x["niveau"]) for x in compte["habilitations"]] == [("validateur", None)]

    def test_portees_refusees(self, client):
        admin = connecter_admin(client)
        def creer(habilitations):
            return client.post("/admin/enseignants", headers=admin, json={"nom": "N", "email": "nouveau@pkp.test", "habilitations": habilitations})
        r = creer([{"role": "validateur", "domaine": "francais-lycee"}])
        assert r.status_code == 422 and "pas activé" in r.json()["detail"]
        r = creer([{"role": "validateur", "domaine": "maths-lycee", "niveau": "4e"}])
        assert r.status_code == 422 and "Niveau 4e" in r.json()["detail"]
        assert creer([{"role": "validateur", "domaine": "inconnu"}]).status_code == 422
        assert creer([]).status_code == 422
        assert client.get("/admin/enseignants", headers=admin, params={"q": "nouveau"}).json() == []

    def test_l_ancien_formulaire_conserve_les_autres_habilitations(self, client):
        """Décocher « anglais » ne touche ni à la validation des maths, ni à un niveau précis."""
        admin = connecter_admin(client)
        compte, _ = _creer(client, admin, "c@pkp.test", [
            {"role": "professeur", "domaine": "maths-lycee"}, {"role": "professeur", "domaine": "anglais-college"},
            {"role": "validateur", "domaine": "maths-lycee", "niveau": "1re"},
        ])
        corps = {"nom": "c", "email": "c@pkp.test", "enseigne_maths": True, "enseigne_anglais": False, "referent_anglais": False}
        r = client.post(f"/admin/enseignants/{compte['id']}", headers=admin, json=corps)
        assert r.status_code == 200, r.text
        assert {(x["role"], x["domaine"], x["niveau"]) for x in r.json()["habilitations"]} == {
            ("professeur", "maths-lycee", None), ("validateur", "maths-lycee", "1re"),
        }
        assert r.json()["enseigne_anglais"] is False

    def test_le_dernier_administrateur_reste_administrateur(self, client):
        admin = connecter_admin(client)
        moi = _compte(client, admin, "admin@pkp.test")
        second, _ = _creer(client, admin, "admin2@pkp.test", [{"role": "professeur", "domaine": "maths-lycee"}], role="admin")
        # Deux administrateurs : le second peut perdre son rôle ; seul, l'autre ne peut pas.
        corps = {"nom": "admin2", "email": "admin2@pkp.test", "role": "enseignant", "habilitations": [{"role": "professeur", "domaine": "maths-lycee"}]}
        assert client.post(f"/admin/enseignants/{second['id']}", headers=admin, json=corps).status_code == 200
        assert client.post(f"/admin/enseignants/{moi['id']}/activation", headers=admin, json={"actif": False}).status_code == 422


class TestValidationParMatiere:
    def test_un_validateur_de_maths_ne_valide_pas_l_anglais(self, client):
        admin = connecter_admin(client)
        _soumettre_anglais(client, admin)
        _, maths = _creer(client, admin, "vm@pkp.test", [
            {"role": "professeur", "domaine": "anglais-college"}, {"role": "validateur", "domaine": "maths-lycee"},
        ])
        assert client.get("/anglais/validation", headers=maths).status_code == 403
        assert client.post("/anglais/validation/4E-02/valider", headers=maths).status_code == 403

    def test_un_validateur_des_deux_matieres_valide_les_deux(self, client, session):
        admin = connecter_admin(client)
        _soumettre_anglais(client, admin)
        _, deux = _creer(client, admin, "v2@pkp.test", [
            {"role": "validateur", "domaine": "maths-lycee"}, {"role": "validateur", "domaine": "anglais-college"},
        ])
        assert "4E-02" in [s["code"] for s in client.get("/anglais/validation", headers=deux).json()]
        assert client.post("/anglais/validation/4E-02/valider", headers=deux).json()["statut"] == "valide"

    def test_l_auteur_qualifie_ne_valide_pas_son_contenu(self, client):
        admin = connecter_admin(client)
        moi = _compte(client, admin, "admin@pkp.test")
        corps = {"nom": moi["nom"], "email": moi["email"], "role": "admin", "habilitations": [
            {"role": "validateur", "domaine": "maths-lycee"}, {"role": "validateur", "domaine": "anglais-college"},
        ]}
        assert client.post(f"/admin/enseignants/{moi['id']}", headers=admin, json=corps).status_code == 200
        _soumettre_anglais(client, admin)
        r = client.post("/admin/anglais/seances/4E-02/valider", headers=admin)
        assert r.status_code == 409 and "propre contenu" in r.json()["detail"]

    def test_un_niveau_restreint_la_validation(self, client, session):
        admin = connecter_admin(client)
        anglais = _compte(client, admin, EMAIL_ANGLAIS_DEMO)
        corps = {"nom": anglais["nom"], "email": anglais["email"], "habilitations": [
            {"role": "professeur", "domaine": "anglais-college"}, {"role": "validateur", "domaine": "anglais-college", "niveau": "3e"},
        ]}
        assert client.post(f"/admin/enseignants/{anglais['id']}", headers=admin, json=corps).status_code == 200
        _soumettre_anglais(client, admin)  # séance de 4e
        h = connecter_enseignant(client, email=EMAIL_ANGLAIS_DEMO)
        a_valider = [s["code"] for s in client.get("/anglais/validation", headers=h).json()]
        assert a_valider and all(code.startswith("3E") for code in a_valider)
        r = client.post("/anglais/validation/4E-02/valider", headers=h)
        assert r.status_code == 403 and "(4e)" in r.json()["detail"]

    def test_l_administrateur_sans_qualification_ne_valide_pas_les_questions(self, client, session):
        admin = connecter_admin(client)
        seconde, terminale = _question(session, Niveau.SECONDE), _question(session, Niveau.TERMINALE)
        moi = _compte(client, admin, "admin@pkp.test")
        corps = {"nom": moi["nom"], "email": moi["email"], "role": "admin", "habilitations": [
            {"role": "professeur", "domaine": "maths-lycee"}, {"role": "validateur", "domaine": "maths-lycee", "niveau": "Tle"},
        ]}
        assert client.post(f"/admin/enseignants/{moi['id']}", headers=admin, json=corps).status_code == 200
        r = client.post(f"/admin/questions/{seconde}/validation", headers=admin, json={"statut": "a-corriger"})
        assert r.status_code == 403 and "Maths lycée (2nde)" in r.json()["detail"]
        assert client.post(f"/admin/questions/{terminale}/validation", headers=admin, json={"statut": "a-corriger"}).status_code == 200
        corps["habilitations"] = [{"role": "professeur", "domaine": "maths-lycee"}]
        assert client.post(f"/admin/enseignants/{moi['id']}", headers=admin, json=corps).status_code == 200
        assert client.post(f"/admin/questions/{terminale}/validation", headers=admin, json={"statut": "a-corriger"}).status_code == 403


class TestDomaines:
    def test_liste_et_compteurs(self, client):
        domaines = client.get("/admin/domaines", headers=connecter_admin(client)).json()
        assert [d["code"] for d in domaines] == [
            "maths-college", "maths-lycee", "anglais-college", "anglais-lycee", "francais-college", "francais-lycee",
        ]
        maths = next(d for d in domaines if d["code"] == "maths-lycee")
        assert (maths["actif"], maths["public"], maths["nb_professeurs"], maths["nb_validateurs"]) == (True, True, 2, 1)

    def test_activer_puis_habiliter_puis_desactiver(self, client):
        admin = connecter_admin(client)
        r = client.post("/admin/domaines/francais-lycee", headers=admin, json={"actif": False, "public": True})
        assert r.status_code == 422  # public suppose actif
        assert client.post("/admin/domaines/francais-lycee", headers=admin, json={"actif": True, "public": False}).status_code == 200
        _creer(client, admin, "fr@pkp.test", [{"role": "validateur", "domaine": "francais-lycee"}])
        r = client.post("/admin/domaines/francais-lycee", headers=admin, json={"actif": False, "public": False})
        assert r.status_code == 409 and "habilitation" in r.json()["detail"]

    def test_fermer_au_public_bloque_sans_rien_supprimer(self, client):
        admin = connecter_admin(client)
        eleve = connecter_eleve(client)
        assert client.post("/admin/domaines/maths-lycee", headers=admin, json={"actif": True, "public": False}).status_code == 200
        r = client.post("/seances", headers=eleve, json={})
        assert r.status_code == 403 and "fermé" in r.json()["detail"]
        prof = connecter_enseignant(client)
        assert client.post("/enseignants/classes", headers=prof, json={"niveau": "2nde", "parcours": "tronc-commun"}).status_code == 403
        assert client.get("/enseignants/classes", headers=prof).json()  # les classes et l'historique restent
        client.post("/admin/domaines/maths-lycee", headers=admin, json={"actif": True, "public": True})
        assert client.post("/seances", headers=eleve, json={}).status_code == 201

    def test_fermer_l_anglais(self, client):
        admin = connecter_admin(client)
        client.post("/admin/domaines/anglais-college", headers=admin, json={"actif": True, "public": False})
        h = connecter_enseignant(client, email=EMAIL_ANGLAIS_DEMO)
        assert client.post("/anglais/groupes", headers=h, json={"nom": "G", "niveau": "4e"}).status_code == 403


class TestFamilles:
    def test_creer_rattacher_detacher(self, client, session):
        admin = connecter_admin(client)
        yanis = session.scalar(select(models.Eleve.id).where(models.Eleve.prenom == "Yanis"))
        r = client.post("/admin/parents", headers=admin, json={"email": "famille@exemple.fr", "eleve_id": LINA})
        assert r.status_code == 201 and len(r.json()["mot_de_passe_provisoire"]) == 16
        famille = r.json()["famille"]
        assert [e["prenom"] for e in famille["enfants"]] == ["Lina"]
        r = client.post(f"/admin/parents/{famille['id']}/enfants", headers=admin, json={"eleve_id": yanis})
        assert [e["prenom"] for e in r.json()["enfants"]] == ["Lina", "Yanis"]
        assert client.post(f"/admin/parents/{famille['id']}/enfants", headers=admin, json={"eleve_id": yanis}).status_code == 409
        r = client.delete(f"/admin/parents/{famille['id']}/enfants/{yanis}", headers=admin)
        detail = r.json()
        assert [e["prenom"] for e in detail["enfants"]] == ["Lina"]
        assert [(h["action"], h["enfant"], h["par"]) for h in detail["historique"]] == [
            ("retrait", "Yanis (2NDE-A-DEMO)", "Administrateur : Administrateur Démo"),
            ("ajout", "Yanis (2NDE-A-DEMO)", "Administrateur : Administrateur Démo"),
            ("ajout", "Lina (2NDE-A-DEMO)", "Administrateur : Administrateur Démo"),
        ]
        # Dernier enfant détaché : le compte disparaît.
        assert client.delete(f"/admin/parents/{famille['id']}/enfants/{LINA}", headers=admin).json() is None
        assert client.get(f"/admin/parents/{famille['id']}", headers=admin).status_code == 404

    def test_le_detachement_prend_effet_immediatement(self, client, session):
        parent = connecter_parent(client)
        yanis = session.scalar(select(models.Eleve.id).where(models.Eleve.prenom == "Yanis"))
        admin = connecter_admin(client)
        parent_id = client.get("/admin/parents", headers=admin, params={"q": EMAIL}).json()["elements"][0]["id"]
        client.post(f"/admin/parents/{parent_id}/enfants", headers=admin, json={"eleve_id": yanis})
        assert client.get(f"/parents/enfants/{yanis}", headers=parent).status_code == 200
        client.delete(f"/admin/parents/{parent_id}/enfants/{yanis}", headers=admin)
        assert client.get(f"/parents/enfants/{yanis}", headers=parent).status_code == 404
        assert client.get(f"/parents/enfants/{LINA}", headers=parent).status_code == 200
        # Le rattachement fait par le professeur figure aussi dans l'historique.
        par = [h["par"] for h in client.get(f"/admin/parents/{parent_id}", headers=admin).json()["historique"]]
        assert par[-1] == "Professeur : Enseignant Démo"

    def test_recherche_par_classe_et_suppression(self, client, session):
        connecter_parent(client)
        admin = connecter_admin(client)
        assert client.get("/admin/parents", headers=admin).status_code == 422  # jamais de liste complète
        classe_id = session.scalar(select(models.Eleve.classe_id).where(models.Eleve.id == LINA))
        page = client.get("/admin/parents", headers=admin, params={"classe_id": classe_id}).json()
        assert page["total"] == 1 and page["elements"][0]["email"] == EMAIL
        parent_id = page["elements"][0]["id"]
        assert client.delete(f"/admin/parents/{parent_id}", headers=admin, params={"confirmation": "autre"}).status_code == 422
        assert client.delete(f"/admin/parents/{parent_id}", headers=admin, params={"confirmation": EMAIL}).status_code == 204
        assert session.get(models.Eleve, LINA) is not None
        assert client.post("/parents/connexion", json={"email": EMAIL, "mot_de_passe": "un-mot-de-passe-solide"}).status_code == 401
