# Issue #172 — Accueil et demandes : contacts adultes et demandes (Claude)
"""« Accueil et demandes » : traitement des demandes des adultes qui ne sont pas encore inscrits (issue #172).

Réservé aux administrateurs (jeton admin, rôle revérifié en base à chaque requête) : un professeur ou un validateur
n'y a aucun accès, quelles que soient ses habilitations. Le journal note le traitement (catégorie, statut, issue,
responsable, présence de notes, téléchargement, export, suppression), jamais les coordonnées, le message, les notes
ni le CV. Aucune action ne crée de compte, d'inscription, d'habilitation ni de contrat, et rien n'est envoyé.
"""

import json
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select

from app import accueil, collaboration, journal
from app.auth import AdminCourant, SessionDB
from app.db import models

router = APIRouter(prefix="/admin/accueil", tags=["accueil"])

Categorie = Literal["famille", "information", "candidature", "partenariat"]
Statut = Literal["nouveau", "a-traiter", "traite"]
Issue = Literal["suite-demandee", "inscription-effective", "refus", "cloture"]
TAILLE_PAGE = 50


# ---------------------------------------------------------------------------------------------------- schémas


class FileAccueil(BaseModel):
    categorie: Categorie
    nouvelles: int
    conservation_jours: int | None  # None : durée non décidée, la file ne collecte rien


class DemandeResume(BaseModel):
    id: int
    reference: str
    categorie: Categorie
    origine: str
    contact_id: int
    contact: str
    organisation: str | None
    statut: Statut
    issue: Issue | None
    a_un_cv: bool
    responsable: str | None
    cree_le: datetime


class PageDemandes(BaseModel):
    demandes: list[DemandeResume]
    total: int
    page: int
    taille_page: int


class Contact(BaseModel):
    id: int
    prenom: str
    nom: str
    email: str
    telephone: str | None
    cree_le: datetime


class DemandeDetail(DemandeResume):
    prenom: str
    nom: str
    email: str
    telephone: str | None
    message: str | None
    details: dict
    cv_taille_octets: int | None
    notes_internes: str | None
    responsable_id: int | None
    maj_le: datetime
    contact_fiche: Contact
    autres_demandes: list[DemandeResume]  # historique du contact, sans fusion des catégories


class SaisieDemande(accueil.CoordonneesAdulte):
    """Demande reçue hors formulaire (téléphone, rencontre) et saisie par un administrateur. Familles et
    informations seulement ; aucune donnée d'enfant ni résultat pédagogique : seulement le besoin exprimé."""

    categorie: Literal["famille", "information"]
    message: Annotated[str, Field(min_length=3, max_length=3000)]

    _nettoyage_message = field_validator("message", mode="before")(accueil.nettoyer)


class Traitement(BaseModel):
    statut: Statut | None = None
    issue: Issue | None = None
    notes_internes: Annotated[str, Field(max_length=3000)] | None = None
    responsable_id: int | None = None


# ---------------------------------------------------------------------------------------------------- vues


def _resume(d: models.DemandeAccueil) -> DemandeResume:
    return DemandeResume(
        id=d.id, reference=d.reference, categorie=d.categorie, origine=d.origine, contact_id=d.contact_id,
        contact=f"{d.prenom} {d.nom}", organisation=d.organisation, statut=d.statut, issue=d.issue,
        a_un_cv=d.cv_fichier is not None, responsable=d.responsable.nom if d.responsable else None,
        cree_le=accueil.utc(d.cree_le),
    )


def _contact(c: models.ContactAdulte) -> Contact:
    return Contact(id=c.id, prenom=c.prenom, nom=c.nom, email=c.email, telephone=c.telephone, cree_le=accueil.utc(c.cree_le))


def _detail(d: models.DemandeAccueil) -> DemandeDetail:
    return DemandeDetail(
        **_resume(d).model_dump(), prenom=d.prenom, nom=d.nom, email=d.email, telephone=d.telephone, message=d.message,
        details=d.details or {}, cv_taille_octets=d.cv_taille_octets, notes_internes=d.notes_internes,
        responsable_id=d.responsable_id, maj_le=accueil.utc(d.maj_le), contact_fiche=_contact(d.contact),
        autres_demandes=[_resume(x) for x in d.contact.demandes if x.id != d.id],
    )


def _demande(session, demande_id: int) -> models.DemandeAccueil:
    d = session.get(models.DemandeAccueil, demande_id)
    if d is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Demande introuvable.")
    return d


def _contact_ou_404(session, contact_id: int) -> models.ContactAdulte:
    c = session.get(models.ContactAdulte, contact_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contact introuvable.")
    return c


# ---------------------------------------------------------------------------------------------------- routes


@router.get("/files", response_model=list[FileAccueil])
def files(admin: AdminCourant, session: SessionDB) -> list[FileAccueil]:
    nouvelles = accueil.compter_nouvelles(session)
    return [FileAccueil(categorie=c, nouvelles=nouvelles[c], conservation_jours=accueil.conservation(c)) for c in accueil.CATEGORIES]


@router.get("/demandes", response_model=PageDemandes)
def lister(
    admin: AdminCourant,
    session: SessionDB,
    categorie: Categorie | None = None,
    statut: Statut | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    depuis: datetime | None = None,
    jusqua: datetime | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
) -> PageDemandes:
    D = models.DemandeAccueil
    filtres = []
    if categorie:
        filtres.append(D.categorie == categorie)
    if statut:
        filtres.append(D.statut == statut)
    if depuis:
        filtres.append(D.cree_le >= depuis)
    if jusqua:
        filtres.append(D.cree_le <= jusqua)
    if q and q.strip():
        motif = f"%{q.strip().lower()}%"
        filtres.append(or_(*(func.lower(c).like(motif) for c in (D.reference, D.prenom, D.nom, D.email, D.organisation))))
    total = session.scalar(select(func.count()).select_from(D).where(*filtres)) or 0
    demandes = session.scalars(
        select(D).where(*filtres).order_by(D.cree_le.desc(), D.id.desc()).offset((page - 1) * TAILLE_PAGE).limit(TAILLE_PAGE)
    )
    return PageDemandes(demandes=[_resume(d) for d in demandes], total=total, page=page, taille_page=TAILLE_PAGE)


@router.post("/demandes", response_model=DemandeDetail, status_code=status.HTTP_201_CREATED)
def saisir(corps: SaisieDemande, admin: AdminCourant, session: SessionDB) -> DemandeDetail:
    accueil.exiger_conservation(corps.categorie)
    d = accueil.creer_demande(
        session, categorie=corps.categorie, origine="saisie-admin", prenom=corps.prenom, nom=corps.nom,
        email=corps.email, telephone=corps.telephone or None, message=corps.message,
    )
    session.flush()
    journal.noter(session, admin, "saisir", "demande-accueil", d.id, apres={"categorie": d.categorie})
    session.commit()
    return _detail(d)


@router.get("/demandes/{demande_id}", response_model=DemandeDetail)
def lire(demande_id: int, admin: AdminCourant, session: SessionDB) -> DemandeDetail:
    return _detail(_demande(session, demande_id))


@router.post("/demandes/{demande_id}", response_model=DemandeDetail)
def traiter(demande_id: int, corps: Traitement, admin: AdminCourant, session: SessionDB) -> DemandeDetail:
    d = _demande(session, demande_id)
    champs = corps.model_dump(exclude_unset=True)
    if champs.get("responsable_id") is not None:
        responsable = session.get(models.Enseignant, champs["responsable_id"])
        if responsable is None or responsable.role.value != "admin":
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Le responsable du traitement doit être un administrateur.")
    statut = champs.get("statut", d.statut)
    issue = champs.get("issue", d.issue)
    if statut == "traite" and issue is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Indiquez l'issue du traitement.")
    if statut != "traite" and "issue" not in champs:
        issue = None  # une demande rouverte n'a plus d'issue
    elif statut != "traite" and issue is not None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "L'issue ne s'indique que pour une demande traitée.")
    if issue is not None and issue not in accueil.ISSUES[d.categorie]:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Cette issue ne s'applique pas à cette file.")
    champs["statut"], champs["issue"] = statut, issue

    def trace() -> dict:  # jamais le texte des notes, seulement leur présence
        return {"statut": d.statut, "issue": d.issue, "responsable_id": d.responsable_id, "notes": bool(d.notes_internes)}

    avant = trace()
    for cle, valeur in champs.items():
        setattr(d, cle, (valeur.strip() or None) if cle == "notes_internes" and isinstance(valeur, str) else valeur)
    d.maj_le = accueil.maintenant()
    journal.noter(session, admin, "traiter", "demande-accueil", d.id, avant, trace())
    session.commit()
    return _detail(d)


@router.post("/demandes/{demande_id}/detacher", response_model=DemandeDetail)
def detacher(demande_id: int, admin: AdminCourant, session: SessionDB) -> DemandeDetail:
    """Rattachement à tort (même e-mail, autre personne) : la demande reçoit son propre contact."""
    d = _demande(session, demande_id)
    if len(d.contact.demandes) < 2:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Cette demande est la seule de son contact.")
    ancien = d.contact_id
    accueil.detacher(session, d)
    journal.noter(session, admin, "detacher", "demande-accueil", d.id, {"contact_id": ancien}, {"contact_id": d.contact_id})
    session.commit()
    session.refresh(d)
    return _detail(d)


@router.get("/demandes/{demande_id}/cv")
def telecharger_cv(demande_id: int, admin: AdminCourant, session: SessionDB) -> FileResponse:
    d = _demande(session, demande_id)
    chemin = collaboration.chemin_cv(d)
    journal.noter(session, admin, "telecharger-cv", "demande-accueil", d.id)
    session.commit()
    return FileResponse(
        chemin, media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="CV-{d.reference}.pdf"',
            "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete("/demandes/{demande_id}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_demande(demande_id: int, admin: AdminCourant, session: SessionDB) -> Response:
    """Effacement d'une demande et de son CV ; le contact part avec sa dernière demande."""
    d = _demande(session, demande_id)
    fichier, contact_id = d.cv_fichier, d.contact_id
    journal.noter(session, admin, "supprimer", "demande-accueil", d.id, {"categorie": d.categorie, "cv": fichier is not None})
    session.delete(d)
    session.flush()
    accueil.supprimer_contacts_sans_demande(session, [contact_id])
    session.commit()
    collaboration.supprimer_cv(fichier)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/contacts/{contact_id}/export")
def exporter_contact(contact_id: int, admin: AdminCourant, session: SessionDB) -> Response:
    """Droit d'accès : le contact et toutes ses demandes (les CV se téléchargent à part)."""
    c = _contact_ou_404(session, contact_id)
    journal.noter(session, admin, "exporter", "contact-accueil", c.id)
    session.commit()
    contenu = {
        "contact": _contact(c).model_dump(mode="json"),
        "demandes": [
            _detail(d).model_dump(mode="json", exclude={"contact_fiche", "autres_demandes", "responsable_id"})
            for d in c.demandes
        ],
    }
    return Response(
        json.dumps(contenu, ensure_ascii=False, indent=2), media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="contact-{c.id}.json"', "Cache-Control": "private, no-store"},
    )


@router.delete("/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_contact(contact_id: int, admin: AdminCourant, session: SessionDB) -> Response:
    """Effacement demandé par la personne : le contact, toutes ses demandes et tous ses CV."""
    c = _contact_ou_404(session, contact_id)
    fichiers = [d.cv_fichier for d in c.demandes]
    journal.noter(session, admin, "supprimer", "contact-accueil", c.id, {"demandes": len(fichiers), "cv": sum(f is not None for f in fichiers)})
    session.delete(c)
    session.commit()
    for nom in fichiers:
        collaboration.supprimer_cv(nom)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
