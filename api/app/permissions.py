"""Domaines pédagogiques et habilitations : qui enseigne, et qui valide, matière par matière (CDC V2, § 3.1 et 3.2).

Un validateur est qualifié domaine par domaine : un validateur de maths ne valide pas l'anglais, et le rôle
d'administrateur ne donne pas, à lui seul, le droit de valider (EX.9-bis).

Les cases historiques de `enseignant` (`enseigne_maths`, `enseigne_anglais`, `referent_anglais`) restent lues par les
espaces existants : elles sont recalculées depuis les habilitations à chaque modification (`appliquer`).
"""

from datetime import UTC, datetime
from typing import NamedTuple

from sqlalchemy.orm import Session

from app.db import models

PROFESSEUR, VALIDATEUR = "professeur", "validateur"
ROLES = (PROFESSEUR, VALIDATEUR)

MATHS_LYCEE, ANGLAIS_COLLEGE = "maths-lycee", "anglais-college"

NIVEAUX_COLLEGE = ["6e", "5e", "4e", "3e"]


class Domaine(NamedTuple):
    code: str
    matiere: str
    cycle: str
    libelle: str
    niveaux: list[str]
    actif: bool
    public: bool


# Réglages de départ (migration 0023) : seuls les deux domaines déjà en service sont ouverts.
DOMAINES = (
    Domaine("maths-college", "maths", "college", "Maths collège", NIVEAUX_COLLEGE, False, False),
    Domaine(MATHS_LYCEE, "maths", "lycee", "Maths lycée", ["2nde", "1re", "Tle"], True, True),
    Domaine(ANGLAIS_COLLEGE, "anglais", "college", "Anglais collège", NIVEAUX_COLLEGE, True, True),
    Domaine("anglais-lycee", "anglais", "lycee", "Anglais lycée", ["2nde", "1re", "Tle"], False, False),
    Domaine("francais-college", "francais", "college", "Français collège", NIVEAUX_COLLEGE, False, False),
    Domaine("francais-lycee", "francais", "lycee", "Français lycée", ["2nde", "1re"], False, False),
)
LIBELLES = {d.code: d.libelle for d in DOMAINES}

# Domaine de chaque espace existant : les classes de maths sont au lycée, les groupes d'anglais au collège.
DOMAINE_CLASSES, DOMAINE_GROUPES_ANGLAIS = MATHS_LYCEE, ANGLAIS_COLLEGE

# Case historique ↔ habilitation qui la remplace.
CASES = {
    "enseigne_maths": (PROFESSEUR, MATHS_LYCEE),
    "enseigne_anglais": (PROFESSEUR, ANGLAIS_COLLEGE),
    "referent_anglais": (VALIDATEUR, ANGLAIS_COLLEGE),
}


class Portee(NamedTuple):
    role: str
    domaine: str
    niveau: str | None = None


class HabilitationRefusee(ValueError):
    pass


def portees(enseignant: models.Enseignant) -> list[Portee]:
    return [Portee(h.role, h.domaine_code, h.niveau) for h in enseignant.habilitations]


def normaliser(session: Session, demandees: list[Portee]) -> list[Portee]:
    """Contrôle et simplifie : domaine actif, niveau du domaine, pas de doublon ni de niveau inclus dans « tout »."""
    retenues: list[Portee] = []
    for p in demandees:
        if p.role not in ROLES:
            raise HabilitationRefusee(f"Rôle inconnu : {p.role}.")
        domaine = session.get(models.DomainePedagogique, p.domaine)
        if domaine is None:
            raise HabilitationRefusee(f"Domaine inconnu : {p.domaine}.")
        if not domaine.actif:
            raise HabilitationRefusee(f"{domaine.libelle} n'est pas activé : activez-le d'abord dans la configuration.")
        if p.niveau is not None and p.niveau not in domaine.niveaux:
            raise HabilitationRefusee(f"Niveau {p.niveau} absent de {domaine.libelle}.")
        if p not in retenues:
            retenues.append(p)
    tout = {(p.role, p.domaine) for p in retenues if p.niveau is None}
    return [p for p in retenues if p.niveau is None or (p.role, p.domaine) not in tout]


def depuis_cases(actuelles: list[Portee], **cases: bool) -> list[Portee]:
    """Compatibilité avec l'ancien formulaire (cases à cocher) : seules les cases changées modifient les habilitations,
    les autres (validateur de maths, niveaux précis, autres domaines) sont conservées telles quelles."""
    resultat = list(actuelles)
    for case, voulue in cases.items():
        role, domaine = CASES[case]
        if voulue == any(p.role == role and p.domaine == domaine for p in actuelles):
            continue
        resultat = [p for p in resultat if (p.role, p.domaine) != (role, domaine)]
        if voulue:
            resultat.append(Portee(role, domaine))
    return resultat


def appliquer(session: Session, enseignant: models.Enseignant, voulues: list[Portee], par: models.Enseignant | None) -> None:
    """Remplace les habilitations du compte et recalcule ses cases historiques. Lève `HabilitationRefusee`."""
    voulues = normaliser(session, voulues)
    actuelles = {Portee(h.role, h.domaine_code, h.niveau): h for h in enseignant.habilitations}
    for portee, h in actuelles.items():
        if portee not in voulues:
            enseignant.habilitations.remove(h)
    for portee in voulues:
        if portee not in actuelles:
            enseignant.habilitations.append(models.Habilitation(
                role=portee.role, domaine_code=portee.domaine, niveau=portee.niveau,
                accordee_par_id=par.id if par else None, accordee_le=datetime.now(UTC),
            ))
    for case, (role, domaine) in CASES.items():
        setattr(enseignant, case, any(p.role == role and p.domaine == domaine for p in voulues))


def peut_valider(enseignant: models.Enseignant, domaine: str, niveau: str | None) -> bool:
    return any(
        h.role == VALIDATEUR and h.domaine_code == domaine and (h.niveau is None or h.niveau == niveau)
        for h in enseignant.habilitations
    )


def refus_validation(enseignant: models.Enseignant, domaine: str, niveau: str | None) -> str | None:
    """Motif du refus, ou None si le compte est qualifié pour valider ce contenu."""
    if peut_valider(enseignant, domaine, niveau):
        return None
    cible = LIBELLES.get(domaine, domaine) + (f" ({niveau})" if niveau else "")
    return f"Vous n'êtes pas validateur pour {cible} : un validateur qualifié dans cette matière doit le faire."


def domaines_valides(enseignant: models.Enseignant) -> set[str]:
    return {h.domaine_code for h in enseignant.habilitations if h.role == VALIDATEUR}


def refus_domaine_ferme(session: Session, domaine: str) -> str | None:
    """Un domaine non public n'accepte ni nouvelle séance d'élève, ni nouvelle classe ou nouveau groupe (EX.4)."""
    d = session.get(models.DomainePedagogique, domaine)
    if d is not None and d.public:
        return None
    return f"{LIBELLES.get(domaine, domaine)} est fermé pour le moment : aucune nouvelle séance n'est possible."
