"""Espace parent : connexion, suivi du travail des enfants, code personnel choisi pour l'enfant.

Le compte est créé par le professeur ; mot de passe oublié : le professeur ou un administrateur
en donne un nouveau, provisoire (aucun courriel n'est envoyé). Un parent ne voit que ses enfants
(404 sinon, pour ne pas révéler l'existence des autres élèves).
"""

import secrets
from datetime import UTC, datetime
from functools import cache

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app import enfants as enfants_famille, inscriptions, limitation, parents
from app.auth import PARENT, ParentAuthentifie, ParentCourant, SessionDB
from app.config import settings
from app.db import models
from app.progression import historique_reponses
from app.routes.enseignants import _attribuer_identifiant
from app.schemas import (
    ChangementMotDePasse,
    CodeChoisi,
    CodeEnfantModifie,
    ConnexionEnseignant,
    EnfantResume,
    JetonParent,
    PageHistorique,
    TableauEnfant,
)
from app.security import (
    creer_jeton,
    doit_rehacher,
    hacher_code_eleve,
    hacher_mot_de_passe,
    normaliser_code,
    probleme_code_choisi,
    verifier_mot_de_passe,
    version_mot_de_passe,
)
router = APIRouter(prefix="/parents", tags=["parent"])


@cache
def _empreinte_leurre() -> str:
    return hacher_mot_de_passe(secrets.token_hex(16))


def _jeton(parent: models.Parent) -> JetonParent:
    version = version_mot_de_passe(parent.mot_de_passe_hash)
    return JetonParent(
        jeton=creer_jeton(PARENT, parent.id, settings.duree_jeton_parent_h, version),
        email=parent.email,
        mdp_provisoire=parent.mdp_provisoire,
    )


@router.post("/connexion", response_model=JetonParent)
def connexion(corps: ConnexionEnseignant, request: Request, session: SessionDB) -> JetonParent:
    ip = limitation.adresse_ip(request)
    compte = f"parent:{corps.email}"
    limitation.verifier((limitation.par_ip, ip), (limitation.echecs_enseignant, compte))
    limitation.par_ip.enregistrer(ip)

    parent = session.scalar(select(models.Parent).where(models.Parent.email == corps.email))
    # Même calcul (et même durée) que l'e-mail existe ou non : on ne révèle pas les comptes.
    empreinte = parent.mot_de_passe_hash if parent else _empreinte_leurre()
    if not verifier_mot_de_passe(corps.mot_de_passe, empreinte) or parent is None:
        limitation.echecs_enseignant.enregistrer(compte)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou mot de passe incorrect.")
    limitation.echecs_enseignant.effacer(compte)
    if doit_rehacher(parent.mot_de_passe_hash):
        parent.mot_de_passe_hash = hacher_mot_de_passe(corps.mot_de_passe)
    parent.derniere_connexion = datetime.now(UTC)
    session.commit()
    return _jeton(parent)


@router.post("/mot-de-passe", response_model=JetonParent)
def changer_mot_de_passe(corps: ChangementMotDePasse, parent: ParentAuthentifie, session: SessionDB) -> JetonParent:
    """Obligatoire après un mot de passe provisoire. Les autres sessions ouvertes cessent de fonctionner."""
    if not verifier_mot_de_passe(corps.actuel, parent.mot_de_passe_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Mot de passe actuel incorrect.")
    if corps.nouveau == corps.actuel:
        raise HTTPException(422, "Le nouveau mot de passe doit être différent de l'actuel.")
    parent.mot_de_passe_hash = hacher_mot_de_passe(corps.nouveau)
    parent.mdp_provisoire = False
    session.commit()
    return _jeton(parent)


def _mon_enfant(session: SessionDB, parent: models.Parent, eleve_id: int) -> models.Eleve:
    enfant = next((e for e in parents.enfants(session, parent) if e.id == eleve_id), None)
    if enfant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Élève introuvable.")
    return enfant


@router.get("/enfants", response_model=list[EnfantResume])
def mes_enfants(parent: ParentCourant, session: SessionDB) -> list[EnfantResume]:
    return [parents.resume(session, e) for e in parents.enfants(session, parent)]


@router.get("/enfants/{eleve_id}", response_model=TableauEnfant)
def tableau(eleve_id: int, parent: ParentCourant, session: SessionDB) -> TableauEnfant:
    return parents.tableau(session, _mon_enfant(session, parent, eleve_id))


@router.get("/enfants/{eleve_id}/historique", response_model=PageHistorique)
def historique(
    eleve_id: int, parent: ParentCourant, session: SessionDB, page: int = 1, erreurs: bool = False
) -> PageHistorique:
    return historique_reponses(session, _mon_enfant(session, parent, eleve_id), page, erreurs)


@router.put("/enfants/{eleve_id}/code", response_model=CodeEnfantModifie)
def choisir_code(eleve_id: int, corps: CodeChoisi, parent: ParentCourant, session: SessionDB) -> CodeEnfantModifie:
    """Le parent choisit le code personnel de son enfant. Il vaut pour toutes ses inscriptions reliées ;
    l'ancien code et les sessions ouvertes de l'enfant cessent de fonctionner."""
    enfant = _mon_enfant(session, parent, eleve_id)
    if enfant.enfant is None:
        _attribuer_identifiant(enfant)
    code = normaliser_code(corps.code)
    probleme = probleme_code_choisi(code, parents.mots_interdits(enfant.enfant or enfant))
    if probleme:
        raise HTTPException(422, probleme)
    if enfant.enfant is not None:  # enfant d'une famille : sa carte unique, pour toutes ses matières
        enfant.enfant.code_hash = hacher_code_eleve(code)
        enfants_famille.synchroniser(enfant.enfant)
        session.commit()
        return CodeEnfantModifie(identifiant=enfant.enfant.identifiant)
    enfant.code_hash = hacher_code_eleve(code)
    for autre in inscriptions.liees(session, enfant):
        autre.code_hash = enfant.code_hash
    session.commit()
    return CodeEnfantModifie(identifiant=enfant.identifiant)
