"""Choix de la prochaine question.

1. Les questions archivées sont écartées.
2. Une question réussie est « au repos » tant que l'élève n'a pas donné `ESPACEMENT_REVISION` autres réponses
   depuis cette réussite : elle ne revient pas tout de suite (ticket #26). Passé ce délai, elle redevient
   disponible : c'est la révision espacée. Une question ratée reste disponible (retravailler une erreur),
   mais jamais deux fois de suite s'il y a autre chose à proposer.
3. On travaille la compétence la moins maîtrisée parmi celles qui ont une question disponible (à égalité :
   plus petit identifiant). Une compétence dont toutes les questions sont au repos cède la place.
4. Si toutes les questions sont au repos, on se rabat sur une question à valeurs variables (`variable`) :
   l'exercice revient avec d'autres nombres, ce n'est pas la même question. Sans elle, il n'y a rien à
   proposer (None) : l'application le dit à l'élève et lui propose de réviser (`espacement=0`), de changer
   de chapitres ou de terminer, au lieu de boucler en silence.
5. La difficulté visée suit la maîtrise : 1 à 0 %, 5 à 100 %.
6. Dans la compétence, on préfère, dans l'ordre :
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

# Nombre de réponses (dans les compétences en jeu) avant qu'une question réussie puisse revenir.
ESPACEMENT_REVISION = 20


def difficulte_cible(maitrise: float) -> int:
    return 1 + round(maitrise * 4)


def questions_au_repos(historique: Sequence[Reponse], espacement: int = ESPACEMENT_REVISION) -> set[int]:
    """Questions dont la dernière réponse est juste et date de moins de `espacement` réponses."""
    if espacement <= 0:
        return set()
    derniere_position: dict[int, int] = {}
    for position, reponse in enumerate(historique):
        derniere_position[reponse.question_id] = position
    fin = len(historique)
    return {
        qid
        for qid, position in derniere_position.items()
        if historique[position].correcte and fin - position <= espacement
    }


def choisir_prochaine_question(
    candidates: Sequence[Question],
    historique: Sequence[Reponse],
    espacement: int = ESPACEMENT_REVISION,
) -> Question | None:
    """Choisit la prochaine question à poser, ou None s'il n'y a rien à proposer.

    `historique` est ordonné de la réponse la plus ancienne à la plus récente. `espacement=0` : révision
    demandée par l'élève, les questions déjà réussies reviennent.
    """
    disponibles = [q for q in candidates if not q.archivee]
    au_repos = questions_au_repos(historique, espacement)
    eligibles = [q for q in disponibles if q.id not in au_repos] or [
        q for q in disponibles if q.variable
    ]
    if not eligibles:
        return None

    maitrises = {
        c: calculer_maitrise(historique, c) for c in {q.competence_id for q in eligibles}
    }
    competence = min(maitrises, key=lambda c: (maitrises[c], c))
    cible = difficulte_cible(maitrises[competence])

    nb_posees = Counter(r.question_id for r in historique)
    reussies = {r.question_id for r in historique if r.correcte}
    derniere = historique[-1].question_id if historique else None

    return min(
        (q for q in eligibles if q.competence_id == competence),
        key=lambda q: (
            q.id == derniere,
            q.id in reussies,
            nb_posees[q.id],
            abs(q.difficulte - cible),
            q.id,
        ),
    )
