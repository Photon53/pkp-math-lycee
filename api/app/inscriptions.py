"""Un même élève inscrit dans plusieurs parcours (spécialité, mise à niveau, excellence, examens…).

Chaque inscription reste un compte élève distinct, dans sa classe : séances, progression et statistiques
restent séparées par parcours. Les inscriptions reliées partagent un `groupe_id` (l'id de la première)
et le même code personnel ; l'élève passe de l'une à l'autre sans ressaisir de code.

Seul le professeur qui possède les deux classes peut relier deux inscriptions.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.schemas import InscriptionLiee


class LienImpossible(ValueError):
    pass


def liees(session: Session, eleve: models.Eleve) -> list[models.Eleve]:
    """Les autres inscriptions du même élève (sans `eleve` lui-même)."""
    if eleve.groupe_id is None:
        return []
    autres = session.scalars(
        select(models.Eleve).where(models.Eleve.groupe_id == eleve.groupe_id, models.Eleve.id != eleve.id)
    )
    return sorted(autres, key=lambda e: e.classe.code)


def decrire(eleve: models.Eleve, actuelle: bool = False) -> InscriptionLiee:
    return InscriptionLiee(
        eleve_id=eleve.id,
        prenom=eleve.prenom,
        code_classe=eleve.classe.code,
        niveau=eleve.classe.niveau,
        parcours=eleve.classe.parcours,
        actuelle=actuelle,
    )


def suggestions(session: Session, eleve: models.Eleve) -> list[models.Eleve]:
    """Même prénom dans les autres classes du même professeur, pas encore relié."""
    deja = {e.id for e in liees(session, eleve)} | {eleve.id}
    classes = {e.classe_id for e in liees(session, eleve)} | {eleve.classe_id}
    candidats = session.scalars(
        select(models.Eleve)
        .join(models.Classe)
        .where(models.Classe.enseignant_id == eleve.classe.enseignant_id, models.Eleve.classe_id.not_in(classes))
    )
    prenom = eleve.prenom.casefold()
    return sorted(
        (e for e in candidats if e.id not in deja and e.prenom.casefold() == prenom), key=lambda e: e.classe.code
    )


def relier(session: Session, eleve: models.Eleve, autre: models.Eleve) -> None:
    """Relie `autre` (et ses inscriptions déjà reliées) à `eleve`, qui donne son code personnel à tous."""
    if autre.id == eleve.id:
        raise LienImpossible("Une inscription ne peut pas être reliée à elle-même.")
    if autre.classe.enseignant_id != eleve.classe.enseignant_id:
        raise LienImpossible("Les deux classes doivent être les vôtres.")
    groupe_a = [eleve, *liees(session, eleve)]
    groupe_b = [autre, *liees(session, autre)]
    if {e.classe_id for e in groupe_a} & {e.classe_id for e in groupe_b}:
        raise LienImpossible("Un élève ne peut avoir qu'une inscription par classe.")
    if eleve.code_hash is None:
        raise LienImpossible("Générez d'abord le code personnel de cet élève.")
    groupe = min(e.id for e in groupe_a + groupe_b)
    for e in groupe_a + groupe_b:
        e.groupe_id = groupe
        # Un seul code à retenir : l'ancien code de l'autre inscription, et ses sessions, cessent de fonctionner.
        e.code_hash = eleve.code_hash


def delier(session: Session, eleve: models.Eleve) -> None:
    """Retire cette inscription de son groupe (elle garde son code ; le professeur peut en générer un autre)."""
    restants = liees(session, eleve)
    eleve.groupe_id = None
    if len(restants) == 1:
        restants[0].groupe_id = None
    elif restants and eleve.id == min(e.id for e in [eleve, *restants]):
        nouveau = min(e.id for e in restants)
        for e in restants:
            e.groupe_id = nouveau
