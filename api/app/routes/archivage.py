"""Archivage des classes et des groupes en fin d'année (V3, Lot 3), réservé à l'administrateur.

Une classe ou un groupe archivé sort des listes actives : plus de séance, plus d'inscription, plus d'accès
pour le professeur. Rien n'est supprimé : inscriptions, séances, réponses et progression restent en base,
visibles sur la fiche de l'élève, et le rétablissement remet tout en service. La suppression définitive
reste réservée au droit à l'effacement.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app import archives, journal
from app.auth import AdminCourant, SessionDB
from app.db import models
from app.routes.anglais import groupes_actifs
from app.routes.masse import ResultatMasse
from app.schemas_admin import ArchivageClasses

router = APIRouter(prefix="/admin", tags=["administration"])


def _trouver(session: SessionDB, modele, ids: list[int], nom: str) -> list:
    trouves = session.scalars(select(modele).where(modele.id.in_(ids))).all()
    if len(trouves) != len(set(ids)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{nom} introuvable.")
    return list(trouves)


def _regler(session: SessionDB, admin: models.Enseignant, objets: list, corps: ArchivageClasses, objet: str) -> ResultatMasse:
    changes = [o for o in objets if (o.archivee_le is None) == corps.archiver]
    maintenant = datetime.now(UTC)
    for o in changes:
        if corps.archiver:
            o.archivee_le, o.archivee_par, o.motif_archivage = maintenant, archives.par_admin(admin), corps.motif.strip() or None
        else:
            o.archivee_le = o.archivee_par = o.motif_archivage = None
    if changes:
        journal.noter(session, admin, "archiver" if corps.archiver else "retablir", objet, None,
                      apres={"ids": [o.id for o in changes], "motif": corps.motif.strip() or None})
    session.commit()
    return ResultatMasse(traites=len(changes))


@router.post("/classes/archivage", response_model=ResultatMasse)
def archiver_classes(corps: ArchivageClasses, admin: AdminCourant, session: SessionDB) -> ResultatMasse:
    """Archive (ou rétablit) des classes de maths. Déjà dans l'état demandé : ignorées."""
    return _regler(session, admin, _trouver(session, models.Classe, corps.ids, "Classe"), corps, "classe")


@router.post("/anglais/groupes/archivage", response_model=ResultatMasse)
def archiver_groupes(corps: ArchivageClasses, admin: AdminCourant, session: SessionDB) -> ResultatMasse:
    """Archive (ou rétablit) des groupes d'anglais. Rétablir un groupe dont le nom est repris entre-temps
    par un groupe actif du même professeur est refusé : renommez l'un des deux d'abord."""
    groupes = _trouver(session, models.GroupeAnglais, corps.ids, "Groupe")
    if not corps.archiver:
        for g in groupes:
            if g.archivee_le is not None and any(
                a.id != g.id and a.nom.lower() == g.nom.lower() for a in groupes_actifs(g.enseignant)
            ):
                raise HTTPException(status.HTTP_409_CONFLICT,
                                    f"{g.enseignant.nom} a déjà un groupe actif « {g.nom} » : renommez-le avant de rétablir celui-ci.")
    return _regler(session, admin, groupes, corps, "groupe_anglais")
