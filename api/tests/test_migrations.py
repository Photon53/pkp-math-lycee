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
    "classe_chapitre", "seance_chapitre", "groupe_anglais", "eleve_anglais",
    "seance_anglais", "seance_anglais_version", "progression_anglais", "parent", "parent_eleve",
    "domaine_pedagogique", "habilitation", "rattachement_parent", "enfant", "parent_enfant", "archive_inscription", "demande_aide",
    "remarque",
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
        # 0027 : l'élève créé par le professeur devient un enfant du niveau de sa classe.
        enfant = c.exec_driver_sql("select id, prenom, niveau from enfant").one()
        assert enfant[1:] == ("Lina", "2nde")
        assert c.exec_driver_sql("select enfant_id from eleve").scalar() == enfant[0]
    moteur.dispose()


def test_eleves_relies_et_parents_rejoignent_un_seul_enfant(tmp_path):
    """0027 : deux inscriptions reliées (même élève, deux parcours) donnent un seul enfant, qui garde
    l'identifiant et le code de l'élève ; le parent rattaché suit l'enfant."""
    url = f"sqlite:///{tmp_path / 'familles.db'}"
    config = config_alembic(url)
    command.upgrade(config, "0026")
    moteur = creer_moteur(url)
    with moteur.begin() as c:
        c.exec_driver_sql("insert into enseignant (id, nom, email, mot_de_passe_hash) values (1, 'E', 'e@x.test', 'h')")
        for cid, code, parcours in [(1, "2NDE-TC-A", "tronc-commun"), (2, "2NDE-EXC-B", "excellence")]:
            c.exec_driver_sql(
                "insert into classe (id, code, niveau, parcours, enseignant_id, domaine_code) "
                f"values ({cid}, '{code}', '2nde', '{parcours}', 1, 'maths-lycee')"
            )
        c.exec_driver_sql("insert into eleve (id, prenom, classe_id, code_hash, identifiant, groupe_id) values (1, 'Lina', 1, 'h1', 'lina-k7m4', 1)")
        c.exec_driver_sql("insert into eleve (id, prenom, classe_id, code_hash, groupe_id) values (2, 'Lina', 2, 'h1', 1)")
        c.exec_driver_sql("insert into eleve (id, prenom, classe_id) values (3, 'Noé', 1)")
        c.exec_driver_sql("insert into parent (id, email, mot_de_passe_hash) values (1, 'p@x.test', 'h')")
        c.exec_driver_sql("insert into parent_eleve (parent_id, eleve_id) values (1, 2)")
    command.upgrade(config, "0027")
    with moteur.connect() as c:
        enfants = c.exec_driver_sql("select id, prenom, identifiant, code_hash from enfant order by id").all()
        assert [(e[1], e[3]) for e in enfants] == [("Lina", "h1"), ("Noé", None)]
        assert enfants[0][2] == "lina-k7m4" and enfants[1][2].startswith("noe-")
        assert c.exec_driver_sql("select enfant_id from eleve order by id").scalars().all() == [enfants[0][0]] * 2 + [enfants[1][0]]
        assert c.exec_driver_sql("select parent_id, enfant_id from parent_enfant").all() == [(1, enfants[0][0])]
    moteur.dispose()


def test_downgrade_puis_upgrade(db_url):
    config = config_alembic(db_url)
    command.downgrade(config, "base")
    moteur = creer_moteur(db_url)
    assert set(inspect(moteur).get_table_names()) == {"alembic_version"}
    moteur.dispose()
    command.upgrade(config, "head")


def test_retour_arriere_du_lot_0_v3(db_url):
    """Scripts retour-v3-lot0-*.sh : 0029 → 0028 retire seulement la table des archives, sans toucher au reste ;
    la remontée la recrée."""
    config = config_alembic(db_url)
    moteur = creer_moteur(db_url)
    with moteur.begin() as c:
        c.exec_driver_sql("insert into enfant (prenom, nom, niveau, identifiant) values ('Lina', '', '2nde', 'lina-test')")
        enfant = c.exec_driver_sql("select id from enfant").scalar()
        c.exec_driver_sql(
            "insert into archive_inscription (enfant_id, matiere, domaine_code, niveau, cours, enseignant, archivee_le,"
            " par, motif, resume, contenu) values (?, 'maths', 'maths-lycee', '2nde', '2NDE-X', 'Prof', '2026-11-05',"
            " 'Administrateur : A', 'classe supprimée', '{}', '{}')", (enfant,))
    moteur.dispose()
    command.downgrade(config, "0028")
    moteur = creer_moteur(db_url)
    # Revenir en 0028 retire aussi les tables des migrations suivantes.
    tables_recentes = {"archive_inscription", "demande_aide", "remarque"}
    assert set(inspect(moteur).get_table_names()) == (TABLES - tables_recentes) | {"alembic_version"}
    with moteur.connect() as c:
        assert c.exec_driver_sql("select identifiant from enfant").scalars().all() == ["lina-test"]
    moteur.dispose()
    command.upgrade(config, "head")
    moteur = creer_moteur(db_url)
    assert "archive_inscription" in inspect(moteur).get_table_names()
    moteur.dispose()
