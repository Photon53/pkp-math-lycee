"""Ticket #48 : prévalidation IA des exercices, réservée aux administrateurs, par un compte de service dédié."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.db import models
from app.referentiel import Niveau, StatutValidation
from app.routes import prevalidation_ia
from tests.conftest import connecter_admin, connecter_eleve, connecter_enseignant, entete
from tests.test_parents import connecter_parent
from tests.test_validation_maths import corps_de, question_de, validateur_2nde

ADMIN = "/admin/prevalidation-ia"
SERVICE = "/service-ia/prevalidations"


def nouveau_jeton(client, admin, nom="Vérificateur IA", duree_jours=30) -> tuple[int, dict]:
    r = client.post(f"{ADMIN}/comptes", headers=admin, json={"nom": nom, "duree_jours": duree_jours})
    assert r.status_code == 201, r.text
    return r.json()["compte"]["id"], entete(r.json()["jeton"])


def demander(client, admin, question_ids) -> dict:
    r = client.post(f"{ADMIN}/demandes", headers=admin, json={"question_ids": question_ids})
    assert r.status_code == 201, r.text
    return r.json()


def rapport(version: str, **changements) -> dict:
    corps = {
        "version": version, "modele": "claude-opus-5-5", "version_modele": "2026-06", "resultat": "erreur-detectee",
        "synthese": "La réponse attendue ne correspond pas à l'énoncé.",
        "reponse_independante": "x = 3",
        "remarques_enonce": "Énoncé clair.", "remarques_reponse": "La solution proposée vaut 4, le calcul donne 3.",
        "controle_programme": "Conforme au niveau et à la compétence visée.",
        "etapes": [{"numero": 1, "avis": "correcte"}, {"numero": 2, "avis": "erronee", "remarque": "Erreur de signe."}],
        "anomalies": [{"element": "reponse", "gravite": "erreur", "description": "Réponse fausse.",
                       "justification": "2x - 1 = 5 donne x = 3.", "suggestion": "Remplacer 4 par 3."}],
        "verifications": [{"nature": "symbolique", "description": "Résolution de 2x - 1 = 5", "outil": "sympy", "issue": "ecart"}],
    }
    return {**corps, **changements}


@pytest.fixture
def admin(client):
    return connecter_admin(client)


@pytest.fixture
def question(session):
    return question_de(session, Niveau.SECONDE)


def traiter(client, admin, question, **changements) -> tuple[int, dict]:
    """Demande, lecture de l'énoncé puis du corrigé, dépôt du rapport : renvoie (id, en-tête du service)."""
    _, service = nouveau_jeton(client, admin)
    p = demander(client, admin, [question.id])["creees"][0]
    enonce = client.get(f"{SERVICE}/{p['id']}/enonce", headers=service).json()
    assert client.get(f"{SERVICE}/{p['id']}/corrige", headers=service).status_code == 200
    r = client.post(f"{SERVICE}/{p['id']}/rapport", headers=service, json=rapport(enonce["version"], **changements))
    assert r.status_code == 201, r.text
    return p["id"], service


class TestParcoursComplet:
    def test_demande_enonce_sans_corrige_puis_rapport(self, client, session, admin, question):
        _, service = nouveau_jeton(client, admin)
        lot = demander(client, admin, [question.id])
        pid = lot["creees"][0]["id"]
        assert lot["creees"][0]["statut"] == "en-attente" and lot["lot"].startswith("L-")

        assert [d["id"] for d in client.get(SERVICE, headers=service).json()] == [pid]
        # Le corrigé n'est pas servi avant l'énoncé : l'IA résout d'abord seule.
        assert client.get(f"{SERVICE}/{pid}/corrige", headers=service).status_code == 409
        enonce = client.get(f"{SERVICE}/{pid}/enonce", headers=service).json()
        texte = str(enonce)
        assert enonce["exercice"]["enonce"] and "reponse_attendue" not in texte and "correction" not in enonce["exercice"]
        assert question.solution not in str(enonce["exercice"]) or question.solution in question.enonce
        assert enonce["contexte"]["niveau"] == "2nde" and "attendus_du_programme" in enonce["contexte"]
        corrige = client.get(f"{SERVICE}/{pid}/corrige", headers=service).json()
        assert corrige["reponse_attendue"]

        r = client.post(f"{SERVICE}/{pid}/rapport", headers=service, json=rapport(enonce["version"]))
        assert r.status_code == 201 and r.json()["resultat"] == "erreur-detectee"

        detail = client.get(f"{ADMIN}/{pid}", headers=admin).json()
        assert detail["statut"] == "terminee" and detail["obsolete"] is False
        assert detail["modele"] == "claude-opus-5-5" and detail["version_modele"] == "2026-06"
        assert detail["demandee_par"] and detail["question_id"] == question.id and detail["version_complete"] == enonce["version"]
        assert detail["rapport"]["anomalies"][0]["suggestion"] == "Remplacer 4 par 3."
        assert detail["enonce_lu_le"] <= detail["corrige_lu_le"]
        # Plus rien à traiter, et un second rapport est refusé.
        assert client.get(SERVICE, headers=service).json() == []
        assert client.post(f"{SERVICE}/{pid}/rapport", headers=service, json=rapport(enonce["version"])).status_code == 404

    def test_la_validation_humaine_et_le_contenu_ne_changent_pas(self, client, session, admin, question):
        avant = (question.statut_validation, question.valide_par, question.enonce, question.solution, question.correction)
        traiter(client, admin, question, resultat="aucune-anomalie", anomalies=[], synthese="Rien à signaler.")
        session.expire_all()
        q = session.get(models.Question, question.id)
        assert (q.statut_validation, q.valide_par, q.enonce, q.solution, q.correction) == avant
        assert q.statut_validation != StatutValidation.VALIDEE

    def test_echantillon_varie(self, client, admin):
        r = client.post(f"{ADMIN}/demandes", headers=admin, json={"echantillon": {"taille": 10, "niveau": "2nde"}})
        assert r.status_code == 201, r.text
        creees = r.json()["creees"]
        assert len(creees) == 10 and all(c["niveau"] == "2nde" for c in creees)
        assert len({c["competence"] for c in creees}) >= 5

    def test_pas_de_doublon_en_attente(self, client, admin, question):
        demander(client, admin, [question.id])
        second = demander(client, admin, [question.id])
        assert second["creees"] == [] and len(second["deja_en_attente"]) == 1

    def test_annuler(self, client, admin, question):
        _, service = nouveau_jeton(client, admin)
        pid = demander(client, admin, [question.id])["creees"][0]["id"]
        assert client.post(f"{ADMIN}/{pid}/annuler", headers=admin).json()["statut"] == "annulee"
        assert client.get(f"{SERVICE}/{pid}/enonce", headers=service).status_code == 404


class TestVersion:
    def test_modifier_l_exercice_rend_la_prevalidation_obsolete(self, client, session, admin, question):
        pid, _ = traiter(client, admin, question)
        r = client.post(f"/admin/questions/{question.id}", headers=admin, json=corps_de(question, difficulte=(question.difficulte % 5) + 1))
        assert r.status_code == 200, r.text
        assert client.get(f"{ADMIN}/{pid}", headers=admin).json()["obsolete"] is True
        assert [p["id"] for p in client.get(ADMIN, headers=admin, params={"obsolete": True}).json()] == [pid]

    def test_rapport_refuse_si_l_exercice_a_change_entre_temps(self, client, session, admin, question):
        _, service = nouveau_jeton(client, admin)
        pid = demander(client, admin, [question.id])["creees"][0]["id"]
        version = client.get(f"{SERVICE}/{pid}/enonce", headers=service).json()["version"]
        client.post(f"/admin/questions/{question.id}", headers=admin, json=corps_de(question, difficulte=(question.difficulte % 5) + 1))
        assert client.get(SERVICE, headers=service).json() == []
        assert client.post(f"{SERVICE}/{pid}/rapport", headers=service, json=rapport(version)).status_code == 409

    def test_rapport_d_une_autre_version_refuse(self, client, admin, question):
        _, service = nouveau_jeton(client, admin)
        pid = demander(client, admin, [question.id])["creees"][0]["id"]
        client.get(f"{SERVICE}/{pid}/enonce", headers=service)
        assert client.post(f"{SERVICE}/{pid}/rapport", headers=service, json=rapport("0" * 64)).status_code == 409


class TestRapport:
    @pytest.mark.parametrize(
        "changements",
        [
            {"resultat": "aucune-anomalie"},  # avec une anomalie « erreur »
            {"resultat": "erreur-detectee", "anomalies": []},
            {"resultat": "a-revoir", "anomalies": []},
            {"resultat": "incertain", "points_incertains": []},
            {"resultat": "valide"},
            {"statut_validation": "validee"},  # champ inconnu : aucune porte vers la validation humaine
        ],
    )
    def test_rapport_incoherent_refuse(self, client, admin, question, changements):
        _, service = nouveau_jeton(client, admin)
        pid = demander(client, admin, [question.id])["creees"][0]["id"]
        version = client.get(f"{SERVICE}/{pid}/enonce", headers=service).json()["version"]
        assert client.post(f"{SERVICE}/{pid}/rapport", headers=service, json=rapport(version, **changements)).status_code == 422

    def test_avis_incertain(self, client, admin, question):
        pid, _ = traiter(
            client, admin, question, resultat="incertain", anomalies=[],
            points_incertains=["La figure citée par l'énoncé n'est pas fournie : vérification impossible."],
        )
        assert client.get(f"{ADMIN}/{pid}", headers=admin).json()["resultat"] == "incertain"


class TestAccesReserveAuxAdministrateurs:
    ROUTES = [("get", ADMIN), ("get", f"{ADMIN}/1"), ("post", f"{ADMIN}/demandes"), ("get", f"{ADMIN}/comptes"),
              ("post", f"{ADMIN}/comptes"), ("get", f"{ADMIN}/acces"), ("get", f"{ADMIN}/bilan"), ("post", f"{ADMIN}/1/verite")]

    def comptes(self, client, session):
        validateur_2nde(session)  # le professeur de démo devient validateur pédagogique, sans être administrateur
        return {
            "professeur validateur": connecter_enseignant(client),
            "eleve": connecter_eleve(client),
            "parent": connecter_parent(client),
            "anonyme": {},
        }

    def test_tout_autre_role_est_refuse_cote_serveur(self, client, session, admin, question):
        pid = demander(client, admin, [question.id])["creees"][0]["id"]
        for role, h in self.comptes(client, session).items():
            for methode, chemin in [*self.ROUTES, ("get", f"{ADMIN}/{pid}"), ("post", f"{ADMIN}/{pid}/annuler")]:
                r = client.request(methode.upper(), chemin, headers=h, json={})
                assert r.status_code in (401, 403), (role, chemin, r.status_code)

    def test_un_validateur_ne_peut_pas_ouvrir_l_espace_admin(self, client, session):
        validateur_2nde(session)
        r = client.post("/admin/connexion", json={"email": "demo@pkp.test", "mot_de_passe": "demo-pkp-2026"})
        assert r.status_code in (401, 403)

    def test_rien_dans_les_vues_professeur_et_validateur(self, client, session, admin, question):
        traiter(client, admin, question)
        validateur_2nde(session)
        h = connecter_enseignant(client)
        textes = [
            client.get("/enseignants/validation/questions", headers=h, params={"niveau": "2nde"}).text,
            client.get("/admin/questions", headers=admin, params={"q": question.enonce[:20]}).text,
        ]
        for t in textes:
            assert "prevalidation" not in t and "erreur-detectee" not in t and "claude-opus" not in t

    def test_permission_reservee_au_role_admin(self, client, session):
        from app import permissions

        prof = validateur_2nde(session)
        assert permissions.exiger(prof, "prevalidation.ia") is not None


class TestCompteDeService:
    def test_jeton_montre_une_fois_et_stocke_en_empreinte(self, client, session, admin):
        cid, service = nouveau_jeton(client, admin)
        jeton = service["Authorization"].removeprefix("Bearer ")
        compte = session.get(models.CompteServiceIA, cid)
        assert jeton not in (compte.empreinte, compte.prefixe) and jeton.startswith(compte.prefixe)
        assert "jeton" not in client.get(f"{ADMIN}/comptes", headers=admin).text.replace("prefixe", "")

    def test_jeton_revoque_refuse_et_trace(self, client, session, admin):
        cid, service = nouveau_jeton(client, admin)
        assert client.get(SERVICE, headers=service).status_code == 200
        assert client.post(f"{ADMIN}/comptes/{cid}/revoquer", headers=admin).json()["etat"] == "revoque"
        assert client.get(SERVICE, headers=service).status_code == 401
        codes = [a["code_http"] for a in client.get(f"{ADMIN}/acces", headers=admin, params={"compte_id": cid}).json()]
        assert codes == [401, 200]

    def test_jeton_expire_refuse(self, client, session, admin):
        cid, service = nouveau_jeton(client, admin)
        compte = session.get(models.CompteServiceIA, cid)
        compte.expire_le = datetime.now(UTC) - timedelta(minutes=1)
        session.commit()
        assert client.get(SERVICE, headers=service).status_code == 401

    def test_duree_limitee(self, client, admin):
        r = client.post(f"{ADMIN}/comptes", headers=admin, json={"nom": "Trop long", "duree_jours": 365})
        assert r.status_code == 422

    def test_renouveler_revoque_l_ancien_jeton(self, client, admin):
        cid, ancien = nouveau_jeton(client, admin)
        r = client.post(f"{ADMIN}/comptes/{cid}/renouveler", headers=admin, json={"duree_jours": 7})
        assert r.status_code == 201
        nouveau = entete(r.json()["jeton"])
        assert client.get(SERVICE, headers=ancien).status_code == 401
        assert client.get(SERVICE, headers=nouveau).status_code == 200

    def test_jeton_faux_ou_absent(self, client):
        for h in ({}, entete("pkpia_1_faux"), entete("n-importe-quoi")):
            assert client.get(SERVICE, headers=h).status_code == 401

    def test_jeton_humain_refuse_par_le_service(self, client, admin):
        assert client.get(SERVICE, headers=admin).status_code == 401
        assert client.get(SERVICE, headers=connecter_enseignant(client)).status_code == 401

    def test_hors_perimetre_le_jeton_de_service_n_ouvre_rien(self, client, admin, question):
        """Ni données des élèves, ni comptes, ni publication ou validation humaine, ni gestion de ses propres jetons."""
        cid, service = nouveau_jeton(client, admin)
        for methode, chemin, corps in [
            ("get", "/admin/eleves", None),
            ("get", "/admin/enseignants", None),
            ("get", "/admin/questions", None),
            ("post", f"/admin/questions/{question.id}/validation", {"statut": "validee"}),
            ("post", f"/enseignants/validation/questions/{question.id}/validation", {"statut": "validee"}),
            ("get", "/enseignants/classes", None),
            ("get", f"{ADMIN}", None),
            ("post", f"{ADMIN}/demandes", {"question_ids": [question.id]}),
            ("post", f"{ADMIN}/comptes/{cid}/renouveler", {"duree_jours": 90}),
        ]:
            r = client.request(methode.upper(), chemin, headers=service, json=corps)
            assert r.status_code == 401, (chemin, r.status_code)

    def test_demande_inexistante(self, client, admin):
        _, service = nouveau_jeton(client, admin)
        assert client.get(f"{SERVICE}/999999/enonce", headers=service).status_code == 404

    def test_limite_de_debit(self, client, admin, monkeypatch):
        _, service = nouveau_jeton(client, admin)
        monkeypatch.setattr(prevalidation_ia.limitation.service_ia_par_compte, "max_evenements", 3)
        codes = [client.get(SERVICE, headers=service).status_code for _ in range(4)]
        assert codes == [200, 200, 200, 429]

    def test_trop_de_tentatives_refusees(self, client):
        codes = [client.get(SERVICE, headers=entete("pkpia_1_faux")).status_code for _ in range(21)]
        assert codes[-1] == 429


class TestBilanDeLEssai:
    def test_erreurs_non_detectees_mesurees(self, client, session, admin):
        questions = session.scalars(
            select(models.Question).where(models.Question.archivee.is_(False)).order_by(models.Question.id).limit(3)
        ).all()
        _, service = nouveau_jeton(client, admin)
        lot = demander(client, admin, [q.id for q in questions])
        resultats = ["erreur-detectee", "aucune-anomalie", "aucune-anomalie"]
        verites = ["erronee", "erronee", "correcte"]
        for p, resultat, verite in zip(lot["creees"], resultats, verites):
            version = client.get(f"{SERVICE}/{p['id']}/enonce", headers=service).json()["version"]
            corps = rapport(version, resultat=resultat, **({"anomalies": []} if resultat == "aucune-anomalie" else {}))
            assert client.post(f"{SERVICE}/{p['id']}/rapport", headers=service, json=corps).status_code == 201
            assert client.post(f"{ADMIN}/{p['id']}/verite", headers=admin, json={"verite": verite}).status_code == 200
        b = client.get(f"{ADMIN}/bilan", headers=admin, params={"lot": lot["lot"]}).json()
        assert b["rendues"] == 3 and b["erronees_connues"] == 2 and b["detectees"] == 1
        assert b["non_detectees"] == 1 and b["non_detectees_ids"] == [lot["creees"][1]["id"]] and b["taux_non_detection"] == 0.5
        assert b["fausses_alertes"] == 0
        assert session.scalars(select(models.JournalAdmin).where(models.JournalAdmin.objet == "prevalidation_ia")).all()
