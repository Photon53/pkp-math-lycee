"""Dossiers de français en préparation : consultation et validation, réservées aux adultes habilités (#98).

Aucune route élève : un jeton d'élève, d'enfant ou de parent est refusé (401) partout ici. Un adulte doit être
administrateur, ou professeur/validateur habilité dans le domaine et le niveau du dossier ; le domaine doit être
actif (préparation par l'équipe). L'ouverture au public n'est ni nécessaire ni modifiée.
"""
# Issue #98 — Intégration du premier dossier Français 3e en DEV (Claude)

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import francais, journal, permissions
from app.auth import EnseignantAuthentifie, SessionDB
from app.db import models

router = APIRouter(prefix="/francais", tags=["français"])


def membre_francais(enseignant: EnseignantAuthentifie, session: SessionDB) -> models.Enseignant:
    if enseignant.mdp_provisoire:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Choisissez d'abord un nouveau mot de passe.")
    actifs = [code for code in francais.DOMAINES_FRANCAIS if francais.domaine_actif(session, code)]
    if not any(francais.peut_lire(enseignant, code, None) for code in actifs):
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "Réservé aux adultes habilités en français, dans un domaine activé pour la préparation.")
    return enseignant


MembreFrancais = Annotated[models.Enseignant, Depends(membre_francais)]


def dossier_ou_404(session: Session, code: str, qui: models.Enseignant) -> models.DossierFrancais:
    """Dossier introuvable, de domaine inactif ou hors des habilitations : même réponse, rien n'est divulgué."""
    d = session.scalar(select(models.DossierFrancais).where(models.DossierFrancais.code == code))
    if d is None or not francais.domaine_actif(session, d.domaine_code) or not francais.peut_lire(qui, d.domaine_code, d.niveau):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier introuvable.")
    return d


def _sans_cache(reponse: Response) -> None:
    # Corrigés et supports professeur : ni cache partagé, ni conservation par le navigateur.
    reponse.headers["Cache-Control"] = "private, no-store"


@router.get("/dossiers")
def lister(qui: MembreFrancais, session: SessionDB, reponse: Response):
    _sans_cache(reponse)
    return [francais.resume(d, qui) for d in francais.lisibles(session, qui)]


@router.get("/dossiers/{code}/eleve")
def apercu_eleve(code: str, qui: MembreFrancais, session: SessionDB, reponse: Response):
    """Aperçu, pour l'adulte, de la partie destinée aux élèves (version courante), sans corrigé."""
    _sans_cache(reponse)
    d = dossier_ou_404(session, code, qui)
    return {**francais.resume(d, qui), "eleve": francais.vue_eleve(d.courante)}


@router.get("/dossiers/{code}/professeur")
def supports_professeur(code: str, qui: MembreFrancais, session: SessionDB, reponse: Response):
    _sans_cache(reponse)
    d = dossier_ou_404(session, code, qui)
    return {**francais.resume(d, qui), "professeur": francais.vue_professeur(d.courante)}


@router.get("/dossiers/{code}/historique")
def historique(code: str, qui: MembreFrancais, session: SessionDB, reponse: Response):
    _sans_cache(reponse)
    return francais.historique(dossier_ou_404(session, code, qui))


class Refus(BaseModel):
    motif: Annotated[str, Field(max_length=2000)]

    @field_validator("motif")
    @classmethod
    def _motif(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Le motif du refus est obligatoire.")
        return v


def _decider(code: str, qui: models.Enseignant, session: Session, motif: str | None) -> dict:
    """Décision d'un validateur habilité (domaine et niveau), jamais l'auteur ; journalisée.

    Valider ne publie rien aux élèves : il n'existe pas de module élève pour le français.
    """
    d = dossier_ou_404(session, code, qui)
    if refus := permissions.refus_validation(qui, d.domaine_code, d.niveau):
        raise HTTPException(status.HTTP_403_FORBIDDEN, refus)
    courante = d.courante
    if probleme := francais.peut_decider(courante, qui):
        raise HTTPException(status.HTTP_409_CONFLICT, probleme)
    if motif is None:
        francais.valider(d, qui)
    else:
        francais.refuser(d, qui, motif)
    journal.noter(session, qui, "valider" if motif is None else "refuser", "dossier_francais", d.id,
                  {"code": d.code, "version": courante.numero, "statut": "soumis"},
                  {"code": d.code, "version": courante.numero, "statut": courante.statut, "motif": motif})
    session.commit()
    return francais.resume(d, qui)


@router.post("/dossiers/{code}/valider")
def valider(code: str, qui: MembreFrancais, session: SessionDB):
    return _decider(code, qui, session, None)


@router.post("/dossiers/{code}/refuser")
def refuser(code: str, corps: Refus, qui: MembreFrancais, session: SessionDB):
    return _decider(code, qui, session, corps.motif)
