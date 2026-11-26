# Issue #162 — Passation adaptative du diagnostic, lot 3 (Claude)
from pkp_engine.diagnostic import (
    MAX_QUESTIONS,
    CompetenceDiagnostic,
    Conclusion,
    Observation,
    QuestionDiagnostic,
    Resultat,
    conclusions,
    etat_competence,
    prochaine_question,
)

J, F, NSP, ATT = Resultat.JUSTE, Resultat.FAUX, Resultat.NE_SAIT_PAS, Resultat.EN_ATTENTE


def comp(cid: int, difficultes: list[int], retour: tuple[int, ...] = ()) -> CompetenceDiagnostic:
    return CompetenceDiagnostic(
        cid, tuple(QuestionDiagnostic(cid * 100 + i, cid, d) for i, d in enumerate(difficultes, 1)), retour
    )


def jouer(entree, toutes, reponses):
    """Fait passer le diagnostic : `reponses(question)` donne le résultat ; renvoie les observations."""
    obs: list[Observation] = []
    while (q := prochaine_question(entree, toutes, obs)) is not None:
        obs.append(Observation(q.id, q.competence_id, reponses(q)))
    return obs


A = comp(1, [1, 2, 3, 2])
B = comp(2, [2, 3])


class TestDansUneCompetence:
    def test_commence_par_la_difficulte_2(self):
        assert prochaine_question([A], {1: A}, []).difficulte == 2

    def test_deux_reussites_closent_la_competence(self):
        obs = jouer([A, B], {1: A, 2: B}, lambda q: J)
        assert [o.competence_id for o in obs] == [1, 1, 2, 2]
        assert etat_competence(A, obs).conclusion is Conclusion.ACQUISE

    def test_apres_une_reussite_pas_plus_simple(self):
        q1 = prochaine_question([A], {1: A}, [])
        q2 = prochaine_question([A], {1: A}, [Observation(q1.id, 1, J)])
        assert q2.difficulte >= q1.difficulte

    def test_apres_un_echec_deux_relances_dont_une_plus_simple(self):
        q1 = prochaine_question([A], {1: A}, [])
        obs = [Observation(q1.id, 1, F)]
        q2 = prochaine_question([A], {1: A}, obs)
        assert q2.difficulte < q1.difficulte
        obs.append(Observation(q2.id, 1, J))
        q3 = prochaine_question([A], {1: A}, obs)
        assert q3 is not None and q3.competence_id == 1
        obs.append(Observation(q3.id, 1, F))
        assert etat_competence(A, obs).close and etat_competence(A, obs).conclusion is Conclusion.FRAGILE

    def test_une_erreur_isolee_ne_conclut_pas_a_reprendre(self):
        obs = jouer([A], {1: A}, lambda q: F if q.difficulte == 2 and q.id == 102 else J)
        assert etat_competence(A, obs).conclusion is not Conclusion.A_REPRENDRE

    def test_je_ne_sais_pas_compte_comme_un_echec_pour_les_relances(self):
        obs = jouer([A], {1: A}, lambda q: NSP)
        assert len(obs) == 3 and etat_competence(A, obs).conclusion is Conclusion.A_REPRENDRE

    def test_redaction_en_attente_ni_juste_ni_faux(self):
        obs = jouer([B], {2: B}, lambda q: ATT)
        assert len(obs) == 2 and etat_competence(B, obs).conclusion is Conclusion.EN_ATTENTE

    def test_competence_sans_question_ignoree(self):
        vide = CompetenceDiagnostic(9, ())
        assert prochaine_question([vide, B], {9: vide, 2: B}, []).competence_id == 2


class TestDescente:
    BAS = comp(30, [1, 2])  # niveau inférieur
    HAUT = comp(10, [2, 2, 3], retour=(30,))
    SUITE = comp(20, [2, 3])
    TOUTES = {10: HAUT, 20: SUITE, 30: BAS}

    def test_a_reprendre_ouvre_le_niveau_precedent_avant_la_suite(self):
        obs = jouer([self.HAUT, self.SUITE], self.TOUTES, lambda q: F if q.competence_id == 10 else J)
        ordre = [o.competence_id for o in obs]
        assert ordre == [10, 10, 10, 30, 30, 20, 20]

    def test_pas_de_descente_si_acquise(self):
        obs = jouer([self.HAUT, self.SUITE], self.TOUTES, lambda q: J)
        assert 30 not in {o.competence_id for o in obs}

    def test_retour_inconnu_ou_cyclique_sans_boucle(self):
        x = comp(1, [2, 2], retour=(2, 99))
        y = comp(2, [2, 2], retour=(1,))
        obs = jouer([x], {1: x, 2: y}, lambda q: F)
        assert {o.competence_id for o in obs} == {1, 2}


def test_passation_bornee():
    beaucoup = [comp(i, [2, 2, 2, 2]) for i in range(1, 30)]
    obs = jouer(beaucoup, {c.id: c for c in beaucoup}, lambda q: F)
    assert len(obs) == MAX_QUESTIONS


def test_conclusions_des_seules_competences_interrogees():
    obs = jouer([A], {1: A, 2: B}, lambda q: J)
    assert set(conclusions({1: A, 2: B}, obs)) == {1}
