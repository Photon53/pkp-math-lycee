"""Journal des actions d'administration (EA2.3) : qui, quoi, sur quel objet, avant et après.

L'entrée est ajoutée à la session de l'action : elle est enregistrée dans la même transaction,
ou pas du tout si l'action échoue.
"""

from datetime import date, datetime
from enum import Enum

from sqlalchemy.orm import Session

from app.db import models


def instantane(objet, champs: tuple[str, ...]) -> dict:
    """Valeurs JSON des champs d'un objet (dates en ISO, énumérations par leur valeur)."""

    def json(v):
        if isinstance(v, Enum):
            return v.value
        if isinstance(v, (date, datetime)):
            return v.isoformat()
        return v

    return {c: json(getattr(objet, c)) for c in champs}


def noter(
    session: Session,
    admin: models.Enseignant,
    action: str,
    objet: str,
    objet_id: int | None = None,
    avant: dict | None = None,
    apres: dict | None = None,
) -> None:
    session.add(
        models.JournalAdmin(admin_id=admin.id, action=action, objet=objet, objet_id=objet_id, avant=avant, apres=apres)
    )
