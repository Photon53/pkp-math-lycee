"""Purge RGPD : supprime les élèves sans activité depuis `PKP_RETENTION_JOURS`.

Activité = début de la dernière séance, ou date de création si l'élève n'a
jamais commencé de séance. Séances et réponses partent en cascade.

Usage, depuis `api/` :
    python -m app.purge --simulation   # liste sans rien supprimer
    python -m app.purge                # supprime
"""

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import DateTime, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import models


@dataclass(frozen=True)
class ElevePurge:
    id: int
    prenom: str
    code_classe: str
    derniere_activite: datetime


def eleves_inactifs(session: Session, limite: datetime) -> list[ElevePurge]:
    derniere_seance = (
        select(models.Seance.eleve_id, func.max(models.Seance.debut).label("debut"))
        .group_by(models.Seance.eleve_id)
        .subquery()
    )
    # type_ explicite : sinon SQLite renvoie une chaîne au lieu d'une date.
    activite = func.coalesce(derniere_seance.c.debut, models.Eleve.cree_le, type_=DateTime(timezone=True))
    lignes = session.execute(
        select(models.Eleve.id, models.Eleve.prenom, models.Classe.code, activite)
        .join(models.Classe)
        .outerjoin(derniere_seance, derniere_seance.c.eleve_id == models.Eleve.id)
        .where(activite < limite)
        .order_by(models.Classe.code, models.Eleve.prenom)
    )
    return [ElevePurge(*ligne) for ligne in lignes]


def purger(
    session: Session,
    *,
    retention_jours: int | None = None,
    maintenant: datetime | None = None,
    simulation: bool = False,
) -> list[ElevePurge]:
    retention = settings.retention_jours if retention_jours is None else retention_jours
    limite = (maintenant or datetime.now(UTC)) - timedelta(days=retention)
    inactifs = eleves_inactifs(session, limite)
    if not simulation:
        for eleve in inactifs:
            session.delete(session.get(models.Eleve, eleve.id))
        session.commit()
    return inactifs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--simulation", action="store_true", help="liste les élèves concernés sans les supprimer")
    args = parser.parse_args()

    from app.db.session import SessionLocale

    with SessionLocale() as session:
        inactifs = purger(session, simulation=args.simulation)
    verbe = "seraient supprimés" if args.simulation else "supprimés"
    print(f"{len(inactifs)} élève(s) sans activité depuis {settings.retention_jours} jours {verbe}.")
    for e in inactifs:
        print(f"  - {e.prenom} ({e.code_classe}), dernière activité {e.derniere_activite:%Y-%m-%d}")


if __name__ == "__main__":
    main()
