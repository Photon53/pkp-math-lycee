"""Contenu pédagogique : format YAML, vérification, import idempotent, routes /cours."""

from pathlib import Path
from textwrap import dedent

import pytest
from sqlalchemy import func, select

from app import contenu
from app.contenu import ContenuInvalide, charger, importer
from app.db import models
from tests.conftest import connecter_eleve

MINIMAL = """
chapitre: {code: TEST-CH, niveau: 2nde, ordre: 7, titre: Chapitre test}
competences:
  - code: TEST-C
    libelle: Compétence test
    cours: "Le cours avec $x^2$."
    resume: "Le résumé."
    questions:
      - {code: TEST-C-01, difficulte: 1, type: numerique, enonce: "1 + 1 ?", solution: 2}
      - {code: TEST-C-02, difficulte: 2, type: qcm, enonce: "Choix ? A) un  B) deux", solution: B}
"""


def ecrire(dossier: Path, texte: str, nom: str = "2nde/07-test.yaml") -> Path:
    chemin = dossier / nom
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(dedent(texte), encoding="utf-8")
    return chemin


def erreurs(dossier: Path) -> str:
    with pytest.raises(ContenuInvalide) as exc:
        charger(dossier)
    return "\n".join(exc.value.erreurs)


def compter(session, modele) -> int:
    return session.scalar(select(func.count()).select_from(modele))


class TestDepotReel:
    def test_tout_le_contenu_du_depot_est_valide(self):
        """Garde-fou CI : aucune solution illisible, aucun QCM incohérent, aucun code en double."""
        fichiers = charger()
        assert {f.chapitre.niveau.value for _, f in fichiers} == {"2nde", "1re", "Tle"}

    def test_ordre_scolaire(self):
        niveaux = [f.chapitre.niveau.value for _, f in charger()]
        assert niveaux == sorted(niveaux, key=["2nde", "1re", "Tle"].index)


class TestVerification:
    def test_fichier_minimal_valide(self, tmp_path):
        ecrire(tmp_path, MINIMAL)
        [(_, fichier)] = charger(tmp_path)
        assert fichier.competences[0].questions[0].solution == "2"  # entier YAML -> texte

    @pytest.mark.parametrize(
        ("avant", "apres", "message"),
        [
            ("solution: 2}", "solution: \"2 +\"}", "TEST-C-01 : solution « 2 + » illisible"),
            ("solution: B}", "solution: C}", "TEST-C-02 : solution « C » absente des choix"),
            ("code: TEST-C-02", "code: AUTRE-02", "le code doit commencer par « TEST-C- »"),
            ("code: TEST-C-02", "code: TEST-C-01", "question « TEST-C-01 » déjà défini"),
            ("difficulte: 2", "difficulte: 6", "difficulte : Input should be less than or equal to 5"),
            ("niveau: 2nde", "niveau: 3eme", "chapitre.niveau"),
            ('cours: "Le cours avec $x^2$."', 'cours: "Formule $x^2 non fermée."', "nombre impair de « $ »"),
            ('resume: "Le résumé."', "", "`cours` et `resume` vont ensemble"),
            ("type: numerique", "typ: numerique", "Extra inputs are not permitted"),
        ],
    )
    def test_erreurs_signalees_avec_le_fichier(self, tmp_path, avant, apres, message):
        assert avant in MINIMAL
        ecrire(tmp_path, MINIMAL.replace(avant, apres, 1))
        texte = erreurs(tmp_path)
        assert "2nde/07-test.yaml" in texte
        assert message in texte

    def test_codes_en_double_entre_fichiers(self, tmp_path):
        ecrire(tmp_path, MINIMAL)
        ecrire(tmp_path, MINIMAL.replace("ordre: 7", "ordre: 8"), "2nde/08-copie.yaml")
        texte = erreurs(tmp_path)
        assert "chapitre « TEST-CH » déjà défini dans 2nde/07-test.yaml" in texte

    def test_dossier_vide(self, tmp_path):
        assert "aucun fichier .yaml" in erreurs(tmp_path)

    def test_toutes_les_erreurs_d_un_coup(self, tmp_path):
        ecrire(tmp_path, MINIMAL.replace("solution: 2}", "solution: \"2 +\"}").replace("solution: B}", "solution: Z}"))
        assert erreurs(tmp_path).count("TEST-C-0") == 2


class TestImport:
    def test_import_puis_idempotent(self, session, tmp_path):
        ecrire(tmp_path, MINIMAL)
        rapport = importer(session, charger(tmp_path))
        assert rapport.crees == {"chapitres": 1, "compétences": 1, "leçons": 1, "questions": 2}
        assert importer(session, charger(tmp_path)).vide

    def test_mise_a_jour_d_une_question(self, session, tmp_path):
        ecrire(tmp_path, MINIMAL)
        importer(session, charger(tmp_path))
        ecrire(tmp_path, MINIMAL.replace('"1 + 1 ?"', '"Combien font 1 + 1 ?"'))
        rapport = importer(session, charger(tmp_path))
        assert rapport.modifies["questions"] == 1 and rapport.crees["questions"] == 0
        assert session.scalar(select(models.Question.enonce).where(models.Question.code == "TEST-C-01")) == "Combien font 1 + 1 ?"

    def test_question_retiree_archivee_puis_restauree(self, session, tmp_path):
        ecrire(tmp_path, MINIMAL)
        importer(session, charger(tmp_path))
        sans_q2 = MINIMAL.split("      - {code: TEST-C-02")[0]
        ecrire(tmp_path, sans_q2)
        assert importer(session, charger(tmp_path)).questions_archivees == ["TEST-C-02"]
        assert compter(session, models.Question) == 2  # archivée, jamais supprimée
        ecrire(tmp_path, MINIMAL)
        importer(session, charger(tmp_path))
        q2 = session.scalar(select(models.Question).where(models.Question.code == "TEST-C-02"))
        assert q2.archivee is False

    def test_questions_de_l_interface_enseignant_preservees(self, session, tmp_path):
        ecrire(tmp_path, MINIMAL)
        importer(session, charger(tmp_path))
        competence = session.scalar(select(models.Competence).where(models.Competence.code == "TEST-C"))
        session.add(models.Question(competence=competence, enonce="Ajoutée à la main", type="numerique", solution="1", difficulte=1))
        session.commit()
        assert importer(session, charger(tmp_path)).vide
        assert session.scalar(select(models.Question.archivee).where(models.Question.enonce == "Ajoutée à la main")) is False

    def test_simulation_ne_modifie_rien(self, session, tmp_path):
        ecrire(tmp_path, MINIMAL)
        rapport = importer(session, charger(tmp_path), simulation=True)
        assert rapport.crees["questions"] == 2
        assert compter(session, models.Chapitre) == 0

    def test_lecon_retiree_supprimee(self, session, tmp_path):
        ecrire(tmp_path, MINIMAL)
        importer(session, charger(tmp_path))
        ecrire(tmp_path, MINIMAL.replace('    cours: "Le cours avec $x^2$."\n    resume: "Le résumé."\n', ""))
        importer(session, charger(tmp_path))
        assert compter(session, models.Lecon) == 0

    def test_echange_d_ordre_entre_chapitres(self, session, tmp_path):
        ecrire(tmp_path, MINIMAL)
        autre = MINIMAL.replace("TEST-C", "AUTRE-C").replace("TEST-CH", "AUTRE-CH").replace("ordre: 7", "ordre: 8")
        ecrire(tmp_path, autre, "2nde/08-autre.yaml")
        importer(session, charger(tmp_path))
        ecrire(tmp_path, MINIMAL.replace("ordre: 7", "ordre: 8"))
        ecrire(tmp_path, autre.replace("ordre: 8", "ordre: 7"), "2nde/08-autre.yaml")
        importer(session, charger(tmp_path))  # ne heurte pas la contrainte unique (niveau, ordre)
        ordres = dict(session.execute(select(models.Chapitre.code, models.Chapitre.ordre)).all())
        assert ordres == {"TEST-CH": 8, "AUTRE-CH": 7}


class TestBaseExistante:
    def test_reprise_d_une_base_d_avant_les_codes(self, session):
        """Base de la phase 3 : chapitres en « 2nde-1 », questions sans code.
        L'import doit les reconnaître, pas les dupliquer, et ne pas toucher à l'historique."""
        chapitre = models.Chapitre(code="2nde-1", niveau="2nde", ordre=1, titre="Ancien titre")
        competence = models.Competence(code="2NDE-FRAC", libelle="Fractions", chapitre=chapitre)
        ancienne = models.Question(competence=competence, enonce="Calculer 1/2 + 1/3.", type="numerique", solution="5/6", difficulte=1)
        session.add(ancienne)
        session.commit()

        importer(session, contenu.charger())

        session.refresh(ancienne)
        assert ancienne.code == "2NDE-FRAC-01"
        assert session.scalar(select(func.count()).where(models.Question.enonce == "Calculer 1/2 + 1/3.")) == 1
        session.refresh(chapitre)
        assert (chapitre.code, chapitre.titre) == ("2NDE-NOMBRES", "Nombres et calculs")


class TestRoutesCours:
    def test_sommaire_du_niveau_de_l_eleve(self, client):
        sommaire = client.get("/cours", headers=connecter_eleve(client, "Emma", "TLE-C-DEMO")).json()
        assert [ch["code"] for ch in sommaire] == ["TLE-SUITES", "TLE-LN"]
        assert [c["code"] for c in sommaire[0]["competences"]] == ["TLE-SUI-REC", "TLE-SUI-LIM", "TLE-SUI-OPE", "TLE-SUI-COMP"]
        assert all(c["a_une_lecon"] for ch in sommaire for c in ch["competences"])

    def test_lecon(self, client):
        h = connecter_eleve(client, "Emma", "TLE-C-DEMO")
        competence_id = client.get("/cours", headers=h).json()[1]["competences"][0]["id"]
        lecon = client.get(f"/cours/{competence_id}", headers=h).json()
        assert lecon["code"] == "TLE-LN-DEF"
        assert lecon["chapitre"] == "Fonction logarithme népérien"
        assert "$\\ln(1) = 0$" in lecon["resume"]

    def test_cours_d_un_autre_niveau_introuvable(self, client):
        h_tle = connecter_eleve(client, "Emma", "TLE-C-DEMO")
        assert client.get("/cours/1", headers=h_tle).status_code == 404  # 2NDE-FRAC
        assert client.get("/cours/999", headers=h_tle).status_code == 404

    def test_reserve_aux_eleves(self, client):
        assert client.get("/cours").status_code == 401

    def test_question_servie_avec_sa_competence(self, client):
        h = connecter_eleve(client, "Emma", "TLE-C-DEMO")
        seance = client.post("/seances", headers=h).json()["id"]
        q = client.get(f"/seances/{seance}/question", headers=h).json()
        codes_tle = {c["id"] for ch in client.get("/cours", headers=h).json() for c in ch["competences"]}
        assert q["competence_id"] in codes_tle
