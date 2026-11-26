# Issue #162 — Diagnostic des acquis antérieurs, lot 2 (Claude)
"""Chapitres de diagnostic : format, import, non-diffusion, choix multiples, rédactions en attente, isolement de la
maîtrise. Le QCM existant garde son comportement (voir aussi engine/tests/test_types_diagnostic.py)."""

import pytest
from sqlalchemy import func, select

from app import diagnostic
from app.config import settings
from app.contenu import charger, importer, inventaire
from app.db import models
from app.db.conversions import historique_eleve
from app.diagnostic import DiagnosticRefuse
from app.progression import progression_eleve
from app.referentiel import NatureChapitre, Niveau, Parcours, StatutObservation, StatutValidation
from app.routes.pkp_math import Lecteur, _permis
from tests.conftest import connecter_admin, connecter_eleve, connecter_enseignant
from tests.test_contenu import MINIMAL, ecrire, erreurs

DIAG = """
chapitre: {code: TEST-DIAG, niveau: 2nde, nature: diagnostic, publics: [tronc-commun], programme_prerequis: 3e-2020,
           ordre: 96, titre: Diagnostic test}
competences:
  - code: TEST-DIAG-C
    libelle: Compétence de diagnostic
    questions:
      - {code: TEST-DIAG-C-01, difficulte: 1, type: qcm, enonce: "Choix ? A) un  B) deux", solution: B}
      - {code: TEST-DIAG-C-02, difficulte: 2, type: choix_multiples, enonce: "Vrai ? A) a  B) b  C) c  D) d", solution: AC}
      - {code: TEST-DIAG-C-03, difficulte: 3, type: redaction, enonce: "Justifie.", solution: "Réponse attendue.",
         correction: {etapes: [Premier argument., Second argument.]}}
      - {code: TEST-DIAG-C-04, difficulte: 1, type: numerique, enonce: "1 + 1 ?", solution: 2}
"""
CHEMIN_DIAG = "2nde/diagnostic/96-test.yaml"


def ecrire_diag(dossier, texte: str = DIAG):
    return ecrire(dossier, texte, CHEMIN_DIAG)


# --- Format ---------------------------------------------------------------------------------------------------


class TestFormat:
    def test_diagnostic_minimal_valide(self, tmp_path):
        ecrire_diag(tmp_path)
        [(_, f)] = charger(tmp_path)
        assert f.chapitre.diagnostic and f.chapitre.parcours is Parcours.TRONC_COMMUN
        assert f.chapitre.programme_prerequis == "3e-2020"

    @pytest.mark.parametrize(
        "avant, apres, message",
        [
            ("publics: [tronc-commun], ", "publics: [tronc-commun], parcours: tronc-commun, ", "n'a pas de `parcours`"),
            ("publics: [tronc-commun]", "publics: [specialite]", "n'est pas un parcours principal en 2nde"),
            ("publics: [tronc-commun]", "publics: [mise-a-niveau]", "n'est pas un parcours principal en 2nde"),
            ("publics: [tronc-commun]", "publics: []", "`publics` : au moins un parcours"),
            (" programme_prerequis: 3e-2020,", "", "`programme_prerequis` obligatoire"),
            ("solution: AC}", "solution: CA}", "dans l'ordre"),
            ("solution: AC}", "solution: AE}", "E absente(s) des choix"),
            ("\n         correction: {etapes: [Premier argument., Second argument.]}}", "}", "a un corrigé"),
        ],
    )
    def test_erreurs(self, tmp_path, avant, apres, message):
        assert avant in DIAG
        ecrire_diag(tmp_path, DIAG.replace(avant, apres))
        assert message in erreurs(tmp_path)

    def test_rangement_sous_diagnostic(self, tmp_path):
        ecrire(tmp_path, DIAG, "2nde/tronc-commun/96-test.yaml")
        assert "à ranger dans contenu/2nde/diagnostic/" in erreurs(tmp_path)

    @pytest.mark.parametrize("type_, solution", [("choix_multiples", "AB"), ("redaction", "texte")])
    def test_types_nouveaux_reserves_au_diagnostic(self, tmp_path, type_, solution):
        ligne = '      - {code: TEST-C-02, difficulte: 2, type: qcm, enonce: "Choix ? A) un  B) deux", solution: B}'
        assert ligne in MINIMAL
        nouvelle = (f'      - {{code: TEST-C-02, difficulte: 2, type: {type_}, enonce: "Choix ? A) un  B) deux", '
                    f'solution: {solution}, correction: {{etapes: [Une étape.]}}}}')
        ecrire(tmp_path, MINIMAL.replace(ligne, nouvelle))
        assert "réservés aux chapitres de diagnostic : TEST-C-02" in erreurs(tmp_path)

    def test_apprentissage_sans_publics(self, tmp_path):
        ecrire(tmp_path, MINIMAL.replace("ordre: 7,", "ordre: 7, publics: [tronc-commun],"))
        assert "ne concernent que les chapitres de diagnostic" in erreurs(tmp_path)

    def test_exemption_cours_et_difficultes_limitee_au_diagnostic(self, tmp_path):
        ecrire(tmp_path, MINIMAL.replace('    cours: "Le cours avec $x^2$."\n    resume: "Le résumé."\n', ""))
        ecrire_diag(tmp_path)
        texte = inventaire(charger(tmp_path))
        trous = texte.split("## Trous à combler")[1].split("## Registre")[0]
        assert "`TEST-C` (Compétence test) : aucune question de difficulté 3, 4, 5" in trous
        assert "`TEST-C` (Compétence test) : pas de cours" in trous
        assert "TEST-DIAG" not in trous
        assert "### 2nde — Diagnostic des acquis antérieurs" in texte


# --- Import et non-diffusion -----------------------------------------------------------------------------------


@pytest.fixture
def chapitre_diag(session, tmp_path) -> models.Chapitre:
    """Le diagnostic test importé dans la base de démo (sans archiver la banque) : questions « à valider »."""
    ecrire_diag(tmp_path)
    importer(session, charger(tmp_path), archiver_absentes=False)
    return session.scalar(select(models.Chapitre).where(models.Chapitre.code == "TEST-DIAG"))


def _lina(session) -> models.Eleve:
    return session.scalar(select(models.Eleve).where(models.Eleve.prenom == "Lina"))


def _valider(session, chapitre: models.Chapitre) -> None:
    for c in chapitre.competences:
        for q in c.questions:
            q.statut_validation, q.valide_par = StatutValidation.VALIDEE, "Mme Relectrice"
    session.commit()


def _du_test(questions: list[models.Question]) -> list[models.Question]:
    return [q for q in questions if q.code.startswith("TEST-DIAG-")]


def _question(chapitre: models.Chapitre, code: str) -> models.Question:
    return next(q for c in chapitre.competences for q in c.questions if q.code == code)


class TestImport:
    def test_nature_et_statut_a_valider(self, client, session, chapitre_diag):
        assert chapitre_diag.nature is NatureChapitre.DIAGNOSTIC
        assert chapitre_diag.publics == ["tronc-commun"] and chapitre_diag.programme_prerequis == "3e-2020"
        types = {q.code: q.type.value for c in chapitre_diag.competences for q in c.questions}
        assert types["TEST-DIAG-C-02"] == "choix_multiples" and types["TEST-DIAG-C-03"] == "redaction"
        assert all(q.statut_validation is StatutValidation.A_VALIDER for c in chapitre_diag.competences for q in c.questions)

    def test_jamais_ouvert_par_l_import(self, client, session, chapitre_diag):
        ouvert = session.scalar(
            select(func.count()).select_from(models.chapitres_de_classe)
            .where(models.chapitres_de_classe.c.chapitre_id == chapitre_diag.id)
        )
        assert ouvert == 0

    def test_import_idempotent(self, client, session, chapitre_diag, tmp_path):
        assert importer(session, charger(tmp_path), archiver_absentes=False).vide


class TestNonDiffusion:
    """Questions « à valider » : jamais servies, même avec PKP_SERVIR_QUESTIONS_NON_VALIDEES (vrai par défaut).
    Questions validées : jamais par l'entraînement, ni par les pages des enfants et des parents."""

    def test_reglage_par_defaut_sert_les_non_validees_a_l_entrainement(self):
        assert settings.servir_questions_non_validees  # c'est pourquoi le diagnostic a sa propre règle

    def test_non_validees_jamais_diffusables(self, client, session, chapitre_diag):
        lina = _lina(session)
        assert chapitre_diag in diagnostic.chapitres_du_public(session, lina.classe)
        assert diagnostic.questions_diffusables(session, lina.classe) == []  # banque du dépôt comprise : rien de validé
        with pytest.raises(DiagnosticRefuse):
            diagnostic.enregistrer_observation(session, lina, _question(chapitre_diag, "TEST-DIAG-C-04"), "2")

    def test_validees_diffusables_au_seul_public(self, client, session, chapitre_diag):
        _valider(session, chapitre_diag)
        lina = _lina(session)
        assert len(_du_test(diagnostic.questions_diffusables(session, lina.classe))) == 4
        autre = session.scalar(select(models.Classe).where(models.Classe.niveau != Niveau.SECONDE))
        assert diagnostic.questions_diffusables(session, autre) == []
        chapitre_diag.publics = ["professionnel"]
        session.commit()
        assert _du_test(diagnostic.questions_diffusables(session, lina.classe)) == []

    def test_archivee_ou_masquee_non_diffusable(self, client, session, chapitre_diag):
        _valider(session, chapitre_diag)
        lina = _lina(session)
        _question(chapitre_diag, "TEST-DIAG-C-01").archivee = True
        session.commit()
        assert len(_du_test(diagnostic.questions_diffusables(session, lina.classe))) == 3
        chapitre_diag.masque = True
        session.commit()
        assert _du_test(diagnostic.questions_diffusables(session, lina.classe)) == []

    def test_absent_du_programme_du_professeur(self, client, session, chapitre_diag):
        h = connecter_enseignant(client)
        classe = next(c for c in client.get("/enseignants/classes", headers=h).json() if c["code"] == "2NDE-A-DEMO")
        programme = client.get(f"/enseignants/classes/{classe['id']}/chapitres", headers=h).json()
        assert chapitre_diag.id not in {c["id"] for c in programme}
        r = client.put(f"/enseignants/classes/{classe['id']}/chapitres", headers=h,
                       json={"chapitre_ids": [chapitre_diag.id]})
        assert r.status_code == 422

    def test_jamais_servi_en_entrainement_meme_valide_et_ouvert_de_force(self, client, session, chapitre_diag):
        _valider(session, chapitre_diag)
        lina = _lina(session)
        lina.classe.chapitres_proposes = [chapitre_diag]  # état anormal, posé directement en base
        session.commit()
        h = connecter_eleve(client)
        assert client.get("/eleves/moi/chapitres", headers=h).json() == []
        assert client.post("/seances", headers=h, json={"chapitre_ids": [chapitre_diag.id]}).status_code in (409, 422)
        competence = chapitre_diag.competences[0].id
        assert client.post("/seances", headers=h, json={"competence_ids": [competence]}).status_code in (409, 422)
        assert all(p["competence_id"] != competence for p in client.get("/eleves/moi/progression", headers=h).json())
        assert client.get(f"/pkp-math/chapitres/{chapitre_diag.id}", headers=h).status_code == 404
        assert chapitre_diag.id not in {c["id"] for c in client.get("/pkp-math/catalogue", headers=h).json()}

    def test_seance_existante_ne_sert_pas_le_diagnostic(self, client, session, chapitre_diag):
        _valider(session, chapitre_diag)
        h = connecter_eleve(client)
        seance = client.post("/seances", headers=h, json={}).json()["id"]
        ids_diag = {q.id for c in chapitre_diag.competences for q in c.questions}
        for _ in range(5):
            r = client.get(f"/seances/{seance}/question", headers=h)
            if r.status_code == 204:
                break
            assert r.json()["id"] not in ids_diag
            client.post(f"/seances/{seance}/reponses", headers=h, json={"question_id": r.json()["id"], "reponse_donnee": "0"})

    def test_ni_enfants_ni_parents(self, client, session, chapitre_diag):
        _valider(session, chapitre_diag)
        apprentissage = session.scalar(
            select(models.Chapitre).where(models.Chapitre.niveau == Niveau.SECONDE,
                                          models.Chapitre.nature == NatureChapitre.APPRENTISSAGE)
        )
        for role in ("parent", "enfant"):
            lecteur = Lecteur(role, complet=False, niveaux={Niveau.SECONDE})
            assert _permis(session, lecteur, apprentissage)
            assert not _permis(session, lecteur, chapitre_diag)
        assert _permis(session, Lecteur("enseignant", complet=True), chapitre_diag)  # relecture par les adultes

    def test_absent_des_chiffres_publics(self, client, session, chapitre_diag):
        avant = client.get("/domaines/chiffres").json()
        _valider(session, chapitre_diag)
        assert client.get("/domaines/chiffres").json() == avant


# --- Observations : choix multiples, rédactions en attente, isolement de la maîtrise ---------------------------


@pytest.fixture
def lina_et_diag(client, session, chapitre_diag):
    _valider(session, chapitre_diag)
    return _lina(session), chapitre_diag


class TestObservations:
    @pytest.mark.parametrize("saisie, statut", [
        ("AC", StatutObservation.JUSTE), ("C, A", StatutObservation.JUSTE), ("A", StatutObservation.FAUX),
        ("ACD", StatutObservation.FAUX), ("A, D", StatutObservation.FAUX),
    ])
    def test_choix_multiples_ensemble_exact(self, session, lina_et_diag, saisie, statut):
        lina, ch = lina_et_diag
        obs = diagnostic.enregistrer_observation(session, lina, _question(ch, "TEST-DIAG-C-02"), saisie)
        assert obs.statut is statut

    def test_qcm_inchange(self, session, lina_et_diag):
        lina, ch = lina_et_diag
        q = _question(ch, "TEST-DIAG-C-01")
        assert diagnostic.enregistrer_observation(session, lina, q, "b").statut is StatutObservation.JUSTE
        assert diagnostic.enregistrer_observation(session, lina, q, "AB").statut is StatutObservation.FAUX

    def test_redaction_en_attente_sans_le_moteur(self, session, lina_et_diag, monkeypatch):
        def interdit(*_):
            raise AssertionError("une rédaction ne passe jamais par la correction automatique")

        monkeypatch.setattr(diagnostic, "verifier", interdit)
        lina, ch = lina_et_diag
        obs = diagnostic.enregistrer_observation(session, lina, _question(ch, "TEST-DIAG-C-03"), "Réponse attendue.")
        assert obs.statut is StatutObservation.EN_ATTENTE and obs.corrige_le is None
        assert diagnostic.en_attente(session, lina.classe) == [obs]

    def test_correction_par_le_professeur_de_la_classe(self, session, lina_et_diag):
        lina, ch = lina_et_diag
        obs = diagnostic.enregistrer_observation(session, lina, _question(ch, "TEST-DIAG-C-03"), "Ma justification.")
        autre = models.Enseignant(nom="Autre", email="autre@pkp.test", mot_de_passe_hash="x")
        session.add(autre)
        session.flush()
        with pytest.raises(DiagnosticRefuse):
            diagnostic.corriger_observation(session, obs, True, autre)
        diagnostic.corriger_observation(session, obs, True, lina.classe.enseignant)
        assert obs.statut is StatutObservation.JUSTE and obs.corrige_par == lina.classe.enseignant
        assert diagnostic.en_attente(session, lina.classe) == []
        with pytest.raises(DiagnosticRefuse):
            diagnostic.corriger_observation(session, obs, False, lina.classe.enseignant)

    def test_redaction_longue_acceptee_reponse_courte_bornee(self, session, lina_et_diag):
        lina, ch = lina_et_diag
        diagnostic.enregistrer_observation(session, lina, _question(ch, "TEST-DIAG-C-03"), "x" * 3000)
        with pytest.raises(DiagnosticRefuse):
            diagnostic.enregistrer_observation(session, lina, _question(ch, "TEST-DIAG-C-04"), "1" * 300)

    def test_maitrise_isolee(self, client, session, lina_et_diag):
        lina, ch = lina_et_diag
        avant = [p.model_dump() for p in progression_eleve(session, lina)]
        historique = historique_eleve(session, lina.id)
        nb_reponses = session.scalar(select(func.count(models.Reponse.id)))
        for code, saisie in [("TEST-DIAG-C-01", "B"), ("TEST-DIAG-C-02", "AC"), ("TEST-DIAG-C-03", "Texte"),
                             ("TEST-DIAG-C-04", "2"), ("TEST-DIAG-C-04", "3")]:
            diagnostic.enregistrer_observation(session, lina, _question(ch, code), saisie)
        obs = diagnostic.en_attente(session, lina.classe)[0]
        diagnostic.corriger_observation(session, obs, True, lina.classe.enseignant)
        session.commit()
        assert session.scalar(select(func.count(models.Reponse.id))) == nb_reponses
        assert historique_eleve(session, lina.id) == historique
        assert [p.model_dump() for p in progression_eleve(session, lina)] == avant
        h = connecter_eleve(client)
        assert client.get("/eleves/moi/historique", headers=h).json()["total"] == len(historique)

    def test_export_rgpd(self, client, session, lina_et_diag):
        lina, ch = lina_et_diag
        diagnostic.enregistrer_observation(session, lina, _question(ch, "TEST-DIAG-C-03"), "Ma justification.")
        session.commit()
        from app.progression import export_eleve
        import json

        donnees = json.loads(export_eleve(session, lina).body)
        assert donnees["observations_diagnostic"][0]["statut"] == "en-attente-de-correction"


class TestAdministration:
    def test_tester_une_redaction_ne_plante_pas(self, client):
        r = client.post("/admin/questions/tester", headers=connecter_admin(client),
                        json={"type": "redaction", "solution": "texte", "reponse": "texte"})
        assert r.status_code == 200 and r.json()["correcte"] is False

    @pytest.mark.parametrize("type_, solution", [("redaction", "texte"), ("choix_multiples", "AC")])
    def test_creation_dans_l_interface_refusee(self, client, type_, solution):
        corps = {"competence_id": 3, "enonce": "Vrai ? A) a  B) b  C) c", "type": type_, "solution": solution, "difficulte": 2}
        r = client.post("/admin/questions", headers=connecter_admin(client), json=corps)
        assert r.status_code == 422 and "fichiers de diagnostic" in r.text


class TestEffacement:
    def test_observations_supprimees_avec_l_eleve(self, client, session, lina_et_diag):
        lina, ch = lina_et_diag
        diagnostic.enregistrer_observation(session, lina, _question(ch, "TEST-DIAG-C-03"), "Ma justification.")
        session.commit()
        session.delete(lina)
        session.commit()
        assert session.scalar(select(func.count(models.ObservationDiagnostic.id))) == 0
