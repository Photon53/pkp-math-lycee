"""Espace élève PKP Anglais : connexion par identifiant + code, séances validées, quiz corrigés, « I can ».

Seules les versions validées par un référent sont ouvertes aux élèves (CDC anglais V1.8).
Les corrigés ne quittent jamais le serveur avant l'envoi des réponses.
"""
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app import anglais_contenu, limitation, permissions
from app.auth import ELEVE_ANGLAIS, EleveAnglaisCourant, SessionDB
from app.config import settings
from app.db import models
from app.routes.eleves import ECHEC_IDENTIFIANT, _code_leurre
from app.schemas import ConnexionIdentifiant
from app.security import creer_jeton, normaliser_identifiant, verifier_code_eleve, version_mot_de_passe

router = APIRouter(prefix="/anglais/eleve", tags=["anglais-eleve"])


class EleveAnglaisInfo(BaseModel):
    prenom: str
    niveau: str
    groupe: str


class JetonEleveAnglais(BaseModel):
    jeton: str
    eleve: EleveAnglaisInfo


class Reponses(BaseModel):
    # Index du choix retenu pour chaque question, dans l'ordre ; None = sans réponse.
    reponses: Annotated[list[int | None], Field(max_length=50)]


class AutoEvaluation(BaseModel):
    i_can: Annotated[list[Literal[anglais_contenu.NIVEAUX_I_CAN]], Field(max_length=10)]  # type: ignore[valid-type]


def _info(eleve: models.EleveAnglais) -> EleveAnglaisInfo:
    return EleveAnglaisInfo(prenom=eleve.prenom, niveau=eleve.groupe.niveau, groupe=eleve.groupe.nom)


@router.post("/connexion", response_model=JetonEleveAnglais)
def connexion(corps: ConnexionIdentifiant, request: Request, session: SessionDB) -> JetonEleveAnglais:
    """Identifiant + code personnel imprimés sur la carte : mêmes protections que l'espace de maths."""
    ip = limitation.adresse_ip(request)
    identifiant = normaliser_identifiant(corps.identifiant)
    compte = f"eleve-anglais:{identifiant}"
    limitation.verifier((limitation.par_ip, ip), (limitation.codes_inconnus, ip), (limitation.echecs_code_eleve, compte))
    limitation.par_ip.enregistrer(ip)

    eleve = session.scalar(select(models.EleveAnglais).where(models.EleveAnglais.identifiant == identifiant))
    empreinte = eleve.code_hash if eleve and eleve.code_hash else _code_leurre()  # même durée dans tous les cas
    if not verifier_code_eleve(corps.code_personnel, empreinte) or not (eleve and eleve.code_hash):
        if eleve is None:
            limitation.codes_inconnus.enregistrer(ip)  # freine la recherche d'identifiants
        limitation.echecs_code_eleve.enregistrer(compte)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, ECHEC_IDENTIFIANT)
    limitation.echecs_code_eleve.effacer(compte)
    if not eleve.groupe.enseignant.actif:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Le compte de ton professeur est suspendu.")
    duree_h = settings.duree_jeton_eleve_longue_j * 24 if corps.rester_connecte else settings.duree_jeton_eleve_h
    jeton = creer_jeton(ELEVE_ANGLAIS, eleve.id, duree_h, version_mot_de_passe(eleve.code_hash))
    return JetonEleveAnglais(jeton=jeton, eleve=_info(eleve))


@router.get("/moi", response_model=EleveAnglaisInfo)
def moi(eleve: EleveAnglaisCourant) -> EleveAnglaisInfo:
    return _info(eleve)


def _publiee(session: SessionDB, eleve: models.EleveAnglais, code: str) -> models.SeanceAnglaisVersion:
    """Version validée d'une séance du niveau de l'élève ; sinon 404 (rien ne trahit un brouillon).
    Domaine fermé au public : 403, sans rien supprimer (EX.4)."""
    refus = permissions.refus_domaine_ferme(session, permissions.DOMAINE_GROUPES_ANGLAIS)
    if refus:
        raise HTTPException(status.HTTP_403_FORBIDDEN, refus)
    seance = anglais_contenu.par_code(session, code)
    version = seance and seance.niveau == eleve.groupe.niveau and seance.publiee
    if not version:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Séance introuvable.")
    return version


def _progression(session: SessionDB, eleve: models.EleveAnglais, code: str) -> models.ProgressionAnglais:
    p = next((p for p in eleve.progression if p.code == code), None)
    if p is None:
        p = models.ProgressionAnglais(code=code, meilleur_score=0, total=0, tentatives=0, i_can=[])
        eleve.progression.append(p)
    return p


@router.get("/seances")
def mes_seances(eleve: EleveAnglaisCourant, session: SessionDB):
    """Séances validées de son niveau, avec sa progression."""
    suivi = {p.code: p for p in eleve.progression}
    lignes = []
    for s in anglais_contenu.toutes(session):
        v = s.publiee
        if s.niveau != eleve.groupe.niveau or v is None:
            continue
        p = suivi.get(s.code)
        lignes.append({
            "code": s.code, "titre": v.contenu["title"], "objectif": v.contenu["objective"],
            "can_do": v.cahier.get("can_do", []),
            "score": p.meilleur_score if p else None, "total": p.total if p else None,
            "tentatives": p.tentatives if p else 0, "i_can": p.i_can if p else [],
        })
    return lignes


@router.get("/seances/{code}")
def ma_seance(code: str, eleve: EleveAnglaisCourant, session: SessionDB):
    p = next((p for p in eleve.progression if p.code == code), None)
    return {**anglais_contenu.vue_eleve(_publiee(session, eleve, code)), "i_can": p.i_can if p else []}


@router.post("/seances/{code}/corriger")
def corriger(code: str, corps: Reponses, eleve: EleveAnglaisCourant, session: SessionDB):
    """Correction immédiate ; seul le meilleur score est conservé."""
    resultat = anglais_contenu.corriger(_publiee(session, eleve, code), corps.reponses)
    p = _progression(session, eleve, code)
    p.tentatives += 1
    p.total = resultat["total"]
    p.meilleur_score = max(p.meilleur_score, resultat["score"])
    session.commit()
    return {**resultat, "meilleur_score": p.meilleur_score}


@router.put("/seances/{code}/i-can")
def auto_evaluer(code: str, corps: AutoEvaluation, eleve: EleveAnglaisCourant, session: SessionDB):
    version = _publiee(session, eleve, code)
    if len(corps.i_can) != len(version.cahier.get("can_do", [])):
        raise HTTPException(422, "Une réponse par phrase « I can » est attendue.")
    p = _progression(session, eleve, code)
    p.i_can = list(corps.i_can)
    session.commit()
    return {"i_can": p.i_can}
