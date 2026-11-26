"""Calculs de progression partagés entre la vue élève et la vue enseignant."""

from collections import Counter
from datetime import UTC, datetime
from urllib.parse import quote

from fastapi.responses import JSONResponse

from pkp_engine import TypeQuestion, calculer_maitrise, est_maitrisee
from sqlalchemy import func, select
from sqlalchemy.orm import Session, contains_eager

from app import exemplaires, inscriptions
from app.db import models
from app.config import settings
from app.db.conversions import historique_eleve
from app.referentiel import NatureChapitre, StatutValidation
from app.schemas import AvancementCompetence, EleveResume, PageHistorique, ProgressionCompetence, ReponseHistorique

TAILLE_PAGE_HISTORIQUE = 30
# Méthode PKP : bonnes réponses attendues avant de passer à l'étape suivante.
OBJECTIF_BASES = 3
OBJECTIF_AVANCEES = 2


def programme_de(classe: models.Classe):
    """Conditions SQL : chapitres du domaine (maths ou français), du niveau ET du parcours (spécialité) de la classe.
    Jamais un chapitre de diagnostic (issue #162) : il ne s'ouvre pas comme un chapitre d'entraînement."""
    return (
        models.Chapitre.domaine_code == classe.domaine_code,
        models.Chapitre.niveau == classe.niveau,
        models.Chapitre.parcours == classe.parcours,
        *filtre_apprentissage(),
    )


def filtre_apprentissage() -> tuple:
    """Condition SQL : chapitres d'apprentissage seulement. Un chapitre de diagnostic n'est jamais servi en séance,
    ni ouvert à une classe, ni montré aux enfants et aux parents (issue #162)."""
    return (models.Chapitre.nature == NatureChapitre.APPRENTISSAGE,)


def est_apprentissage(chapitre: models.Chapitre) -> bool:
    return chapitre.nature is NatureChapitre.APPRENTISSAGE


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
    """Chapitres que l'enseignant a ouverts pour cette classe (hors chapitres masqués par un administrateur).

    Vue du professeur. Côté élève, utiliser `ids_ouverts_eleve`, qui applique l'ouverture du domaine (#176).
    """
    return [c.id for c in classe.chapitres_proposes if not c.masque and est_apprentissage(c)]


def ids_ouverts_eleve(session: Session, classe: models.Classe) -> list[int]:
    """Chapitres ouverts que les élèves de la classe peuvent lire : aucun si l'accès à la classe est refusé (#176)."""
    from app.permissions import refus_acces_classe

    return [] if refus_acces_classe(session, classe) else ids_ouverts(classe)


def filtre_validation() -> tuple:
    """Questions servables (requête jointe à `competence`) : jamais celles d'une compétence masquée ;
    en production, on peut ne servir que les questions validées par un enseignant."""
    masque = (models.Competence.masque.is_(False),)
    if settings.servir_questions_non_validees:
        return masque
    return (*masque, models.Question.statut_validation == StatutValidation.VALIDEE)


def validees_en_priorite(session: Session, questions: list) -> list:
    """Une compétence qui a au moins une question validée (non archivée, quelle que soit sa difficulté)
    ne sert plus que ses questions validées : la banque passe aux questions relues compétence par
    compétence, au rythme de la validation. Le filtre de difficulté d'une séance ne change pas la règle.
    `questions` : objets ou lignes portant `competence_id` et `statut_validation`."""
    validees = set(
        session.scalars(
            select(models.Question.competence_id).distinct().where(
                models.Question.competence_id.in_({q.competence_id for q in questions}),
                models.Question.archivee.is_(False),
                models.Question.statut_validation == StatutValidation.VALIDEE,
            )
        )
    )
    return [q for q in questions if q.competence_id not in validees or q.statut_validation == StatutValidation.VALIDEE]


def nb_questions_servables(session: Session, chapitre_ids: list[int]) -> dict[int, int]:
    """Nombre de questions qu'un élève peut recevoir, par chapitre (même règle que `validees_en_priorite`)."""
    lignes = session.execute(
        select(
            models.Competence.chapitre_id,
            models.Competence.id,
            models.Question.statut_validation == StatutValidation.VALIDEE,
            func.count(models.Question.id),
        )
        .join(models.Question, models.Question.competence_id == models.Competence.id)
        .where(
            models.Competence.chapitre_id.in_(chapitre_ids), models.Question.archivee.is_(False),
            models.Question.type != TypeQuestion.REDACTION,  # #179 : jamais servie en séance
            *filtre_validation(),
        )
        .group_by(models.Competence.chapitre_id, models.Competence.id, models.Question.statut_validation)
    )
    par_competence: dict[tuple[int, int], Counter] = {}
    for chapitre_id, competence_id, validee, nb in lignes:
        par_competence.setdefault((chapitre_id, competence_id), Counter())[bool(validee)] += nb
    total: Counter = Counter()
    for (chapitre_id, _), nb in par_competence.items():
        total[chapitre_id] += nb[True] or nb[False]
    return dict(total)


def competences_du_niveau(session: Session, eleve: models.Eleve) -> list[models.Competence]:
    """Compétences des chapitres ouverts de la classe de l'élève."""
    return list(
        session.scalars(
            select(models.Competence)
            .join(models.Chapitre)
            .where(models.Chapitre.id.in_(ids_ouverts(eleve.classe)), models.Competence.masque.is_(False))
            .order_by(models.Chapitre.ordre, models.Competence.ordre)
            # Le chapitre est déjà joint : pas une requête de plus par compétence pour lire son titre.
            .options(contains_eager(models.Competence.chapitre))
        )
    )


def _acces_refuse(session: Session, eleve: models.Eleve) -> bool:
    from app.permissions import refus_acces_classe

    return refus_acces_classe(session, eleve.classe) is not None


def progression_eleve(session: Session, eleve: models.Eleve, limiter: bool = False) -> list[ProgressionCompetence]:
    """Progression par compétence des chapitres ouverts de la classe.

    `limiter` (vue de l'élève et de son parent, #176, décision du 19/11/2026) : si la classe n'a pas accès à son
    domaine (domaine fermé, classe non pilote ou révoquée), seules les compétences déjà travaillées sont listées,
    pour ne pas révéler le programme d'un domaine fermé. La vue du professeur n'est pas limitée.
    """
    historique = historique_eleve(session, eleve.id)
    nb_par_competence = Counter(r.competence_id for r in historique)
    competences = competences_du_niveau(session, eleve)
    if limiter and _acces_refuse(session, eleve):
        competences = [c for c in competences if nb_par_competence[c.id]]
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
        for c in competences
    ]


def resume_eleve(session: Session, eleve: models.Eleve) -> EleveResume:
    historique = historique_eleve(session, eleve.id)
    competences = competences_du_niveau(session, eleve)
    return EleveResume(
        id=eleve.id,
        prenom=eleve.prenom,
        identifiant=eleve.identifiant or (eleve.enfant.identifiant if eleve.enfant else None),
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
        # Issue #162 : réponses au diagnostic, conservées à part de la progression (taux de maîtrise).
        # Issue #179 (RGPD-2) : rédactions de l'élève, toutes versions, avec le commentaire du professeur.
        "redactions": [
            {
                "sujet": r.question.enonce,
                "version": r.version,
                "texte": r.texte,
                "statut": r.statut,
                "commentaire": r.commentaire,
                "remise_le": r.remise_le.isoformat() if r.remise_le else None,
                "corrigee_le": r.corrigee_le.isoformat() if r.corrigee_le else None,
                "conserver_jusqu_au": r.conserver_jusqu_au.isoformat(),
            }
            for r in session.scalars(
                select(models.Redaction).where(models.Redaction.eleve_id == eleve.id)
                .order_by(models.Redaction.question_id, models.Redaction.version)
            )
        ],
        # Issue #217 : dossiers de français (quiz, auto-évaluation, réponses rédigées avec le retour du professeur).
        "francais": {
            "progression": [
                {"dossier": p.code, "meilleur_score": p.meilleur_score, "premier_score": p.premier_score,
                 "total": p.total, "tentatives": p.tentatives, "auto_evaluation": p.auto_evaluation}
                for p in session.scalars(select(models.ProgressionFrancais)
                                         .where(models.ProgressionFrancais.eleve_id == eleve.id)
                                         .order_by(models.ProgressionFrancais.code))
            ],
            "reponses_quiz": [
                {"dossier": r.code, "essai": r.essai, "question": r.question, "choix": r.choix, "juste": r.juste,
                 "repondu_le": r.repondu_le.isoformat()}
                for r in session.scalars(select(models.ReponseQuizFrancais)
                                         .where(models.ReponseQuizFrancais.eleve_id == eleve.id)
                                         .order_by(models.ReponseQuizFrancais.code, models.ReponseQuizFrancais.essai,
                                                   models.ReponseQuizFrancais.question))
            ],
            "reponses_redigees": [
                {"dossier": r.code, "question": r.question, "texte": r.texte, "statut": r.statut,
                 "commentaire": r.commentaire, "remise_le": r.remise_le.isoformat() if r.remise_le else None,
                 "corrigee_le": r.corrigee_le.isoformat() if r.corrigee_le else None,
                 "conserver_jusqu_au": r.conserver_jusqu_au.isoformat()}
                for r in session.scalars(select(models.ReponseRedigeeFrancais)
                                         .where(models.ReponseRedigeeFrancais.eleve_id == eleve.id)
                                         .order_by(models.ReponseRedigeeFrancais.code, models.ReponseRedigeeFrancais.question))
            ],
        },
        "observations_diagnostic": [
            {
                "question": o.question.enonce,
                "reponse_donnee": o.reponse_donnee,
                "statut": o.statut.value,
                "observe_le": o.observe_le.isoformat(),
                "corrige_le": o.corrige_le.isoformat() if o.corrige_le else None,
            }
            for o in session.scalars(
                select(models.ObservationDiagnostic)
                .where(models.ObservationDiagnostic.eleve_id == eleve.id)
                .order_by(models.ObservationDiagnostic.observe_le, models.ObservationDiagnostic.id)
            )
        ],
    }
    nom = f"pkp-{eleve.classe.code}-{eleve.prenom}.json".replace(" ", "_")
    # filename* (RFC 5987) : les prénoms accentués restent lisibles.
    return JSONResponse(donnees, headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(nom)}"})


def historique_reponses(
    session: Session, eleve: models.Eleve, page: int = 1, erreurs_seulement: bool = False, competence_id: int | None = None,
    pour_parent: bool = False,
) -> PageHistorique:
    """Réponses de l'élève, de la plus récente à la plus ancienne, avec la correction de chaque question.

    `pour_parent` (#176, SEC-D6 option b) : si la classe n'a pas accès à son domaine, énoncé, solution et correction
    sont retirés ; la réponse donnée, le résultat et les libellés restent (données de l'enfant).
    """
    masquer = pour_parent and _acces_refuse(session, eleve)
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
                competence=c.libelle, chapitre=ch.titre, type=q.type,
                difficulte=q.difficulte, reponse_donnee=r.reponse_donnee, correcte=r.correcte, duree_s=round(r.duree_s, 1),
                **({"enonce": "", "solution": "", "correction": None, "contenu_masque": True} if masquer else {
                    "enonce": exemplaires.enonce(q, r.tirage), "solution": exemplaires.solution(q, r.tirage),
                    "correction": exemplaires.correction(q, r.tirage)}),
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
