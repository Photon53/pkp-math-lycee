"""Espace de l'enfant : une seule carte (identifiant + code), puis le choix de la matière.

PKP Math ouvre l'une de ses inscriptions de maths (jeton élève habituel), PKP Anglais son groupe d'anglais
(jeton anglais habituel) ; PKP Français est affiché « bientôt disponible ». Les anciennes cartes d'élève de
maths (créées directement dans une classe) passent par la même connexion.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app import enfants, limitation
from app.auth import CARTE_BLOQUEE, ELEVE, ELEVE_ANGLAIS, ENFANT, EnfantCourant, SessionDB, carte_bloquee
from app.config import settings
from app.db import models
from app.routes.anglais_eleves import JetonEleveAnglais, _info as info_anglais
from app.routes.eleves import CARTE_ANGLAIS, ECHEC_IDENTIFIANT, _carte_anglais, _code_leurre, _info as info_maths
from app.schemas import ConnexionCarte, ConnexionIdentifiant, EspaceEnfant, JetonEleve
from app.security import creer_jeton, normaliser_identifiant, verifier_code_eleve, version_mot_de_passe

router = APIRouter(prefix="/enfants", tags=["enfant"])


@router.post("/connexion", response_model=ConnexionCarte)
def connexion(corps: ConnexionIdentifiant, request: Request, session: SessionDB) -> ConnexionCarte:
    """Identifiant + code imprimés sur la carte. Mêmes protections que les autres connexions élève :
    un seul message d'échec, durée constante, limitation des essais par adresse et par compte."""
    ip = limitation.adresse_ip(request)
    identifiant = normaliser_identifiant(corps.identifiant)
    compte = f"carte:{identifiant}"
    limitation.verifier((limitation.par_ip, ip), (limitation.codes_inconnus, ip), (limitation.echecs_code_eleve, compte))
    limitation.par_ip.enregistrer(ip)
    duree_h = settings.duree_jeton_eleve_longue_j * 24 if corps.rester_connecte else settings.duree_jeton_eleve_h

    enfant = session.scalar(select(models.Enfant).where(models.Enfant.identifiant == identifiant))
    eleve = None if enfant else session.scalar(select(models.Eleve).where(models.Eleve.identifiant == identifiant))
    titulaire = enfant or eleve
    empreinte = titulaire.code_hash if titulaire and titulaire.code_hash else _code_leurre()  # même durée
    if not verifier_code_eleve(corps.code_personnel, empreinte) or not (titulaire and titulaire.code_hash):
        if titulaire is None and _carte_anglais(session, identifiant, corps.code_personnel):
            raise HTTPException(status.HTTP_409_CONFLICT, CARTE_ANGLAIS)
        if titulaire is None:
            limitation.codes_inconnus.enregistrer(ip)  # freine la recherche d'identifiants
        limitation.echecs_code_eleve.enregistrer(compte)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, ECHEC_IDENTIFIANT)
    limitation.echecs_code_eleve.effacer(compte)
    if carte_bloquee(titulaire):
        raise HTTPException(status.HTTP_403_FORBIDDEN, CARTE_BLOQUEE)

    if enfant is not None:
        enfant.derniere_connexion = datetime.now(UTC)
        session.commit()
        jeton = creer_jeton(ENFANT, enfant.id, duree_h, version_mot_de_passe(enfant.code_hash))
        return ConnexionCarte(type="enfant", jeton=jeton, enfant=enfants.espace(enfant))
    if not eleve.classe.enseignant.actif:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Le compte de ton professeur est suspendu.")
    jeton = creer_jeton(ELEVE, eleve.id, duree_h, version_mot_de_passe(eleve.code_hash))
    return ConnexionCarte(type="eleve", jeton=jeton, eleve=info_maths(eleve))


@router.get("/moi", response_model=EspaceEnfant)
def moi(enfant: EnfantCourant) -> EspaceEnfant:
    return enfants.espace(enfant)


@router.post("/moi/maths/{eleve_id}", response_model=JetonEleve)
def ouvrir_maths(eleve_id: int, enfant: EnfantCourant) -> JetonEleve:
    """Ouvre une inscription de maths de l'enfant (tronc commun, excellence, mise à niveau…)."""
    eleve = next((e for e in enfant.inscriptions if e.id == eleve_id), None)
    if eleve is None or eleve.code_hash is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Inscription introuvable.")
    if not eleve.classe.enseignant.actif:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Le compte du professeur de cette classe est suspendu.")
    jeton = creer_jeton(ELEVE, eleve.id, settings.duree_jeton_eleve_h, version_mot_de_passe(eleve.code_hash))
    return JetonEleve(jeton=jeton, eleve=info_maths(eleve))


@router.post("/moi/anglais/{eleve_id}", response_model=JetonEleveAnglais)
def ouvrir_anglais(eleve_id: int, enfant: EnfantCourant) -> JetonEleveAnglais:
    eleve = next((e for e in enfant.inscriptions_anglais if e.id == eleve_id), None)
    if eleve is None or eleve.code_hash is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Inscription introuvable.")
    if not eleve.groupe.enseignant.actif:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Le compte du professeur de ce groupe est suspendu.")
    jeton = creer_jeton(ELEVE_ANGLAIS, eleve.id, settings.duree_jeton_eleve_h, version_mot_de_passe(eleve.code_hash))
    return JetonEleveAnglais(jeton=jeton, eleve=info_anglais(eleve))
