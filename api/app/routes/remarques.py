"""Remarques et suggestions (ticket #30).

Tout compte connecté (élève, parent, professeur) envoie une remarque « avec son nom » ou « anonyme ».
Anonyme : rien de l'identité n'est enregistré (ni nom, ni rôle, ni identifiant), donc rien ne peut apparaître dans
l'administration, les exports ou le journal. Le compte connecté sert seulement, en mémoire, à limiter le spam.
L'auteur suit sa remarque avec sa référence et son code de suivi confidentiel, montré une seule fois.
"""

import csv
import hashlib
import hmac
import io
import secrets
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from app import auth, journal, limitation
from app.auth import AdminCourant, Identifiants, SessionDB
from app.config import settings
from app.db import models
from app.security import ALPHABET_CODE

router = APIRouter(tags=["remarques"])

Categorie = Literal[
    "bug", "dysfonctionnement", "amelioration-fonctionnelle", "amelioration-pedagogique",
    "erreur-pedagogique", "lien-inaccessible", "question", "autre",
]
Statut = Literal["recue", "en-cours", "resolue", "fermee"]
Priorite = Literal["basse", "normale", "haute"]


def _maintenant() -> datetime:
    return datetime.now(UTC)


def _utc(d: datetime | None) -> datetime | None:
    return d.replace(tzinfo=UTC) if d is not None and d.tzinfo is None else d


# ---------------------------------------------------------------------------------------------------- schémas


class NouvelleRemarque(BaseModel):
    categorie: Categorie
    description: Annotated[str, Field(min_length=5, max_length=3000)]
    page: Annotated[str, Field(max_length=300)] | None = None
    # Choix explicite, sans valeur par défaut : l'interface fait choisir avant l'envoi.
    anonyme: bool

    @field_validator("description", "page", mode="before")
    @classmethod
    def _nettoyer(cls, v):
        return v.strip() if isinstance(v, str) else v


class AccuseReception(BaseModel):
    reference: str
    code_suivi: str  # montré une seule fois : seule son empreinte est conservée
    anonyme: bool
    statut: Statut


class DemandeSuivi(BaseModel):
    reference: Annotated[str, Field(max_length=20)]
    code: Annotated[str, Field(max_length=40)]


class RemarqueSuivie(BaseModel):
    reference: str
    categorie: Categorie
    statut: Statut
    reponse: str | None
    cree_le: datetime
    maj_le: datetime


class Auteur(BaseModel):
    role: str
    nom: str


class RemarqueAdmin(BaseModel):
    id: int
    reference: str
    categorie: Categorie
    description: str
    page: str | None
    anonyme: bool
    auteur: Auteur | None  # toujours None pour une remarque anonyme
    statut: Statut
    priorite: Priorite
    assignee: str | None
    reponse: str | None
    cree_le: datetime
    maj_le: datetime


class TraitementRemarque(BaseModel):
    statut: Statut | None = None
    priorite: Priorite | None = None
    assignee_id: int | None = None
    reponse: Annotated[str, Field(max_length=3000)] | None = None


# ---------------------------------------------------------------------------------------------------- auteur


def _auteur(identifiants: Identifiants, session: SessionDB) -> tuple[str, int, str]:
    """(rôle, identifiant, nom affiché) du compte connecté, quel que soit l'espace ; 401 sinon."""
    # Type de compte (≤ 12 caractères) : les identifiants des tables diffèrent, il précise la table.
    essais = (
        ("eleve", auth.eleve_courant, lambda e: f"{e.prenom} ({e.classe.code})"),
        ("enfant", auth.enfant_courant, lambda e: e.prenom),
        ("eleve-ang", auth.eleve_anglais_courant, lambda e: f"{e.prenom} ({e.groupe.nom})"),
        ("parent", auth.parent_courant, lambda p: f"{p.prenom} {p.nom}".strip() or p.email),
        ("professeur", auth._enseignant_pret, lambda e: e.nom),
    )
    for type_compte, lire, nom in essais:
        try:
            compte = lire(identifiants, session)
        except HTTPException:
            continue
        return type_compte, compte.id, nom(compte)
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentification requise.", headers={"WWW-Authenticate": "Bearer"})


def _empreinte(code: str) -> str:
    return hmac.new(settings.secret_key.encode(), code.strip().upper().encode(), hashlib.sha256).hexdigest()


def _reference() -> str:
    return "R-" + "".join(secrets.choice(ALPHABET_CODE) for _ in range(8))


def _code_suivi() -> str:
    brut = "".join(secrets.choice(ALPHABET_CODE) for _ in range(12))
    return f"{brut[:4]}-{brut[4:8]}-{brut[8:]}"


def _role_affiche(type_compte: str) -> str:
    return {"enfant": "eleve", "eleve-ang": "eleve"}.get(type_compte, type_compte)


# ---------------------------------------------------------------------------------------------------- auteur : routes


@router.post("/remarques", response_model=AccuseReception, status_code=status.HTTP_201_CREATED)
def envoyer(corps: NouvelleRemarque, request: Request, identifiants: Identifiants, session: SessionDB) -> AccuseReception:
    type_compte, compte_id, nom = _auteur(identifiants, session)
    cle_compte, ip = f"{type_compte}:{compte_id}", limitation.adresse_ip(request)  # en mémoire seulement
    limitation.verifier((limitation.remarques_par_compte, cle_compte), (limitation.remarques_par_ip, ip))
    limitation.remarques_par_compte.enregistrer(cle_compte)
    limitation.remarques_par_ip.enregistrer(ip)

    code = _code_suivi()
    while True:
        reference = _reference()
        if session.scalar(select(models.Remarque.id).where(models.Remarque.reference == reference)) is None:
            break
    remarque = models.Remarque(
        reference=reference, code_suivi_empreinte=_empreinte(code), categorie=corps.categorie,
        description=corps.description, page=corps.page or None, anonyme=corps.anonyme,
        statut="recue", priorite="normale", cree_le=_maintenant(), maj_le=_maintenant(),
        **({} if corps.anonyme else {"auteur_role": type_compte, "auteur_id": compte_id, "auteur_nom": nom[:120]}),
    )
    session.add(remarque)
    session.commit()
    return AccuseReception(reference=reference, code_suivi=code, anonyme=corps.anonyme, statut="recue")


@router.post("/remarques/suivi", response_model=RemarqueSuivie)
def suivre(corps: DemandeSuivi, request: Request, session: SessionDB) -> RemarqueSuivie:
    """Suivi par référence et code confidentiel : sans compte, donc possible pour une remarque anonyme."""
    ip = limitation.adresse_ip(request)
    limitation.verifier((limitation.suivi_remarques_par_ip, ip))
    remarque = session.scalar(select(models.Remarque).where(models.Remarque.reference == corps.reference.strip().upper()))
    if remarque is None or not hmac.compare_digest(remarque.code_suivi_empreinte, _empreinte(corps.code)):
        limitation.suivi_remarques_par_ip.enregistrer(ip)
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Référence ou code de suivi incorrect.")
    return _vue_suivi(remarque)


@router.get("/remarques/miennes", response_model=list[RemarqueSuivie])
def mes_remarques(identifiants: Identifiants, session: SessionDB) -> list[RemarqueSuivie]:
    """Remarques envoyées avec son nom. Les remarques anonymes ne sont reliées à aucun compte : code de suivi."""
    type_compte, compte_id, _ = _auteur(identifiants, session)
    remarques = session.scalars(
        select(models.Remarque)
        .where(models.Remarque.auteur_role == type_compte, models.Remarque.auteur_id == compte_id)
        .order_by(models.Remarque.cree_le.desc())
    )
    return [_vue_suivi(r) for r in remarques]


def _vue_suivi(r: models.Remarque) -> RemarqueSuivie:
    return RemarqueSuivie(
        reference=r.reference, categorie=r.categorie, statut=r.statut, reponse=r.reponse,
        cree_le=_utc(r.cree_le), maj_le=_utc(r.maj_le),
    )


# ---------------------------------------------------------------------------------------------------- administration


def _vue_admin(r: models.Remarque) -> RemarqueAdmin:
    return RemarqueAdmin(
        id=r.id, reference=r.reference, categorie=r.categorie, description=r.description, page=r.page,
        anonyme=r.anonyme,
        auteur=None if r.anonyme or r.auteur_nom is None else Auteur(role=_role_affiche(r.auteur_role), nom=r.auteur_nom),
        statut=r.statut, priorite=r.priorite, assignee=r.assignee.nom if r.assignee else None, reponse=r.reponse,
        cree_le=_utc(r.cree_le), maj_le=_utc(r.maj_le),
    )


def _filtrer(session, categorie, statut, priorite, depuis, jusqua):
    requete = select(models.Remarque).order_by(models.Remarque.cree_le.desc())
    if categorie:
        requete = requete.where(models.Remarque.categorie == categorie)
    if statut:
        requete = requete.where(models.Remarque.statut == statut)
    if priorite:
        requete = requete.where(models.Remarque.priorite == priorite)
    if depuis:
        requete = requete.where(models.Remarque.cree_le >= depuis)
    if jusqua:
        requete = requete.where(models.Remarque.cree_le <= jusqua)
    return session.scalars(requete.limit(500)).all()


@router.get("/admin/remarques", response_model=list[RemarqueAdmin])
def lister(
    admin: AdminCourant,
    session: SessionDB,
    categorie: Categorie | None = None,
    statut: Statut | None = None,
    priorite: Priorite | None = None,
    depuis: datetime | None = None,
    jusqua: datetime | None = None,
) -> list[RemarqueAdmin]:
    return [_vue_admin(r) for r in _filtrer(session, categorie, statut, priorite, depuis, jusqua)]


@router.get("/admin/remarques/export.csv")
def exporter(
    admin: AdminCourant,
    session: SessionDB,
    categorie: Categorie | None = None,
    statut: Statut | None = None,
    priorite: Priorite | None = None,
) -> Response:
    tampon = io.StringIO()
    ecrivain = csv.writer(tampon, delimiter=";")
    ecrivain.writerow(["Référence", "Date", "Catégorie", "Statut", "Priorité", "Auteur", "Page", "Description", "Réponse"])
    for r in map(_vue_admin, _filtrer(session, categorie, statut, priorite, None, None)):
        auteur = "Anonyme" if r.anonyme else f"{r.auteur.nom} ({r.auteur.role})" if r.auteur else ""
        ecrivain.writerow([r.reference, f"{r.cree_le:%Y-%m-%d %H:%M}", r.categorie, r.statut, r.priorite, auteur,
                           r.page or "", r.description, r.reponse or ""])
    return Response(
        "﻿" + tampon.getvalue(), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="remarques.csv"'},
    )


@router.post("/admin/remarques/{remarque_id}", response_model=RemarqueAdmin)
def traiter(remarque_id: int, corps: TraitementRemarque, admin: AdminCourant, session: SessionDB) -> RemarqueAdmin:
    r = session.get(models.Remarque, remarque_id)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Remarque introuvable.")
    champs = corps.model_dump(exclude_unset=True)
    if "assignee_id" in champs and champs["assignee_id"] is not None:
        assignee = session.get(models.Enseignant, champs["assignee_id"])
        if assignee is None or assignee.role.value != "admin":
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "On ne peut assigner une remarque qu'à un administrateur.")
    # Journal : seulement le traitement, jamais l'identité de l'auteur ni le texte de la remarque.
    avant = {k: getattr(r, k) for k in champs if k != "reponse"} | ({"reponse": bool(r.reponse)} if "reponse" in champs else {})
    for k, v in champs.items():
        setattr(r, k, v.strip() or None if k == "reponse" and isinstance(v, str) else v)
    r.maj_le = _maintenant()
    apres = {k: getattr(r, k) for k in champs if k != "reponse"} | ({"reponse": bool(r.reponse)} if "reponse" in champs else {})
    journal.noter(session, admin, "traiter", "remarque", r.id, avant, apres)
    session.commit()
    return _vue_admin(r)
