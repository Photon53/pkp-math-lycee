import pkp_engine
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db import models
from app.db.conversions import historique_eleve, question_vers_domaine
from app.db.seed import EMAIL_DEMO, charger_demo
from app.security import verifier_mot_de_passe


@pytest.fixture
def demo(session):
    charger_demo(session)
    return session


def compter(session, modele) -> int:
    return session.scalar(select(func.count()).select_from(modele))


class TestDonneesDeDemo:
    def test_contenu(self, demo):
        assert compter(demo, models.Enseignant) == 1
        assert compter(demo, models.Classe) == 3
        assert compter(demo, models.Eleve) == 5
        assert compter(demo, models.Chapitre) == 7
        assert compter(demo, models.Competence) == 17
        assert compter(demo, models.Question) == 80
        assert compter(demo, models.Lecon) == 17
        assert compter(demo, models.Reponse) == 7

    def test_idempotent(self, demo):
        assert charger_demo(demo) is False
        assert compter(demo, models.Question) == 80

    def test_chaque_solution_est_acceptee_par_le_moteur(self, demo):
        """Garde-fou qualité : une solution illisible lèverait ExpressionInvalide."""
        for q in demo.scalars(select(models.Question)):
            assert pkp_engine.corriger(question_vers_domaine(q), q.solution), q.enonce

    def test_reponses_corrigees_par_le_moteur(self, demo):
        lina = demo.scalar(select(models.Eleve).where(models.Eleve.prenom == "Lina"))
        assert [r.correcte for r in historique_eleve(demo, lina.id)] == [True, False, True, False, True]

    def test_mot_de_passe_hache(self, demo):
        enseignant = demo.scalar(select(models.Enseignant).where(models.Enseignant.email == EMAIL_DEMO))
        assert enseignant.mot_de_passe_hash.startswith("scrypt$")
        assert verifier_mot_de_passe("demo-pkp-2026", enseignant.mot_de_passe_hash)
        assert not verifier_mot_de_passe("mauvais", enseignant.mot_de_passe_hash)


class TestContraintes:
    def test_prenom_unique_dans_une_classe(self, demo):
        classe = demo.scalar(select(models.Classe).where(models.Classe.code == "2NDE-A-DEMO"))
        demo.add(models.Eleve(prenom="Lina", classe=classe))
        with pytest.raises(IntegrityError):
            demo.flush()

    def test_meme_prenom_dans_deux_classes(self, demo):
        classe = demo.scalar(select(models.Classe).where(models.Classe.code == "1RE-B-DEMO"))
        demo.add(models.Eleve(prenom="Lina", classe=classe))
        demo.flush()

    def test_difficulte_entre_1_et_5(self, demo):
        competence = demo.scalar(select(models.Competence))
        demo.add(models.Question(competence=competence, enonce="?", type=pkp_engine.TypeQuestion.QCM, solution="A", difficulte=6))
        with pytest.raises(IntegrityError):
            demo.flush()

    def test_question_jamais_supprimee(self, demo):
        question = demo.scalar(select(models.Question))
        demo.delete(question)
        with pytest.raises(models.SuppressionInterdite):
            demo.flush()

    def test_question_avec_reponses_protegee_aussi_en_sql(self, demo):
        """Même en contournant l'ORM, la clé étrangère RESTRICT bloque la suppression."""
        question_id = demo.scalar(select(models.Reponse.question_id))
        with pytest.raises(IntegrityError):
            demo.execute(models.Question.__table__.delete().where(models.Question.id == question_id))

    def test_question_archivee_reste_dans_l_historique(self, demo):
        question = demo.scalar(select(models.Reponse)).question
        question.archivee = True
        demo.commit()
        assert compter(demo, models.Reponse) == 7


class TestPurgeRgpd:
    def test_supprimer_un_eleve_supprime_ses_seances_et_reponses(self, demo):
        lina = demo.scalar(select(models.Eleve).where(models.Eleve.prenom == "Lina"))
        demo.delete(lina)
        demo.commit()
        assert compter(demo, models.Seance) == 1
        assert compter(demo, models.Reponse) == 2

    def test_supprimer_une_classe_supprime_ses_eleves(self, demo):
        demo.execute(models.Classe.__table__.delete().where(models.Classe.code == "2NDE-A-DEMO"))
        demo.commit()
        assert compter(demo, models.Eleve) == 2
        assert compter(demo, models.Reponse) == 0
        assert compter(demo, models.Question) == 80


def test_historique_vers_moteur(demo):
    yanis = demo.scalar(select(models.Eleve).where(models.Eleve.prenom == "Yanis"))
    historique = historique_eleve(demo, yanis.id)
    assert all(isinstance(r, pkp_engine.Reponse) for r in historique)
    assert [r.correcte for r in historique] == [False, True]
    # Le moteur fonctionne directement sur ces données.
    candidates = [question_vers_domaine(q) for q in demo.scalars(select(models.Question))]
    prochaine = pkp_engine.choisir_prochaine_question(candidates, historique)
    assert prochaine is not None and not prochaine.archivee
