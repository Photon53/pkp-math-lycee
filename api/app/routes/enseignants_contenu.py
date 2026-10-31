"""Espace enseignant : lecture de tous les cours (module 2) et ressources de ses classes (module 3).

Le professeur lit toute la banque, y compris les chapitres qu'il n'a pas encore ouverts :
il prépare un chapitre avant de le proposer à ses élèves. Il ne modifie pas les cours.
"""

from fastapi import APIRouter, HTTPException, Request, Response, status
from pkp_engine import Niveau
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app import ressources
from app.auth import EnseignantCourant, SessionDB
from app.config import settings
from app.db import models
from app.referentiel import Parcours, PorteeRessource, TypeRessource
from app.schemas import (
    ChapitreCoursEnseignant,
    CompetenceCoursEnseignant,
    LeconInfo,
    QuestionEnseignant,
    RessourceCreation,
    RessourceDetail,
)

router = APIRouter(prefix="/enseignants", tags=["enseignant"])

# Ordre scolaire, et non alphabétique (« 1re » < « 2nde »).
ORDRE_NIVEAUX = {Niveau.SECONDE: 0, Niveau.PREMIERE: 1, Niveau.TERMINALE: 2}


# --- Cours ------------------------------------------------------------------------


def _contient(competence: models.Competence, terme: str) -> bool:
    textes = [competence.libelle]
    if competence.lecon:
        textes += [competence.lecon.cours, competence.lecon.resume]
    return any(terme in t.lower() for t in textes)


@router.get("/cours", response_model=list[ChapitreCoursEnseignant])
def sommaire(
    enseignant: EnseignantCourant,
    session: SessionDB,
    niveau: Niveau | None = None,
    parcours: Parcours | None = None,
    q: str | None = None,
) -> list[ChapitreCoursEnseignant]:
    """Sommaire de la banque ; `q` cherche dans les titres, libellés et textes de cours (EA4.8)."""
    requete = (
        select(models.Chapitre)
        .where(models.Chapitre.masque.is_(False))
        .options(selectinload(models.Chapitre.competences).selectinload(models.Competence.lecon))
        .order_by(models.Chapitre.niveau, models.Chapitre.parcours, models.Chapitre.ordre)
    )
    if niveau is not None:
        requete = requete.where(models.Chapitre.niveau == niveau)
    if parcours is not None:
        requete = requete.where(models.Chapitre.parcours == parcours)
    terme = q.strip().lower() if q else ""

    nb_questions = dict(
        session.execute(
            select(models.Question.competence_id, func.count())
            .where(models.Question.archivee.is_(False))
            .group_by(models.Question.competence_id)
        ).all()
    )
    ouvert_dans: dict[int, list[str]] = {}
    for classe in enseignant.classes:
        for chapitre in classe.chapitres_proposes:
            ouvert_dans.setdefault(chapitre.id, []).append(classe.code)

    resultat = []
    chapitres = sorted(session.scalars(requete), key=lambda c: (ORDRE_NIVEAUX[c.niveau], c.parcours.value, c.ordre))
    for ch in chapitres:
        competences = [c for c in sorted(ch.competences, key=lambda c: (c.ordre, c.code)) if not c.masque]
        if terme and terme not in ch.titre.lower():
            competences = [c for c in competences if _contient(c, terme)]
            if not competences:
                continue
        resultat.append(
            ChapitreCoursEnseignant(
                id=ch.id, code=ch.code, titre=ch.titre, niveau=ch.niveau, parcours=ch.parcours,
                ouvert_dans=sorted(ouvert_dans.get(ch.id, [])),
                competences=[
                    CompetenceCoursEnseignant(
                        id=c.id, code=c.code, libelle=c.libelle, a_une_lecon=c.lecon is not None,
                        nb_questions=nb_questions.get(c.id, 0),
                    )
                    for c in competences
                ],
            )
        )
    return resultat


@router.get("/cours/{competence_id}", response_model=LeconInfo)
def lecon(competence_id: int, enseignant: EnseignantCourant, session: SessionDB) -> LeconInfo:
    competence = session.get(models.Competence, competence_id)
    if competence is None or competence.lecon is None or competence.masque or competence.chapitre.masque:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cours introuvable.")
    return LeconInfo(
        competence_id=competence.id,
        code=competence.code,
        libelle=competence.libelle,
        chapitre=competence.chapitre.titre,
        chapitre_id=competence.chapitre_id,
        cours=competence.lecon.cours,
        resume=competence.lecon.resume,
        objectifs=competence.objectifs or [],
        methodes=competence.methodes or [],
        erreurs_frequentes=competence.erreurs_frequentes or [],
        ressources=ressources.pour_enseignant(session, enseignant, None, competence.id)
        + ressources.pour_enseignant(session, enseignant, competence.chapitre_id, None),
    )


@router.get("/cours/{competence_id}/questions", response_model=list[QuestionEnseignant])
def questions_de_la_competence(competence_id: int, _: EnseignantCourant, session: SessionDB) -> list[models.Question]:
    """Exercices de la compétence, avec solution (volet repliable sous le cours, EA4.3)."""
    return list(
        session.scalars(
            select(models.Question)
            .where(models.Question.competence_id == competence_id, models.Question.archivee.is_(False))
            .order_by(models.Question.difficulte, models.Question.id)
        )
    )


# --- Ressources de ses classes ------------------------------------------------------


def _ma_ressource(session: SessionDB, ressource_id: int, enseignant: models.Enseignant) -> models.Ressource:
    r = session.get(models.Ressource, ressource_id)
    if r is None or r.auteur_id != enseignant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ressource introuvable.")
    return r


@router.get("/ressources", response_model=list[RessourceDetail])
def mes_ressources(enseignant: EnseignantCourant, session: SessionDB) -> list[RessourceDetail]:
    lignes = session.scalars(
        select(models.Ressource)
        .where(models.Ressource.auteur_id == enseignant.id)
        .order_by(models.Ressource.cree_le.desc())
    )
    return [ressources.detail(session, r) for r in lignes]


@router.post("/ressources", response_model=RessourceDetail, status_code=status.HTTP_201_CREATED)
def creer_ressource(corps: RessourceCreation, enseignant: EnseignantCourant, session: SessionDB) -> RessourceDetail:
    if corps.type == TypeRessource.PDF:
        nb_pdf = session.scalar(
            select(func.count()).select_from(models.Ressource).where(
                models.Ressource.auteur_id == enseignant.id, models.Ressource.type == TypeRessource.PDF
            )
        )
        if nb_pdf >= settings.pdf_max_par_enseignant:
            raise HTTPException(409, f"Limite de {settings.pdf_max_par_enseignant} PDF atteinte.")
    r = models.Ressource(portee=PorteeRessource.CLASSE, auteur=enseignant)
    ressources.appliquer(session, r, corps, enseignant)
    session.add(r)
    session.commit()
    return ressources.detail(session, r)


@router.post("/ressources/{ressource_id}", response_model=RessourceDetail)
def modifier_ressource(
    ressource_id: int, corps: RessourceCreation, enseignant: EnseignantCourant, session: SessionDB
) -> RessourceDetail:
    r = _ma_ressource(session, ressource_id, enseignant)
    ressources.appliquer(session, r, corps, enseignant)
    session.commit()
    return ressources.detail(session, r)


@router.put("/ressources/{ressource_id}/fichier", response_model=RessourceDetail)
async def envoyer_pdf(ressource_id: int, request: Request, enseignant: EnseignantCourant, session: SessionDB) -> RessourceDetail:
    """Corps de la requête = le PDF brut (Content-Type: application/pdf)."""
    r = _ma_ressource(session, ressource_id, enseignant)
    if r.type != TypeRessource.PDF:
        raise HTTPException(422, "Cette ressource est un lien, pas un PDF.")
    ressources.enregistrer_pdf(r, await _lire_corps(request))
    session.commit()
    return ressources.detail(session, r)


async def _lire_corps(request: Request) -> bytes:
    """Lit le corps en s'arrêtant dès que la taille maximale est dépassée."""
    limite = settings.pdf_taille_max_mo * 1024 * 1024
    morceaux, total = [], 0
    async for morceau in request.stream():
        total += len(morceau)
        if total > limite:
            raise HTTPException(413, f"Le PDF dépasse {settings.pdf_taille_max_mo} Mo.")
        morceaux.append(morceau)
    return b"".join(morceaux)


@router.delete("/ressources/{ressource_id}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_ressource(ressource_id: int, enseignant: EnseignantCourant, session: SessionDB) -> Response:
    r = _ma_ressource(session, ressource_id, enseignant)
    fichier = r.fichier
    session.delete(r)
    session.commit()
    ressources.supprimer_fichier(fichier)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

