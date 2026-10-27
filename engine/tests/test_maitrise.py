import pytest

from pkp_engine import SEUIL_MAITRISE, Reponse, calculer_maitrise, est_maitrisee


def r(correcte: bool, competence_id: int = 1, question_id: int = 1) -> Reponse:
    return Reponse(question_id, competence_id, correcte, 30.0)


def test_sans_historique():
    assert calculer_maitrise([], 1) == 0.0


def test_une_bonne_reponse_ne_suffit_pas():
    assert calculer_maitrise([r(True)], 1) == pytest.approx(0.5)


def test_que_des_erreurs():
    assert calculer_maitrise([r(False)] * 10, 1) == 0.0


def test_cinq_reussites_d_affilee_atteignent_le_seuil():
    assert not est_maitrisee([r(True)] * 4, 1)
    assert est_maitrisee([r(True)] * 5, 1)


def test_reste_strictement_sous_1():
    assert SEUIL_MAITRISE < calculer_maitrise([r(True)] * 100, 1) < 1.0


def test_les_reponses_recentes_comptent_plus():
    progres = calculer_maitrise([r(False), r(True)], 1)
    regression = calculer_maitrise([r(True), r(False)], 1)
    assert progres > regression


def test_une_vieille_erreur_s_efface():
    assert not est_maitrisee([r(False)] * 3 + [r(True)] * 7, 1)
    assert est_maitrisee([r(False)] * 3 + [r(True)] * 10, 1)


def test_ignore_les_autres_competences():
    historique = [r(True, competence_id=2)] * 10 + [r(False, competence_id=1)]
    assert calculer_maitrise(historique, 1) == 0.0
    assert est_maitrisee(historique, 2)
