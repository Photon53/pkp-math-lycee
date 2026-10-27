"""Calcul du taux de maîtrise d'une compétence.

Moyenne pondérée des réussites, où chaque réponse pèse `DECROISSANCE` fois
moins que la suivante : les réponses récentes comptent davantage. Seules les
`FENETRE` dernières réponses sont prises en compte, si bien qu'une erreur
ancienne finit par s'effacer complètement.

Un « a priori » de poids `POIDS_A_PRIORI` (valeur 0) est ajouté au
dénominateur : sans preuves suffisantes, la maîtrise reste basse. Il faut
environ 5 bonnes réponses d'affilée pour atteindre `SEUIL_MAITRISE`.
"""

from collections.abc import Sequence

from pkp_engine.domain import Reponse

DECROISSANCE = 0.9
FENETRE = 10
POIDS_A_PRIORI = 1.0
SEUIL_MAITRISE = 0.8


def calculer_maitrise(historique: Sequence[Reponse], competence_id: int) -> float:
    """Taux de maîtrise d'une compétence, entre 0.0 et 1.0.

    `historique` est l'ensemble des réponses de l'élève, de la plus ancienne
    à la plus récente.
    """
    reponses = [r for r in historique if r.competence_id == competence_id][-FENETRE:]
    poids_total = 0.0
    score = 0.0
    for rang, reponse in enumerate(reversed(reponses)):
        poids = DECROISSANCE**rang
        poids_total += poids
        if reponse.correcte:
            score += poids
    return score / (poids_total + POIDS_A_PRIORI)


def est_maitrisee(historique: Sequence[Reponse], competence_id: int) -> bool:
    return calculer_maitrise(historique, competence_id) >= SEUIL_MAITRISE
