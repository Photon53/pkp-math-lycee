"""Référentiels officiels, liens compétence → attendu, corrections détaillées, matrice de couverture."""

import hashlib
from datetime import date
from pathlib import Path
from textwrap import dedent

import pytest

from app import matrice, programmes
from app.contenu import ContenuInvalide, charger
from app.programmes import ReferentielInvalide

PDF = b"%PDF-1.4 programme de test"


def referentiel(dossier: Path, attendus: str | None = None) -> Path:
    """Un programme de test (1re spécialité) avec deux capacités, une démonstration et un approfondissement."""
    (dossier / "sources").mkdir(parents=True)
    (dossier / "sources" / "bo.pdf").write_bytes(PDF)
    (dossier / "sources" / "sources.yaml").write_text(
        dedent(f"""
        - code: bo-test
          titre: Programme de test
          bulletin: BO de test
          fichier: bo.pdf
          sha256: {hashlib.sha256(PDF).hexdigest()}
          obtenu_le: 2026-10-31
        """),
        encoding="utf-8",
    )
    (dossier / "1re-test").mkdir()
    (dossier / "1re-test" / "programme.yaml").write_text(
        "code: TEST-1RE\ntitre: Test\nniveau: 1re\nparcours: specialite\nsource: bo-test\nen_vigueur_du: 2026-09-01\n",
        encoding="utf-8",
    )
    (dossier / "1re-test" / "theme.yaml").write_text(
        dedent(
            attendus
            or """
            theme: {code: SD, titre: Second degré, partie: Algèbre}
            attendus:
              - {code: TEST-1RE-SD-01, type: capacite, texte: Résoudre une équation du second degré.}
              - {code: TEST-1RE-SD-02, type: capacite, texte: Factoriser un polynôme du second degré.}
              - {code: TEST-1RE-SD-03, type: demonstration, texte: Résolution de l'équation., evaluation: auto_evaluation}
              - {code: TEST-1RE-SD-04, type: approfondissement, texte: Polynômes de degré 3.}
            """
        ),
        encoding="utf-8",
    )
    return dossier


def contenu(dossier: Path, competence: str, questions: str = "") -> Path:
    chemin = dossier / "1re" / "specialite" / "01-test.yaml"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(
        dedent("""
        chapitre: {code: TEST-CH, niveau: 1re, parcours: specialite, ordre: 1, titre: Test}
        competences:
        """) + competence + questions,  # blocs déjà indentés comme dans le fichier final
        encoding="utf-8",
    )
    return dossier


COMPETENCE = """
  - code: TEST-SD
    libelle: Résoudre
    attendus: [TEST-1RE-SD-01]
    cours: "Cours."
    resume: "Résumé."
    questions:
"""


def question(numero: int, difficulte: int = 1, extra: str = "") -> str:
    return f"""
      - code: TEST-SD-{numero:02d}
        difficulte: {difficulte}
        type: numerique
        enonce: "Plus grande racine de $x^2 - 4$ ?"
        solution: 2
{extra}"""


def erreurs_contenu(dossier: Path, codes: set[str]) -> str:
    with pytest.raises(ContenuInvalide) as exc:
        charger(dossier, codes_attendus=codes)
    return "\n".join(exc.value.erreurs)


class TestReferentielsDuDepot:
    def test_referentiels_du_depot_valides(self):
        """Garde-fou CI : sources présentes et intactes, codes d'attendus cohérents."""
        r = programmes.charger()
        assert "1RE-SPE-2026" in r.programmes
        assert any(a.type.value == "demonstration" for _, a in r.du_programme("1RE-SPE-2026"))

    def test_attendus_du_contenu_existent(self):
        charger()  # le contenu du dépôt ne cite que des attendus présents dans referentiels/


class TestChargementReferentiel:
    def test_pdf_modifie_detecte(self, tmp_path):
        referentiel(tmp_path)
        (tmp_path / "sources" / "bo.pdf").write_bytes(PDF + b" modifie")
        with pytest.raises(ReferentielInvalide, match="empreinte"):
            programmes.charger(tmp_path)

    def test_code_d_attendu_hors_programme(self, tmp_path):
        referentiel(tmp_path, """
            theme: {code: SD, titre: T, partie: P}
            attendus:
              - {code: AUTRE-SD-01, type: capacite, texte: Un attendu mal nommé.}
            """)
        with pytest.raises(ReferentielInvalide, match="doit commencer par « TEST-1RE-SD- »"):
            programmes.charger(tmp_path)


class TestReglesDeContenu:
    def test_attendu_inconnu(self, tmp_path):
        contenu(tmp_path, COMPETENCE.replace("TEST-1RE-SD-01", "TEST-1RE-SD-99"), question(1))
        assert "attendu « TEST-1RE-SD-99 » absent des référentiels" in erreurs_contenu(tmp_path, {"TEST-1RE-SD-01"})

    def test_prerequis_inconnu(self, tmp_path):
        contenu(tmp_path, COMPETENCE.replace("    cours:", "    prerequis: [TEST-RIEN]\n    cours:"), question(1))
        assert "prérequis « TEST-RIEN » inconnu" in erreurs_contenu(tmp_path, {"TEST-1RE-SD-01"})

    @pytest.mark.parametrize(
        ("extra", "message"),
        [
            ("        validation: {statut: validee, par: M. Durand, le: 2026-11-02}\n        auteur: R. Martin\n",
             "une question « validee » a une correction détaillée"),
            ("        auteur: M. Durand\n        validation: {statut: validee, par: m. durand, le: 2026-11-02}\n"
             "        correction: {etapes: [On factorise.], resultat: 2}\n",
             "le relecteur (`validation.par`) ne peut pas être l'auteur"),
            ("        correction: {etapes: [On factorise.], resultat: 3}\n", "non équivalent à la solution"),
            ("        correction: {etapes: [On factorise.]}\n", "correction.resultat obligatoire"),
        ],
    )
    def test_corrections_et_validation(self, tmp_path, extra, message):
        contenu(tmp_path, COMPETENCE, question(1, extra=extra))
        assert message in erreurs_contenu(tmp_path, {"TEST-1RE-SD-01"})

    def test_question_validee_et_corrigee_acceptee(self, tmp_path):
        extra = (
            "        auteur: R. Martin\n"
            "        validation: {statut: validee, par: M. Durand, le: 2026-11-02}\n"
            "        correction:\n"
            "          methode: Produit nul.\n"
            "          etapes: [\"$x^2 - 4 = (x-2)(x+2)$\", Les racines sont $-2$ et $2$.]\n"
            "          resultat: \"4/2\"\n"
        )
        contenu(tmp_path, COMPETENCE, question(1, extra=extra))
        [(_, fichier)] = charger(tmp_path, codes_attendus={"TEST-1RE-SD-01"})
        assert fichier.competences[0].questions[0].correction.etapes[1] == "Les racines sont $-2$ et $2$."

    def test_methode_avec_exemple_resolu(self, tmp_path):
        methode = COMPETENCE.replace(
            "    questions:",
            "    methodes:\n"
            "      - titre: Résoudre avec le discriminant\n"
            "        etapes: [Calculer $\\Delta$., Conclure selon son signe.]\n"
            "        exemple: {enonce: 'Résoudre $x^2 - 1 = 0$.', resolution: ['$\\Delta = 4$'], resultat: '$-1$ et $1$'}\n"
            "    erreurs_frequentes:\n"
            "      - {erreur: Oublier les parenthèses autour de $b$., explication: \"$(-3)^2 = 9$.\"}\n"
            "    questions:",
        )
        contenu(tmp_path, methode, question(1))
        [(_, fichier)] = charger(tmp_path, codes_attendus={"TEST-1RE-SD-01"})
        assert fichier.competences[0].methodes[0].exemple.resultat == "$-1$ et $1$"


class TestMatrice:
    def _couverture(self, tmp_path, questions: str):
        r = programmes.charger(referentiel(tmp_path / "ref"))
        fichiers = charger(contenu(tmp_path / "contenu", COMPETENCE, questions), codes_attendus=set(r.attendus))
        return r, fichiers, {l.attendu.code: l for l in matrice.couverture(r, fichiers, "TEST-1RE")}

    def test_statuts(self, tmp_path):
        _, _, lignes = self._couverture(tmp_path, question(1) + question(2, 2))
        assert lignes["TEST-1RE-SD-01"].statut == matrice.PARTIEL  # 2 questions : pas encore évalué
        assert lignes["TEST-1RE-SD-02"].statut == matrice.ABSENT
        assert not lignes["TEST-1RE-SD-04"].attendu.obligatoire

    def test_evalue_puis_valide(self, tmp_path):
        valide = (
            "        auteur: R. Martin\n"
            "        validation: {statut: validee, par: M. Durand, le: 2026-11-02}\n"
            "        correction: {etapes: [On factorise.], resultat: 2}\n"
        )
        _, _, lignes = self._couverture(tmp_path, "".join(question(i, 1 + i % 3) for i in range(1, 6)))
        assert lignes["TEST-1RE-SD-01"].statut == matrice.EVALUE
        _, _, lignes = self._couverture(tmp_path / "b", "".join(question(i, 1 + i % 3, valide) for i in range(1, 6)))
        assert lignes["TEST-1RE-SD-01"].statut == matrice.VALIDE

    def test_demonstration_non_automatisee(self, tmp_path):
        r = programmes.charger(referentiel(tmp_path / "ref"))
        competence = COMPETENCE.replace("[TEST-1RE-SD-01]", "[TEST-1RE-SD-03]")
        fichiers = charger(contenu(tmp_path / "contenu", competence, question(1)), codes_attendus=set(r.attendus))
        [ligne] = [l for l in matrice.couverture(r, fichiers, "TEST-1RE") if l.attendu.code == "TEST-1RE-SD-03"]
        assert ligne.statut == matrice.NON_AUTOMATISE

    def test_markdown_et_ecarts(self, tmp_path):
        r, fichiers, _ = self._couverture(tmp_path, question(1))
        texte = matrice.en_markdown(r, fichiers, "TEST-1RE", date(2026, 10, 31))
        assert "| ◐ | `TEST-1RE-SD-01`" in texte and "Attendus saisis : **4**, dont 3 obligatoires" in texte
        rapport = matrice.ecarts(r, fichiers, "TEST-1RE")
        assert "TEST-1RE-SD-02" in rapport and "Approfondissements non traités (facultatifs) : TEST-1RE-SD-04" in rapport
