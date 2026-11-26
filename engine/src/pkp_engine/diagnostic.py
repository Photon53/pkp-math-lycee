# Issue #162 — Diagnostic des acquis antérieurs, lot 3 : passation adaptative (Claude)
"""Choix de la question suivante d'un diagnostic, et conclusion par compétence.

Règles (cahier de l'issue #162) :
1. Les compétences du questionnaire d'entrée sont parcourues dans l'ordre.
2. Dans une compétence, la première question visée est de difficulté `DIFFICULTE_DEPART` (la plus proche).
3. Après une réussite : une question de difficulté égale ou supérieure. Après `REUSSITES_CONVERGENTES` réussites,
   la compétence est close (on n'insiste pas sur les questions très simples).
4. Après un échec ou un « Je ne sais pas » : `RELANCES_APRES_ECHEC` questions de plus sur la même compétence, la
   première plus simple si possible. Une seule erreur ne suffit pas à conclure.
5. Une réponse rédigée en attente de correction ne compte ni comme réussite ni comme échec.
6. Une compétence close « à reprendre » ouvre ses compétences de `retour` (même notion, niveau précédent) avant de
   passer à la compétence suivante : un élève de 3e redescend vers la 5e, puis la 6e, seulement là où il le faut.
7. `MAX_QUESTIONS` borne la passation.

La conclusion est une observation, pas une note : elle ne modifie jamais le taux de maîtrise.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum

DIFFICULTE_DEPART = 2
REUSSITES_CONVERGENTES = 2
RELANCES_APRES_ECHEC = 2
MAX_QUESTIONS_PAR_COMPETENCE = 4
MAX_QUESTIONS = 45


class Resultat(str, Enum):
    JUSTE = "juste"
    FAUX = "faux"
    NE_SAIT_PAS = "je-ne-sais-pas"
    EN_ATTENTE = "en-attente-de-correction"


class Conclusion(str, Enum):
    ACQUISE = "reussites-convergentes"
    FRAGILE = "resultats-partages"
    A_REPRENDRE = "a-reprendre"
    EN_ATTENTE = "en-attente-de-correction"
    NON_CONCLUE = "non-conclue"


@dataclass(frozen=True)
class QuestionDiagnostic:
    id: int
    competence_id: int
    difficulte: int


@dataclass(frozen=True)
class CompetenceDiagnostic:
    id: int
    questions: tuple[QuestionDiagnostic, ...]
    # Compétences du diagnostic du niveau précédent, ouvertes si celle-ci est « à reprendre ».
    retour: tuple[int, ...] = field(default=())


@dataclass(frozen=True)
class Observation:
    question_id: int
    competence_id: int
    resultat: Resultat


@dataclass(frozen=True)
class EtatCompetence:
    close: bool
    conclusion: Conclusion
    observations: int


def _echec(r: Resultat) -> bool:
    return r in (Resultat.FAUX, Resultat.NE_SAIT_PAS)


def etat_competence(competence: CompetenceDiagnostic, observations: Sequence[Observation]) -> EtatCompetence:
    obs = [o for o in observations if o.competence_id == competence.id]
    resultats = [o.resultat for o in obs]
    justes = resultats.count(Resultat.JUSTE)
    echecs = sum(_echec(r) for r in resultats)
    attente = resultats.count(Resultat.EN_ATTENTE)
    posees = {o.question_id for o in obs}
    restantes = [q for q in competence.questions if q.id not in posees]
    premier_echec = next((i for i, r in enumerate(resultats) if _echec(r)), None)
    relances = len(resultats) - premier_echec - 1 if premier_echec is not None else 0

    close = (
        justes >= REUSSITES_CONVERGENTES
        or (premier_echec is not None and relances >= RELANCES_APRES_ECHEC)
        or len(obs) >= MAX_QUESTIONS_PAR_COMPETENCE
        or not restantes
    )
    if justes >= REUSSITES_CONVERGENTES and echecs == 0:
        conclusion = Conclusion.ACQUISE
    elif justes and echecs:
        conclusion = Conclusion.FRAGILE
    elif echecs >= 2:  # aucune réussite : des erreurs répétées, pas une erreur isolée
        conclusion = Conclusion.A_REPRENDRE
    elif attente:
        conclusion = Conclusion.EN_ATTENTE
    else:
        conclusion = Conclusion.NON_CONCLUE
    return EtatCompetence(close, conclusion, len(obs))


def _question_dans(competence: CompetenceDiagnostic, observations: Sequence[Observation]) -> QuestionDiagnostic:
    obs = [o for o in observations if o.competence_id == competence.id]
    posees = {o.question_id for o in obs}
    restantes = [q for q in competence.questions if q.id not in posees]
    if not obs:
        return min(restantes, key=lambda q: (abs(q.difficulte - DIFFICULTE_DEPART), q.difficulte, q.id))
    derniere = next(q for q in competence.questions if q.id == obs[-1].question_id)
    resultat = obs[-1].resultat
    if resultat is Resultat.JUSTE:
        plus_dures = [q for q in restantes if q.difficulte >= derniere.difficulte]
        return min(plus_dures or restantes, key=lambda q: (abs(q.difficulte - derniere.difficulte), q.id))
    if _echec(resultat):
        plus_simples = [q for q in restantes if q.difficulte < derniere.difficulte]
        if plus_simples:
            return min(plus_simples, key=lambda q: (derniere.difficulte - q.difficulte, q.id))
    return min(restantes, key=lambda q: (abs(q.difficulte - derniere.difficulte), q.difficulte, q.id))


def prochaine_question(
    entree: Sequence[CompetenceDiagnostic],
    competences: dict[int, CompetenceDiagnostic],
    observations: Sequence[Observation],
) -> QuestionDiagnostic | None:
    """Question suivante, ou None : la passation est terminée.

    `entree` : compétences du questionnaire d'entrée, dans l'ordre ; `competences` : toutes les compétences
    joignables (entrée et retours), par identifiant ; `observations` : réponses déjà données, dans l'ordre."""
    if len(observations) >= MAX_QUESTIONS:
        return None
    vues: set[int] = set()

    def parcourir(liste: Sequence[CompetenceDiagnostic]) -> QuestionDiagnostic | None:
        for competence in liste:
            if competence.id in vues:
                continue
            vues.add(competence.id)
            if not competence.questions:
                continue
            etat = etat_competence(competence, observations)
            if not etat.close:
                return _question_dans(competence, observations)
            if etat.conclusion is Conclusion.A_REPRENDRE:
                retours = [competences[c] for c in competence.retour if c in competences]
                if (question := parcourir(retours)) is not None:
                    return question
        return None

    return parcourir(entree)


def conclusions(
    competences: dict[int, CompetenceDiagnostic], observations: Sequence[Observation]
) -> dict[int, EtatCompetence]:
    """État de chaque compétence interrogée (au moins une observation)."""
    interrogees = {o.competence_id for o in observations}
    return {cid: etat_competence(c, observations) for cid, c in competences.items() if cid in interrogees}
