"""Questions à valeurs variables : de nouveaux nombres à chaque service, corrigés avec ces nombres,
« refaire avec d'autres nombres » après une erreur, et un historique qui remontre l'exercice posé."""

from app import exemplaires
from app.db import models
from tests.conftest import connecter_eleve, connecter_enseignant


def _competence_id(client, code: str) -> int:
    h = connecter_enseignant(client)
    return next(c["id"] for c in client.get("/enseignants/competences", headers=h).json() if c["code"] == code)


def _question_variable(client, session, h) -> tuple[int, dict]:
    """Séance ciblée sur 2NDE-EQ1 : on répond faux aux questions fixes jusqu'à tomber sur une variable."""
    s = client.post("/seances", headers=h, json={"competence_ids": [_competence_id(client, "2NDE-EQ1")]}).json()["id"]
    for _ in range(15):
        q = client.get(f"/seances/{s}/question", headers=h).json()
        if q["variable"]:
            return s, q
        client.post(f"/seances/{s}/reponses", headers=h, json={"question_id": q["id"], "reponse_donnee": "123456"})
    raise AssertionError("aucune question à valeurs variables servie")


def _bonne_reponse(session, seance_id: int) -> str:
    seance = session.get(models.Seance, seance_id)
    session.refresh(seance)
    return exemplaires.solution(seance.question_courante, seance.tirage_courant)


def test_enonce_rempli_et_redemande_identique(client, session):
    h = connecter_eleve(client, "Lina")
    s, q = _question_variable(client, session, h)
    assert "[[" not in q["enonce"] and "Résoudre" in q["enonce"]
    assert client.get(f"/seances/{s}/question", headers=h).json() == q  # mêmes nombres tant qu'on n'a pas répondu


def test_corrigee_avec_les_nombres_tires(client, session):
    h = connecter_eleve(client, "Lina")
    s, q = _question_variable(client, session, h)
    solution = _bonne_reponse(session, s)
    r = client.post(f"/seances/{s}/reponses", headers=h, json={"question_id": q["id"], "reponse_donnee": solution}).json()
    assert r["correcte"] is True and r["solution"] == solution
    assert "[[" not in str(r["correction"]) and r["correction"]["resultat"] == solution


def test_refaire_avec_d_autres_nombres(client, session):
    h = connecter_eleve(client, "Lina")
    s, q = _question_variable(client, session, h)
    client.post(f"/seances/{s}/reponses", headers=h, json={"question_id": q["id"], "reponse_donnee": "123456"})
    enonces = set()
    for _ in range(8):
        v = client.post(f"/seances/{s}/variante", headers=h, json={"question_id": q["id"]})
        assert v.status_code == 200 and v.json()["id"] == q["id"]
        enonces.add(v.json()["enonce"])
        client.post(f"/seances/{s}/reponses", headers=h, json={"question_id": q["id"], "reponse_donnee": "123456"})
    assert len(enonces) > 1  # d'autres nombres


def test_variante_refusee_hors_de_propos(client, session):
    h = connecter_eleve(client, "Lina")
    s, q = _question_variable(client, session, h)
    # Question en cours, pas encore corrigée : pas de variante.
    assert client.post(f"/seances/{s}/variante", headers=h, json={"question_id": q["id"]}).status_code == 409
    client.post(f"/seances/{s}/reponses", headers=h, json={"question_id": q["id"], "reponse_donnee": "0"})
    # Une autre question que celle qui vient d'être corrigée : refusé.
    assert client.post(f"/seances/{s}/variante", headers=h, json={"question_id": q["id"] + 999}).status_code == 409


def test_historique_remontre_l_exercice_pose(client, session):
    h = connecter_eleve(client, "Lina")
    s, q = _question_variable(client, session, h)
    client.post(f"/seances/{s}/reponses", headers=h, json={"question_id": q["id"], "reponse_donnee": "123456"})
    dernier = client.get("/eleves/moi/historique", headers=h).json()["elements"][0]
    assert dernier["enonce"] == q["enonce"] and "[[" not in dernier["solution"]
