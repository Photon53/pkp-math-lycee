"""Objets du domaine, immuables et indépendants de la persistance."""

from dataclasses import dataclass
from enum import Enum


class Niveau(str, Enum):
    SECONDE = "2nde"
    PREMIERE = "1re"
    TERMINALE = "Tle"


class TypeQuestion(str, Enum):
    QCM = "qcm"
    NUMERIQUE = "numerique"
    EXPRESSION = "expression"


@dataclass(frozen=True)
class Question:
    id: int
    competence_id: int
    enonce: str
    type: TypeQuestion
    solution: str
    difficulte: int  # 1 (facile) à 5 (difficile)
    archivee: bool = False


@dataclass(frozen=True)
class Reponse:
    question_id: int
    competence_id: int
    correcte: bool
    duree_s: float
