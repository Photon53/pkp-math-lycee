"""Calculs de progression partagés entre la vue élève et la vue enseignant."""

from collections import Counter

from pkp_engine import calculer_maitrise, est_maitrisee
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import models
from app.config import settings
from app.db.conversions import historique_eleve
from app.referentiel import StatutValidation
from app.schemas import EleveResume, ProgressionCompetence


def programme_de(classe: models.Classe):
    """Conditions SQL : chapitres du niveau ET du parcours (spécialité) de la classe."""
    return (models.Chapitre.niveau == classe.niveau, models.Chapitre.parcours == classe.parcours)


def chapitres_du_programme(session: Session, classe: models.Classe) -> list[models.Chapitre]:
    """Tous les chapitres du niveau et du parcours de la classe, dans l'ordre de l'année."""
    return list(session.scalars(select(models.Chapitre).where(*programme_de(classe)).order_by(models.Chapitre.ordre)))


def ids_ouverts(classe: models.Classe) -> list[int]:
    """Chapitres que l'enseignant a ouverts pour cette classe."""
    return [c.id for c in classe.chapitres_proposes]


def filtre_validation() -> tuple:
    """En production, on peut ne servir que les questions validées par un enseignant."""
    if settings.servir_questions_non_validees:
        return ()
    return (models.Question.statut_validation == StatutValidation.VALIDEE,)


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
            .where(models.Chapitre.id.in_(ids_ouverts(eleve.classe)))
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
    )
