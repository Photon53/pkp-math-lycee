import pytest

from pkp_engine import ExpressionInvalide, Question, TypeQuestion, corriger


def q(type_: TypeQuestion, solution: str) -> Question:
    return Question(1, 1, "énoncé", type_, solution, 2)


class TestQcm:
    @pytest.mark.parametrize("saisie", ["B", "b", "  B ", "b\n"])
    def test_casse_et_espaces_ignores(self, saisie):
        assert corriger(q(TypeQuestion.QCM, "B"), saisie)

    @pytest.mark.parametrize("saisie", ["A", "", "BB"])
    def test_mauvaise_reponse(self, saisie):
        assert not corriger(q(TypeQuestion.QCM, "B"), saisie)


class TestNumerique:
    @pytest.mark.parametrize("saisie", ["0.5", "0,5", ".5", "1/2", "2/4", " 0.50 ", "+0.5"])
    def test_ecritures_equivalentes(self, saisie):
        assert corriger(q(TypeQuestion.NUMERIQUE, "1/2"), saisie)

    @pytest.mark.parametrize(
        ("solution", "saisie"),
        [("1000", "1 000"), ("-3", "−3"), ("9", "3²"), ("8", "2^3"), ("12", "3×4"), ("1.4142135623730951", "sqrt(2)")],
    )
    def test_notations_francaises(self, solution, saisie):
        assert corriger(q(TypeQuestion.NUMERIQUE, solution), saisie)

    @pytest.mark.parametrize("saisie", ["0.33", "0.4", "", "abc", "2x", "1/0", "import os", "__import__('os')"])
    def test_refuse(self, saisie):
        assert not corriger(q(TypeQuestion.NUMERIQUE, "1/3"), saisie)

    def test_solution_illisible_est_une_erreur_de_donnees(self):
        with pytest.raises(ExpressionInvalide):
            corriger(q(TypeQuestion.NUMERIQUE, "1/+/"), "1")


class TestExpression:
    @pytest.mark.parametrize(
        "saisie",
        ["x^2 + 2x + 1", "(x+1)^2", "(x+1)(x+1)", "x² + 2*x + 1", "1 + 2x + x*x", "(1+x)²"],
    )
    def test_formes_equivalentes(self, saisie):
        assert corriger(q(TypeQuestion.EXPRESSION, "(x+1)^2"), saisie)

    @pytest.mark.parametrize("saisie", ["x^2 + 1", "x^2 + 2x", "(y+1)^2", "", "x +", "sqrt"])
    def test_formes_differentes(self, saisie):
        assert not corriger(q(TypeQuestion.EXPRESSION, "(x+1)^2"), saisie)

    def test_plusieurs_variables(self):
        question = q(TypeQuestion.EXPRESSION, "(a+b)(a-b)")
        assert corriger(question, "a² - b²")
        assert not corriger(question, "a² + b²")

    def test_meme_domaine_accepte(self):
        # Les deux ne sont définies que pour x > 0 : les points négatifs sont ignorés.
        assert corriger(q(TypeQuestion.EXPRESSION, "ln(x) + ln(2)"), "ln(2x)")

    def test_domaines_differents_refuse(self):
        # Piège classique : ln(x²) = 2ln|x|, pas 2ln(x).
        assert not corriger(q(TypeQuestion.EXPRESSION, "ln(x^2)"), "2ln(x)")

    def test_fonctions_et_constantes(self):
        assert corriger(q(TypeQuestion.EXPRESSION, "exp(2x)"), "exp(x)^2")
        assert corriger(q(TypeQuestion.EXPRESSION, "2pi*x"), "2πx")

    @pytest.mark.parametrize(
        ("solution", "saisie"),
        [("ln(5)", "ln5"), ("ln(5)", "ln 5"), ("2ln(2)", "2ln2"), ("ln(x) + 1", "ln x + 1"),
         ("ln(x) + 1", "1 + lnx"), ("sqrt(2)/2", "sqrt(2)/2"), ("cos(x)", "cosx")],
    )
    def test_fonction_sans_parentheses(self, solution, saisie):
        type_ = TypeQuestion.EXPRESSION if "x" in solution else TypeQuestion.NUMERIQUE
        assert corriger(q(type_, solution), saisie)

    @pytest.mark.parametrize(
        ("solution", "saisie"),
        # Ambigu : ln(2)·x ou ln(2x) ? ln(x)² ou ln(x²) ? ln(2)/3 ou ln(2/3) ? -> refusé, jamais deviné.
        [("ln(2x)", "ln2x"), ("2ln(x)", "ln x^2"), ("ln(2/3)", "ln 2/3")],
    )
    def test_fonction_sans_parentheses_ambigue_refusee(self, solution, saisie):
        type_ = TypeQuestion.EXPRESSION if "x" in solution else TypeQuestion.NUMERIQUE
        assert not corriger(q(type_, solution), saisie)

    def test_saisie_trop_longue(self):
        assert not corriger(q(TypeQuestion.EXPRESSION, "x"), "x" + "+0" * 200)

    def test_puissance_enorme_ne_plante_pas(self):
        assert not corriger(q(TypeQuestion.EXPRESSION, "x"), "9^9^9^9")
