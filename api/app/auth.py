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
# Jeton distinct : un élève d'anglais n'ouvre jamais l'espace de maths, et inversement.
ELEVE_ANGLAIS = "eleve_anglais"
PARENT = "parent"

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


def eleve_anglais_courant(identifiants: Identifiants, session: SessionDB) -> models.EleveAnglais:
    lu = identifiants and lire_jeton(identifiants.credentials, ELEVE_ANGLAIS)
    eleve = lu and session.get(models.EleveAnglais, lu[0])
    # Mêmes refus que l'élève de maths : supprimé, code régénéré depuis l'émission, professeur désactivé.
    if (
        not eleve
        or eleve.code_hash is None
        or not hmac.compare_digest(lu[1], version_mot_de_passe(eleve.code_hash))
        or not eleve.groupe.enseignant.actif
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


def _enseignant_pret(identifiants: Identifiants, session: Session) -> models.Enseignant:
    enseignant = _compte(identifiants, session, ENSEIGNANT)
    if enseignant.mdp_provisoire:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Choisissez d'abord un nouveau mot de passe.")
    return enseignant


def enseignant_courant(identifiants: Identifiants, session: SessionDB) -> models.Enseignant:
    """Espace professeur de mathématiques : la discipline est revérifiée en base à chaque requête."""
    enseignant = _enseignant_pret(identifiants, session)
    if not enseignant.enseigne_maths:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Réservé aux professeurs de mathématiques.")
    return enseignant


def enseignant_anglais(identifiants: Identifiants, session: SessionDB) -> models.Enseignant:
    """Espace PKP Anglais : séances, déroulés et corrigés réservés aux professeurs d'anglais."""
    enseignant = _enseignant_pret(identifiants, session)
    if not enseignant.enseigne_anglais:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Réservé aux professeurs d'anglais.")
    return enseignant


def admin_courant(identifiants: Identifiants, session: SessionDB) -> models.Enseignant:
    # Jeton « admin » distinct (30 min, second facteur) ; le rôle est revérifié en base à chaque requête.
    admin = _compte(identifiants, session, ADMIN)
    if admin.role != Role.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Réservé aux administrateurs.")
    return admin


def _parent(identifiants: Identifiants, session: Session) -> models.Parent:
    lu = identifiants and lire_jeton(identifiants.credentials, PARENT)
    parent = lu and session.get(models.Parent, lu[0])
    # Refusé si : compte supprimé (plus d'enfant rattaché) ou mot de passe changé / réinitialisé depuis l'émission.
    if not parent or not hmac.compare_digest(lu[1], version_mot_de_passe(parent.mot_de_passe_hash)):
        raise _non_authentifie()
    return parent


def parent_authentifie(identifiants: Identifiants, session: SessionDB) -> models.Parent:
    """Connecté, même avec un mot de passe provisoire : seul le changement de mot de passe l'accepte."""
    return _parent(identifiants, session)


def parent_courant(identifiants: Identifiants, session: SessionDB) -> models.Parent:
    parent = _parent(identifiants, session)
    if parent.mdp_provisoire:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Choisissez d'abord un nouveau mot de passe.")
    return parent


EleveCourant = Annotated[models.Eleve, Depends(eleve_courant)]
EleveAnglaisCourant = Annotated[models.EleveAnglais, Depends(eleve_anglais_courant)]
EnseignantCourant = Annotated[models.Enseignant, Depends(enseignant_courant)]
EnseignantAnglais = Annotated[models.Enseignant, Depends(enseignant_anglais)]
EnseignantAuthentifie = Annotated[models.Enseignant, Depends(enseignant_authentifie)]
AdminCourant = Annotated[models.Enseignant, Depends(admin_courant)]
ParentCourant = Annotated[models.Parent, Depends(parent_courant)]
ParentAuthentifie = Annotated[models.Parent, Depends(parent_authentifie)]
