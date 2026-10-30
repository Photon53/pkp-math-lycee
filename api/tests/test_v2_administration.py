"""Cahier des charges V2 : rôle administrateur, IHM d'administration, cours professeur, ressources."""

import pytest
from sqlalchemy import select

from app import security
from app.config import settings
from app.db import models
from app.main import app
from tests.conftest import connecter_admin, connecter_eleve, connecter_enseignant, entete

PDF_MINIMAL = b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\ntrailer << /Root 1 0 R >>\n%%EOF\n"


def _routes_admin() -> list[tuple[str, str]]:
    # Le schéma OpenAPI liste toutes les routes, y compris celles des routeurs inclus.
    return [
        (methode.upper(), chemin)
        for chemin, operations in app.openapi()["paths"].items()
        if chemin.startswith("/admin/") and chemin != "/admin/connexion"
        for methode in operations
    ]


def test_toutes_les_routes_admin_sont_controlees():
    assert len(_routes_admin()) > 40


class TestAccesAdministrateur:
    @pytest.mark.parametrize(("methode", "chemin"), _routes_admin())
    def test_chaque_route_admin_refuse_un_jeton_enseignant(self, client, methode, chemin):
        """Recette lot A : un jeton professeur n'ouvre aucune route /admin."""
        url = chemin.replace("{niveau}", "2nde").replace("{parcours}", "tronc-commun")
        for nom in ("enseignant_id", "eleve_id", "chapitre_id", "competence_id", "version_id", "question_id", "ressource_id", "domaine_id"):
            url = url.replace("{" + nom + "}", "1")
        r = client.request(methode, url, headers=connecter_enseignant(client))
        assert r.status_code == 401

    def test_connexion_admin_reservee_aux_administrateurs(self, client):
        r = client.post("/admin/connexion", json={"email": "demo@pkp.test", "mot_de_passe": "demo-pkp-2026"})
        assert r.status_code == 403

    def test_role_revérifie_en_base(self, client, fabrique):
        h = connecter_admin(client)
        with fabrique() as s:
            s.scalar(select(models.Enseignant).where(models.Enseignant.email == "admin@pkp.test")).role = "enseignant"
            s.commit()
        assert client.get("/admin/moi", headers=h).status_code == 403

    def test_second_facteur(self, client, fabrique, monkeypatch):
        monkeypatch.setattr(settings, "totp_admin_obligatoire", True)
        corps = {"email": "admin@pkp.test", "mot_de_passe": "demo-pkp-2026"}
        assert client.post("/admin/connexion", json=corps).status_code == 403  # pas encore configuré
        secret = security.generer_secret_totp()
        with fabrique() as s:
            s.scalar(select(models.Enseignant).where(models.Enseignant.email == "admin@pkp.test")).totp_secret = secret
            s.commit()
        assert client.post("/admin/connexion", json=corps).status_code == 401
        assert client.post("/admin/connexion", json={**corps, "code_totp": "000000"}).status_code in (401,)
        connecter_admin(client, code_totp=security.code_totp(secret))

    def test_totp_conforme_rfc_6238(self):
        # Vecteur de test de la RFC 6238 (SHA-1, T = 59 s) tronqué à 6 chiffres.
        secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
        assert security.code_totp(secret, 59) == "287082"
        assert security.verifier_totp(secret, "287082", 59 + 30)  # pas voisin accepté

    def test_jeton_admin_court(self, client):
        r = client.post("/admin/connexion", json={"email": "admin@pkp.test", "mot_de_passe": "demo-pkp-2026"})
        assert r.json()["expire_dans_min"] == 30


class TestProfesseurs:
    def test_creer_puis_mot_de_passe_provisoire_a_changer(self, client):
        """Recette lot C : le nouveau professeur se connecte et doit changer son mot de passe."""
        h = connecter_admin(client)
        r = client.post("/admin/enseignants", headers=h, json={"nom": "Mme Martin", "email": "Martin@Lycee.fr"})
        assert r.status_code == 201
        provisoire = r.json()["mot_de_passe_provisoire"]
        connexion = client.post("/enseignants/connexion", json={"email": "martin@lycee.fr", "mot_de_passe": provisoire}).json()
        assert connexion["mdp_provisoire"] is True
        h_prof = entete(connexion["jeton"])
        assert client.get("/enseignants/classes", headers=h_prof).status_code == 403
        nouveau = client.post(
            "/enseignants/mot-de-passe", headers=h_prof, json={"actuel": provisoire, "nouveau": "un-vrai-mot-de-passe"}
        ).json()
        assert nouveau["mdp_provisoire"] is False
        assert client.get("/enseignants/classes", headers=h_prof).status_code == 401  # ancien jeton fermé
        assert client.get("/enseignants/classes", headers=entete(nouveau["jeton"])).status_code == 200

    def test_email_deja_pris(self, client):
        r = client.post("/admin/enseignants", headers=connecter_admin(client), json={"nom": "X", "email": "demo@pkp.test"})
        assert r.status_code == 409

    def test_desactiver_bloque_le_professeur_et_ses_eleves(self, client):
        h_eleve = connecter_eleve(client)
        h_prof = connecter_enseignant(client)
        h = connecter_admin(client)
        demo = next(e for e in client.get("/admin/enseignants", headers=h).json() if e["email"] == "demo@pkp.test")
        assert client.post(f"/admin/enseignants/{demo['id']}/activation", headers=h, json={"actif": False}).status_code == 200
        assert client.get("/enseignants/classes", headers=h_prof).status_code == 401
        assert client.get("/eleves/moi", headers=h_eleve).status_code == 401
        r = client.post("/enseignants/connexion", json={"email": "demo@pkp.test", "mot_de_passe": "demo-pkp-2026"})
        assert r.status_code == 403
        client.post(f"/admin/enseignants/{demo['id']}/activation", headers=h, json={"actif": True})
        connecter_eleve(client)

    def test_pas_d_auto_desactivation_ni_de_perte_de_role(self, client):
        h = connecter_admin(client)
        moi = client.get("/admin/moi", headers=h).json()
        assert client.post(f"/admin/enseignants/{moi['id']}/activation", headers=h, json={"actif": False}).status_code == 422
        corps = {"nom": moi["nom"], "email": moi["email"], "role": "enseignant"}
        assert client.post(f"/admin/enseignants/{moi['id']}", headers=h, json=corps).status_code == 422

    def test_transfert_puis_suppression(self, client):
        h = connecter_admin(client)
        nouveau = client.post("/admin/enseignants", headers=h, json={"nom": "M. Remplaçant", "email": "r@lycee.fr"}).json()
        demo = next(e for e in client.get("/admin/enseignants", headers=h).json() if e["email"] == "demo@pkp.test")
        assert client.delete(f"/admin/enseignants/{demo['id']}?confirmation=demo@pkp.test", headers=h).status_code == 409
        de, vers = client.post(
            f"/admin/enseignants/{demo['id']}/transfert", headers=h, json={"vers_enseignant_id": nouveau["enseignant"]["id"]}
        ).json()
        assert (de["nb_classes"], vers["nb_classes"]) == (0, 3)
        assert client.delete(f"/admin/enseignants/{demo['id']}?confirmation=autre@x.fr", headers=h).status_code == 422
        assert client.delete(f"/admin/enseignants/{demo['id']}?confirmation=demo@pkp.test", headers=h).status_code == 204

    def test_chaque_ecriture_est_journalisee(self, client):
        h = connecter_admin(client)
        client.post("/admin/enseignants", headers=h, json={"nom": "Mme Martin", "email": "martin@lycee.fr"})
        entree = client.get("/admin/journal", headers=h).json()["elements"][0]
        assert (entree["action"], entree["objet"], entree["admin"]) == ("creer", "enseignant", "Administrateur Démo")
        assert entree["apres"]["email"] == "martin@lycee.fr"


class TestEleves:
    def test_liste_transverse_sans_code_en_clair(self, client):
        page = client.get("/admin/eleves", headers=connecter_admin(client)).json()
        assert page["total"] == 5
        assert all("code" not in e for e in page["elements"])
        lina = next(e for e in page["elements"] if e["prenom"] == "Lina")
        assert (lina["classe"], lina["nb_seances"], lina["a_un_code"]) == ("2NDE-A-DEMO", 1, True)

    def test_deplacer_vers_une_classe_du_meme_professeur(self, client):
        h = connecter_admin(client)
        lina = next(e for e in client.get("/admin/eleves?q=lin", headers=h).json()["elements"])
        classe = next(c for c in client.get("/admin/classes", headers=h).json() if c["code"] == "1RE-B-DEMO")
        r = client.post(f"/admin/eleves/{lina['id']}/deplacement", headers=h, json={"classe_id": classe["id"]})
        assert r.json()["classe"] == "1RE-B-DEMO"

    def test_export_journalise(self, client):
        h = connecter_admin(client)
        lina = client.get("/admin/eleves?q=Lina", headers=h).json()["elements"][0]
        assert client.get(f"/admin/eleves/{lina['id']}/export", headers=h).json()["eleve"]["prenom"] == "Lina"
        assert client.get("/admin/journal?action=exporter", headers=h).json()["total"] == 1


class TestCoursAdmin:
    def test_lecon_modifiee_puis_restauree_a_l_identique(self, client):
        """Recette lot C : une leçon modifiée puis restaurée retrouve son texte exact."""
        h = connecter_admin(client)
        competence = next(c for ch in client.get("/admin/contenu", headers=h).json() for c in ch["competences"] if c["a_une_lecon"])
        origine = client.get(f"/admin/lecons/{competence['id']}", headers=h).json()
        modifiee = client.post(
            f"/admin/lecons/{competence['id']}", headers=h, json={"cours": "Nouveau cours $x^2$", "resume": "Résumé"}
        ).json()
        assert modifiee["cours"] == "Nouveau cours $x^2$" and len(modifiee["versions"]) == 1
        restauree = client.post(f"/admin/lecons/versions/{modifiee['versions'][0]['id']}/restaurer", headers=h).json()
        assert (restauree["cours"], restauree["resume"]) == (origine["cours"], origine["resume"])

    def test_formule_mal_fermee_refusee(self, client):
        h = connecter_admin(client)
        r = client.post("/admin/lecons/1", headers=h, json={"cours": "Soit $x", "resume": "ok"})
        assert r.status_code == 422

    def test_import_yaml_n_ecrase_pas_une_modification_admin(self, client, fabrique):
        from app import contenu

        h = connecter_admin(client)
        client.post("/admin/lecons/1", headers=h, json={"cours": "Version admin", "resume": "R"})
        with fabrique() as s:
            rapport = contenu.importer(s, contenu.charger())
            assert any("leçon" in p for p in rapport.protegees)
        assert client.get("/admin/lecons/1", headers=h).json()["cours"] == "Version admin"

    def test_chapitre_masque_disparait_pour_les_eleves(self, client):
        h = connecter_admin(client)
        h_eleve = connecter_eleve(client)
        chapitre = client.get("/eleves/moi/chapitres", headers=h_eleve).json()[0]
        client.post(f"/admin/chapitres/{chapitre['id']}", headers=h, json={"titre": chapitre["titre"], "masque": True})
        assert chapitre["id"] not in {c["id"] for c in client.get("/eleves/moi/chapitres", headers=h_eleve).json()}
        assert chapitre["id"] not in {c["id"] for c in client.get("/cours", headers=h_eleve).json()}

    def test_ordre_des_chapitres(self, client):
        h = connecter_admin(client)
        chapitres = [c for c in client.get("/admin/contenu?niveau=2nde", headers=h).json()]
        ids = [c["id"] for c in chapitres][::-1]
        assert client.post("/admin/chapitres/ordre/2nde/tronc-commun", headers=h, json={"ids": ids}).status_code == 204
        assert [c["id"] for c in client.get("/admin/contenu?niveau=2nde", headers=h).json()] == ids


class TestExercicesAdmin:
    def test_creer_avec_solution_testee(self, client):
        h = connecter_admin(client)
        essai = {"type": "expression", "solution": "x^2 - 4x + 4", "reponse": "(x-2)^2"}
        assert client.post("/admin/questions/tester", headers=h, json=essai).json() == {"correcte": True, "solution_lisible": True}
        corps = {"competence_id": 3, "enonce": "Développer $(x-2)^2$.", "type": "expression", "solution": "x^2 - 4x + 4", "difficulte": 2}
        q = client.post("/admin/questions", headers=h, json=corps).json()
        assert (q["auteur"], q["statut_validation"]) == ("Administrateur Démo", "a-valider")

    def test_solution_illisible_refusee(self, client):
        corps = {"competence_id": 3, "enonce": "?", "type": "numerique", "solution": "2x", "difficulte": 2}
        assert client.post("/admin/questions", headers=connecter_admin(client), json=corps).status_code == 422

    def test_question_repondue_ne_change_pas_de_solution(self, client):
        """Recette lot C : on archive et on recrée plutôt que de fausser les statistiques."""
        h = connecter_admin(client)
        q = client.get("/admin/questions?q=2NDE-FRAC-01", headers=h).json()["elements"][0]
        assert q["nb_reponses"] > 0
        corps = {k: q[k] for k in ("competence_id", "enonce", "type", "difficulte", "source", "adaptation")}
        assert client.post(f"/admin/questions/{q['id']}", headers=h, json={**corps, "solution": "42"}).status_code == 409
        assert client.post(f"/admin/questions/{q['id']}", headers=h, json={**corps, "solution": q["solution"], "difficulte": 4}).status_code == 200

    def test_relecteur_different_de_l_auteur(self, client):
        h = connecter_admin(client)
        corps = {"competence_id": 3, "enonce": "Calculer 1+1.", "type": "numerique", "solution": "2", "difficulte": 1}
        q = client.post("/admin/questions", headers=h, json=corps).json()
        assert client.post(f"/admin/questions/{q['id']}/validation", headers=h, json={"statut": "validee"}).status_code == 422
        r = client.post(f"/admin/questions/{q['id']}/validation", headers=h, json={"statut": "a-corriger"})
        assert r.json()["valide_par"] == "Administrateur Démo"

    def test_filtres_et_pagination(self, client):
        page = client.get("/admin/questions?niveau=1re&type=qcm", headers=connecter_admin(client)).json()
        assert len(page["elements"]) <= 50
        assert all(q["niveau"] == "1re" and q["type"] == "qcm" for q in page["elements"])


class TestCoursProfesseur:
    def test_tous_les_cours_meme_sans_classe(self, client):
        """Recette lot B : un professeur sans classe lit tous les cours de Terminale."""
        h = connecter_admin(client)
        provisoire = client.post("/admin/enseignants", headers=h, json={"nom": "Mme Neuve", "email": "neuve@lycee.fr"}).json()
        jeton = client.post("/enseignants/connexion", json={"email": "neuve@lycee.fr", "mot_de_passe": provisoire["mot_de_passe_provisoire"]}).json()["jeton"]
        jeton = client.post(
            "/enseignants/mot-de-passe", headers=entete(jeton),
            json={"actuel": provisoire["mot_de_passe_provisoire"], "nouveau": "mot-de-passe-solide"},
        ).json()["jeton"]
        sommaire = client.get("/enseignants/cours?niveau=Tle", headers=entete(jeton)).json()
        assert sommaire and all(ch["niveau"] == "Tle" and ch["ouvert_dans"] == [] for ch in sommaire)
        competence = next(c for ch in sommaire for c in ch["competences"] if c["a_une_lecon"])
        lecon = client.get(f"/enseignants/cours/{competence['id']}", headers=entete(jeton)).json()
        assert lecon["cours"]

    def test_classes_ou_le_chapitre_est_ouvert(self, client):
        sommaire = client.get("/enseignants/cours?niveau=2nde", headers=connecter_enseignant(client)).json()
        assert all(ch["ouvert_dans"] == ["2NDE-A-DEMO"] for ch in sommaire)

    def test_recherche(self, client):
        sommaire = client.get("/enseignants/cours?q=fraction", headers=connecter_enseignant(client)).json()
        assert sommaire and len(sommaire) < 10

    def test_exercices_avec_solutions_sous_le_cours(self, client):
        questions = client.get("/enseignants/cours/1/questions", headers=connecter_enseignant(client)).json()
        assert questions and all("solution" in q for q in questions)


class TestRessources:
    def _classe_demo(self, client, h, code="2NDE-A-DEMO") -> int:
        return next(c["id"] for c in client.get("/enseignants/classes", headers=h).json() if c["code"] == code)

    def _competence_ouverte(self, client) -> int:
        h_eleve = connecter_eleve(client)
        chapitre = client.get("/cours", headers=h_eleve).json()[0]
        return next(c["id"] for c in chapitre["competences"] if c["a_une_lecon"])

    def test_lien_du_professeur_visible_de_sa_classe_seulement(self, client):
        h = connecter_enseignant(client)
        competence = self._competence_ouverte(client)
        corps = {"type": "lien", "titre": "Vidéo", "url": "https://www.example.org/video", "competence_id": competence,
                 "classe_ids": [self._classe_demo(client, h)]}
        r = client.post("/enseignants/ressources", headers=h, json=corps)
        assert r.status_code == 201 and r.json()["domaine"] == "example.org"
        lecon = client.get(f"/cours/{competence}", headers=connecter_eleve(client)).json()
        assert [x["titre"] for x in lecon["ressources"]] == ["Vidéo"]

    @pytest.mark.parametrize("url", ["http://example.org", "javascript:alert(1)", "https://user:mdp@example.org"])
    def test_lien_non_https_refuse(self, client, url):
        h = connecter_enseignant(client)
        corps = {"type": "lien", "titre": "X", "url": url, "chapitre_id": 1, "classe_ids": [self._classe_demo(client, h)]}
        assert client.post("/enseignants/ressources", headers=h, json=corps).status_code == 422

    def test_domaine_interdit(self, client):
        client.post("/admin/domaines-interdits", headers=connecter_admin(client), json={"domaine": "mauvais.example"})
        h = connecter_enseignant(client)
        corps = {"type": "lien", "titre": "X", "url": "https://www.sous.mauvais.example/x", "chapitre_id": 1,
                 "classe_ids": [self._classe_demo(client, h)]}
        assert client.post("/enseignants/ressources", headers=h, json=corps).status_code == 422

    def _pdf(self, client, h, competence) -> int:
        corps = {"type": "pdf", "titre": "Fiche", "source": "Moi", "licence": "CC BY", "competence_id": competence,
                 "classe_ids": [self._classe_demo(client, h)], "droits_declares": True}
        return client.post("/enseignants/ressources", headers=h, json=corps).json()["id"]

    def test_pdf_controle_et_servi_selon_les_droits(self, client):
        """Recette lot D : faux PDF refusé ; un élève d'une autre classe reçoit 404."""
        h = connecter_enseignant(client)
        competence = self._competence_ouverte(client)
        rid = self._pdf(client, h, competence)
        faux = client.put(f"/enseignants/ressources/{rid}/fichier", headers={**h, "Content-Type": "application/pdf"}, content=b"MZ\x90 pas un pdf")
        assert faux.status_code == 422
        js = client.put(f"/enseignants/ressources/{rid}/fichier", headers=h, content=PDF_MINIMAL + b"/JavaScript")
        assert js.status_code == 422
        ok = client.put(f"/enseignants/ressources/{rid}/fichier", headers=h, content=PDF_MINIMAL)
        assert ok.status_code == 200 and ok.json()["a_un_fichier"]
        r = client.get(f"/ressources/{rid}/fichier", headers=connecter_eleve(client))
        assert (r.status_code, r.headers["content-type"], r.content) == (200, "application/pdf", PDF_MINIMAL)
        assert client.get(f"/ressources/{rid}/fichier", headers=connecter_eleve(client, "Hugo", "1RE-B-DEMO")).status_code == 404
        assert client.get(f"/ressources/{rid}/fichier").status_code == 401

    def test_pdf_trop_gros(self, client, monkeypatch):
        monkeypatch.setattr(settings, "pdf_taille_max_mo", 0)
        h = connecter_enseignant(client)
        rid = self._pdf(client, h, self._competence_ouverte(client))
        assert client.put(f"/enseignants/ressources/{rid}/fichier", headers=h, content=PDF_MINIMAL).status_code == 413

    def test_pdf_sans_declaration_de_droits(self, client):
        h = connecter_enseignant(client)
        corps = {"type": "pdf", "titre": "Fiche", "source": "Manuel", "licence": "Tous droits réservés", "chapitre_id": 1,
                 "classe_ids": [self._classe_demo(client, h)]}
        assert client.post("/enseignants/ressources", headers=h, json=corps).status_code == 422

    def test_masquage_par_l_administrateur(self, client):
        """Recette lot D : une ressource masquée disparaît côté élève, le motif est visible du professeur."""
        h = connecter_enseignant(client)
        competence = self._competence_ouverte(client)
        corps = {"type": "lien", "titre": "Site", "url": "https://example.org", "competence_id": competence,
                 "classe_ids": [self._classe_demo(client, h)]}
        rid = client.post("/enseignants/ressources", headers=h, json=corps).json()["id"]
        h_admin = connecter_admin(client)
        assert client.post(f"/admin/ressources/{rid}/masquage", headers=h_admin, json={"masquee": True}).status_code == 422
        client.post(f"/admin/ressources/{rid}/masquage", headers=h_admin, json={"masquee": True, "motif": "Publicité"})
        assert client.get(f"/cours/{competence}", headers=connecter_eleve(client)).json()["ressources"] == []
        mienne = client.get("/enseignants/ressources", headers=h).json()[0]
        assert (mienne["masquee"], mienne["motif_masquage"]) == (True, "Publicité")

    def test_lien_mort_cache_apres_deux_controles(self, client, fabrique, monkeypatch):
        from app import ressources

        h = connecter_enseignant(client)
        competence = self._competence_ouverte(client)
        corps = {"type": "lien", "titre": "Mort", "url": "https://example.org/404", "competence_id": competence,
                 "classe_ids": [self._classe_demo(client, h)]}
        client.post("/enseignants/ressources", headers=h, json=corps)
        monkeypatch.setattr(ressources, "lien_repond", lambda url: False)
        with fabrique() as s:
            assert ressources.verifier_liens(s) == []
        assert len(client.get(f"/cours/{competence}", headers=connecter_eleve(client)).json()["ressources"]) == 1
        with fabrique() as s:
            assert len(ressources.verifier_liens(s)) == 1
        assert client.get(f"/cours/{competence}", headers=connecter_eleve(client)).json()["ressources"] == []

    def test_ressource_commune_visible_de_tous(self, client):
        competence = self._competence_ouverte(client)
        corps = {"type": "lien", "titre": "Commune", "url": "https://example.org", "competence_id": competence}
        assert client.post("/admin/ressources", headers=connecter_admin(client), json=corps).status_code == 201
        assert client.get(f"/cours/{competence}", headers=connecter_eleve(client)).json()["ressources"][0]["portee"] == "commune"
        assert client.get(f"/enseignants/cours/{competence}", headers=connecter_enseignant(client)).json()["ressources"]


class TestStatistiques:
    def test_tableau_de_bord(self, client):
        connecter_enseignant(client)  # dernière connexion
        stats = client.get("/admin/statistiques?periode=30", headers=connecter_admin(client)).json()
        assert stats["eleves_total"] == 5 and stats["eleves_actifs"] == 2
        assert stats["reponses"] == 7 and stats["seances"] == 2
        assert stats["professeurs_actifs"] >= 1
        assert sum(c["a_valider"] + c["validees"] + c["a_corriger"] for c in stats["couverture"]) > 0

    def test_agregats_sous_le_seuil_masques(self, client):
        """Moins de 5 élèves : aucun taux par chapitre n'est publié (EA3.20)."""
        stats = client.get("/admin/statistiques", headers=connecter_admin(client)).json()
        assert stats["reussite_par_chapitre"] and all(c["taux_reussite"] is None for c in stats["reussite_par_chapitre"])

    def test_periode_inconnue(self, client):
        assert client.get("/admin/statistiques?periode=12", headers=connecter_admin(client)).status_code == 422


class TestCommandeAdmin:
    def test_promouvoir_un_compte_v1_puis_second_facteur(self, client, fabrique):
        """Passage V1 → V2 : le compte professeur existant devient administrateur, mot de passe inchangé."""
        from app import admin as cli

        with fabrique() as s:
            assert cli.promouvoir(s, "Demo@PKP.test").role == "admin"
            uri = cli.configurer_totp(s, "demo@pkp.test")
        assert uri.startswith("otpauth://totp/") and "secret=" in uri
        r = client.post("/admin/connexion", json={"email": "demo@pkp.test", "mot_de_passe": "demo-pkp-2026"})
        assert r.status_code == 401  # second facteur désormais demandé

    def test_promouvoir_un_compte_inconnu(self, session):
        from app import admin as cli

        with pytest.raises(cli.ErreurAdmin):
            cli.promouvoir(session, "personne@x.fr")
