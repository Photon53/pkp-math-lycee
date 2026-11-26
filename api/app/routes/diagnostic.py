# Issue #162 — Diagnostic des acquis antérieurs, lot 3 : passation (Claude)
"""Passation du diagnostic par l'élève, ouverture et suivi par le professeur.

Aucune route élève ne renvoie de solution ni de verdict : le diagnostic observe, il ne corrige pas devant l'élève.
Les réponses vont dans `observation_diagnostic`, jamais dans `reponse` (le taux de maîtrise n'en tient pas compte).
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Response, status
from pkp_engine import TypeQuestion
from pydantic import BaseModel, Field

from app import diagnostic, exemplaires, permissions
from app.auth import EleveCourant, EnseignantCourant, SessionDB
from app.diagnostic import DiagnosticRefuse
from app.routes.enseignants import _ma_classe

router = APIRouter(tags=["diagnostic"])


class EtatDiagnostic(BaseModel):
    # ferme | indisponible | a-commencer | en-cours | termine
    statut: str
    nb_reponses: int = 0


class QuestionDiagnosticPublique(BaseModel):
    """Ce que voit l'élève : ni solution, ni difficulté, ni compétence (le diagnostic n'est pas une note)."""

    id: int
    numero: int
    enonce: str
    type: TypeQuestion


class ReponseDiagnostic(BaseModel):
    question_id: int
    # Rédaction : jusqu'à 4 000 caractères ; réponse courte : 200 (contrôlé par le service).
    reponse_donnee: Annotated[str, Field(max_length=4000)] | None = None
    ne_sait_pas: bool = False


class AccuseReception(BaseModel):
    """Réponse enregistrée : volontairement sans verdict ni solution."""

    enregistree: bool = True


class OuvertureDiagnostic(BaseModel):
    ouvert: bool


class SuiviEleveDiagnostic(BaseModel):
    eleve_id: int
    prenom: str
    statut: str
    nb_reponses: int
    nb_en_attente: int


class DiagnosticClasse(BaseModel):
    ouvert: bool
    nb_questions_disponibles: int
    eleves: list[SuiviEleveDiagnostic]


def _refus(exc: DiagnosticRefuse) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, str(exc))


def _domaine_ouvert(session: SessionDB, eleve) -> None:
    refus = permissions.refus_acces_classe(session, eleve.classe)
    if refus:
        raise HTTPException(status.HTTP_403_FORBIDDEN, refus)


# --- Élève --------------------------------------------------------------------------------------------------------


@router.get("/eleves/moi/diagnostic", response_model=EtatDiagnostic)
def etat(eleve: EleveCourant, session: SessionDB) -> EtatDiagnostic:
    passation = diagnostic.passation_de(session, eleve)
    return EtatDiagnostic(
        statut=diagnostic.statut(session, eleve), nb_reponses=len(passation.observations) if passation else 0
    )


@router.post("/eleves/moi/diagnostic", response_model=EtatDiagnostic)
def demarrer(eleve: EleveCourant, session: SessionDB) -> EtatDiagnostic:
    """Commence le diagnostic, ou reprend celui en cours."""
    _domaine_ouvert(session, eleve)
    try:
        passation = diagnostic.demarrer(session, eleve)
    except DiagnosticRefuse as exc:
        raise _refus(exc) from exc
    session.commit()
    return EtatDiagnostic(statut=diagnostic.EN_COURS, nb_reponses=len(passation.observations))


@router.get(
    "/eleves/moi/diagnostic/question",
    response_model=QuestionDiagnosticPublique,
    responses={204: {"description": "Diagnostic terminé."}},
)
def question(eleve: EleveCourant, session: SessionDB):
    _domaine_ouvert(session, eleve)
    try:
        q = diagnostic.question_suivante(session, eleve)
    except DiagnosticRefuse as exc:
        raise _refus(exc) from exc
    session.commit()
    if q is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    passation = diagnostic.passation_de(session, eleve)
    publique = exemplaires.publique(q, None)
    return QuestionDiagnosticPublique(
        id=q.id, numero=diagnostic.numero_courant(passation), enonce=publique["enonce"], type=q.type
    )


@router.post("/eleves/moi/diagnostic/reponses", response_model=AccuseReception)
def repondre(corps: ReponseDiagnostic, eleve: EleveCourant, session: SessionDB) -> AccuseReception:
    _domaine_ouvert(session, eleve)
    try:
        diagnostic.repondre(session, eleve, corps.question_id, corps.reponse_donnee, corps.ne_sait_pas)
    except DiagnosticRefuse as exc:
        raise _refus(exc) from exc
    session.commit()
    return AccuseReception()


# --- Professeur ---------------------------------------------------------------------------------------------------


def _vue_classe(session: SessionDB, classe) -> DiagnosticClasse:
    return DiagnosticClasse(
        ouvert=classe.diagnostic_ouvert,
        nb_questions_disponibles=len(diagnostic.questions_diffusables(session, classe)),
        eleves=[SuiviEleveDiagnostic(**ligne) for ligne in diagnostic.suivi_classe(session, classe)],
    )


@router.get("/enseignants/classes/{classe_id}/diagnostic", response_model=DiagnosticClasse)
def diagnostic_de_la_classe(classe_id: int, enseignant: EnseignantCourant, session: SessionDB) -> DiagnosticClasse:
    return _vue_classe(session, _ma_classe(session, classe_id, enseignant))


@router.put("/enseignants/classes/{classe_id}/diagnostic", response_model=DiagnosticClasse)
def ouvrir_diagnostic(
    classe_id: int, corps: OuvertureDiagnostic, enseignant: EnseignantCourant, session: SessionDB
) -> DiagnosticClasse:
    """Ouvre ou ferme le diagnostic aux élèves de la classe. Fermer interrompt les passations en cours (elles
    reprennent à la réouverture) ; aucune réponse n'est effacée."""
    classe = _ma_classe(session, classe_id, enseignant)
    classe.diagnostic_ouvert = corps.ouvert
    session.commit()
    return _vue_classe(session, classe)
