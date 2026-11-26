# Issue #162 — Diagnostic des acquis antérieurs, lot 3 : passation (Claude)
"""Passation : ouverture par le professeur, une question à la fois sans correction, « Je ne sais pas », relances,
descente vers le niveau précédent, maîtrise inchangée, questions non validées jamais servies."""

import pytest
from sqlalchemy import func, select

from app.contenu import charger, importer
from app.db import models
from app.referentiel import StatutObservation, StatutValidation
from tests.conftest import connecter_eleve, connecter_enseignant
from tests.test_contenu import ecrire, erreurs

HAUT = """
chapitre: {code: TEST-PASS, niveau: 2nde, nature: diagnostic, publics: [tronc-commun], programme_prerequis: 3e-2020,
           ordre: 95, titre: Diagnostic de passation}
competences:
  - code: TEST-PASS-A
    libelle: Notion A
    retour: [TEST-BAS-A]
    questions:
      - {code: TEST-PASS-A-01, difficulte: 2, type: qcm, enonce: "Choix ? A) un  B) deux", solution: B}
      - {code: TEST-PASS-A-02, difficulte: 2, type: choix_multiples, enonce: "Vrai ? A) a  B) b  C) c", solution: AC}
      - {code: TEST-PASS-A-03, difficulte: 1, type: numerique, enonce: "1 + 1 ?", solution: 2}
      - {code: TEST-PASS-A-04, difficulte: 3, type: redaction, enonce: "Justifie.", solution: "Attendu.",
         correction: {etapes: [Un argument., Un autre.]}}
  - code: TEST-PASS-B
    libelle: Notion B
    questions:
      - {code: TEST-PASS-B-01, difficulte: 2, type: numerique, enonce: "2 + 2 ?", solution: 4}
      - {code: TEST-PASS-B-02, difficulte: 2, type: numerique, enonce: "3 + 3 ?", solution: 6}
  - code: TEST-PASS-C
    libelle: Notion C, à justifier
    questions:
      - {code: TEST-PASS-C-01, difficulte: 2, type: redaction, enonce: "Explique.", solution: "Attendu.",
         correction: {etapes: [Un argument., Un autre.]}}
"""
BAS = """
chapitre: {code: TEST-BAS, niveau: 3e, nature: diagnostic, publics: [tronc-commun], programme_prerequis: 4e-2020,
           ordre: 95, titre: Diagnostic du niveau précédent}
competences:
  - code: TEST-BAS-A
    libelle: Notion A, niveau précédent
    questions:
      - {code: TEST-BAS-A-01, difficulte: 1, type: numerique, enonce: "5 + 5 ?", solution: 10}
      - {code: TEST-BAS-A-02, difficulte: 2, type: numerique, enonce: "6 + 6 ?", solution: 12}
"""


def ecrire_banque(dossier, haut: str = HAUT, bas: str = BAS) -> None:
    ecrire(dossier, haut, "2nde/diagnostic/95-test.yaml")
    ecrire(dossier, bas, "3e/diagnostic/95-test.yaml")


@pytest.fixture
def banque(client, session, tmp_path):
    """Les deux diagnostics de test importés, validés ; la banque du dépôt reste « à valider »."""
    ecrire_banque(tmp_path)
    importer(session, charger(tmp_path), archiver_absentes=False)
    for q in session.scalars(select(models.Question).where(models.Question.code.like("TEST-%"))):
        q.statut_validation, q.valide_par = StatutValidation.VALIDEE, "Mme Relectrice"
    session.commit()


def _classe(client, h) -> int:
    return next(c["id"] for c in client.get("/enseignants/classes", headers=h).json() if c["code"] == "2NDE-A-DEMO")


@pytest.fixture
def ouvert(client, banque):
    h = connecter_enseignant(client)
    r = client.put(f"/enseignants/classes/{_classe(client, h)}/diagnostic", headers=h, json={"ouvert": True})
    assert r.status_code == 200 and r.json()["ouvert"]
    return h


def _code(session, question_id: int) -> str:
    return session.get(models.Question, question_id).code


def _solution(session, question_id: int) -> str:
    q = session.get(models.Question, question_id)
    return "Ma justification." if q.type.value == "redaction" else q.solution


def passer(client, session, h, reponse) -> list[str]:
    """Fait passer tout le diagnostic ; `reponse(code, solution)` donne la saisie (None : « Je ne sais pas »)."""
    assert client.post("/eleves/moi/diagnostic", headers=h).status_code == 200
    codes = []
    while (r := client.get("/eleves/moi/diagnostic/question", headers=h)).status_code == 200:
        q = r.json()
        codes.append(_code(session, q["id"]))
        saisie = reponse(codes[-1], _solution(session, q["id"]))
        corps = {"question_id": q["id"], "reponse_donnee": saisie, "ne_sait_pas": saisie is None}
        assert client.post("/eleves/moi/diagnostic/reponses", headers=h, json=corps).json() == {"enregistree": True}
        assert len(codes) < 60
    assert r.status_code == 204
    return codes


class TestOuverture:
    def test_ferme_par_defaut(self, client, banque):
        h = connecter_eleve(client)
        assert client.get("/eleves/moi/diagnostic", headers=h).json()["statut"] == "ferme"
        assert client.post("/eleves/moi/diagnostic", headers=h).status_code == 409
        assert client.get("/eleves/moi/diagnostic/question", headers=h).status_code == 409

    def test_vue_du_professeur(self, client, ouvert):
        vue = client.get(f"/enseignants/classes/{_classe(client, ouvert)}/diagnostic", headers=ouvert).json()
        assert vue["ouvert"] and vue["nb_questions_disponibles"] == 9
        assert {e["prenom"]: e["statut"] for e in vue["eleves"]}["Lina"] == "a-commencer"

    def test_autre_professeur_refuse(self, client, ouvert, session):
        autre = models.Enseignant(nom="Autre", email="autre@pkp.test", mot_de_passe_hash="x")
        session.add(autre)
        session.commit()
        classe = session.scalar(select(models.Classe).where(models.Classe.code == "2NDE-A-DEMO"))
        classe.enseignant_id = autre.id
        session.commit()
        assert client.put(f"/enseignants/classes/{classe.id}/diagnostic", headers=ouvert, json={"ouvert": False}).status_code == 404


class TestNonDiffusion:
    def test_non_validees_jamais_servies_meme_ouvert(self, client, session, tmp_path):
        ecrire_banque(tmp_path)
        importer(session, charger(tmp_path), archiver_absentes=False)  # « à valider »
        h = connecter_enseignant(client)
        client.put(f"/enseignants/classes/{_classe(client, h)}/diagnostic", headers=h, json={"ouvert": True})
        e = connecter_eleve(client)
        assert client.get("/eleves/moi/diagnostic", headers=e).json()["statut"] == "indisponible"
        assert client.post("/eleves/moi/diagnostic", headers=e).status_code == 409

    def test_retour_non_valide_jamais_servi(self, client, session, ouvert):
        for q in session.scalars(select(models.Question).where(models.Question.code.like("TEST-BAS-%"))):
            q.statut_validation = StatutValidation.A_VALIDER
        session.commit()
        codes = passer(client, session, connecter_eleve(client), lambda code, s: None)
        assert not any(c.startswith("TEST-BAS") for c in codes)


class TestPassation:
    def test_question_sans_solution_ni_difficulte_et_stable(self, client, session, ouvert):
        h = connecter_eleve(client)
        client.post("/eleves/moi/diagnostic", headers=h)
        q1 = client.get("/eleves/moi/diagnostic/question", headers=h).json()
        assert set(q1) == {"id", "numero", "enonce", "type"} and q1["numero"] == 1
        assert client.get("/eleves/moi/diagnostic/question", headers=h).json() == q1
        r = client.post("/eleves/moi/diagnostic/reponses", headers=h, json={"question_id": q1["id"] + 9999, "reponse_donnee": "B"})
        assert r.status_code == 409

    def test_reponse_sans_correction(self, client, session, ouvert):
        h = connecter_eleve(client)
        client.post("/eleves/moi/diagnostic", headers=h)
        q = client.get("/eleves/moi/diagnostic/question", headers=h).json()
        r = client.post("/eleves/moi/diagnostic/reponses", headers=h, json={"question_id": q["id"], "reponse_donnee": "faux"})
        assert r.json() == {"enregistree": True}

    def test_reponse_vide_refusee(self, client, ouvert):
        h = connecter_eleve(client)
        client.post("/eleves/moi/diagnostic", headers=h)
        q = client.get("/eleves/moi/diagnostic/question", headers=h).json()
        r = client.post("/eleves/moi/diagnostic/reponses", headers=h, json={"question_id": q["id"], "reponse_donnee": "  "})
        assert r.status_code == 409 and "Je ne sais pas" in r.json()["detail"]

    def test_tout_juste_deux_questions_par_notion_puis_termine(self, client, session, ouvert):
        h = connecter_eleve(client)
        codes = passer(client, session, h, lambda code, s: s)
        a = [c for c in codes if c.startswith("TEST-PASS-A")]
        b = [c for c in codes if c.startswith("TEST-PASS-B")]
        assert len(a) == 2 and len(b) == 2 and not any(c.startswith("TEST-BAS") for c in codes)
        assert client.get("/eleves/moi/diagnostic", headers=h).json() == {"statut": "termine", "nb_reponses": 5}
        assert client.post("/eleves/moi/diagnostic", headers=h).status_code == 409
        statuts = {o.question.code: o.statut for o in session.scalars(select(models.ObservationDiagnostic))}
        assert statuts["TEST-PASS-A-02"] is StatutObservation.JUSTE  # choix multiples, ensemble exact
        assert all(o.duree_s is not None and o.passation_id for o in session.scalars(select(models.ObservationDiagnostic)))

    def test_je_ne_sais_pas_relances_puis_descente(self, client, session, ouvert):
        h = connecter_eleve(client)
        codes = passer(client, session, h, lambda code, s: None if code.startswith("TEST-PASS-A") else s)
        a = [c for c in codes if c.startswith("TEST-PASS-A")]
        assert len(a) == 3  # un échec, puis deux relances
        premier_bas = codes.index(next(c for c in codes if c.startswith("TEST-BAS")))
        premier_b = codes.index(next(c for c in codes if c.startswith("TEST-PASS-B")))
        assert premier_bas < premier_b  # le niveau précédent avant la notion suivante
        nsp = session.scalars(
            select(models.ObservationDiagnostic).where(models.ObservationDiagnostic.statut == StatutObservation.NE_SAIT_PAS)
        ).all()
        assert len(nsp) == 3 and all(o.reponse_donnee == "" for o in nsp)

    def test_redaction_en_attente_et_longue(self, client, session, ouvert):
        h = connecter_eleve(client)
        codes = passer(client, session, h, lambda code, s: "x" * 3000 if code == "TEST-PASS-C-01" else s)
        assert "TEST-PASS-C-01" in codes
        obs = session.scalar(
            select(models.ObservationDiagnostic).join(models.Question).where(models.Question.code == "TEST-PASS-C-01")
        )
        assert obs.statut is StatutObservation.EN_ATTENTE and len(obs.reponse_donnee) == 3000

    def test_fermeture_puis_reouverture_reprend_la_meme_question(self, client, session, ouvert):
        classe = _classe(client, ouvert)
        h = connecter_eleve(client)
        client.post("/eleves/moi/diagnostic", headers=h)
        q = client.get("/eleves/moi/diagnostic/question", headers=h).json()
        client.put(f"/enseignants/classes/{classe}/diagnostic", headers=ouvert, json={"ouvert": False})
        assert client.get("/eleves/moi/diagnostic/question", headers=h).status_code == 409
        client.put(f"/enseignants/classes/{classe}/diagnostic", headers=ouvert, json={"ouvert": True})
        assert client.get("/eleves/moi/diagnostic/question", headers=h).json()["id"] == q["id"]

    def test_suivi_du_professeur(self, client, session, ouvert):
        passer(client, session, connecter_eleve(client), lambda code, s: s)
        vue = client.get(f"/enseignants/classes/{_classe(client, ouvert)}/diagnostic", headers=ouvert).json()
        lina = next(e for e in vue["eleves"] if e["prenom"] == "Lina")
        assert lina["statut"] == "termine" and lina["nb_reponses"] == 5 and lina["nb_en_attente"] == 1


class TestMaitriseIsolee:
    def test_passation_sans_effet_sur_la_progression(self, client, session, ouvert):
        h = connecter_eleve(client)
        progression = client.get("/eleves/moi/progression", headers=h).json()
        historique = client.get("/eleves/moi/historique", headers=h).json()["total"]
        nb_reponses = session.scalar(select(func.count(models.Reponse.id)))
        passer(client, session, h, lambda code, s: None if code.endswith("1") else s)
        assert client.get("/eleves/moi/progression", headers=h).json() == progression
        assert client.get("/eleves/moi/historique", headers=h).json()["total"] == historique
        assert session.scalar(select(func.count(models.Reponse.id))) == nb_reponses


class TestRetourDansLeContenu:
    def test_retour_vers_le_meme_niveau_refuse(self, tmp_path):
        ecrire_banque(tmp_path, HAUT.replace("retour: [TEST-BAS-A]", "retour: [TEST-PASS-B]"))
        assert "retour « TEST-PASS-B » : compétence d'un diagnostic du niveau précédent attendue" in erreurs(tmp_path)

    def test_retour_inconnu_refuse(self, tmp_path):
        ecrire_banque(tmp_path, HAUT.replace("retour: [TEST-BAS-A]", "retour: [TEST-INCONNU]"))
        assert "retour « TEST-INCONNU »" in erreurs(tmp_path)

    def test_retour_reserve_au_diagnostic(self, tmp_path):
        from tests.test_contenu import MINIMAL

        ecrire(tmp_path, MINIMAL.replace("    libelle: Compétence test\n", "    libelle: Compétence test\n    retour: [TEST-C]\n"))
        assert "`retour` ne concerne que les chapitres de diagnostic" in erreurs(tmp_path)
