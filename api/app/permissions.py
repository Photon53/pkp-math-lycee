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
from app.referentiel import Role

PROFESSEUR, VALIDATEUR = "professeur", "validateur"
ROLES = (PROFESSEUR, VALIDATEUR)

MATHS_COLLEGE, MATHS_LYCEE, ANGLAIS_COLLEGE = "maths-college", "maths-lycee", "anglais-college"
ANGLAIS_LYCEE = "anglais-lycee"

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
    Domaine(MATHS_COLLEGE, "maths", "college", "Maths collège", NIVEAUX_COLLEGE, False, False),
    Domaine(MATHS_LYCEE, "maths", "lycee", "Maths lycée", ["2nde", "1re", "Tle"], True, True),
    Domaine(ANGLAIS_COLLEGE, "anglais", "college", "Anglais collège", NIVEAUX_COLLEGE, True, True),
    Domaine(ANGLAIS_LYCEE, "anglais", "lycee", "Anglais lycée", ["2nde", "1re", "Tle"], False, False),
    Domaine("francais-college", "francais", "college", "Français collège", NIVEAUX_COLLEGE, False, False),
    Domaine("francais-lycee", "francais", "lycee", "Français lycée", ["2nde", "1re"], False, False),
)
LIBELLES = {d.code: d.libelle for d in DOMAINES}
MATIERES = {d.code: d.matiere for d in DOMAINES}

# Domaine donné aux nouvelles classes et aux nouveaux groupes par les espaces actuels ; chaque classe, chapitre,
# groupe et séance d'anglais porte ensuite son domaine (colonne `domaine_code`, EX.2).
DOMAINE_CLASSES, DOMAINE_GROUPES_ANGLAIS = MATHS_LYCEE, ANGLAIS_COLLEGE


def domaine_anglais(niveau: str) -> str:
    """Domaine d'un groupe ou d'une séance d'anglais : Anglais collège (6e à 3e) ou Anglais lycée."""
    return ANGLAIS_COLLEGE if niveau in NIVEAUX_COLLEGE else ANGLAIS_LYCEE


def enseigne(enseignant: models.Enseignant, domaine: str, niveau: str | None = None) -> bool:
    """Habilitation de professeur (ou de validateur) sur ce domaine, pour tout le domaine ou ce niveau."""
    return any(
        h.domaine_code == domaine and (h.niveau is None or niveau is None or h.niveau == niveau)
        for h in enseignant.habilitations
    )


def enseigne_francais(enseignant: models.Enseignant) -> bool:
    return any(h.domaine_code.startswith("francais-") for h in enseignant.habilitations)


def refus_matiere_enseignee(enseignant: models.Enseignant, matiere: str, domaine: str, niveau) -> str | None:
    """Un professeur ne crée de classe que dans sa matière (français : habilitation sur ce domaine et ce niveau)."""
    if matiere == "francais":
        niveau = getattr(niveau, "value", niveau)
        return None if enseigne(enseignant, domaine, niveau) else f"Vous n'enseignez pas le français en {niveau}."
    return None if enseignant.enseigne_maths else "Vous n'enseignez pas les mathématiques."


def refus_niveau(session: Session, domaine: str, niveau: str) -> str | None:
    """Le niveau doit être l'un de ceux du domaine (remplace les contraintes `niveau IN (...)` de l'anglais)."""
    d = session.get(models.DomainePedagogique, domaine)
    if d is not None and niveau in d.niveaux:
        return None
    return f"Le niveau {niveau} ne fait pas partie de {LIBELLES.get(domaine, domaine)}."

# Case historique ↔ habilitation qui la remplace.
CASES = {
    "enseigne_maths": (PROFESSEUR, MATHS_LYCEE),
    "enseigne_anglais": (PROFESSEUR, ANGLAIS_COLLEGE),
    "referent_anglais": (VALIDATEUR, ANGLAIS_COLLEGE),
}
# La case « enseigne les maths » ouvre l'espace des classes, collège comme lycée.
# Les cases d'anglais ouvrent l'espace Boussole Anglais, collège comme lycée.
AUSSI_COCHEE_PAR = {
    "enseigne_maths": [(PROFESSEUR, MATHS_COLLEGE)],
    "enseigne_anglais": [(PROFESSEUR, ANGLAIS_LYCEE)],
    "referent_anglais": [(VALIDATEUR, ANGLAIS_LYCEE)],
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
    for case, portee in CASES.items():
        cochee_par = [portee, *AUSSI_COCHEE_PAR.get(case, [])]
        setattr(enseignant, case, any((p.role, p.domaine) in cochee_par for p in voulues))


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


DOMAINES_MATHS = (MATHS_COLLEGE, MATHS_LYCEE)


def valide_les_maths(enseignant: models.Enseignant) -> bool:
    """Validateur d'au moins un domaine de maths : page « Validation » de l'espace professeur (ticket #29)."""
    return bool(domaines_valides(enseignant) & set(DOMAINES_MATHS))


def refus_domaine_ferme(session: Session, domaine: str) -> str | None:
    """Un domaine non public n'accepte ni nouvelle séance d'élève, ni nouvelle classe ou nouveau groupe (EX.4)."""
    d = session.get(models.DomainePedagogique, domaine)
    if d is not None and d.public:
        return None
    return f"{LIBELLES.get(domaine, domaine)} est fermé pour le moment : aucune nouvelle séance n'est possible."


# --- Permissions (CDC V2, EX.7) ------------------------------------------------------------------
# Table de correspondance dans le code, pas un moteur configurable en base. L'admin a toutes les permissions
# sauf `contenu.valider`, qui vient d'une habilitation de validateur, domaine par domaine (EX.9-bis).
# `prevalidation.ia` (ticket #48) n'appartient qu'aux administrateurs : aucune habilitation ne la donne.

PERMISSIONS = (
    "contenu.lire", "contenu.modifier", "contenu.soumettre", "contenu.valider", "contenu.publier",
    "comptes.gerer", "parents.gerer", "pilotage.global", "pilotage.domaine", "configuration",
    "prevalidation.ia",
)
PAR_ROLE = {
    PROFESSEUR: ("contenu.lire", "contenu.soumettre", "pilotage.domaine"),
    VALIDATEUR: ("contenu.lire", "contenu.valider", "contenu.publier"),
}


def permissions_de(enseignant: models.Enseignant, domaine: str | None = None) -> set[str]:
    """Permissions d'un compte, dans un domaine donné ou dans au moins un domaine (`domaine` vide)."""
    accordees: set[str] = set()
    if enseignant.role == Role.ADMIN:
        accordees.update(p for p in PERMISSIONS if p != "contenu.valider")
    for h in enseignant.habilitations:
        if domaine is None or h.domaine_code == domaine:
            accordees.update(PAR_ROLE[h.role])
    return accordees


def exiger(enseignant: models.Enseignant, permission: str, domaine: str | None = None) -> str | None:
    """Refus lisible si la permission manque, sinon None ; chaque route lève ensuite son 403."""
    if permission not in PERMISSIONS:
        raise ValueError(f"Permission inconnue : {permission}")
    if permission in permissions_de(enseignant, domaine):
        return None
    return "Vous n'avez pas la permission nécessaire pour cette action."
