"""Ticket #27 : corrigés détaillés (gabarit), inventaire des réponses réduites au résultat, pilote fonctions affines."""

import pytest

from app import contenu
from app.contenu import COMPLET, A_COMPLETER, RESULTAT_SEUL, CorrectionYaml, charger, niveau_de_corrige


def question(type_="numerique", **correction):
    corps = {"code": "T-01", "difficulte": 2, "type": type_, "enonce": "Calculer.", "solution": "2"}
    if correction:
        corps["correction"] = correction
    return contenu.QuestionYaml(**corps)


@pytest.fixture(scope="module")
def fichiers():
    return charger()


class TestClassement:
    def test_resultat_seul(self):
        assert niveau_de_corrige(question()) == RESULTAT_SEUL
        assert niveau_de_corrige(question(etapes=["$x = 2$."], resultat="2")) == RESULTAT_SEUL

    def test_a_completer(self):
        # Une étape, mais la méthode est donnée ; ou deux étapes sans vérification.
        assert niveau_de_corrige(question(methode="Résoudre.", etapes=["$x = 2$."], resultat="2")) == A_COMPLETER
        assert niveau_de_corrige(question(methode="Résoudre.", etapes=["a", "b"], resultat="2")) == A_COMPLETER

    def test_complet(self):
        q = question(formule="$x = -p/m$", etapes=["a", "b"], resultat="2", verification="$f(2) = 0$.")
        assert niveau_de_corrige(q) == COMPLET
        # QCM : la vérification n'est pas exigée.
        qcm = contenu.QuestionYaml(code="T-02", difficulte=1, type="qcm", enonce="A) 1  B) 2", solution="B",
                                   correction={"methode": "Lire.", "etapes": ["a", "b"], "resultat": "B"})
        assert niveau_de_corrige(qcm) == COMPLET


class TestGabarit:
    def test_rubriques_facultatives(self):
        c = CorrectionYaml(etapes=["a"])
        assert c.rappel is None and c.formule is None and c.verification is None and c.autre_methode is None

    def test_dollars_controles_dans_toutes_les_rubriques(self):
        q = question(etapes=["a"], resultat="2", verification="$f(2) = 0")
        assert any("$" in e for e in contenu._verifier_correction(q))


class TestPilote:
    def test_corriges_pilotes_complets(self, fichiers):
        """Fonctions affines (priorité du pilote) : chaque corrigé suit le gabarit complet."""
        pilotes = [
            q for _, f in fichiers for c in f.competences if c.code in contenu.COMPETENCES_PILOTES_CORRIGES
            for q in c.questions if not q.archivee
        ]
        assert pilotes
        incomplets = [q.code for q in pilotes if niveau_de_corrige(q) != COMPLET]
        assert not incomplets, f"corrigés pilotes à compléter : {incomplets}"
        # Les étapes justifient : au moins une formule ou un rappel dans le chapitre, et une substitution chiffrée.
        assert all(q.correction.formule or q.correction.rappel for q in pilotes)

    def test_corriges_pilotes_restent_a_valider(self, fichiers):
        """La revue humaine est préservée : le brouillon réécrit n'est pas validé d'office."""
        for _, f in fichiers:
            for c in f.competences:
                if c.code in contenu.COMPETENCES_PILOTES_CORRIGES:
                    assert all(q.validation.statut.value != "validee" or q.validation.par for q in c.questions)


def test_inventaire_des_corriges_a_jour(fichiers):
    """Garde-fou : docs/audit/CORRIGES-INVENTAIRE.md est régénéré après chaque modification du contenu."""
    assert contenu.CORRIGES_PAR_DEFAUT.read_text(encoding="utf-8") == contenu.inventaire_corriges(fichiers), (
        "Inventaire des corrigés périmé : lancer `python -m app.contenu corrections` depuis api/"
    )
