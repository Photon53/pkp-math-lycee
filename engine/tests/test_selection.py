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


# Ticket #26 : une question réussie ne revient pas tout de suite.
from pkp_engine import ESPACEMENT_REVISION, questions_au_repos  # noqa: E402


def qv(id_: int, competence_id: int = 1) -> Question:
    return Question(id_, competence_id, f"Q{id_}", TypeQuestion.NUMERIQUE, "1", 1, variable=True)


def test_reproduction_deux_questions_reussies_ne_tournent_plus_en_boucle():
    """Avant : compétence 1 la plus faible, ses deux questions réussies revenaient en alternance."""
    historique = [r(10, False, 2), r(1, True), r(10, False, 2), r(2, True), r(10, False, 2)]
    candidates = [q(1), q(2), q(10, competence_id=2), q(11, competence_id=2)]
    # Compétence 2 est la plus faible (que des erreurs) ; même en forçant la compétence 1, rien n'y est disponible.
    assert choisir_prochaine_question([q(1), q(2)], historique) is None
    assert choisir_prochaine_question(candidates, historique).id == 11


def test_competence_entierement_reussie_cede_la_place():
    # Compétence 1 moins maîtrisée (1 juste sur 3), mais ses questions disponibles sont toutes au repos.
    historique = [r(5, False), r(6, False), r(1, True), r(20, True, 2), r(21, True, 2), r(22, True, 2)]
    candidates = [q(1), q(20, competence_id=2), q(23, competence_id=2)]
    assert choisir_prochaine_question(candidates, historique).id == 23


def test_reponse_juste_met_au_repos():
    assert questions_au_repos([r(1, True)]) == {1}
    assert choisir_prochaine_question([q(1), q(2, difficulte=5)], [r(1, True)]).id == 2


def test_reponse_fausse_reste_a_retravailler():
    historique = [r(1, False), r(2, True)]
    assert questions_au_repos(historique) == {2}
    assert choisir_prochaine_question([q(1), q(2)], historique).id == 1


def test_erreur_corrigee_ensuite_met_au_repos():
    assert questions_au_repos([r(1, False), r(1, True)]) == {1}
    assert questions_au_repos([r(1, True), r(1, False)]) == set()


def test_revision_espacee_apres_le_delai():
    historique = [r(1, True)] + [r(100 + i, True, 2) for i in range(ESPACEMENT_REVISION)]
    assert 1 not in questions_au_repos(historique)
    assert choisir_prochaine_question([q(1)], historique).id == 1
    assert choisir_prochaine_question([q(1)], historique[:-1]) is None


def test_changement_de_seance_l_historique_suit_l_eleve():
    # L'historique est celui de l'élève, toutes séances confondues : la réussite d'hier compte aujourd'hui.
    seance_1 = [r(1, True), r(2, True)]
    seance_2 = [r(3, False)]
    assert choisir_prochaine_question([q(1), q(2), q(3), q(4)], seance_1 + seance_2).id == 4


def test_banque_epuisee_rien_plutot_qu_une_boucle():
    historique = [r(1, True), r(2, True)]
    assert choisir_prochaine_question([q(1), q(2)], historique) is None


def test_revision_demandee_par_l_eleve():
    historique = [r(1, True), r(2, True)]
    assert choisir_prochaine_question([q(1), q(2)], historique, espacement=0).id == 1


def test_variante_a_valeurs_variables_en_dernier_recours():
    historique = [r(1, True), r(2, True)]
    assert choisir_prochaine_question([q(1), qv(2)], historique).id == 2
    # Une question fixe disponible passe avant la variante.
    assert choisir_prochaine_question([q(1), qv(2), q(3, difficulte=5)], historique).id == 3


def test_progression_chaque_question_servie_une_fois_avant_toute_repetition():
    candidates = [q(i, difficulte=1 + i % 5) for i in range(1, 9)]
    historique: list[Reponse] = []
    servies = []
    while (choix := choisir_prochaine_question(candidates, historique)) is not None:
        servies.append(choix.id)
        historique.append(r(choix.id, True))
    assert sorted(servies) == list(range(1, 9))
