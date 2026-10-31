"""Vocabulaire du référentiel : parcours (spécialités), traçabilité des sources, validation.

La banque s'ordonne ainsi : niveau (classe) → parcours (spécialité) → chapitre (cours)
→ compétence → difficulté (1 à 5).
"""

from enum import Enum

from pkp_engine import Niveau


class Parcours(str, Enum):
    TRONC_COMMUN = "tronc-commun"  # Seconde : enseignement commun de mathématiques
    SPECIALITE = "specialite"  # Première et Terminale : spécialité mathématiques
    COMPLEMENTAIRES = "complementaires"  # Terminale : option mathématiques complémentaires
    EXPERTES = "expertes"  # Terminale : option mathématiques expertes
    SCIENTIFIQUE = "scientifique"  # Première : mathématiques de l'enseignement scientifique (sans la spécialité)
    TECHNOLOGIQUE = "technologique"  # Première et Terminale : voie technologique (STMG, STI2D, STL, ST2S…)
    EXCELLENCE = "excellence"  # Tous niveaux : exercices très poussés et olympiades (groupe d'approfondissement)
    MISE_A_NIVEAU = "mise-a-niveau"  # Tous niveaux : vérifier les bases de l'année précédente (groupe de soutien)
    EXAMENS = "examens"  # 1re et Tle : épreuve anticipée, bac blanc, sujets type annales


PARCOURS_PAR_NIVEAU: dict[Niveau, tuple[Parcours, ...]] = {
    Niveau.SECONDE: (Parcours.TRONC_COMMUN, Parcours.MISE_A_NIVEAU, Parcours.EXCELLENCE),
    Niveau.PREMIERE: (
        Parcours.SPECIALITE, Parcours.SCIENTIFIQUE, Parcours.TECHNOLOGIQUE,
        Parcours.MISE_A_NIVEAU, Parcours.EXCELLENCE, Parcours.EXAMENS,
    ),
    Niveau.TERMINALE: (
        Parcours.SPECIALITE, Parcours.COMPLEMENTAIRES, Parcours.EXPERTES, Parcours.TECHNOLOGIQUE,
        Parcours.MISE_A_NIVEAU, Parcours.EXCELLENCE, Parcours.EXAMENS,
    ),
}

LIBELLES_PARCOURS = {
    Parcours.TRONC_COMMUN: "Tronc commun",
    Parcours.SPECIALITE: "Spécialité",
    Parcours.COMPLEMENTAIRES: "Maths complémentaires",
    Parcours.EXPERTES: "Maths expertes",
    Parcours.SCIENTIFIQUE: "Enseignement scientifique",
    Parcours.TECHNOLOGIQUE: "Voie technologique",
    Parcours.EXCELLENCE: "Excellence et olympiades",
    Parcours.MISE_A_NIVEAU: "Mise à niveau",
    Parcours.EXAMENS: "Préparation aux examens",
}


# Abréviation du parcours dans le code d'une classe (« TLE-EXP-4KQ7M ») : on devine la spécialité au premier coup d'œil.
ABREVIATIONS_PARCOURS = {
    Parcours.TRONC_COMMUN: "TC",
    Parcours.SPECIALITE: "SPE",
    Parcours.SCIENTIFIQUE: "ES",
    Parcours.COMPLEMENTAIRES: "COMP",
    Parcours.EXPERTES: "EXP",
    Parcours.TECHNOLOGIQUE: "TECH",
    Parcours.MISE_A_NIVEAU: "MAN",
    Parcours.EXCELLENCE: "EXC",
    Parcours.EXAMENS: "EXAM",
}


def parcours_par_defaut(niveau: Niveau) -> Parcours:
    return PARCOURS_PAR_NIVEAU[niveau][0]


class Adaptation(str, Enum):
    """Lien entre une question et sa source (registre des sources)."""

    ORIGINALE = "originale"  # rédigée pour PKP, sans source
    INSPIREE = "inspiree"  # idée reprise, énoncé et valeurs entièrement réécrits
    ADAPTEE = "adaptee"  # texte d'une source modifié : la licence de la source s'applique
    REPRODUITE = "reproduite"  # texte d'une source repris, avec autorisation ou licence libre


class StatutValidation(str, Enum):
    A_VALIDER = "a-valider"
    VALIDEE = "validee"
    A_CORRIGER = "a-corriger"


SOURCE_PKP = "PKP Math"


class Role(str, Enum):
    ENSEIGNANT = "enseignant"
    ADMIN = "admin"


class TypeRessource(str, Enum):
    LIEN = "lien"
    PDF = "pdf"


class PorteeRessource(str, Enum):
    COMMUNE = "commune"  # ajoutée par un administrateur, pour tous
    CLASSE = "classe"  # ajoutée par un professeur, pour les classes qu'il choisit


class PublicRessource(str, Enum):
    TOUS = "tous"
    ELEVES = "eleves"
    ENSEIGNANTS = "enseignants"

# Une source sans licence claire ne peut servir que d'inspiration (jamais adaptée ni reproduite).
LICENCES_NON_CLAIRES = {"", "aucune", "inconnue", "non clarifiée", "non clarifiee", "a verifier", "à vérifier"}
