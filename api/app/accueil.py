# Issue #172 — Accueil et demandes : contacts adultes et demandes (Claude)
"""« Accueil et demandes » : contacts adultes, demandes par file, rattachement prudent, conservation (issue #172).

Quatre files, une par finalité : familles et préinscriptions, informations et questions, candidatures de
professeurs, partenariats de structures. Les retours des utilisateurs déjà inscrits restent dans « Remarques »
(#30) : il n'y a pas de seconde boîte de réception pour eux.

Rattachement prudent : une demande rejoint un contact existant seulement si l'e-mail normalisé est **identique**
(minuscules, espaces retirés ; aucune ressemblance approchée). Ce rattachement ne donne aucun accès, ne relie aucun
enfant ni aucun compte, et n'écrase jamais les coordonnées du contact : celles saisies restent sur la demande.
Un administrateur peut détacher une demande rattachée à tort.

Conservation : une durée par file (`PKP_ACCUEIL_CONSERVATION_JOURS`), décidée par le propriétaire (RGPD-3). Sans
durée, la file ne collecte rien et la purge n'y touche pas. Un contact sans demande est supprimé.
"""

import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app import collaboration
from app.config import settings
from app.db import models
from app.schemas import _EMAIL, _PRENOM
from app.security import ALPHABET_CODE

CATEGORIES = ("famille", "information", "candidature", "partenariat")
LIBELLES = {
    "famille": "familles et préinscriptions",
    "information": "informations et questions",
    "candidature": "candidatures de professeurs",
    "partenariat": "partenariats de structures",
}
PREFIXES = {"famille": "F-", "information": "I-", "candidature": "C-", "partenariat": "P-"}
# Issue possible du traitement, par file : seule une demande de famille peut aboutir à une inscription effective.
ISSUES = {
    "famille": ("suite-demandee", "inscription-effective", "refus", "cloture"),
    "information": ("suite-demandee", "cloture"),
    "candidature": ("suite-demandee", "refus", "cloture"),
    "partenariat": ("suite-demandee", "refus", "cloture"),
}


def nettoyer(v):
    return v.strip() if isinstance(v, str) else v


class CoordonneesAdulte(BaseModel):
    """Coordonnées d'un adulte, communes à toutes les files : prénom, nom, e-mail, téléphone facultatif."""

    prenom: Annotated[str, Field(min_length=1, max_length=60)]
    nom: Annotated[str, Field(min_length=1, max_length=80)]
    email: Annotated[str, Field(min_length=5, max_length=254)]
    telephone: Annotated[str, Field(max_length=30, pattern=r"^[0-9+ ().-]*$")] | None = None

    _nettoyage = field_validator("prenom", "nom", "telephone", mode="before")(nettoyer)

    @field_validator("prenom", "nom")
    @classmethod
    def _lettres(cls, v: str) -> str:
        v = " ".join(v.split())
        if not _PRENOM.match(v):
            raise ValueError("Prénom et nom : lettres, espaces, tirets et apostrophes seulement.")
        return v

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = normaliser_email(v)
        if not _EMAIL.match(v):
            raise ValueError("Adresse e-mail invalide.")
        return v


def maintenant() -> datetime:
    return datetime.now(UTC)


def utc(d: datetime) -> datetime:
    """SQLite rend des dates sans fuseau : elles sont en UTC."""
    return d.replace(tzinfo=UTC) if d.tzinfo is None else d


def normaliser_email(email: str) -> str:
    return "".join(email.split()).lower()


def conservation(categorie: str) -> int | None:
    return settings.accueil_conservation_jours.get(categorie)


def exiger_conservation(categorie: str) -> None:
    """Aucune donnée n'entre dans une file dont la durée de conservation n'est pas décidée."""
    if not conservation(categorie):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"La durée de conservation des {LIBELLES[categorie]} n'est pas encore fixée : aucune demande ne peut être enregistrée.",
        )


def nouvelle_reference(session: Session, categorie: str) -> str:
    while True:
        reference = PREFIXES[categorie] + "".join(secrets.choice(ALPHABET_CODE) for _ in range(8))
        if session.scalar(select(models.DemandeAccueil.id).where(models.DemandeAccueil.reference == reference)) is None:
            return reference


def contact_pour(session: Session, prenom: str, nom: str, email: str, telephone: str | None) -> models.ContactAdulte:
    """Contact à l'e-mail normalisé identique, sinon un nouveau. Les coordonnées existantes ne sont jamais modifiées."""
    email = normaliser_email(email)
    existant = session.scalar(
        select(models.ContactAdulte).where(models.ContactAdulte.email == email).order_by(models.ContactAdulte.id).limit(1)
    )
    if existant is not None:
        return existant
    contact = models.ContactAdulte(prenom=prenom, nom=nom, email=email, telephone=telephone, cree_le=maintenant())
    session.add(contact)
    return contact


def creer_demande(
    session: Session,
    *,
    categorie: str,
    origine: str,
    prenom: str,
    nom: str,
    email: str,
    telephone: str | None = None,
    organisation: str | None = None,
    message: str | None = None,
    details: dict | None = None,
) -> models.DemandeAccueil:
    """Enregistre la demande (sans valider la transaction) ; rien d'autre n'est créé : ni compte, ni accès."""
    email = normaliser_email(email)
    instant = maintenant()
    demande = models.DemandeAccueil(
        reference=nouvelle_reference(session, categorie), contact=contact_pour(session, prenom, nom, email, telephone),
        categorie=categorie, origine=origine, prenom=prenom, nom=nom, email=email, telephone=telephone,
        organisation=organisation, message=message, details=details or {}, statut="nouveau", cree_le=instant, maj_le=instant,
    )
    session.add(demande)
    return demande


def detacher(session: Session, demande: models.DemandeAccueil) -> models.ContactAdulte:
    """Rattachement à tort : la demande reçoit son propre contact, créé avec les coordonnées qu'elle porte."""
    ancien = demande.contact
    nouveau = models.ContactAdulte(
        prenom=demande.prenom, nom=demande.nom, email=demande.email, telephone=demande.telephone, cree_le=maintenant()
    )
    session.add(nouveau)
    demande.contact = nouveau
    session.flush()
    supprimer_contacts_sans_demande(session, [ancien.id])
    return nouveau


def supprimer_contacts_sans_demande(session: Session, ids: list[int] | None = None) -> int:
    sans_demande = ~models.ContactAdulte.demandes.any()
    requete = delete(models.ContactAdulte).where(sans_demande)
    if ids is not None:
        requete = requete.where(models.ContactAdulte.id.in_(ids))
    return session.execute(requete, execution_options={"synchronize_session": False}).rowcount or 0


def compter_nouvelles(session: Session) -> dict[str, int]:
    lignes = session.execute(
        select(models.DemandeAccueil.categorie, func.count())
        .where(models.DemandeAccueil.statut == "nouveau")
        .group_by(models.DemandeAccueil.categorie)
    )
    return {c: 0 for c in CATEGORIES} | dict(lignes.all())


def purger(session: Session, maintenant_: datetime | None = None, *, simulation: bool = False) -> int:
    """Supprime, file par file, les demandes sans traitement depuis la durée décidée, CV compris, puis les contacts
    restés sans demande. Les CV sont effacés du disque après la validation : jamais de demande sans son CV."""
    instant = maintenant_ or maintenant()
    echues = []
    for categorie, jours in settings.accueil_conservation_jours.items():
        limite = instant - timedelta(days=jours)
        echues += session.scalars(
            select(models.DemandeAccueil).where(models.DemandeAccueil.categorie == categorie, models.DemandeAccueil.maj_le < limite)
        ).all()
    if simulation:
        return len(echues)
    fichiers = [d.cv_fichier for d in echues]
    for d in echues:
        session.delete(d)
    session.flush()
    supprimer_contacts_sans_demande(session)
    session.commit()
    for nom in fichiers:
        collaboration.supprimer_cv(nom)
    return len(echues)
