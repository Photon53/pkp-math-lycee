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


PARCOURS_PAR_NIVEAU: dict[Niveau, tuple[Parcours, ...]] = {
    Niveau.SECONDE: (Parcours.TRONC_COMMUN,),
    Niveau.PREMIERE: (Parcours.SPECIALITE,),
    Niveau.TERMINALE: (Parcours.SPECIALITE, Parcours.COMPLEMENTAIRES, Parcours.EXPERTES),
}

LIBELLES_PARCOURS = {
    Parcours.TRONC_COMMUN: "Tronc commun",
    Parcours.SPECIALITE: "Spécialité",
    Parcours.COMPLEMENTAIRES: "Maths complémentaires",
    Parcours.EXPERTES: "Maths expertes",
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

# Une source sans licence claire ne peut servir que d'inspiration (jamais adaptée ni reproduite).
LICENCES_NON_CLAIRES = {"", "aucune", "inconnue", "non clarifiée", "non clarifiee", "a verifier", "à vérifier"}
