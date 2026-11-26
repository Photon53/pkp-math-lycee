"""Rédaction en ligne (issue #179, décision RGPD-2) : l'élève écrit sa rédaction sur un sujet de français, la remet,
son professeur la corrige ; l'élève peut ensuite la réécrire dans une nouvelle version.

Règles (cadre du propriétaire du 19/11/2026, à confirmer par le responsable de traitement) :
- usage : corriger et suivre les progrès ; aucune autre utilisation ;
- accès : l'élève à ses propres textes ; le professeur de sa classe aux versions **remises** (jamais aux brouillons) ;
  aucun autre élève ; l'administrateur n'a pas de route d'accès aux textes ; les parents non plus ;
- conservation : jusqu'au 31 août de l'année scolaire, puis purge ; 30 jours après l'archivage de la classe ;
  suppression avec l'élève ; incluses dans l'export RGPD de l'élève ;
- aucun texte de rédaction dans les journaux ;
- fermé tant que `PKP_REDACTION_ACTIVE` est faux : toutes les routes répondent 403.

Les règles d'accès des classes pilotes (#176) s'appliquent : un sujet n'est disponible que dans un chapitre ouvert
de la classe, et seulement si la classe a accès à son domaine.
"""
# Issue #179 — Rédaction en ligne et correction par le professeur (Claude)

from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from pkp_engine import TypeQuestion
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import EleveCourant, EnseignantCourant, SessionDB
from app.config import settings
from app.db import models
from app.progression import filtre_validation, ids_ouverts_eleve

router = APIRouter(tags=["redactions"])

FERMEE = "La rédaction en ligne n'est pas encore ouverte."
Texte = Annotated[str, Field(min_length=1, max_length=10_000)]


def fin_annee_scolaire(jour: date) -> date:
    """31 août de l'année scolaire du jour donné (septembre à août)."""
    return date(jour.year if jour.month <= 8 else jour.year + 1, 8, 31)


def _maintenant() -> datetime:
    return datetime.now(UTC)


def _ouverte() -> None:
    if not settings.redaction_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, FERMEE)


# --- Schémas ----------------------------------------------------------------------------------------------------


class SujetRedaction(BaseModel):
    question_id: int
    chapitre: str
    competence: str
    enonce: str
    statut: str | None  # dernière version de l'élève, ou None s'il n'a rien écrit
    version: int | None


class VersionRedaction(BaseModel):
    id: int
    version: int
    texte: str
    statut: str
    commentaire: str | None
    maj_le: datetime
    remise_le: datetime | None
    corrigee_le: datetime | None


class DetailRedaction(BaseModel):
    question_id: int
    enonce: str
    versions: list[VersionRedaction]
    conserver_jusqu_au: date | None


class Saisie(BaseModel):
    texte: Texte


class RedactionClasse(BaseModel):
    id: int
    eleve: str
    sujet: str
    version: int
    statut: str
    remise_le: datetime | None
    corrigee_le: datetime | None


class RedactionProfesseur(BaseModel):
    id: int
    eleve: str
    sujet: str
    guide: str  # réponse attendue ou pistes, pour le professeur seulement
    correction: dict | None
    version: int
    texte: str
    statut: str
    commentaire: str | None
    remise_le: datetime | None


class Correction(BaseModel):
    commentaire: Texte


# --- Élève ------------------------------------------------------------------------------------------------------


def _sujets(session: Session, eleve: models.Eleve) -> list[models.Question]:
    """Sujets de rédaction des chapitres ouverts de la classe (règles d'accès #176 et de validation V2-D3)."""
    ouverts = ids_ouverts_eleve(session, eleve.classe)
    if not ouverts:
        return []
    return list(session.scalars(
        select(models.Question)
        .join(models.Competence)
        .join(models.Chapitre)
        .where(
            models.Chapitre.id.in_(ouverts), models.Question.type == TypeQuestion.REDACTION,
            models.Question.archivee.is_(False), *filtre_validation(),
        )
        .order_by(models.Chapitre.ordre, models.Competence.ordre, models.Question.id)
    ))


def _sujet(session: Session, eleve: models.Eleve, question_id: int) -> models.Question:
    sujet = next((q for q in _sujets(session, eleve) if q.id == question_id), None)
    if sujet is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sujet introuvable.")
    return sujet


def _versions(session: Session, eleve_id: int, question_id: int) -> list[models.Redaction]:
    return list(session.scalars(
        select(models.Redaction)
        .where(models.Redaction.eleve_id == eleve_id, models.Redaction.question_id == question_id)
        .order_by(models.Redaction.version)
    ))


def _detail(session: Session, eleve: models.Eleve, sujet: models.Question) -> DetailRedaction:
    versions = _versions(session, eleve.id, sujet.id)
    return DetailRedaction(
        question_id=sujet.id, enonce=sujet.enonce,
        versions=[VersionRedaction(
            id=r.id, version=r.version, texte=r.texte, statut=r.statut, commentaire=r.commentaire, maj_le=r.maj_le,
            remise_le=r.remise_le, corrigee_le=r.corrigee_le,
        ) for r in versions],
        conserver_jusqu_au=versions[-1].conserver_jusqu_au if versions else None,
    )


@router.get("/eleves/moi/redactions", response_model=list[SujetRedaction])
def mes_sujets(eleve: EleveCourant, session: SessionDB) -> list[SujetRedaction]:
    _ouverte()
    resultat = []
    for q in _sujets(session, eleve):
        derniere = (_versions(session, eleve.id, q.id) or [None])[-1]
        resultat.append(SujetRedaction(
            question_id=q.id, chapitre=q.competence.chapitre.titre, competence=q.competence.libelle, enonce=q.enonce,
            statut=derniere.statut if derniere else None, version=derniere.version if derniere else None,
        ))
    return resultat


@router.get("/eleves/moi/redactions/{question_id}", response_model=DetailRedaction)
def ma_redaction(question_id: int, eleve: EleveCourant, session: SessionDB) -> DetailRedaction:
    _ouverte()
    return _detail(session, eleve, _sujet(session, eleve, question_id))


@router.put("/eleves/moi/redactions/{question_id}", response_model=DetailRedaction)
def enregistrer(question_id: int, corps: Saisie, eleve: EleveCourant, session: SessionDB) -> DetailRedaction:
    """Enregistre le brouillon ; après une correction, commence une nouvelle version (réécriture)."""
    _ouverte()
    sujet = _sujet(session, eleve, question_id)
    if len(corps.texte) > settings.redaction_longueur_max:
        raise HTTPException(422, f"Ta rédaction dépasse {settings.redaction_longueur_max} caractères.")
    versions = _versions(session, eleve.id, sujet.id)
    derniere = versions[-1] if versions else None
    maintenant = _maintenant()
    if derniere is not None and derniere.statut == "remise":
        raise HTTPException(status.HTTP_409_CONFLICT, "Ta rédaction est remise : attends la correction de ton professeur.")
    if derniere is not None and derniere.statut == "brouillon":
        derniere.texte, derniere.maj_le = corps.texte, maintenant
    else:
        session.add(models.Redaction(
            eleve_id=eleve.id, question_id=sujet.id, version=(derniere.version + 1) if derniere else 1,
            texte=corps.texte, statut="brouillon", cree_le=maintenant, maj_le=maintenant,
            conserver_jusqu_au=fin_annee_scolaire(maintenant.date()),
        ))
    session.commit()
    return _detail(session, eleve, sujet)


@router.post("/eleves/moi/redactions/{question_id}/remise", response_model=DetailRedaction)
def remettre(question_id: int, eleve: EleveCourant, session: SessionDB) -> DetailRedaction:
    _ouverte()
    sujet = _sujet(session, eleve, question_id)
    versions = _versions(session, eleve.id, sujet.id)
    derniere = versions[-1] if versions else None
    if derniere is None or derniere.statut != "brouillon" or not derniere.texte.strip():
        raise HTTPException(status.HTTP_409_CONFLICT, "Écris et enregistre ta rédaction avant de la remettre.")
    derniere.statut, derniere.remise_le = "remise", _maintenant()
    session.commit()
    return _detail(session, eleve, sujet)


# --- Professeur -------------------------------------------------------------------------------------------------


def _ma_classe(session: Session, classe_id: int, enseignant: models.Enseignant) -> models.Classe:
    classe = session.get(models.Classe, classe_id)
    if classe is None or classe.enseignant_id != enseignant.id or classe.archivee_le is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Classe introuvable.")
    return classe


def _remise_de_ma_classe(session: Session, redaction_id: int, enseignant: models.Enseignant) -> models.Redaction:
    """Une version remise ou corrigée d'un élève d'une classe active du professeur ; jamais un brouillon."""
    r = session.get(models.Redaction, redaction_id)
    if r is None or r.statut == "brouillon":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rédaction introuvable.")
    _ma_classe(session, r.eleve.classe_id, enseignant)
    return r


def _nom(eleve: models.Eleve) -> str:
    return eleve.prenom


@router.get("/enseignants/classes/{classe_id}/redactions", response_model=list[RedactionClasse])
def redactions_de_la_classe(classe_id: int, enseignant: EnseignantCourant, session: SessionDB) -> list[RedactionClasse]:
    """Versions remises ou corrigées des élèves de la classe, les plus récentes d'abord."""
    _ouverte()
    classe = _ma_classe(session, classe_id, enseignant)
    lignes = session.scalars(
        select(models.Redaction)
        .join(models.Eleve)
        .where(models.Eleve.classe_id == classe.id, models.Redaction.statut != "brouillon")
        .order_by(models.Redaction.remise_le.desc(), models.Redaction.id.desc())
    )
    return [RedactionClasse(
        id=r.id, eleve=_nom(r.eleve), sujet=r.question.enonce, version=r.version, statut=r.statut,
        remise_le=r.remise_le, corrigee_le=r.corrigee_le,
    ) for r in lignes]


@router.get("/enseignants/redactions/{redaction_id}", response_model=RedactionProfesseur)
def lire_redaction(redaction_id: int, enseignant: EnseignantCourant, session: SessionDB) -> RedactionProfesseur:
    _ouverte()
    r = _remise_de_ma_classe(session, redaction_id, enseignant)
    return RedactionProfesseur(
        id=r.id, eleve=_nom(r.eleve), sujet=r.question.enonce, guide=r.question.solution, correction=r.question.correction,
        version=r.version, texte=r.texte, statut=r.statut, commentaire=r.commentaire, remise_le=r.remise_le,
    )


@router.post("/enseignants/redactions/{redaction_id}/correction", response_model=RedactionProfesseur)
def corriger(redaction_id: int, corps: Correction, enseignant: EnseignantCourant, session: SessionDB) -> RedactionProfesseur:
    """Commentaire du professeur ; il peut le reprendre tant que l'élève n'a pas commencé de réécriture."""
    _ouverte()
    r = _remise_de_ma_classe(session, redaction_id, enseignant)
    if _versions(session, r.eleve_id, r.question_id)[-1].id != r.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "L'élève a déjà commencé une nouvelle version.")
    r.commentaire, r.statut, r.corrigee_le, r.correcteur_id = corps.commentaire, "corrigee", _maintenant(), enseignant.id
    session.commit()
    return lire_redaction(redaction_id, enseignant, session)
