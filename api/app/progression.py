"""Calculs de progression partagés entre la vue élève et la vue enseignant."""

from collections import Counter
from datetime import UTC, datetime
from urllib.parse import quote

from fastapi.responses import JSONResponse

from pkp_engine import calculer_maitrise, est_maitrisee
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import inscriptions
from app.db import models
from app.config import settings
from app.db.conversions import historique_eleve
from app.referentiel import StatutValidation
from app.schemas import AvancementCompetence, EleveResume, PageHistorique, ProgressionCompetence, ReponseHistorique

TAILLE_PAGE_HISTORIQUE = 30
# Méthode PKP : bonnes réponses attendues avant de passer à l'étape suivante.
OBJECTIF_BASES = 3
OBJECTIF_AVANCEES = 2


def programme_de(classe: models.Classe):
    """Conditions SQL : chapitres du niveau ET du parcours (spécialité) de la classe."""
    return (models.Chapitre.niveau == classe.niveau, models.Chapitre.parcours == classe.parcours)


def chapitres_du_programme(session: Session, classe: models.Classe) -> list[models.Chapitre]:
    """Tous les chapitres du niveau et du parcours de la classe, dans l'ordre de l'année."""
    return list(
        session.scalars(
            select(models.Chapitre)
            .where(*programme_de(classe), models.Chapitre.masque.is_(False))
            .order_by(models.Chapitre.ordre)
        )
    )


def ids_ouverts(classe: models.Classe) -> list[int]:
    """Chapitres que l'enseignant a ouverts pour cette classe (hors chapitres masqués par un administrateur)."""
    return [c.id for c in classe.chapitres_proposes if not c.masque]


def filtre_validation() -> tuple:
    """Questions servables (requête jointe à `competence`) : jamais celles d'une compétence masquée ;
    en production, on peut ne servir que les questions validées par un enseignant."""
    masque = (models.Competence.masque.is_(False),)
    if settings.servir_questions_non_validees:
        return masque
    return (*masque, models.Question.statut_validation == StatutValidation.VALIDEE)


def nb_questions_servables(session: Session, chapitre_ids: list[int]) -> dict[int, int]:
    """Nombre de questions qu'un élève peut recevoir, par chapitre."""
    lignes = session.execute(
        select(models.Competence.chapitre_id, func.count(models.Question.id))
        .join(models.Question, models.Question.competence_id == models.Competence.id)
        .where(models.Competence.chapitre_id.in_(chapitre_ids), models.Question.archivee.is_(False), *filtre_validation())
        .group_by(models.Competence.chapitre_id)
    )
    return dict(lignes.all())


def competences_du_niveau(session: Session, eleve: models.Eleve) -> list[models.Competence]:
    """Compétences des chapitres ouverts de la classe de l'élève."""
    return list(
        session.scalars(
            select(models.Competence)
            .join(models.Chapitre)
            .where(models.Chapitre.id.in_(ids_ouverts(eleve.classe)), models.Competence.masque.is_(False))
            .order_by(models.Chapitre.ordre, models.Competence.ordre)
        )
    )


def progression_eleve(session: Session, eleve: models.Eleve) -> list[ProgressionCompetence]:
    historique = historique_eleve(session, eleve.id)
    nb_par_competence = Counter(r.competence_id for r in historique)
    return [
        ProgressionCompetence(
            competence_id=c.id,
            code=c.code,
            libelle=c.libelle,
            chapitre=c.chapitre.titre,
            nb_reponses=nb_par_competence[c.id],
            maitrise=calculer_maitrise(historique, c.id),
            maitrisee=est_maitrisee(historique, c.id),
        )
        for c in competences_du_niveau(session, eleve)
    ]


def resume_eleve(session: Session, eleve: models.Eleve) -> EleveResume:
    historique = historique_eleve(session, eleve.id)
    competences = competences_du_niveau(session, eleve)
    return EleveResume(
        id=eleve.id,
        prenom=eleve.prenom,
        a_un_code=eleve.code_hash is not None,
        nb_reponses=len(historique),
        taux_reussite=sum(r.correcte for r in historique) / len(historique) if historique else None,
        competences_maitrisees=sum(est_maitrisee(historique, c.id) for c in competences),
        competences_total=len(competences),
        classes_liees=[e.classe.code for e in inscriptions.liees(session, eleve)],
    )


def export_eleve(session: Session, eleve: models.Eleve) -> JSONResponse:
    """Droit d'accès et de portabilité (RGPD) : toutes les données d'un élève, en JSON."""
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


def historique_reponses(
    session: Session, eleve: models.Eleve, page: int = 1, erreurs_seulement: bool = False, competence_id: int | None = None
) -> PageHistorique:
    """Réponses de l'élève, de la plus récente à la plus ancienne, avec la correction de chaque question."""
    filtres = [models.Seance.eleve_id == eleve.id]
    if competence_id is not None:
        filtres.append(models.Question.competence_id == competence_id)
    base = (
        select(models.Reponse, models.Question, models.Competence, models.Chapitre)
        .join(models.Seance, models.Seance.id == models.Reponse.seance_id)
        .join(models.Question, models.Question.id == models.Reponse.question_id)
        .join(models.Competence, models.Competence.id == models.Question.competence_id)
        .join(models.Chapitre, models.Chapitre.id == models.Competence.chapitre_id)
        .where(*filtres)
    )
    total = session.scalar(select(func.count()).select_from(base.subquery()))
    erreurs = session.scalar(select(func.count()).select_from(base.where(models.Reponse.correcte.is_(False)).subquery()))
    if erreurs_seulement:
        base = base.where(models.Reponse.correcte.is_(False))
    lignes = session.execute(
        base.order_by(models.Reponse.repondu_le.desc(), models.Reponse.id.desc())
        .offset((max(page, 1) - 1) * TAILLE_PAGE_HISTORIQUE)
        .limit(TAILLE_PAGE_HISTORIQUE)
    ).all()
    return PageHistorique(
        total=total,
        erreurs=erreurs,
        elements=[
            ReponseHistorique(
                id=r.id, repondu_le=r.repondu_le, seance_id=r.seance_id, question_id=q.id, competence_id=c.id,
                competence=c.libelle, chapitre=ch.titre, enonce=q.enonce, type=q.type, difficulte=q.difficulte,
                reponse_donnee=r.reponse_donnee, correcte=r.correcte, solution=q.solution, correction=q.correction,
                duree_s=round(r.duree_s, 1),
            )
            for r, q, c, ch in lignes
        ],
    )


def avancement_competence(session: Session, eleve: models.Eleve, competence: models.Competence) -> AvancementCompetence:
    """Bonnes réponses par niveau (1 à 3, puis 4 et 5) et maîtrise calculée par le moteur."""
    lignes = session.execute(
        select(models.Question.difficulte, models.Reponse.correcte)
        .join(models.Reponse, models.Reponse.question_id == models.Question.id)
        .join(models.Seance, models.Seance.id == models.Reponse.seance_id)
        .where(models.Seance.eleve_id == eleve.id, models.Question.competence_id == competence.id)
    ).all()
    historique = historique_eleve(session, eleve.id)
    return AvancementCompetence(
        competence_id=competence.id,
        libelle=competence.libelle,
        reponses=len(lignes),
        reussies_bases=sum(1 for d, ok in lignes if ok and d <= 3),
        objectif_bases=OBJECTIF_BASES,
        reussies_avancees=sum(1 for d, ok in lignes if ok and d >= 4),
        objectif_avancees=OBJECTIF_AVANCEES,
        maitrise=calculer_maitrise(historique, competence.id),
        maitrisee=est_maitrisee(historique, competence.id),
    )
