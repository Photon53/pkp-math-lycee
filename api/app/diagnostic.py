# Issue #162 — Diagnostic des acquis antérieurs, lot 2 (Claude)
"""Diagnostic des acquis antérieurs : règles de diffusion et observations.

- **Diffusion** : une question de diagnostic n'atteint un élève que si elle est **validée** par un professeur, quel
  que soit `PKP_SERVIR_QUESTIONS_NON_VALIDEES` (ce réglage ne concerne que l'entraînement). Les chapitres de
  diagnostic ne passent jamais par les séances d'entraînement (`progression.filtre_apprentissage`).
- **Public** : seulement un élève d'une classe active du niveau du chapitre, dont le parcours figure dans `publics`.
- **Observations** : table `observation_diagnostic`, distincte de `reponse`. Le taux de maîtrise, calculé sur
  `reponse`, ne les lit jamais.
- **Rédaction** : jamais corrigée par le moteur ; « en attente de correction » jusqu'à la décision d'un professeur.
- **Choix multiples** : ensemble exact des lettres cochées, sans crédit partiel (voir `pkp_engine.correction`).

- **Passation** (lot 3) : ouverte par le professeur pour sa classe (`Classe.diagnostic_ouvert`), une passation par
  inscription, une question à la fois servie par le serveur (`pkp_engine.diagnostic`), aucune correction montrée à
  l'élève, « Je ne sais pas » distinct d'une erreur. Une compétence « à reprendre » ouvre ses compétences de `retour`
  (diagnostic du niveau précédent) : elles font partie des questions diffusables à l'élève.

Le dépôt de fichiers (lot 4) et le bilan (lot 5) s'appuient sur ce module.
"""

from datetime import UTC, datetime

from pkp_engine import Verdict, corrige_automatiquement, verifier
from pkp_engine import diagnostic as moteur
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.db.conversions import question_vers_domaine
from app.referentiel import NatureChapitre, Role, StatutObservation, StatutValidation, domaine_maths

LONGUEUR_REPONSE_COURTE = 200
LONGUEUR_REDACTION = 4000


class DiagnosticRefuse(Exception):
    """Action refusée : question non diffusable, élève hors du public, observation déjà corrigée…"""


def filtre_diffusable() -> tuple:
    """Conditions SQL (requête jointe à `competence` et `chapitre`) : questions de diagnostic montrables à un élève."""
    return (
        models.Chapitre.nature == NatureChapitre.DIAGNOSTIC,
        models.Chapitre.masque.is_(False),
        models.Competence.masque.is_(False),
        models.Question.archivee.is_(False),
        models.Question.statut_validation == StatutValidation.VALIDEE,
    )


def chapitres_du_public(session: Session, classe: models.Classe) -> list[models.Chapitre]:
    """Chapitres de diagnostic destinés à cette classe : même niveau, parcours de la classe dans `publics`."""
    if classe.archivee_le is not None:
        return []
    candidats = session.scalars(
        select(models.Chapitre)
        .where(
            models.Chapitre.nature == NatureChapitre.DIAGNOSTIC,
            models.Chapitre.masque.is_(False),
            models.Chapitre.niveau == classe.niveau,
            models.Chapitre.domaine_code == domaine_maths(classe.niveau),
        )
        .order_by(models.Chapitre.ordre)
    )
    return [c for c in candidats if classe.parcours.value in (c.publics or [])]


def plan(session: Session, classe: models.Classe) -> tuple[list[models.Competence], dict[int, models.Competence]]:
    """Compétences du questionnaire d'entrée de la classe (dans l'ordre), et toutes les compétences joignables par
    leurs retours (diagnostics des niveaux précédents), par identifiant."""
    entree = [
        c
        for ch in chapitres_du_public(session, classe)
        for c in sorted(ch.competences, key=lambda c: (c.ordre, c.code))
        if not c.masque
    ]
    toutes = {c.id: c for c in entree}
    a_suivre = list(entree)
    while a_suivre:
        competence = a_suivre.pop()
        for code in competence.retour or []:
            cible = session.scalar(select(models.Competence).where(models.Competence.code == code))
            if (
                cible is not None and cible.id not in toutes and not cible.masque
                and cible.chapitre.nature is NatureChapitre.DIAGNOSTIC and not cible.chapitre.masque
            ):
                toutes[cible.id] = cible
                a_suivre.append(cible)
    return entree, toutes


def questions_diffusables(session: Session, classe: models.Classe) -> list[models.Question]:
    """Questions de diagnostic qu'un élève de cette classe peut recevoir (entrée et retours) : validées seulement."""
    _, competences = plan(session, classe)
    if not competences:
        return []
    return list(
        session.scalars(
            select(models.Question)
            .join(models.Competence, models.Question.competence_id == models.Competence.id)
            .join(models.Chapitre, models.Competence.chapitre_id == models.Chapitre.id)
            .where(models.Competence.id.in_(competences), *filtre_diffusable())
            .order_by(models.Chapitre.niveau, models.Chapitre.ordre, models.Competence.ordre, models.Question.difficulte,
                      models.Question.id)
        )
    )


def est_diffusable(session: Session, question: models.Question, eleve: models.Eleve) -> bool:
    return question.id in {q.id for q in questions_diffusables(session, eleve.classe)}


def statut_automatique(question: models.Question, reponse_donnee: str) -> StatutObservation:
    """Juste ou faux selon le moteur ; « en attente de correction » pour une réponse rédigée (jamais le moteur)."""
    domaine = question_vers_domaine(question)
    if not corrige_automatiquement(domaine):
        return StatutObservation.EN_ATTENTE
    # Une valeur juste mais pas sous la forme demandée n'est pas une réussite (Verdict.FORME).
    return StatutObservation.JUSTE if verifier(domaine, reponse_donnee) is Verdict.JUSTE else StatutObservation.FAUX


def enregistrer_observation(
    session: Session, eleve: models.Eleve, question: models.Question, reponse_donnee: str | None,
    *, ne_sait_pas: bool = False, passation: "models.PassationDiagnostic | None" = None, duree_s: float | None = None,
) -> models.ObservationDiagnostic:
    """Enregistre la réponse d'un élève à une question de diagnostic (dans `observation_diagnostic`, jamais dans
    `reponse`). « Je ne sais pas » est enregistré tel quel, distinct d'une réponse fausse. Lève `DiagnosticRefuse`
    si la question n'est pas diffusable à cet élève."""
    if not est_diffusable(session, question, eleve):
        raise DiagnosticRefuse("Question de diagnostic non disponible pour cet élève (non validée ou hors public).")
    if ne_sait_pas:
        reponse_donnee, statut = "", StatutObservation.NE_SAIT_PAS
    else:
        reponse_donnee = (reponse_donnee or "").strip()
        if not reponse_donnee:
            raise DiagnosticRefuse("Réponse vide : écris une réponse ou choisis « Je ne sais pas ».")
        limite = LONGUEUR_REDACTION if not corrige_automatiquement(question_vers_domaine(question)) else LONGUEUR_REPONSE_COURTE
        if len(reponse_donnee) > limite:
            raise DiagnosticRefuse(f"Réponse trop longue ({limite} caractères au plus).")
        statut = statut_automatique(question, reponse_donnee)
    observation = models.ObservationDiagnostic(
        eleve=eleve, question=question, reponse_donnee=reponse_donnee, statut=statut,
        observe_le=datetime.now(UTC), passation=passation, duree_s=duree_s,
    )
    session.add(observation)
    session.flush()
    return observation


def en_attente(session: Session, classe: models.Classe) -> list[models.ObservationDiagnostic]:
    """Réponses rédigées des élèves de la classe qui attendent la correction du professeur."""
    return list(
        session.scalars(
            select(models.ObservationDiagnostic)
            .join(models.Eleve, models.ObservationDiagnostic.eleve_id == models.Eleve.id)
            .where(models.Eleve.classe_id == classe.id, models.ObservationDiagnostic.statut == StatutObservation.EN_ATTENTE)
            .order_by(models.ObservationDiagnostic.observe_le, models.ObservationDiagnostic.id)
        )
    )


def corriger_observation(
    session: Session, observation: models.ObservationDiagnostic, juste: bool, enseignant: models.Enseignant
) -> models.ObservationDiagnostic:
    """Décision du professeur sur une réponse rédigée. Seul le professeur de la classe (ou un administrateur)
    corrige ; une observation déjà corrigée ne change plus ici (le lot 4 décidera d'une éventuelle révision)."""
    if observation.statut is not StatutObservation.EN_ATTENTE:
        raise DiagnosticRefuse("Cette réponse n'attend pas de correction.")
    if enseignant.role is not Role.ADMIN and observation.eleve.classe.enseignant_id != enseignant.id:
        raise DiagnosticRefuse("Seul le professeur de la classe corrige cette réponse.")
    observation.statut = StatutObservation.JUSTE if juste else StatutObservation.FAUX
    observation.corrige_par = enseignant
    observation.corrige_le = datetime.now(UTC)
    session.flush()
    return observation


# --- Passation (lot 3) --------------------------------------------------------------------------------------------

FERME, INDISPONIBLE, A_COMMENCER, EN_COURS, TERMINE = "ferme", "indisponible", "a-commencer", "en-cours", "termine"


def _maintenant() -> datetime:
    return datetime.now(UTC)


def _utc(instant: datetime) -> datetime:
    return instant if instant.tzinfo else instant.replace(tzinfo=UTC)


def passation_de(session: Session, eleve: models.Eleve) -> "models.PassationDiagnostic | None":
    return session.scalar(select(models.PassationDiagnostic).where(models.PassationDiagnostic.eleve_id == eleve.id))


def _plan_moteur(session: Session, classe: models.Classe):
    """Le plan, avec les seules questions diffusables, pour le moteur (qui ne voit jamais SQLAlchemy)."""
    entree, toutes = plan(session, classe)
    par_competence: dict[int, list] = {}
    for q in questions_diffusables(session, classe):
        par_competence.setdefault(q.competence_id, []).append(
            moteur.QuestionDiagnostic(q.id, q.competence_id, q.difficulte)
        )
    codes = {c.code: c.id for c in toutes.values()}
    competences = {
        c.id: moteur.CompetenceDiagnostic(
            c.id, tuple(par_competence.get(c.id, ())), tuple(codes[r] for r in c.retour or [] if r in codes)
        )
        for c in toutes.values()
    }
    return [competences[c.id] for c in entree], competences


def _observations_moteur(passation: "models.PassationDiagnostic") -> list:
    return [
        moteur.Observation(o.question_id, o.question.competence_id, moteur.Resultat(o.statut.value))
        for o in passation.observations
    ]


def statut(session: Session, eleve: models.Eleve) -> str:
    classe = eleve.classe
    if not classe.diagnostic_ouvert or classe.archivee_le is not None:
        return FERME
    passation = passation_de(session, eleve)
    if passation is not None:
        return TERMINE if passation.fin is not None else EN_COURS
    entree, _ = _plan_moteur(session, classe)
    return A_COMMENCER if any(c.questions for c in entree) else INDISPONIBLE


def demarrer(session: Session, eleve: models.Eleve) -> "models.PassationDiagnostic":
    """Commence la passation, ou reprend celle en cours."""
    etat = statut(session, eleve)
    if etat == EN_COURS:
        return passation_de(session, eleve)
    if etat != A_COMMENCER:
        raise DiagnosticRefuse({
            FERME: "Ton professeur n'a pas ouvert le diagnostic.",
            INDISPONIBLE: "Le diagnostic n'est pas encore prêt pour ta classe.",
            TERMINE: "Tu as déjà terminé le diagnostic.",
        }[etat])
    passation = models.PassationDiagnostic(eleve=eleve, debut=_maintenant())
    session.add(passation)
    session.flush()
    return passation


def _passation_en_cours(session: Session, eleve: models.Eleve) -> "models.PassationDiagnostic":
    etat = statut(session, eleve)
    if etat == FERME:
        raise DiagnosticRefuse("Ton professeur a fermé le diagnostic.")
    if etat != EN_COURS:
        raise DiagnosticRefuse("Aucun diagnostic en cours.")
    return passation_de(session, eleve)


def question_suivante(session: Session, eleve: models.Eleve) -> "models.Question | None":
    """La question en cours (la même tant qu'elle n'a pas de réponse), ou la suivante choisie par le moteur ;
    None : la passation est terminée (et marquée comme telle)."""
    passation = _passation_en_cours(session, eleve)
    if passation.question_courante is not None:
        return passation.question_courante
    entree, competences = _plan_moteur(session, eleve.classe)
    choix = moteur.prochaine_question(entree, competences, _observations_moteur(passation))
    if choix is None:
        passation.fin = _maintenant()
        session.flush()
        return None
    passation.question_courante = session.get(models.Question, choix.id)
    passation.question_servie_le = _maintenant()
    session.flush()
    return passation.question_courante


def repondre(
    session: Session, eleve: models.Eleve, question_id: int, reponse_donnee: str | None, ne_sait_pas: bool = False
) -> "models.ObservationDiagnostic":
    """Réponse à la question en cours uniquement ; aucune correction n'est renvoyée à l'élève."""
    passation = _passation_en_cours(session, eleve)
    question = passation.question_courante
    if question is None or question.id != question_id:
        raise DiagnosticRefuse("Cette question n'est pas la question en cours.")
    duree = (_maintenant() - _utc(passation.question_servie_le)).total_seconds() if passation.question_servie_le else None
    observation = enregistrer_observation(
        session, eleve, question, reponse_donnee, ne_sait_pas=ne_sait_pas, passation=passation, duree_s=duree
    )
    passation.question_courante = None
    passation.question_servie_le = None
    session.flush()
    return observation


def numero_courant(passation: "models.PassationDiagnostic") -> int:
    return len(passation.observations) + 1


def suivi_classe(session: Session, classe: models.Classe) -> list[dict]:
    """Avancement des élèves (sans conclusion : le bilan par compétence est le lot 5)."""
    lignes = []
    for eleve in sorted(classe.eleves, key=lambda e: e.prenom):
        passation = passation_de(session, eleve)
        observations = passation.observations if passation else []
        lignes.append({
            "eleve_id": eleve.id,
            "prenom": eleve.prenom,
            "statut": (TERMINE if passation.fin else EN_COURS) if passation else A_COMMENCER,
            "nb_reponses": len(observations),
            "nb_en_attente": sum(o.statut is StatutObservation.EN_ATTENTE for o in observations),
        })
    return lignes
