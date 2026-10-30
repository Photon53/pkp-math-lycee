"""Ouverture d'une ressource (PDF servi après contrôle des droits, ou lien compté)."""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse, Response

from app import ressources
from app.auth import ADMIN, ELEVE, ENSEIGNANT, Identifiants, SessionDB, admin_courant, eleve_courant, enseignant_courant
from app.db import models
from app.security import lire_jeton

router = APIRouter(prefix="/ressources", tags=["ressources"])


def _ressource_autorisee(ressource_id: int, identifiants: Identifiants, session: SessionDB) -> models.Ressource:
    """Le même PDF s'ouvre depuis les trois espaces : on reconnaît le rôle du jeton."""
    r = session.get(models.Ressource, ressource_id)
    jeton = identifiants.credentials if identifiants else ""
    if lire_jeton(jeton, ADMIN):
        admin_courant(identifiants, session)
        autorise = r is not None
    elif lire_jeton(jeton, ENSEIGNANT):
        enseignant = enseignant_courant(identifiants, session)
        autorise = r is not None and ressources.visible_par_enseignant(r, enseignant)
    elif lire_jeton(jeton, ELEVE):
        eleve = eleve_courant(identifiants, session)
        autorise = r is not None and ressources.visible_par_eleve(r, eleve)
    else:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentification requise.", headers={"WWW-Authenticate": "Bearer"})
    # 404 et non 403 : on ne révèle pas l'existence des ressources des autres.
    if not autorise:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ressource introuvable.")
    return r


@router.get("/{ressource_id}/fichier")
def fichier(ressource_id: int, identifiants: Identifiants, session: SessionDB) -> FileResponse:
    r = _ressource_autorisee(ressource_id, identifiants, session)
    chemin = ressources.chemin_pdf(r)
    ressources.compter_consultation(session, r)
    return FileResponse(
        chemin,
        media_type="application/pdf",
        headers={"Content-Disposition": "inline", "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.post("/{ressource_id}/ouverture", status_code=status.HTTP_204_NO_CONTENT)
def ouverture(ressource_id: int, identifiants: Identifiants, session: SessionDB) -> Response:
    """Compte l'ouverture d'un lien externe (l'interface l'appelle avant d'ouvrir le site)."""
    ressources.compter_consultation(session, _ressource_autorisee(ressource_id, identifiants, session))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
