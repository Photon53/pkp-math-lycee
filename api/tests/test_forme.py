"""Forme exigée (« Développer », « Factoriser »…) : la valeur juste ne suffit pas, et l'élève sait pourquoi."""

from app.db import models
from pkp_engine import Forme, TypeQuestion
from tests.conftest import connecter_admin, connecter_eleve
from tests.test_publication import competence_ouverte


def seule_question_developper(session, competence: models.Competence) -> models.Question:
    """La compétence ne garde qu'une question : « Développer (x+3)² »."""
    questions = [q for q in competence.questions if not q.archivee]
    for q in questions[1:]:
        q.archivee = True
    q = questions[0]
    q.type, q.enonce, q.solution, q.forme, q.gabarit = TypeQuestion.EXPRESSION, "Développer $(x+3)^2$.", "x^2 + 6x + 9", Forme.DEVELOPPEE, None
    session.commit()
    return q


def repondre(client, h, competence_id: int, saisie: str) -> dict:
    s = client.post("/seances", headers=h, json={"competence_ids": [competence_id]}).json()["id"]
    q = client.get(f"/seances/{s}/question", headers=h).json()
    return client.post(f"/seances/{s}/reponses", headers=h, json={"question_id": q["id"], "reponse_donnee": saisie}).json()


class TestEleve:
    def test_recopier_l_enonce_est_refuse_avec_une_remarque(self, client, session):
        h = connecter_eleve(client)
        c = competence_ouverte(client, session, h)
        seule_question_developper(session, c)
        r = repondre(client, h, c.id, "(x+3)^2")
        assert not r["correcte"]
        assert "pas sous forme développée" in r["remarque"]

    def test_forme_developpee_acceptee(self, client, session):
        h = connecter_eleve(client)
        c = competence_ouverte(client, session, h)
        seule_question_developper(session, c)
        r = repondre(client, h, c.id, "x² + 6x + 9")
        assert r["correcte"] and r["remarque"] is None

    def test_mauvaise_valeur_sans_remarque(self, client, session):
        h = connecter_eleve(client)
        c = competence_ouverte(client, session, h)
        seule_question_developper(session, c)
        r = repondre(client, h, c.id, "x^2 + 9")
        assert not r["correcte"] and r["remarque"] is None


class TestAdministration:
    def test_tester_signale_la_forme(self, client):
        essai = {"type": "expression", "solution": "x^2 + 6x + 9", "reponse": "(x+3)^2", "forme": "developpee"}
        r = client.post("/admin/questions/tester", headers=connecter_admin(client), json=essai).json()
        assert r == {"correcte": False, "solution_lisible": True, "forme_non_respectee": True}

    def test_solution_hors_forme_refusee(self, client):
        corps = {"competence_id": 3, "enonce": "Factoriser $x^2-1$.", "type": "expression", "solution": "x^2 - 1",
                 "difficulte": 2, "forme": "factorisee"}
        assert client.post("/admin/questions", headers=connecter_admin(client), json=corps).status_code == 422

    def test_forme_reservee_aux_expressions(self, client):
        corps = {"competence_id": 3, "enonce": "?", "type": "numerique", "solution": "2", "difficulte": 2, "forme": "reduite"}
        assert client.post("/admin/questions", headers=connecter_admin(client), json=corps).status_code == 422

    def test_creer_avec_forme(self, client):
        corps = {"competence_id": 3, "enonce": "Factoriser $x^2-1$.", "type": "expression", "solution": "(x-1)(x+1)",
                 "difficulte": 2, "forme": "factorisee"}
        q = client.post("/admin/questions", headers=connecter_admin(client), json=corps).json()
        assert q["forme"] == "factorisee"


def corps_edition(q: models.Question, **modifs) -> dict:
    return {"competence_id": q.competence_id, "enonce": q.enonce, "type": q.type.value, "solution": q.solution,
            "difficulte": q.difficulte, "forme": q.forme.value if q.forme else None, **modifs}


class TestEditionProtegee:
    def test_forme_verifiee_sur_les_exemplaires_d_une_question_variable(self, client, session):
        from sqlalchemy import select
        q = session.scalar(select(models.Question).where(models.Question.code == "2NDE-DEV-V1"))
        h = connecter_admin(client)
        assert client.post(f"/admin/questions/{q.id}", headers=h, json=corps_edition(q, forme="factorisee")).status_code == 422
        assert client.post(f"/admin/questions/{q.id}", headers=h, json=corps_edition(q)).status_code == 200

    def test_forme_figee_apres_des_reponses(self, client, session):
        h = connecter_eleve(client)
        c = competence_ouverte(client, session, h)
        q = seule_question_developper(session, c)
        repondre(client, h, c.id, "x^2 + 6x + 9")
        r = client.post(f"/admin/questions/{q.id}", headers=connecter_admin(client), json=corps_edition(q, forme="reduite"))
        assert r.status_code == 409
