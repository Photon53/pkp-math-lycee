from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from app.db.models import Base
from app.db.session import creer_moteur
from tests.conftest import config_alembic

TABLES = {
    "lecon_version", "journal_admin", "seance_competence", "ressource", "ressource_classe", "ressource_consultation", "domaine_interdit",
    "enseignant", "classe", "eleve", "chapitre", "competence", "lecon", "question", "seance", "reponse",
    "classe_chapitre", "seance_chapitre",
}


def test_upgrade_cree_toutes_les_tables(db_url):
    moteur = creer_moteur(db_url)
    assert set(inspect(moteur).get_table_names()) == TABLES | {"alembic_version"}
    moteur.dispose()


def test_migrations_a_jour_avec_les_modeles(db_url):
    """Échoue si un modèle a changé sans nouvelle migration (`alembic revision --autogenerate`)."""
    moteur = creer_moteur(db_url)
    with moteur.connect() as connexion:
        differences = compare_metadata(MigrationContext.configure(connexion), Base.metadata)
    moteur.dispose()
    assert differences == []


def test_migration_conserve_les_donnees(tmp_path):
    """Régression : sur SQLite, la 0002 recrée `seance` ; avec les clés étrangères
    actives, cela vidait `reponse` par ON DELETE CASCADE."""
    url = f"sqlite:///{tmp_path / 'ancienne.db'}"
    config = config_alembic(url)
    command.upgrade(config, "0001")
    moteur = creer_moteur(url)
    with moteur.begin() as c:
        for sql in [
            "insert into enseignant values (1, 'E', 'e@x.test', 'h')",
            "insert into classe values (1, 'C1', '2nde', 1)",
            "insert into eleve values (1, 'Lina', 1)",
            "insert into chapitre values (1, '2nde', 'T', 1)",
            "insert into competence values (1, 1, 'C', 'L')",
            "insert into question values (1, 1, '?', 'qcm', 'A', 1, 0, '2026-01-01')",
            "insert into seance values (1, 1, '2026-01-01', null)",
            "insert into reponse values (1, 1, 1, 'A', 1, 3.0, '2026-01-01')",
        ]:
            c.exec_driver_sql(sql)
    command.upgrade(config, "head")  # 0002 recrée `seance`, 0003 recrée `eleve`
    with moteur.connect() as c:
        assert c.exec_driver_sql("select count(*) from reponse").scalar() == 1
        assert c.exec_driver_sql("select count(*) from seance").scalar() == 1
        assert c.exec_driver_sql("select cree_le from eleve").scalar() is not None
        # 0007 : les classes existantes reçoivent tout le programme de leur niveau et parcours.
        assert c.exec_driver_sql("select classe_id, chapitre_id from classe_chapitre").all() == [(1, 1)]
    moteur.dispose()


def test_downgrade_puis_upgrade(db_url):
    config = config_alembic(db_url)
    command.downgrade(config, "base")
    moteur = creer_moteur(db_url)
    assert set(inspect(moteur).get_table_names()) == {"alembic_version"}
    moteur.dispose()
    command.upgrade(config, "head")
