"""Dossiers de français servis aux élèves (#212) : même règle que l'anglais, seule la version validée est lue.

Un élève ne lit un dossier que si :
- son professeur l'a ouvert à sa classe (`/francais/dossiers/{code}/classes/{id}`) ;
- une version du dossier est validée : c'est elle, et elle seule, qui est servie ; une révision soumise ou refusée
  ne la remplace pas ;
- sa classe a accès au domaine : domaine public, ou classe pilote d'un domaine actif mais fermé (SEC-D6), contrôlé
  ici côté API, y compris par adresse directe.

Seule la partie élève est servie : ni corrigé, ni support professeur (ARCH-4).

Activité de l'élève (#217, au niveau de l'anglais) :
- **quiz** corrigé par la plateforme : selon le mode de la classe ou du dossier (#110), correction après chaque
  question (réponse enregistrée d'abord, non modifiable) ou à la fin, une fois chaque question répondue ; meilleur
  score, score du premier essai (figé) et nombre d'essais ;
- **auto-évaluation** à quatre niveaux, une par phrase « Je sais » du dossier, comme le « I can » de l'anglais ;
- **réponses rédigées** aux questions du dossier, relues par le professeur de la classe : mêmes règles que les
  rédactions (RGPD-2, #179) ; fermées tant que `PKP_REDACTION_ACTIVE` est faux (403).
"""
# Issue #212 — Circuit du français aligné sur l'anglais (Claude)

from datetime import UTC, date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import correction, francais, permissions
from app.auth import EleveCourant, SessionDB
from app.config import settings
from app.db import models
from app.routes.redactions import FERMEE, fin_annee_scolaire

router = APIRouter(prefix="/francais/eleve", tags=["français-élève"])

NIVEAUX_AUTO_EVALUATION = ("non_observe", "avec_aide", "en_cours", "autonome")


def _sans_cache(reponse: Response) -> None:
    reponse.headers["Cache-Control"] = "private, no-store"


def _ligne(d, p: models.ProgressionFrancais | None = None) -> dict:
    v = d.validee
    return {"code": d.code, "titre": d.titre, "niveau": d.niveau, "version": v.numero, "nb_quiz": len(v.quiz or []),
            "score": p.meilleur_score if p else None, "total": p.total if p else None,
            "tentatives": p.tentatives if p else 0}


def dossier_servi(session: Session, eleve: models.Eleve, code: str) -> models.DossierFrancais:
    """Le dossier tel que l'élève peut le lire : 403 si sa classe n'a pas accès au domaine (SEC-D6), 404 s'il n'est
    pas ouvert à sa classe ou jamais validé (rien n'est divulgué)."""
    classe = eleve.classe
    if classe.domaine_code.startswith("francais-") and (refus := permissions.refus_acces_classe(session, classe)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, refus)
    d = next((d for d in francais.ouverts_a(session, classe) if d.code == code), None)
    if d is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier introuvable.")
    return d


def progression(session: Session, eleve: models.Eleve, code: str, creer: bool = False) -> models.ProgressionFrancais | None:
    p = session.scalar(select(models.ProgressionFrancais).where(
        models.ProgressionFrancais.eleve_id == eleve.id, models.ProgressionFrancais.code == code))
    if p is None and creer:
        p = models.ProgressionFrancais(eleve_id=eleve.id, code=code, meilleur_score=0, total=0, tentatives=0,
                                       auto_evaluation=[])
        session.add(p)
    return p


def _reponses_redigees(session: Session, eleve: models.Eleve, code: str) -> dict[str, models.ReponseRedigeeFrancais]:
    lignes = session.scalars(select(models.ReponseRedigeeFrancais).where(
        models.ReponseRedigeeFrancais.eleve_id == eleve.id, models.ReponseRedigeeFrancais.code == code))
    return {r.question: r for r in lignes}


def vue_reponse(r: models.ReponseRedigeeFrancais) -> dict:
    return {"question": r.question, "texte": r.texte, "statut": r.statut, "commentaire": r.commentaire,
            "maj_le": r.maj_le.isoformat() if r.maj_le else None,
            "remise_le": r.remise_le.isoformat() if r.remise_le else None,
            "corrigee_le": r.corrigee_le.isoformat() if r.corrigee_le else None}


@router.get("/dossiers")
def mes_dossiers(eleve: EleveCourant, session: SessionDB, reponse: Response):
    """Dossiers ouverts à sa classe, dans leur version validée, avec son meilleur score ; aucun si la classe n'a pas
    accès au domaine."""
    _sans_cache(reponse)
    return [_ligne(d, progression(session, eleve, d.code)) for d in francais.ouverts_a(session, eleve.classe)]


@router.get("/dossiers/{code}")
def mon_dossier(code: str, eleve: EleveCourant, session: SessionDB, reponse: Response):
    _sans_cache(reponse)
    d = dossier_servi(session, eleve, code)
    p = progression(session, eleve, d.code)
    return {
        **_ligne(d, p), "eleve": francais.vue_eleve(d.validee),
        "mode_correction": eleve.classe.mode_correction_de(d.code),
        "premier_score": p.premier_score if p else None, "auto_evaluation": p.auto_evaluation if p else [],
        "saisie_ouverte": settings.redaction_active,
        "reponses": [vue_reponse(r) for r in _reponses_redigees(session, eleve, d.code).values()]
        if settings.redaction_active else [],
    }


# --- Quiz corrigé (#217, comme l'anglais ; mode de correction #110) ---------------------------------------------

class ReponseQuestion(BaseModel):
    reponse: Annotated[int, Field(ge=0, le=10)]


class Reponses(BaseModel):
    reponses: Annotated[list[int | None], Field(max_length=30)]


def _correction(q: dict, juste: bool) -> dict:
    return {"juste": juste, "reponse": q["reponse"], "explication": q.get("explication", "")}


def _deja(session: Session, eleve: models.Eleve, code: str, essai: int) -> dict[int, models.ReponseQuizFrancais]:
    lignes = session.scalars(select(models.ReponseQuizFrancais).where(
        models.ReponseQuizFrancais.eleve_id == eleve.id, models.ReponseQuizFrancais.code == code,
        models.ReponseQuizFrancais.essai == essai))
    return {r.question: r for r in lignes}


@router.post("/dossiers/{code}/quiz/{rang}")
def repondre_question(code: str, rang: int, corps: ReponseQuestion, eleve: EleveCourant, session: SessionDB):
    """Mode « après chaque question » : la réponse est enregistrée (la première compte), puis sa correction rendue."""
    d = dossier_servi(session, eleve, code)
    if eleve.classe.mode_correction_de(d.code) != correction.APRES_CHAQUE_QUESTION:
        raise HTTPException(status.HTTP_409_CONFLICT, "La correction sera donnée à la fin du quiz.")
    quiz = d.validee.quiz or []
    if not 0 <= rang < len(quiz) or corps.reponse >= len(quiz[rang]["choix"]):
        raise HTTPException(422, "Question ou choix inconnu.")
    p = progression(session, eleve, d.code, creer=True)
    essai = p.tentatives + 1
    r = _deja(session, eleve, d.code, essai).get(rang)
    if r is None:
        r = models.ReponseQuizFrancais(eleve_id=eleve.id, code=d.code, essai=essai, question=rang,
                                       choix=corps.reponse, juste=corps.reponse == quiz[rang]["reponse"])
        session.add(r)
        session.commit()
    return {**_correction(quiz[rang], r.juste), "choix": r.choix}


@router.post("/dossiers/{code}/corriger")
def corriger(code: str, corps: Reponses, eleve: EleveCourant, session: SessionDB):
    """Termine l'essai : une réponse par question est exigée (ARCH-4), puis le score est enregistré.

    Une question déjà corrigée pendant l'essai garde sa première réponse : on ne la change pas après sa correction."""
    d = dossier_servi(session, eleve, code)
    quiz = d.validee.quiz or []
    if not quiz:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ce dossier n'a pas de quiz.")
    if len(corps.reponses) != len(quiz) or any(
        r is None or not 0 <= r < len(q["choix"]) for r, q in zip(corps.reponses, quiz, strict=False)
    ):
        raise HTTPException(422, "Réponds à toutes les questions avant de voir la correction.")
    p = progression(session, eleve, d.code, creer=True)
    essai = p.tentatives + 1
    deja = _deja(session, eleve, d.code, essai)
    details = []
    for rang, (choix, q) in enumerate(zip(corps.reponses, quiz, strict=True)):
        r = deja.get(rang)
        if r is None:
            r = models.ReponseQuizFrancais(eleve_id=eleve.id, code=d.code, essai=essai, question=rang, choix=choix,
                                           juste=choix == q["reponse"])
            session.add(r)
        details.append({**_correction(q, r.juste), "choix": r.choix})
    score = sum(x["juste"] for x in details)
    if p.tentatives == 0:
        p.premier_score = score
    p.tentatives, p.total, p.meilleur_score = essai, len(quiz), max(p.meilleur_score, score)
    session.commit()
    return {"score": score, "total": len(quiz), "details": details, "meilleur_score": p.meilleur_score,
            "premier_score": p.premier_score, "tentatives": p.tentatives}


# --- Auto-évaluation (#217, comme « I can ») ---------------------------------------------------------------------

class AutoEvaluation(BaseModel):
    niveaux: Annotated[list[Literal[NIVEAUX_AUTO_EVALUATION]], Field(max_length=20)]  # type: ignore[valid-type]


@router.put("/dossiers/{code}/auto-evaluation")
def auto_evaluer(code: str, corps: AutoEvaluation, eleve: EleveCourant, session: SessionDB):
    d = dossier_servi(session, eleve, code)
    if len(corps.niveaux) != len(d.validee.eleve.get("je_sais", [])) or not corps.niveaux:
        raise HTTPException(422, "Un niveau par phrase « Je sais » du dossier est attendu.")
    p = progression(session, eleve, d.code, creer=True)
    p.auto_evaluation = list(corps.niveaux)
    session.commit()
    return {"auto_evaluation": p.auto_evaluation}


# --- Réponses rédigées, relues par le professeur (#217, règles RGPD-2) --------------------------------------------

class TexteReponse(BaseModel):
    texte: Annotated[str, Field(max_length=5000)]

    @field_validator("texte")
    @classmethod
    def _texte(cls, v: str) -> str:
        return v.strip()


def _question_redigee(session: Session, eleve: models.Eleve, code: str, question: str) -> models.DossierFrancais:
    if not settings.redaction_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, FERMEE)
    d = dossier_servi(session, eleve, code)
    if question not in {q["code"] for q in d.validee.eleve["questions"]}:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question introuvable.")
    return d


@router.put("/dossiers/{code}/reponses/{question}")
def ecrire_reponse(code: str, question: str, corps: TexteReponse, eleve: EleveCourant, session: SessionDB):
    """Brouillon, visible de l'élève seul. Après un retour du professeur, l'élève peut réécrire puis remettre."""
    d = _question_redigee(session, eleve, code, question)
    r = _reponses_redigees(session, eleve, d.code).get(question)
    if r is not None and r.statut == "remise":
        raise HTTPException(status.HTTP_409_CONFLICT, "Réponse déjà remise : attends le retour de ton professeur.")
    maintenant = datetime.now(UTC)
    if r is None:
        r = models.ReponseRedigeeFrancais(eleve_id=eleve.id, code=d.code, question=question,
                                          conserver_jusqu_au=fin_annee_scolaire(date.today()))
        session.add(r)
    r.texte, r.statut, r.maj_le = corps.texte, "brouillon", maintenant
    session.commit()
    return vue_reponse(r)


@router.post("/dossiers/{code}/reponses/{question}/remise")
def remettre_reponse(code: str, question: str, eleve: EleveCourant, session: SessionDB):
    d = _question_redigee(session, eleve, code, question)
    r = _reponses_redigees(session, eleve, d.code).get(question)
    if r is None or r.statut != "brouillon" or not r.texte:
        raise HTTPException(status.HTTP_409_CONFLICT, "Écris ta réponse avant de la remettre.")
    r.statut, r.remise_le = "remise", datetime.now(UTC)
    session.commit()
    return vue_reponse(r)
