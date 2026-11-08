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
# Carte d'un enfant de famille : il choisit ensuite sa matière, qui lui donne un jeton élève ou anglais.
ENFANT = "enfant"

_bearer = HTTPBearer(auto_error=False)

# Compte suspendu temporairement par l'administrateur : refusé à la connexion (403, avec ce message) et pour
# toute session déjà ouverte (401 : retour à la page de connexion).
CARTE_BLOQUEE = "Ton compte est suspendu pour le moment : parles-en à ton professeur."
CLASSE_ARCHIVEE = "Cette classe est terminée : elle a été archivée par l'établissement."
COMPTE_PARENT_BLOQUE = "Votre compte est suspendu temporairement : contactez l'établissement."


def carte_bloquee(inscription: models.Eleve | models.EleveAnglais | models.Enfant) -> bool:
    enfant = inscription if isinstance(inscription, models.Enfant) else inscription.enfant
    return enfant is not None and enfant.bloque_le is not None

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
        or eleve.classe.archivee_le is not None
        or carte_bloquee(eleve)
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
        or eleve.groupe.archivee_le is not None
        or carte_bloquee(eleve)
    ):
        raise _non_authentifie()
    return eleve


def enfant_courant(identifiants: Identifiants, session: SessionDB) -> models.Enfant:
    lu = identifiants and lire_jeton(identifiants.credentials, ENFANT)
    enfant = lu and session.get(models.Enfant, lu[0])
    # Refusé si : enfant supprimé, ou code changé (par le parent ou l'administrateur) depuis l'émission.
    if (
        not enfant
        or enfant.code_hash is None
        or not hmac.compare_digest(lu[1], version_mot_de_passe(enfant.code_hash))
        or carte_bloquee(enfant)
    ):
        raise _non_authentifie()
    return enfant


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
    """Espace des classes (maths, et français depuis F1) : la discipline est revérifiée en base à chaque requête."""
    from app import permissions

    enseignant = _enseignant_pret(identifiants, session)
    if not (enseignant.enseigne_maths or permissions.enseigne_francais(enseignant)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Réservé aux professeurs de mathématiques ou de français.")
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
    if (
        not parent
        or not hmac.compare_digest(lu[1], version_mot_de_passe(parent.mot_de_passe_hash))
        or parent.bloque_le is not None
    ):
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
EnfantCourant = Annotated[models.Enfant, Depends(enfant_courant)]
EleveAnglaisCourant = Annotated[models.EleveAnglais, Depends(eleve_anglais_courant)]
EnseignantCourant = Annotated[models.Enseignant, Depends(enseignant_courant)]
EnseignantAnglais = Annotated[models.Enseignant, Depends(enseignant_anglais)]
EnseignantAuthentifie = Annotated[models.Enseignant, Depends(enseignant_authentifie)]
AdminCourant = Annotated[models.Enseignant, Depends(admin_courant)]
ParentCourant = Annotated[models.Parent, Depends(parent_courant)]
ParentAuthentifie = Annotated[models.Parent, Depends(parent_authentifie)]


def filtre_domaine(domaine: str | None = None) -> str | None:
    """Filtre `?domaine=` des listes de l'admin (CDC V2, EA.2 et recette 5) : vide = tous les domaines."""
    from app import permissions

    if not domaine:
        return None
    if domaine not in permissions.LIBELLES:
        raise HTTPException(422, f"Domaine inconnu : {domaine}.")
    return domaine


FiltreDomaine = Annotated[str | None, Depends(filtre_domaine)]
