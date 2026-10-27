"""Dépendances FastAPI : qui fait la requête ?"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import models
from app.db.session import get_session
from app.security import lire_jeton

ELEVE, ENSEIGNANT = "eleve", "enseignant"

_bearer = HTTPBearer(auto_error=False)

SessionDB = Annotated[Session, Depends(get_session)]
Identifiants = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]


def _non_authentifie() -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Authentification requise.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def eleve_courant(identifiants: Identifiants, session: SessionDB) -> models.Eleve:
    sujet = identifiants and lire_jeton(identifiants.credentials, ELEVE)
    eleve = sujet and session.get(models.Eleve, sujet)
    if not eleve:  # jeton invalide, ou élève supprimé depuis (purge RGPD)
        raise _non_authentifie()
    return eleve


def enseignant_courant(identifiants: Identifiants, session: SessionDB) -> models.Enseignant:
    sujet = identifiants and lire_jeton(identifiants.credentials, ENSEIGNANT)
    enseignant = sujet and session.get(models.Enseignant, sujet)
    if not enseignant:
        raise _non_authentifie()
    return enseignant


EleveCourant = Annotated[models.Eleve, Depends(eleve_courant)]
EnseignantCourant = Annotated[models.Enseignant, Depends(enseignant_courant)]
