"""Objets du domaine, immuables et indépendants de la persistance."""

from dataclasses import dataclass
from enum import Enum


class Niveau(str, Enum):
    # Ordre scolaire : collège (domaine Maths collège), puis lycée (Maths lycée).
    SIXIEME = "6e"
    CINQUIEME = "5e"
    QUATRIEME = "4e"
    TROISIEME = "3e"
    SECONDE = "2nde"
    PREMIERE = "1re"
    TERMINALE = "Tle"


class TypeQuestion(str, Enum):
    QCM = "qcm"
    NUMERIQUE = "numerique"
    EXPRESSION = "expression"
    # Réponse courte en toutes lettres (français : un mot, une forme verbale…) : voir `correction`.
    TEXTE = "texte"
    # Plusieurs bonnes réponses parmi des choix « A) … B) … » : la solution liste les lettres (« AC »).
    CHOIX_MULTIPLES = "choix_multiples"
    # Réponse rédigée (justification, construction) : corrigée par un professeur, jamais par le moteur.
    REDACTION = "redaction"


# Types que le moteur ne corrige pas : la réponse attend la correction d'un professeur.
TYPES_CORRECTION_HUMAINE = frozenset({TypeQuestion.REDACTION})


class Forme(str, Enum):
    """Forme d'écriture exigée pour une question de type expression (voir `formes`)."""

    DEVELOPPEE = "developpee"
    FACTORISEE = "factorisee"
    REDUITE = "reduite"


@dataclass(frozen=True)
class Question:
    id: int
    competence_id: int
    enonce: str
    type: TypeQuestion
    solution: str
    difficulte: int  # 1 (facile) à 5 (difficile)
    archivee: bool = False
    forme: Forme | None = None  # None : seule la valeur compte
    # Valeurs variables (gabarit) : chaque service tire de nouveaux nombres, ce n'est pas la même question.
    variable: bool = False


@dataclass(frozen=True)
class Reponse:
    question_id: int
    competence_id: int
    correcte: bool
    duree_s: float
