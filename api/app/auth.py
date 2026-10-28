"""Dépendances FastAPI : qui fait la requête ?"""

import hmac
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import models
from app.db.session import get_session
from app.security import lire_jeton, version_mot_de_passe

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
    lu = identifiants and lire_jeton(identifiants.credentials, ELEVE)
    eleve = lu and session.get(models.Eleve, lu[0])
    if not eleve:  # jeton invalide, ou élève supprimé depuis (purge RGPD)
        raise _non_authentifie()
    return eleve


def enseignant_courant(identifiants: Identifiants, session: SessionDB) -> models.Enseignant:
    lu = identifiants and lire_jeton(identifiants.credentials, ENSEIGNANT)
    enseignant = lu and session.get(models.Enseignant, lu[0])
    # Jeton émis avant le dernier changement de mot de passe : refusé (audit A-09).
    if not enseignant or not hmac.compare_digest(lu[1], version_mot_de_passe(enseignant.mot_de_passe_hash)):
        raise _non_authentifie()
    return enseignant


EleveCourant = Annotated[models.Eleve, Depends(eleve_courant)]
EnseignantCourant = Annotated[models.Enseignant, Depends(enseignant_courant)]
