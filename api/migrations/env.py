from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from app.config import settings
from app.db.models import Base

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)

url = config.get_main_option("sqlalchemy.url") or settings.database_url


def run_migrations_offline() -> None:
    context.configure(
        url=url,
        target_metadata=Base.metadata,
        literal_binds=True,
        render_as_batch=url.startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Moteur SANS l'activation des clés étrangères de creer_moteur : sur SQLite, le mode
    # batch recrée les tables, et un DROP TABLE avec foreign_keys=ON déclencherait les
    # ON DELETE CASCADE (une migration de `seance` viderait `reponse`).
    # Test : test_migrations.py::test_migration_conserve_les_donnees.
    with create_engine(url).connect() as connexion:
        context.configure(
            connection=connexion,
            target_metadata=Base.metadata,
            # SQLite ne sait pas modifier une table : Alembic la recrée (mode batch).
            render_as_batch=connexion.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
