"""Calculs de progression partagés entre la vue élève et la vue enseignant."""

from collections import Counter

from pkp_engine import calculer_maitrise, est_maitrisee
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.db.conversions import historique_eleve
from app.schemas import EleveResume, ProgressionCompetence


def competences_du_niveau(session: Session, eleve: models.Eleve) -> list[models.Competence]:
    return list(
        session.scalars(
            select(models.Competence)
            .join(models.Chapitre)
            .where(models.Chapitre.niveau == eleve.classe.niveau)
            .order_by(models.Chapitre.ordre, models.Competence.code)
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
