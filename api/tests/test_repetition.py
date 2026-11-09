"""Ticket #26 : une question réussie ne revient pas tout de suite ; la banque épuisée est expliquée à l'élève."""

import pytest
from sqlalchemy import select

from app.db import models
from app.referentiel import Niveau
from tests.conftest import connecter_eleve


@pytest.fixture
def deux_questions(session) -> tuple[int, dict[int, str]]:
    """Une compétence de 2nde réduite à deux questions à valeurs fixes : (compétence, {question: solution})."""
    competence = session.scalars(
        select(models.Competence).join(models.Chapitre)
        .where(models.Chapitre.niveau == Niveau.SECONDE, models.Competence.masque.is_(False))
        .order_by(models.Competence.id)
    ).first()
    questions = [q for q in competence.questions if not q.archivee]
    gardees = [q for q in questions if q.gabarit is None and q.type.value == "numerique"][:2]
    assert len(gardees) == 2
    for q in questions:
        q.archivee = q not in gardees
    session.commit()
    return competence.id, {q.id: q.solution for q in gardees}


def seance(client, h, competence_id) -> int:
    r = client.post("/seances", headers=h, json={"competence_ids": [competence_id]})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def repondre(client, h, s, solutions, juste=True) -> int:
    q = client.get(f"/seances/{s}/question", headers=h).json()
    reponse = solutions[q["id"]] if juste else "faux"
    corps = client.post(f"/seances/{s}/reponses", headers=h, json={"question_id": q["id"], "reponse_donnee": reponse}).json()
    assert corps["correcte"] is juste
    return q["id"]


def test_question_reussie_ne_revient_pas_et_l_epuisement_est_explique(client, deux_questions):
    competence_id, solutions = deux_questions
    h = connecter_eleve(client, "Inès")
    s = seance(client, h, competence_id)
    premiere = repondre(client, h, s, solutions)
    seconde = repondre(client, h, s, solutions)
    assert {premiere, seconde} == set(solutions)

    # Avant : l'une des deux revenait. Maintenant : rien, et l'élève sait pourquoi.
    assert client.get(f"/seances/{s}/question", headers=h).status_code == 204
    assert client.get(f"/seances/{s}/epuisement", headers=h).json() == {
        "motif": "toutes-reussies", "nb_questions": 2, "nb_au_repos": 2,
    }
    # Révision demandée par l'élève : les questions réussies reviennent.
    r = client.get(f"/seances/{s}/question?revision=true", headers=h)
    assert r.status_code == 200 and r.json()["id"] in solutions


def test_erreur_retravaillee_apres_une_autre_question(client, deux_questions):
    competence_id, solutions = deux_questions
    h = connecter_eleve(client, "Inès")
    s = seance(client, h, competence_id)
    ratee = repondre(client, h, s, solutions, juste=False)
    autre = repondre(client, h, s, solutions)
    assert autre != ratee
    assert client.get(f"/seances/{s}/question", headers=h).json()["id"] == ratee


def test_changement_de_seance_les_reussites_sont_conservees(client, deux_questions):
    competence_id, solutions = deux_questions
    h = connecter_eleve(client, "Inès")
    s = seance(client, h, competence_id)
    repondre(client, h, s, solutions)
    repondre(client, h, s, solutions)
    client.post(f"/seances/{s}/fin", headers=h)
    nouvelle = seance(client, h, competence_id)
    assert client.get(f"/seances/{nouvelle}/question", headers=h).status_code == 204
    progression = {p["competence_id"]: p for p in client.get("/eleves/moi/progression", headers=h).json()}
    assert progression[competence_id]["nb_reponses"] >= 2 and progression[competence_id]["maitrise"] > 0


def test_banque_vide(client, session, deux_questions):
    competence_id, solutions = deux_questions
    for qid in solutions:
        session.get(models.Question, qid).archivee = True
    session.commit()
    h = connecter_eleve(client, "Inès")
    s = seance(client, h, competence_id)
    assert client.get(f"/seances/{s}/question", headers=h).status_code == 204
    assert client.get(f"/seances/{s}/epuisement", headers=h).json()["motif"] == "aucune-question"


def test_valeurs_variables_reconnues(client, session):
    """Une question sans gabarit est un null JSON en base : elle ne doit pas passer pour « variable »."""
    from app.routes.eleves import _candidates

    eleve = session.scalars(select(models.Eleve).where(models.Eleve.prenom == "Inès")).one()
    seance_ = models.Seance(eleve=eleve)
    session.add(seance_)
    session.flush()
    candidates = _candidates(session, seance_, eleve)
    gabarits = {q.id: q.gabarit is not None for q in session.scalars(select(models.Question).where(
        models.Question.id.in_([c.id for c in candidates])))}
    assert {c.id: c.variable for c in candidates} == gabarits
    assert any(gabarits.values()) and not all(gabarits.values())
