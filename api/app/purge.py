"""Purge RGPD : supprime les élèves sans activité depuis `PKP_RETENTION_JOURS`.

Les comptes parents qui ne suivent plus aucun enfant sont supprimés en même temps.

Les archives d'inscriptions et les remarques plus anciennes que la durée de conservation sont supprimées aussi.

« Accueil et demandes » (issues #172, #171) : demandes supprimées, CV compris, après la durée de leur file
(`PKP_ACCUEIL_CONSERVATION_JOURS`) sans traitement, puis contacts sans demande ; sans durée décidée (RGPD-3 en
attente), rien n'est supprimé dans la file.

Rédactions (issue #179, RGPD-2) : supprimées après le 31 août de leur année scolaire, et 30 jours après
l'archivage de la classe de l'élève (fin de l'accompagnement), quelle que soit `PKP_RETENTION_JOURS`.
Activité = début de la dernière séance, ou date de création si l'élève n'a
jamais commencé de séance. Séances et réponses partent en cascade.

Usage, depuis `api/` :
    python -m app.purge --simulation   # liste sans rien supprimer
    python -m app.purge                # supprime
"""

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import DateTime, delete, func, select
from sqlalchemy.orm import Session

from app import accueil, inscriptions, parents
from app import simulation as eleves_fictifs
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
            a_supprimer = session.get(models.Eleve, eleve.id)
            inscriptions.delier(session, a_supprimer)  # le numéro de groupe reste celui d'un élève existant
            session.delete(a_supprimer)
        # Les archives d'inscriptions (V3) ont la même durée de conservation, comptée depuis leur archivage.
        session.execute(delete(models.ArchiveInscription).where(models.ArchiveInscription.archivee_le < limite))
        # Remarques et suggestions (ticket #30) : même durée, comptée depuis leur dernier traitement.
        session.execute(delete(models.Remarque).where(models.Remarque.maj_le < limite))
        purger_redactions(session, maintenant or datetime.now(UTC))
        # Élèves fictifs de simulation (issue #184) : invisibles de `eleves_inactifs`, purgés à part.
        eleves_fictifs.purger(session, maintenant)
        # Les comptes parents qui ne suivent plus aucun enfant partent avec le dernier.
        parents.supprimer_orphelins(session)
        session.commit()
        # « Accueil et demandes » (#172), file par file ; après la validation : les CV ne partent qu'avec leur demande.
        accueil.purger(session, maintenant)
    return inactifs


def purger_redactions(session: Session, maintenant: datetime) -> int:
    """Rédactions échues (31 août passé) ou d'élèves dont la classe est archivée depuis plus de 30 jours."""
    fin_accompagnement = maintenant - timedelta(days=JOURS_APRES_DEPART)
    eleves_partis = select(models.Eleve.id).join(models.Classe).where(models.Classe.archivee_le < fin_accompagnement)
    resultat = session.execute(delete(models.Redaction).where(
        (models.Redaction.conserver_jusqu_au < maintenant.date()) | models.Redaction.eleve_id.in_(eleves_partis)
    ))
    # Issue #217 : réponses rédigées aux dossiers de français, mêmes règles (RGPD-2).
    francais = session.execute(delete(models.ReponseRedigeeFrancais).where(
        (models.ReponseRedigeeFrancais.conserver_jusqu_au < maintenant.date())
        | models.ReponseRedigeeFrancais.eleve_id.in_(eleves_partis)
    ))
    return (resultat.rowcount or 0) + (francais.rowcount or 0)


JOURS_APRES_DEPART = 30


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
