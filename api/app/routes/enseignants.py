"""Espace enseignant : classes, suivi des élèves, banque de questions.

Un enseignant ne voit que ses classes et leurs élèves (404 sinon, pour ne pas
révéler l'existence des autres). La banque de questions est commune.
"""

import secrets
from datetime import UTC, datetime
from functools import cache
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pkp_engine import ExpressionInvalide, Niveau, corriger
from sqlalchemy import func, select

from app import limitation
from app.auth import ENSEIGNANT, EnseignantCourant, SessionDB
from app.config import settings
from app.db import models
from app.db.conversions import question_vers_domaine
from app.progression import progression_eleve, resume_eleve
from app.schemas import (
    ClasseCreation,
    ClasseResume,
    CompetenceInfo,
    ConnexionEnseignant,
    EleveResume,
    JetonEnseignant,
    ProgressionCompetence,
    QuestionCreation,
    QuestionEnseignant,
)
from app.security import (
    creer_jeton,
    doit_rehacher,
    hacher_mot_de_passe,
    verifier_mot_de_passe,
    version_mot_de_passe,
)

router = APIRouter(prefix="/enseignants", tags=["enseignant"])

PREFIXES_CODE = {Niveau.SECONDE: "2NDE", Niveau.PREMIERE: "1RE", Niveau.TERMINALE: "TLE"}
# Sans 0/O ni 1/I/L : le code est recopié à la main par des élèves.
ALPHABET_CODE = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


@cache
def _empreinte_leurre() -> str:
    return hacher_mot_de_passe(secrets.token_hex(16))


@router.post("/connexion", response_model=JetonEnseignant)
def connexion(corps: ConnexionEnseignant, request: Request, session: SessionDB) -> JetonEnseignant:
    ip = limitation.adresse_ip(request)
    compte = f"email:{corps.email}"
    # Le compte est bloqué même si le mot de passe est enfin le bon : sinon
    # l'attaquant saurait qu'il a trouvé.
    limitation.verifier((limitation.par_ip, ip), (limitation.echecs_enseignant, compte))
    limitation.par_ip.enregistrer(ip)

    enseignant = session.scalar(select(models.Enseignant).where(models.Enseignant.email == corps.email))
    # Même calcul (et même durée) que l'email existe ou non : on ne révèle pas les comptes.
    empreinte = enseignant.mot_de_passe_hash if enseignant else _empreinte_leurre()
    if not verifier_mot_de_passe(corps.mot_de_passe, empreinte) or enseignant is None:
        limitation.echecs_enseignant.enregistrer(compte)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email ou mot de passe incorrect.")
    limitation.echecs_enseignant.effacer(compte)
    if doit_rehacher(enseignant.mot_de_passe_hash):
        # Empreinte calculée avec un coût plus faible que l'actuel (audit A-06) : on la
        # renforce maintenant que le mot de passe est connu. Les anciens jetons deviennent invalides.
        enseignant.mot_de_passe_hash = hacher_mot_de_passe(corps.mot_de_passe)
        session.commit()
    version = version_mot_de_passe(enseignant.mot_de_passe_hash)
    return JetonEnseignant(
        jeton=creer_jeton(ENSEIGNANT, enseignant.id, settings.duree_jeton_enseignant_h, version), nom=enseignant.nom
    )


# --- Classes et élèves ------------------------------------------------------


def _resume_classe(session: SessionDB, classe: models.Classe) -> ClasseResume:
    nb = session.scalar(select(func.count()).select_from(models.Eleve).where(models.Eleve.classe_id == classe.id))
    return ClasseResume(id=classe.id, code=classe.code, niveau=classe.niveau, nb_eleves=nb)


@router.get("/classes", response_model=list[ClasseResume])
def mes_classes(enseignant: EnseignantCourant, session: SessionDB) -> list[ClasseResume]:
    classes = session.scalars(
        select(models.Classe).where(models.Classe.enseignant_id == enseignant.id).order_by(models.Classe.code)
    )
    return [_resume_classe(session, c) for c in classes]


@router.post("/classes", response_model=ClasseResume, status_code=status.HTTP_201_CREATED)
def creer_classe(corps: ClasseCreation, enseignant: EnseignantCourant, session: SessionDB) -> ClasseResume:
    while True:
        code = f"{PREFIXES_CODE[corps.niveau]}-" + "".join(secrets.choice(ALPHABET_CODE) for _ in range(5))
        if not session.scalar(select(models.Classe).where(models.Classe.code == code)):
            break
    classe = models.Classe(code=code, niveau=corps.niveau, enseignant=enseignant)
    session.add(classe)
    session.commit()
    return _resume_classe(session, classe)


def _ma_classe(session: SessionDB, classe_id: int, enseignant: models.Enseignant) -> models.Classe:
    classe = session.get(models.Classe, classe_id)
    if classe is None or classe.enseignant_id != enseignant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Classe introuvable.")
    return classe


def _mon_eleve(session: SessionDB, eleve_id: int, enseignant: models.Enseignant) -> models.Eleve:
    eleve = session.get(models.Eleve, eleve_id)
    if eleve is None or eleve.classe.enseignant_id != enseignant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Élève introuvable.")
    return eleve


@router.get("/classes/{classe_id}/eleves", response_model=list[EleveResume])
def eleves_de_la_classe(classe_id: int, enseignant: EnseignantCourant, session: SessionDB) -> list[EleveResume]:
    classe = _ma_classe(session, classe_id, enseignant)
    return [resume_eleve(session, e) for e in sorted(classe.eleves, key=lambda e: e.prenom)]


@router.get("/eleves/{eleve_id}/progression", response_model=list[ProgressionCompetence])
def progression(eleve_id: int, enseignant: EnseignantCourant, session: SessionDB) -> list[ProgressionCompetence]:
    return progression_eleve(session, _mon_eleve(session, eleve_id, enseignant))


@router.get("/eleves/{eleve_id}/export")
def exporter_eleve(eleve_id: int, enseignant: EnseignantCourant, session: SessionDB) -> JSONResponse:
    """Droit d'accès et de portabilité (RGPD) : toutes les données d'un élève, en JSON."""
    eleve = _mon_eleve(session, eleve_id, enseignant)
    donnees = {
        "exporte_le": datetime.now(UTC).isoformat(),
        "eleve": {
            "prenom": eleve.prenom,
            "classe": eleve.classe.code,
            "niveau": eleve.classe.niveau.value,
            "cree_le": eleve.cree_le.isoformat(),
        },
        "seances": [
            {
                "debut": s.debut.isoformat(),
                "fin": s.fin.isoformat() if s.fin else None,
                "reponses": [
                    {
                        "question": r.question.enonce,
                        "reponse_donnee": r.reponse_donnee,
                        "correcte": r.correcte,
                        "duree_s": round(r.duree_s, 1),
                        "repondu_le": r.repondu_le.isoformat(),
                    }
                    for r in sorted(s.reponses, key=lambda r: (r.repondu_le, r.id))
                ],
            }
            for s in sorted(eleve.seances, key=lambda s: (s.debut, s.id))
        ],
        "progression": [p.model_dump() for p in progression_eleve(session, eleve)],
    }
    nom = f"pkp-{eleve.classe.code}-{eleve.prenom}.json".replace(" ", "_")
    # filename* (RFC 5987) : les prénoms accentués restent lisibles.
    return JSONResponse(donnees, headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(nom)}"})


@router.delete("/classes/{classe_id}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_classe(classe_id: int, enseignant: EnseignantCourant, session: SessionDB) -> Response:
    """Fin d'année : supprime la classe, ses élèves, leurs séances et réponses."""
    session.delete(_ma_classe(session, classe_id, enseignant))
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/eleves/{eleve_id}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_eleve(eleve_id: int, enseignant: EnseignantCourant, session: SessionDB) -> Response:
    """Droit à l'effacement (RGPD) : supprime l'élève, ses séances et ses réponses."""
    session.delete(_mon_eleve(session, eleve_id, enseignant))
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Banque de questions ----------------------------------------------------


@router.get("/competences", response_model=list[CompetenceInfo])
def competences(_: EnseignantCourant, session: SessionDB) -> list[CompetenceInfo]:
    lignes = session.scalars(
        select(models.Competence).join(models.Chapitre).order_by(models.Chapitre.niveau, models.Chapitre.ordre, models.Competence.code)
    )
    return [
        CompetenceInfo(id=c.id, code=c.code, libelle=c.libelle, chapitre=c.chapitre.titre, niveau=c.chapitre.niveau)
        for c in lignes
    ]


@router.get("/questions", response_model=list[QuestionEnseignant])
def questions(
    _: EnseignantCourant, session: SessionDB, competence_id: int | None = None, archivees: bool = False
) -> list[models.Question]:
    requete = select(models.Question).order_by(models.Question.competence_id, models.Question.difficulte, models.Question.id)
    if competence_id is not None:
        requete = requete.where(models.Question.competence_id == competence_id)
    if not archivees:
        requete = requete.where(models.Question.archivee.is_(False))
    return list(session.scalars(requete))


@router.post("/questions", response_model=QuestionEnseignant, status_code=status.HTTP_201_CREATED)
def creer_question(corps: QuestionCreation, _: EnseignantCourant, session: SessionDB) -> models.Question:
    if session.get(models.Competence, corps.competence_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Compétence introuvable.")
    question = models.Question(**corps.model_dump())
    # La solution doit être comprise par le moteur, sinon aucun élève ne pourrait réussir.
    try:
        lisible = corriger(question_vers_domaine(question), corps.solution)
    except ExpressionInvalide:
        lisible = False
    if not lisible:
        raise HTTPException(422, "Solution illisible par le moteur de correction.")
    session.add(question)
    session.commit()
    return question


@router.post("/questions/{question_id}/archiver", response_model=QuestionEnseignant)
def archiver_question(question_id: int, _: EnseignantCourant, session: SessionDB) -> models.Question:
    """Retire la question des tirages. Elle n'est jamais supprimée : l'historique reste lisible."""
    question = session.get(models.Question, question_id)
    if question is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question introuvable.")
    question.archivee = True
    session.commit()
    return question
