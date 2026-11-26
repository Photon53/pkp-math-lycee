# Issue #162 — Types choix_multiples et redaction (Claude)
"""Choix multiples (ensemble exact, sans ordre, sans crédit partiel) et rédaction (jamais corrigée par le moteur).
Le QCM à une seule lettre garde son comportement."""

import pytest

from pkp_engine import (
    CorrectionHumaineRequise,
    Question,
    TypeQuestion,
    Verdict,
    corrige_automatiquement,
    corriger,
    lettres_choisies,
    verifier,
)


def _q(type_: TypeQuestion, solution: str) -> Question:
    return Question(1, 1, "énoncé A) x  B) y  C) z  D) t", type_, solution, 2)


class TestChoixMultiples:
    @pytest.mark.parametrize("saisie", ["AC", "CA", "A,C", "c ; a", " a  c ", "A, C, A"])
    def test_ensemble_exact_quel_que_soit_l_ordre(self, saisie):
        assert corriger(_q(TypeQuestion.CHOIX_MULTIPLES, "AC"), saisie)

    @pytest.mark.parametrize("saisie", ["A", "C", "ACD", "ABCD", "B", "BD"])
    def test_pas_de_credit_partiel_ni_de_choix_en_trop(self, saisie):
        assert verifier(_q(TypeQuestion.CHOIX_MULTIPLES, "AC"), saisie) is Verdict.FAUX

    @pytest.mark.parametrize("saisie", ["", "   ", "A et C", "A-C", "1,3", "A)C", None])
    def test_saisie_illisible_fausse(self, saisie):
        assert not corriger(_q(TypeQuestion.CHOIX_MULTIPLES, "AC"), saisie)

    def test_lettres_choisies(self):
        assert lettres_choisies("b, a") == frozenset("AB")
        assert lettres_choisies("A2") is None


class TestQcmInchange:
    def test_une_seule_lettre_attendue(self):
        q = _q(TypeQuestion.QCM, "B")
        assert corriger(q, "B") and corriger(q, " b ")
        assert not corriger(q, "AB") and not corriger(q, "B,") and not corriger(q, "A")


class TestRedaction:
    def test_jamais_corrigee_automatiquement(self):
        q = _q(TypeQuestion.REDACTION, "Non : 5² + 6² = 61 ≠ 64.")
        assert not corrige_automatiquement(q)
        with pytest.raises(CorrectionHumaineRequise):
            verifier(q, "Non : 5² + 6² = 61 ≠ 64.")
        with pytest.raises(CorrectionHumaineRequise):
            corriger(q, "n'importe quoi")

    def test_les_autres_types_restent_automatiques(self):
        for type_ in (TypeQuestion.QCM, TypeQuestion.NUMERIQUE, TypeQuestion.EXPRESSION, TypeQuestion.TEXTE,
                      TypeQuestion.CHOIX_MULTIPLES):
            assert corrige_automatiquement(_q(type_, "A"))
