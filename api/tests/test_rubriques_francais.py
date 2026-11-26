"""Rubriques des chapitres de français (issue #177) : conjugaison, grammaire, redaction, mon_cours ; obligatoires en
français, interdites en maths, filtrables sur tous les niveaux à la fois."""
# Issue #177 — Rubriques de l'espace Français (Claude)

import pytest
from sqlalchemy import select

from app.contenu import charger, importer
from app.db import models
from app.referentiel import RubriqueFrancais
from tests.conftest import connecter_admin, connecter_enseignant
from tests.test_classes_pilotes import _classe_pilote, _preparer
from tests.test_contenu import ecrire, erreurs


def _chapitre_fr(code: str, niveau: str, rubrique: str | None, ordre: int = 2) -> str:
    champ = f"rubrique: {rubrique}, " if rubrique else ""
    return f"""
chapitre: {{code: {code}, matiere: francais, {champ}niveau: {niveau}, parcours: tronc-commun, ordre: {ordre}, titre: Chapitre {code}}}
competences:
  - code: {code}-C
    libelle: Compétence {code}
    questions:
      - {{code: {code}-C-01, difficulte: 1, type: qcm, enonce: "Choisir. A) un B) deux", solution: A}}
"""


def test_rubrique_obligatoire_en_francais_et_interdite_en_maths(tmp_path):
    ecrire(tmp_path, _chapitre_fr("FR6-SANS", "6e", None), "francais/6e/tronc-commun/02-sans.yaml")
    assert "`rubrique` obligatoire pour un chapitre de français" in erreurs(tmp_path)

    autre = tmp_path / "inconnue"
    ecrire(autre, _chapitre_fr("FR6-X", "6e", "lecture"), "francais/6e/tronc-commun/02-x.yaml")
    assert "rubrique" in erreurs(autre)

    maths = tmp_path / "maths"
    ecrire(maths, """
chapitre: {code: M2-RUB, rubrique: grammaire, niveau: 2nde, parcours: tronc-commun, ordre: 7, titre: Test}
competences:
  - code: M2-RUB-C
    libelle: Test
    questions:
      - {code: M2-RUB-01, difficulte: 1, type: numerique, enonce: "1+1 ?", solution: "2"}
""")
    assert "`rubrique` ne concerne que les chapitres de français" in erreurs(maths)


def test_import_puis_changement_de_rubrique(session, tmp_path):
    ecrire(tmp_path, _chapitre_fr("FR6-RUB", "6e", "conjugaison"), "francais/6e/tronc-commun/02-rub.yaml")
    importer(session, charger(tmp_path), archiver_absentes=False)
    session.commit()
    chapitre = session.scalar(select(models.Chapitre).where(models.Chapitre.code == "FR6-RUB"))
    assert chapitre.rubrique is RubriqueFrancais.CONJUGAISON
    ecrire(tmp_path, _chapitre_fr("FR6-RUB", "6e", "grammaire"), "francais/6e/tronc-commun/02-rub.yaml")
    rapport = importer(session, charger(tmp_path), archiver_absentes=False)
    session.commit()
    session.refresh(chapitre)
    assert chapitre.rubrique is RubriqueFrancais.GRAMMAIRE and rapport.modifies["chapitres"] == 1


def test_filtre_par_rubrique_sur_tous_les_niveaux(client, session, tmp_path):
    """Un adulte consulte la conjugaison de la 6e à la 3e sans changer de niveau ; les maths ne sont pas mêlées."""
    for code, niveau, rubrique, chemin in (
        ("FR6-CONJ", "6e", "conjugaison", "francais/6e/tronc-commun/02-conj.yaml"),
        ("FR3-CONJ", "3e", "conjugaison", "francais/3e/tronc-commun/02-conj.yaml"),
        ("FR6-GRAM", "6e", "grammaire", "francais/6e/tronc-commun/03-gram.yaml"),
    ):
        ecrire(tmp_path, _chapitre_fr(code, niveau, rubrique, ordre=3 if code.endswith("GRAM") else 2), chemin)
    importer(session, charger(tmp_path), archiver_absentes=False)
    session.commit()
    for h in (connecter_enseignant(client), connecter_admin(client)):
        conjugaison = client.get("/pkp-math/catalogue?rubrique=conjugaison", headers=h).json()
        assert {c["code"] for c in conjugaison} == {"FR6-CONJ", "FR3-CONJ"}
        assert all(c["rubrique"] == "conjugaison" for c in conjugaison)
        tout = client.get("/pkp-math/catalogue", headers=h).json()
        assert {c["rubrique"] for c in tout} == {None, "conjugaison", "grammaire"}
        doc = client.get(f"/pkp-math/chapitres/{conjugaison[0]['id']}", headers=h).json()
        assert doc["rubrique"] == "conjugaison"
        assert client.get("/pkp-math/catalogue?rubrique=lecture", headers=h).status_code == 422


def test_rubrique_visible_par_l_eleve_et_le_professeur(client, pilote_rubrique):
    h, classe = pilote_rubrique
    assert [c["rubrique"] for c in client.get("/eleves/moi/chapitres", headers=h).json()] == ["conjugaison"]
    assert [c["rubrique"] for c in client.get("/cours", headers=h).json()] == ["conjugaison"]
    programme = client.get(f"/enseignants/classes/{classe}/chapitres", headers=connecter_enseignant(client)).json()
    assert [c["rubrique"] for c in programme] == ["conjugaison"]



@pytest.fixture
def pilote_rubrique(client, session, tmp_path):
    ctx = _preparer(client, session, tmp_path)
    classe, h = _classe_pilote(client, ctx, "Lina")
    return h, classe


def test_migration_0043_sur_une_base_avec_des_chapitres_de_francais(tmp_path):
    """Relecture de la PR #185 : une base déjà peuplée de chapitres de français (0042) migre en 0043 sans perte ;
    leurs rubriques restent vides jusqu'au réimport, qui exige désormais le champ puis le renseigne sans doublon."""
    from alembic import command
    from sqlalchemy.orm import sessionmaker

    from app.contenu import ContenuInvalide
    from app.db.session import creer_moteur
    from tests.conftest import config_alembic

    url = f"sqlite:///{tmp_path / 'avant-0043.db'}"
    config = config_alembic(url)
    command.upgrade(config, "0042")
    moteur = creer_moteur(url)
    with moteur.begin() as c:
        c.exec_driver_sql(
            "insert into chapitre (code, niveau, parcours, titre, ordre, masque, domaine_code, nature)"
            " values ('FR5-ANCIEN', '5e', 'tronc-commun', 'Ancien chapitre', 1, 0, 'francais-college', 'apprentissage')"
        )
        chapitre = c.exec_driver_sql("select id from chapitre where code = 'FR5-ANCIEN'").scalar()
        c.exec_driver_sql(
            "insert into competence (chapitre_id, code, libelle, ordre, masque) values (?, 'FR5-ANCIEN-C', 'Ancienne', 1, 0)",
            (chapitre,),
        )
    command.upgrade(config, "0043")
    with moteur.connect() as c:
        assert c.exec_driver_sql("select id, rubrique from chapitre where code = 'FR5-ANCIEN'").one() == (chapitre, None)
        assert c.exec_driver_sql("select count(*) from competence where chapitre_id = ?", (chapitre,)).scalar() == 1

    # Réimport de l'ancien fichier, sans rubrique : refusé, rien ne change.
    ancien = _chapitre_fr("FR5-ANCIEN", "5e", None, ordre=1).replace("Chapitre FR5-ANCIEN", "Ancien chapitre")
    ecrire(tmp_path / "v1", ancien, "francais/5e/tronc-commun/01-ancien.yaml")
    with pytest.raises(ContenuInvalide, match="`rubrique` obligatoire"):
        charger(tmp_path / "v1")
    # Avec la rubrique : même chapitre (pas de doublon), rubrique renseignée.
    ecrire(tmp_path / "v2", ancien.replace("matiere: francais, ", "matiere: francais, rubrique: grammaire, "),
           "francais/5e/tronc-commun/01-ancien.yaml")
    with sessionmaker(bind=moteur)() as session:
        importer(session, charger(tmp_path / "v2"), archiver_absentes=False)
        session.commit()
        lignes = session.execute(select(models.Chapitre.id, models.Chapitre.rubrique).where(models.Chapitre.code == "FR5-ANCIEN")).all()
    assert lignes == [(chapitre, RubriqueFrancais.GRAMMAIRE)]
    # Retour en 0042 : la colonne disparaît, le chapitre et sa compétence restent.
    command.downgrade(config, "0042")
    with moteur.connect() as c:
        assert c.exec_driver_sql("select count(*) from chapitre where code = 'FR5-ANCIEN'").scalar() == 1
        assert c.exec_driver_sql("select count(*) from competence where chapitre_id = ?", (chapitre,)).scalar() >= 1
    moteur.dispose()
