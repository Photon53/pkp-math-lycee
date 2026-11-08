"""PKP Math : résumés de cours, fiches d'exercices et corrigés par chapitre, comme les cahiers PKP Anglais.

Le même document sert à l'écran et à l'export PDF (rendu par le navigateur, formules comprises). Qui voit quoi :
- administrateur et professeur de maths : tout le programme, questions à valider comprises ;
- élève (inscription dans une classe) : les chapitres ouverts de sa classe ;
- enfant de famille : les chapitres de son niveau ;
- parent : les chapitres des niveaux de ses enfants.
Côté élève, enfant et parent, un domaine fermé au public n'est pas servi, et seules les questions servables
le sont (voir `filtre_validation`). Tant qu'une question du chapitre n'est pas validée, le document porte la
mention NON VALIDÉ.
"""

import random
from dataclasses import dataclass

from fastapi import APIRouter, HTTPException, status
from pkp_engine import gabarits
from pydantic import BaseModel
from sqlalchemy import select

from app import permissions
from app.auth import (
    ADMIN,
    ELEVE,
    ENFANT,
    ENSEIGNANT,
    PARENT,
    Identifiants,
    SessionDB,
    admin_courant,
    eleve_courant,
    enfant_courant,
    enseignant_courant,
    parent_courant,
)
from app.db import models
from app.progression import filtre_validation, ids_ouverts
from app.referentiel import LIBELLES_PARCOURS, Niveau, Parcours, StatutValidation, domaine_maths
from app.security import lire_jeton

router = APIRouter(prefix="/pkp-math", tags=["pkp-math"])


class ChapitreCatalogue(BaseModel):
    id: int
    code: str
    titre: str
    niveau: Niveau
    parcours: Parcours
    libelle_parcours: str
    ordre: int
    nb_competences: int
    nb_questions: int
    valide: bool


class QuestionDocument(BaseModel):
    id: int
    code: str | None
    difficulte: int
    type: str
    enonce: str
    solution: str
    correction: dict | None
    validee: bool


class CompetenceDocument(BaseModel):
    id: int
    code: str
    libelle: str
    objectifs: list[str]
    resume: str
    cours: str
    methodes: list[dict]
    erreurs_frequentes: list[dict]
    questions: list[QuestionDocument]


class DocumentChapitre(BaseModel):
    id: int
    code: str
    titre: str
    niveau: Niveau
    parcours: Parcours
    libelle_parcours: str
    valide: bool
    competences: list[CompetenceDocument]


@dataclass
class Lecteur:
    """Qui lit, et ce qu'il a le droit de lire."""

    role: str
    complet: bool  # tout le programme et toutes les questions (admin, professeur)
    chapitres: set[int] | None = None  # chapitres permis ; None : selon les niveaux
    niveaux: set[Niveau] | None = None
    # Accès par niveau seulement : parcours écartés (voie générale ou voie professionnelle, ticket #25).
    parcours_exclus: frozenset[Parcours] = frozenset()


def voie_exclue(classes: "list[models.Classe]") -> frozenset[Parcours]:
    """Parcours de seconde à écarter de l'accès par niveau : l'autre voie que celle de l'élève.

    Un élève de seconde professionnelle ne reçoit pas les chapitres propres à la seconde générale, et
    inversement ; sans classe de maths active, on écarte la voie professionnelle (rien ne change pour
    les comptes existants).
    """
    pro = any(c.parcours == Parcours.PROFESSIONNEL for c in classes if c.domaine_code.startswith("maths-"))
    return frozenset({Parcours.TRONC_COMMUN} if pro else {Parcours.PROFESSIONNEL})


def _lecteur(identifiants: Identifiants, session: SessionDB) -> Lecteur:
    """Le premier jeton reconnu : administrateur, professeur, élève, enfant de famille ou parent."""
    jeton = identifiants and identifiants.credentials
    if not jeton:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentification requise.")
    if lire_jeton(jeton, ADMIN):
        admin_courant(identifiants, session)
        return Lecteur(ADMIN, complet=True)
    if lire_jeton(jeton, ENSEIGNANT):
        enseignant_courant(identifiants, session)
        return Lecteur(ENSEIGNANT, complet=True)
    if lire_jeton(jeton, ELEVE):
        eleve = eleve_courant(identifiants, session)
        return Lecteur(ELEVE, complet=False, chapitres=set(ids_ouverts(eleve.classe)))
    if lire_jeton(jeton, ENFANT):
        enfant = enfant_courant(identifiants, session)
        actives = [e.classe for e in enfant.inscriptions if e.classe.archivee_le is None]
        ouverts = {i for c in actives for i in ids_ouverts(c)}
        return Lecteur(ENFANT, complet=False, chapitres=ouverts, niveaux={enfant.niveau},
                       parcours_exclus=voie_exclue(actives))
    if lire_jeton(jeton, PARENT):
        parent = parent_courant(identifiants, session)
        niveaux = {e.niveau for e in parent.famille} | {e.classe.niveau for e in parent.enfants}
        return Lecteur(PARENT, complet=False, niveaux=niveaux)
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentification requise.")


def _permis(session: SessionDB, lecteur: Lecteur, chapitre: models.Chapitre) -> bool:
    if chapitre.masque:
        return False
    if lecteur.complet:
        return True
    if permissions.refus_domaine_ferme(session, domaine_maths(chapitre.niveau)):
        return False
    if lecteur.chapitres is not None and chapitre.id in lecteur.chapitres:
        return True
    return (lecteur.niveaux is not None and chapitre.niveau in lecteur.niveaux
            and chapitre.parcours not in lecteur.parcours_exclus)


def _questions(session: SessionDB, lecteur: Lecteur, competence: models.Competence) -> list[models.Question]:
    filtres = [models.Question.competence_id == competence.id, models.Question.archivee.is_(False)]
    requete = select(models.Question).join(models.Competence).where(*filtres)
    if not lecteur.complet:
        requete = requete.where(*filtre_validation())
    return list(session.scalars(requete.order_by(models.Question.difficulte, models.Question.id)))


def _instancier(q: models.Question) -> QuestionDocument:
    """Question à gabarit : un tirage fixe (le même à chaque export), pour une fiche reproductible."""
    enonce, solution, correction = q.enonce, q.solution, q.correction
    if q.gabarit:
        try:
            tirage = gabarits.tirer(q.gabarit, random.Random(q.id))
            enonce, solution = gabarits.remplir(enonce, tirage), gabarits.remplir(solution, tirage)
            correction = gabarits.remplir_correction(correction, tirage)
        except gabarits.GabaritInvalide:
            pass
    return QuestionDocument(
        id=q.id, code=q.code, difficulte=q.difficulte, type=q.type.value, enonce=enonce, solution=solution,
        correction=correction, validee=q.statut_validation == StatutValidation.VALIDEE,
    )


def _competences(chapitre: models.Chapitre) -> list[models.Competence]:
    return sorted((c for c in chapitre.competences if not c.masque), key=lambda c: (c.ordre, c.code))


@router.get("/catalogue", response_model=list[ChapitreCatalogue])
def catalogue(identifiants: Identifiants, session: SessionDB, niveau: Niveau | None = None) -> list[ChapitreCatalogue]:
    lecteur = _lecteur(identifiants, session)
    requete = select(models.Chapitre).where(models.Chapitre.masque.is_(False))
    if niveau is not None:
        requete = requete.where(models.Chapitre.niveau == niveau)
    resultat = []
    for ch in session.scalars(requete.order_by(models.Chapitre.niveau, models.Chapitre.parcours, models.Chapitre.ordre)):
        if not _permis(session, lecteur, ch):
            continue
        questions = [q for c in _competences(ch) for q in _questions(session, lecteur, c)]
        resultat.append(ChapitreCatalogue(
            id=ch.id, code=ch.code, titre=ch.titre, niveau=ch.niveau, parcours=ch.parcours,
            libelle_parcours=LIBELLES_PARCOURS.get(ch.parcours, ch.parcours.value), ordre=ch.ordre,
            nb_competences=len(_competences(ch)), nb_questions=len(questions),
            valide=bool(questions) and all(q.statut_validation == StatutValidation.VALIDEE for q in questions),
        ))
    return resultat


@router.get("/chapitres/{chapitre_id}", response_model=DocumentChapitre)
def document(chapitre_id: int, identifiants: Identifiants, session: SessionDB) -> DocumentChapitre:
    """Résumé, cours, méthodes, erreurs fréquentes et questions corrigées de chaque compétence du chapitre."""
    lecteur = _lecteur(identifiants, session)
    chapitre = session.get(models.Chapitre, chapitre_id)
    if chapitre is None or not _permis(session, lecteur, chapitre):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chapitre introuvable.")
    competences = []
    for c in _competences(chapitre):
        questions = [_instancier(q) for q in _questions(session, lecteur, c)]
        competences.append(CompetenceDocument(
            id=c.id, code=c.code, libelle=c.libelle, objectifs=c.objectifs or [],
            resume=c.lecon.resume if c.lecon else "", cours=c.lecon.cours if c.lecon else "",
            methodes=c.methodes or [], erreurs_frequentes=c.erreurs_frequentes or [], questions=questions,
        ))
    toutes = [q for c in competences for q in c.questions]
    return DocumentChapitre(
        id=chapitre.id, code=chapitre.code, titre=chapitre.titre, niveau=chapitre.niveau, parcours=chapitre.parcours,
        libelle_parcours=LIBELLES_PARCOURS.get(chapitre.parcours, chapitre.parcours.value),
        valide=bool(toutes) and all(q.validee for q in toutes), competences=competences,
    )
