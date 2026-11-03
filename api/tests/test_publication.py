"""Publication des questions : validées en priorité, jamais de question non relue si la configuration l'interdit."""

import pytest
from sqlalchemy import func, select

from app.config import settings
from app.db import models
from app.progression import nb_questions_servables
from app.referentiel import StatutValidation
from tests.conftest import connecter_eleve


def competence_ouverte(client, session, h, min_questions: int = 2) -> models.Competence:
    """Une compétence ouverte à Lina, avec plusieurs questions non archivées."""
    for p in client.get("/eleves/moi/progression", headers=h).json():
        nb = session.scalar(
            select(func.count(models.Question.id)).where(
                models.Question.competence_id == p["competence_id"], models.Question.archivee.is_(False)
            )
        )
        if nb >= min_questions:
            return session.get(models.Competence, p["competence_id"])
    pytest.fail("aucune compétence ouverte avec assez de questions")


def valider(session, question: models.Question) -> None:
    question.statut_validation = StatutValidation.VALIDEE
    session.commit()


def questions_servies(client, h, competence_id: int, n: int) -> list[dict]:
    """Les `n` premières questions d'une séance ciblée, en répondant faux à chacune."""
    s = client.post("/seances", headers=h, json={"competence_ids": [competence_id]}).json()["id"]
    servies = []
    for _ in range(n):
        r = client.get(f"/seances/{s}/question", headers=h)
        if r.status_code == 204:
            break
        q = r.json()
        servies.append(q)
        client.post(f"/seances/{s}/reponses", headers=h, json={"question_id": q["id"], "reponse_donnee": "faux"})
    return servies


class TestPriorite:
    def test_sans_question_validee_tout_est_servi_et_signale(self, client, session):
        h = connecter_eleve(client)
        c = competence_ouverte(client, session, h)
        servies = questions_servies(client, h, c.id, 3)
        assert servies and all(q["en_relecture"] for q in servies)

    def test_une_question_validee_remplace_les_autres_de_sa_competence(self, client, session):
        h = connecter_eleve(client)
        c = competence_ouverte(client, session, h)
        validee = next(q for q in c.questions if not q.archivee)
        valider(session, validee)
        servies = questions_servies(client, h, c.id, 3)
        assert {q["id"] for q in servies} == {validee.id}
        assert not any(q["en_relecture"] for q in servies)

    def test_le_compte_par_chapitre_suit_la_meme_regle(self, client, session):
        h = connecter_eleve(client)
        c = competence_ouverte(client, session, h)
        avant = nb_questions_servables(session, [c.chapitre_id])[c.chapitre_id]
        actives = [q for q in c.questions if not q.archivee]
        valider(session, actives[0])
        apres = nb_questions_servables(session, [c.chapitre_id])[c.chapitre_id]
        assert apres == avant - (len(actives) - 1)


class TestQuestionsValideesSeulement:
    @pytest.fixture(autouse=True)
    def seulement_validees(self, monkeypatch):
        monkeypatch.setattr(settings, "servir_questions_non_validees", False)

    def test_aucune_question_a_valider_n_est_servie(self, client, session):
        h = connecter_eleve(client)
        c = competence_ouverte(client, session, h)
        assert questions_servies(client, h, c.id, 1) == []

    def test_seules_les_questions_validees_sont_servies(self, client, session):
        h = connecter_eleve(client)
        c = competence_ouverte(client, session, h)
        validee = next(q for q in c.questions if not q.archivee)
        valider(session, validee)
        assert {q["id"] for q in questions_servies(client, h, c.id, 3)} == {validee.id}


class TestPrioriteEtNiveaux:
    def test_le_filtre_de_niveaux_ne_reouvre_pas_les_questions_non_validees(self, client, session):
        """La compétence a une question validée (niveau 1) : une séance « niveaux 2 à 5 » ne sert pas
        pour autant ses questions non validées."""
        h = connecter_eleve(client)
        c = competence_ouverte(client, session, h)
        actives = [q for q in c.questions if not q.archivee]
        actives[0].difficulte = 1
        for q in actives[1:]:
            q.difficulte = 3
        valider(session, actives[0])
        s = client.post("/seances", headers=h, json={"competence_ids": [c.id], "difficulte_min": 2, "difficulte_max": 5})
        assert client.get(f"/seances/{s.json()['id']}/question", headers=h).status_code == 204
