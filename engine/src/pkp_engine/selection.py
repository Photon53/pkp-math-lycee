"""Choix de la prochaine question.

1. Les questions archivées sont écartées.
2. On travaille la compétence la moins maîtrisée parmi celles qui ont des
   questions disponibles (à égalité : plus petit identifiant).
3. La difficulté visée suit la maîtrise : 1 à 0 %, 5 à 100 %.
4. Dans cette compétence, on préfère, dans l'ordre :
   - ne pas reposer la question qui vient d'être posée ;
   - une question pas encore réussie ;
   - une question posée le moins souvent ;
   - la difficulté la plus proche de la cible ;
   - le plus petit identifiant (résultat déterministe, donc testable).
"""

from collections import Counter
from collections.abc import Sequence

from pkp_engine.domain import Question, Reponse
from pkp_engine.maitrise import calculer_maitrise


def difficulte_cible(maitrise: float) -> int:
    return 1 + round(maitrise * 4)


def choisir_prochaine_question(
    candidates: Sequence[Question], historique: Sequence[Reponse]
) -> Question | None:
    """Choisit la prochaine question à poser, ou None s'il n'y en a plus.

    `historique` est ordonné de la réponse la plus ancienne à la plus récente.
    """
    disponibles = [q for q in candidates if not q.archivee]
    if not disponibles:
        return None

    maitrises = {
        c: calculer_maitrise(historique, c) for c in {q.competence_id for q in disponibles}
    }
    competence = min(maitrises, key=lambda c: (maitrises[c], c))
    cible = difficulte_cible(maitrises[competence])

    nb_posees = Counter(r.question_id for r in historique)
    reussies = {r.question_id for r in historique if r.correcte}
    derniere = historique[-1].question_id if historique else None

    return min(
        (q for q in disponibles if q.competence_id == competence),
        key=lambda q: (
            q.id == derniere,
            q.id in reussies,
            nb_posees[q.id],
            abs(q.difficulte - cible),
            q.id,
        ),
    )
