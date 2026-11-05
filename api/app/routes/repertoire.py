"""Répertoire des élèves et fiche élève (V3, Lot 1), réservés à l'administrateur.

Un élève = un enfant de famille. Les routes existantes (`/admin/enfants`, familles, classes) restent en place.
"""

from typing import Literal

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app import enfants, journal, parents, repertoire
from app.auth import AdminCourant, FiltreDomaine, SessionDB
from app.db import models
from app.schemas import ResponsableAjout
from app.schemas_admin import ChangementNiveau, FicheEleve, PageRepertoire, ResponsableRattache

router = APIRouter(prefix="/admin", tags=["administration"])

# Au-delà de deux responsables, l'administrateur confirme explicitement (rattachements multiples contrôlés).
RESPONSABLES_SANS_CONFIRMATION = 2


def _enfant(session: SessionDB, enfant_id: int) -> models.Enfant:
    enfant = session.get(models.Enfant, enfant_id)
    if enfant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Élève introuvable.")
    return enfant


@router.get("/repertoire", response_model=PageRepertoire)
def lister(
    _: AdminCourant,
    session: SessionDB,
    domaine: FiltreDomaine,
    q: str = "",
    niveau: str | None = None,
    classe_id: int | None = None,
    groupe_id: int | None = None,
    statut: Literal["actif", "bloque"] | None = None,
    sans_responsable: bool = False,
    sans_classe: bool = False,
    a_verifier: bool = False,
    tri: Literal["nom", "niveau", "connexion", "recent"] = "nom",
    page: int = 1,
) -> PageRepertoire:
    """Tous les élèves, 50 par page : recherche (prénom, nom, identifiant, classe, groupe, responsable) et filtres."""
    return repertoire.chercher(
        session, q=q, niveau=niveau, domaine=domaine, classe_id=classe_id, groupe_id=groupe_id, statut=statut,
        sans_responsable=sans_responsable, sans_classe=sans_classe, a_verifier=a_verifier, tri=tri, page=page,
    )


@router.get("/enfants/{enfant_id}/fiche", response_model=FicheEleve)
def fiche(enfant_id: int, _: AdminCourant, session: SessionDB) -> FicheEleve:
    return repertoire.fiche(session, _enfant(session, enfant_id))


@router.post("/enfants/{enfant_id}/responsables", response_model=ResponsableRattache)
def ajouter_responsable(
    enfant_id: int, corps: ResponsableAjout, admin: AdminCourant, session: SessionDB, confirmer: bool = False
) -> ResponsableRattache:
    """Rattache l'élève au compte de cette adresse, ou crée ce compte (mot de passe provisoire donné une fois).
    Au-delà de deux responsables, `confirmer=true` est demandé."""
    enfant = _enfant(session, enfant_id)
    parent = session.scalar(select(models.Parent).where(models.Parent.email == corps.email))
    if parent is not None and parent in enfant.parents:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{corps.email} est déjà responsable de cet élève.")
    if len(enfant.parents) >= RESPONSABLES_SANS_CONFIRMATION and not confirmer:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Cet élève a déjà {len(enfant.parents)} responsables : confirmez l'ajout d'un responsable supplémentaire.",
        )
    if parent is not None and len(parent.famille) >= enfants.MAX_ENFANTS_PAR_FAMILLE:
        raise HTTPException(422, f"Une famille compte au plus {enfants.MAX_ENFANTS_PAR_FAMILLE} enfants.")
    provisoire = None
    if parent is None:
        parent = models.Parent(email=corps.email, mot_de_passe_hash="", mdp_provisoire=True)
        provisoire = parents.reinitialiser(parent)
        session.add(parent)
    if corps.nom:
        parent.nom = corps.nom
    if corps.prenom:
        parent.prenom = corps.prenom
    parent.famille.append(enfant)
    session.flush()
    journal.noter(session, admin, "rattacher-enfant", "parent", parent.id,
                  apres={"enfant": enfant.id, "compte_cree": provisoire is not None})
    session.commit()
    return ResponsableRattache(
        responsable=next(r for r in repertoire.responsables(enfant) if r.id == parent.id),
        cree=provisoire is not None, mot_de_passe_provisoire=provisoire,
    )


@router.delete("/enfants/{enfant_id}/responsables/{parent_id}", response_model=FicheEleve)
def retirer_responsable(enfant_id: int, parent_id: int, admin: AdminCourant, session: SessionDB) -> FicheEleve:
    """Détache le responsable de l'élève ; l'élève et son travail restent. Un compte qui ne suit plus aucun
    enfant est supprimé (RGPD), comme partout ailleurs."""
    enfant = _enfant(session, enfant_id)
    parent = next((p for p in enfant.parents if p.id == parent_id), None)
    if parent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ce compte n'est pas responsable de cet élève.")
    parent.famille.remove(enfant)
    journal.noter(session, admin, "detacher-enfant", "parent", parent.id, avant={"enfant": enfant.id})
    parents.supprimer_orphelins(session)
    session.commit()
    return repertoire.fiche(session, _enfant(session, enfant_id))


@router.post("/enfants/niveau", response_model=PageRepertoire)
def changer_niveau(corps: ChangementNiveau, admin: AdminCourant, session: SessionDB) -> PageRepertoire:
    """Passage au niveau choisi pour plusieurs élèves ; leurs inscriptions restent (signalées « autre niveau »)."""
    choisis = session.scalars(select(models.Enfant).where(models.Enfant.id.in_(corps.ids))).all()
    if len(choisis) != len(set(corps.ids)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Élève introuvable.")
    changes = [e for e in choisis if e.niveau != corps.niveau]
    for e in changes:
        e.niveau = corps.niveau
    if changes:
        journal.noter(session, admin, "changer-niveau", "enfant", None,
                      apres={"ids": [e.id for e in changes], "niveau": corps.niveau.value})
    session.commit()
    return PageRepertoire(total=len(choisis), elements=[repertoire.decrire(e) for e in choisis])
