"""Question « texte » (réponse courte, PKP Français) : contenu, administration, réponse d'élève."""

from app.db import models
from pkp_engine import TypeQuestion
from tests.conftest import connecter_admin, connecter_eleve
from tests.test_contenu import MINIMAL, charger, ecrire, erreurs
from tests.test_forme import repondre
from tests.test_publication import competence_ouverte

QUESTION = '      - {code: TEST-C-01, difficulte: 1, type: numerique, enonce: "1 + 1 ?", solution: 2}'


def avec_question(solution: str, correction: str = "") -> str:
    assert QUESTION in MINIMAL
    ligne = f'      - {{code: TEST-C-01, difficulte: 1, type: texte, enonce: "Conjuguer finir (ils, présent).", solution: "{solution}"{correction}}}'
    return MINIMAL.replace(QUESTION, ligne)


class TestContenu:
    def test_plusieurs_reponses_acceptees(self, tmp_path):
        ecrire(tmp_path, avec_question("finissent | ils finissent"))
        [(_, fichier)] = charger(tmp_path)
        q = fichier.competences[0].questions[0]
        assert q.type is TypeQuestion.TEXTE and q.solution == "finissent | ils finissent"

    def test_reponse_vide_refusee(self, tmp_path):
        ecrire(tmp_path, avec_question("finissent | "))
        assert "une réponse acceptée est vide" in erreurs(tmp_path)

    def test_correction_coherente(self, tmp_path):
        ecrire(tmp_path, avec_question("finissent", ", correction: {etapes: [Troisième personne du pluriel], resultat: finissaient}"))
        assert "correction.resultat « finissaient » non équivalent" in erreurs(tmp_path)

    def test_forme_reservee_aux_expressions(self, tmp_path):
        ecrire(tmp_path, avec_question("finissent", ", forme: developpee"))
        assert "`forme` ne concerne que les questions de type « expression »" in erreurs(tmp_path)


class TestAdministration:
    def test_tester(self, client):
        h = connecter_admin(client)
        essai = {"type": "texte", "solution": "à | a cause de", "reponse": "À"}
        assert client.post("/admin/questions/tester", headers=h, json=essai).json()["correcte"]
        essai["reponse"] = "a"
        r = client.post("/admin/questions/tester", headers=h, json={**essai, "reponse": "a"}).json()
        assert r["correcte"] is False and r["solution_lisible"] is True

    def test_creer(self, client):
        corps = {"competence_id": 3, "enonce": "Nature de « le » dans « je le vois » ?", "type": "texte",
                 "solution": "pronom | pronom personnel", "difficulte": 2}
        r = client.post("/admin/questions", headers=connecter_admin(client), json=corps)
        assert r.status_code in (200, 201) and r.json()["type"] == "texte"


class TestEleve:
    def _seule_question_texte(self, session, competence: models.Competence) -> None:
        questions = [q for q in competence.questions if not q.archivee]
        for q in questions[1:]:
            q.archivee = True
        q = questions[0]
        q.type, q.enonce, q.solution, q.forme, q.gabarit = TypeQuestion.TEXTE, "Le participe passé de « peindre » ?", "peint | peinte", None, None
        session.commit()

    def test_reponse_courte_corrigee(self, client, session):
        h = connecter_eleve(client)
        c = competence_ouverte(client, session, h)
        self._seule_question_texte(session, c)
        # D'abord faux (la question reste à retravailler), puis juste : une réussite la mettrait au repos (#26).
        r = repondre(client, h, c.id, "peins")
        assert not r["correcte"] and r["solution"] == "peint | peinte"
        assert repondre(client, h, c.id, " Peinte. ")["correcte"]
