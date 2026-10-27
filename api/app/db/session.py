from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings


def creer_moteur(url: str | None = None) -> Engine:
    moteur = create_engine(url or settings.database_url)
    if moteur.dialect.name == "sqlite":
        # SQLite n'applique les clés étrangères (CASCADE, RESTRICT) que sur demande.
        @event.listens_for(moteur, "connect")
        def _activer_cles_etrangeres(connexion, _):
            curseur = connexion.cursor()
            curseur.execute("PRAGMA foreign_keys=ON")
            curseur.close()

    return moteur


moteur = creer_moteur()
SessionLocale = sessionmaker(bind=moteur, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """Dépendance FastAPI : une session par requête."""
    with SessionLocale() as session:
        yield session
