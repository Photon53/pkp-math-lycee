from pkp_engine import Question, Reponse, TypeQuestion, choisir_prochaine_question


def q(id_: int, competence_id: int = 1, difficulte: int = 1, archivee: bool = False) -> Question:
    return Question(id_, competence_id, f"Q{id_}", TypeQuestion.NUMERIQUE, "1", difficulte, archivee)


def r(question_id: int, correcte: bool, competence_id: int = 1) -> Reponse:
    return Reponse(question_id, competence_id, correcte, 30.0)


def test_aucune_candidate():
    assert choisir_prochaine_question([], []) is None


def test_question_archivee_jamais_proposee():
    assert choisir_prochaine_question([q(1, archivee=True)], []) is None
    assert choisir_prochaine_question([q(1, archivee=True), q(2)], []).id == 2


def test_debutant_commence_par_le_plus_facile():
    candidates = [q(1, difficulte=3), q(2, difficulte=1), q(3, difficulte=5)]
    assert choisir_prochaine_question(candidates, []).id == 2


def test_eleve_qui_reussit_monte_en_difficulte():
    # 5 réussites -> maîtrise ≈ 0.80 -> difficulté visée 4.
    historique = [r(100 + i, True) for i in range(5)]
    candidates = [q(1, difficulte=1), q(2, difficulte=4), q(3, difficulte=5)]
    assert choisir_prochaine_question(candidates, historique).id == 2


def test_travaille_la_competence_la_plus_faible():
    historique = [r(100 + i, True, competence_id=1) for i in range(5)] + [r(200, False, competence_id=2)]
    candidates = [q(1, competence_id=1), q(2, competence_id=2)]
    assert choisir_prochaine_question(candidates, historique).id == 2


def test_ne_repose_pas_la_derniere_question():
    historique = [r(1, False)]
    assert choisir_prochaine_question([q(1), q(2, difficulte=3)], historique).id == 2


def test_repose_la_derniere_s_il_n_y_a_qu_elle():
    assert choisir_prochaine_question([q(1)], [r(1, False)]).id == 1


def test_prefere_une_question_pas_encore_reussie():
    historique = [r(1, True), r(3, False)]
    # q1 réussie, q3 venant d'être posée : q2 (ratée plus tôt ou jamais vue) passe devant.
    candidates = [q(1), q(2, difficulte=5), q(3)]
    assert choisir_prochaine_question(candidates, historique).id == 2


def test_resultat_deterministe():
    candidates = [q(i, difficulte=1 + i % 5) for i in range(1, 20)]
    historique = [r(i, i % 2 == 0) for i in range(1, 8)]
    premiers = {choisir_prochaine_question(candidates, historique).id for _ in range(10)}
    assert len(premiers) == 1
