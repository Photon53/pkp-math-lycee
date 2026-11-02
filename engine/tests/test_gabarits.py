import random

import pytest

from pkp_engine import Question, TypeQuestion, corriger
from pkp_engine.gabarits import GabaritInvalide, evaluer, lire_tirage, marques, remplir, remplir_correction, tirer

EQUATION = {
    "parametres": {"a": {"entre": [2, 9]}, "x": {"entre": [-6, 6], "sauf": [0]}, "b": {"entre": [-9, 9], "sauf": [0]}},
    "calculs": {"c": "a*x + b"},
    "conditions": ["c != 0"],
}


class TestTirage:
    def test_respecte_les_bornes_les_exclusions_et_les_conditions(self):
        rng = random.Random(0)
        for _ in range(300):
            v = lire_tirage(tirer(EQUATION, rng))
            assert 2 <= v["a"] <= 9 and -6 <= v["x"] <= 6 and v["x"] != 0 and v["b"] != 0
            assert v["c"] == v["a"] * v["x"] + v["b"] and v["c"] != 0

    def test_varie_d_un_tirage_a_l_autre(self):
        rng = random.Random(1)
        assert len({tuple(tirer(EQUATION, rng).values()) for _ in range(30)}) > 20

    def test_parmi_et_pas_decimal(self):
        rng = random.Random(2)
        g = {"parametres": {"s": {"parmi": [-1, 1]}, "p": {"entre": [0.1, 0.9], "pas": 0.1}}}
        for _ in range(100):
            v = lire_tirage(tirer(g, rng))
            assert v["s"] in (-1, 1) and v["p"] * 10 == int(v["p"] * 10) and 0 < v["p"] < 1

    def test_calculs_exacts_en_fractions(self):
        t = tirer({"parametres": {"a": {"parmi": [3]}}, "calculs": {"q": "1/a + 1/6"}})
        assert t["q"] == "1/2"

    def test_division_par_zero_retiree(self):
        g = {"parametres": {"a": {"entre": [-1, 1]}}, "calculs": {"q": "1/a"}}
        assert {tirer(g, random.Random(i))["a"] for i in range(30)} <= {"-1", "1"}

    def test_pgcd(self):
        assert evaluer("pgcd(a, 18)", {"a": 12}) == 6

    def test_conditions_impossibles(self):
        with pytest.raises(GabaritInvalide, match="impossibles"):
            tirer({"parametres": {"a": {"entre": [1, 3]}}, "conditions": ["a > 5"]})

    @pytest.mark.parametrize("expression", ["__import__('os')", "a.real", "[a]", "a if a else 1", "open"])
    def test_pas_d_eval_python(self, expression):
        with pytest.raises(GabaritInvalide):
            evaluer(expression, {"a": 1})


class TestRemplissage:
    TIRAGE = {"a": "1", "b": "-3", "c": "-1", "f": "5/4"}

    def test_formes(self):
        assert remplir("[[a:coef]]x [[b:+]] = [[c]]", self.TIRAGE) == "x - 3 = -1"
        assert remplir("[[c:coef]]y", self.TIRAGE) == "-y"
        assert remplir("$[[f:frac]]$ et $[[-f:frac]]$ ; [[f]]", self.TIRAGE) == "$\\dfrac{5}{4}$ et $-\\dfrac{5}{4}$ ; 5/4"

    def test_expressions_et_latex_intact(self):
        assert remplir("$\\dfrac{1}{2}x = [[2*b + 1]]$", self.TIRAGE) == "$\\dfrac{1}{2}x = -5$"

    def test_correction_remplie_partout(self):
        correction = {"methode": "Isoler x.", "etapes": ["On ajoute [[-b]] : x = [[c-b]]."], "resultat": "[[c-b]]"}
        assert remplir_correction(correction, self.TIRAGE) == {
            "methode": "Isoler x.", "etapes": ["On ajoute 3 : x = 2."], "resultat": "2",
        }

    def test_marques(self):
        assert marques("[[a]] et [[b:+]], $\\dfrac{1}{2}$") == ["a", "b"]


def test_solution_remplie_corrigee_par_le_moteur():
    rng = random.Random(3)
    for _ in range(50):
        t = tirer(EQUATION, rng)
        solution = remplir("[[(c - b)/a]]", t)
        assert corriger(Question(1, 1, "", TypeQuestion.NUMERIQUE, solution, 2), solution)
        assert corriger(Question(1, 1, "", TypeQuestion.NUMERIQUE, solution, 2), remplir("[[x]]", t))
