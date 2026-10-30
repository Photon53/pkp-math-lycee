"""Dépendances FastAPI : qui fait la requête ?"""

import hmac
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import models
from app.db.session import get_session
from app.referentiel import Role
from app.security import lire_jeton, version_mot_de_passe

ELEVE, ENSEIGNANT, ADMIN = "eleve", "enseignant", "admin"

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
    # Refusé si : jeton invalide, élève supprimé (purge RGPD), code personnel
    # régénéré par l'enseignant depuis l'émission du jeton, ou enseignant désactivé.
    if (
        not eleve
        or eleve.code_hash is None
        or not hmac.compare_digest(lu[1], version_mot_de_passe(eleve.code_hash))
        or not eleve.classe.enseignant.actif
    ):
        raise _non_authentifie()
    return eleve


def _compte(identifiants: Identifiants, session: Session, role_jeton: str) -> models.Enseignant:
    lu = identifiants and lire_jeton(identifiants.credentials, role_jeton)
    enseignant = lu and session.get(models.Enseignant, lu[0])
    # Jeton émis avant le dernier changement de mot de passe : refusé (audit A-09).
    if (
        not enseignant
        or not enseignant.actif
        or not hmac.compare_digest(lu[1], version_mot_de_passe(enseignant.mot_de_passe_hash))
    ):
        raise _non_authentifie()
    return enseignant


def enseignant_authentifie(identifiants: Identifiants, session: SessionDB) -> models.Enseignant:
    """Connecté, même avec un mot de passe provisoire : seul le changement de mot de passe l'accepte."""
    return _compte(identifiants, session, ENSEIGNANT)


def enseignant_courant(identifiants: Identifiants, session: SessionDB) -> models.Enseignant:
    enseignant = _compte(identifiants, session, ENSEIGNANT)
    if enseignant.mdp_provisoire:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Choisissez d'abord un nouveau mot de passe.")
    return enseignant


def admin_courant(identifiants: Identifiants, session: SessionDB) -> models.Enseignant:
    # Jeton « admin » distinct (30 min, second facteur) ; le rôle est revérifié en base à chaque requête.
    admin = _compte(identifiants, session, ADMIN)
    if admin.role != Role.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Réservé aux administrateurs.")
    return admin


EleveCourant = Annotated[models.Eleve, Depends(eleve_courant)]
EnseignantCourant = Annotated[models.Enseignant, Depends(enseignant_courant)]
EnseignantAuthentifie = Annotated[models.Enseignant, Depends(enseignant_authentifie)]
AdminCourant = Annotated[models.Enseignant, Depends(admin_courant)]
