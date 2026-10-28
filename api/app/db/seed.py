"""Données de démonstration. Usage, depuis `api/` : `python -m app.db.seed`

1. Importe le contenu pédagogique de `contenu/` (chapitres, cours, questions).
2. Crée, si absents, un enseignant, des classes, des élèves et un historique de réponses.
Idempotent : relancer ne duplique rien.

Compte enseignant de démo (local uniquement) :
    email        : demo@pkp.test
    mot de passe : valeur de PKP_DEMO_MOT_DE_PASSE, sinon « demo-pkp-2026 »
"""

import os
from datetime import UTC, datetime, timedelta

from pkp_engine import Niveau, corriger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import contenu
from app.db import models
from app.db.conversions import question_vers_domaine
from app.security import hacher_mot_de_passe

EMAIL_DEMO = "demo@pkp.test"

CLASSES = [
    ("2NDE-A-DEMO", Niveau.SECONDE, ["Lina", "Yanis", "Inès"]),
    ("1RE-B-DEMO", Niveau.PREMIERE, ["Hugo"]),
    ("TLE-C-DEMO", Niveau.TERMINALE, ["Emma"]),
]

# (prénom, [(code question, réponse saisie)])
SEANCES = [
    ("Lina", [("2NDE-FRAC-01", "5/6"), ("2NDE-FRAC-02", "1/5"), ("2NDE-DEV-01", "x²+6x+9"),
              ("2NDE-DEV-03", "2x²+7x+4"), ("2NDE-EQ1-01", "5")]),
    ("Yanis", [("2NDE-FRAC-01", "2/5"), ("2NDE-FRAC-01", "5/6")]),
]


def charger_demo(session: Session) -> bool:
    """Charge le contenu puis les données de démo. Renvoie False si la démo existait déjà."""
    contenu.importer(session, contenu.charger())

    if session.scalar(select(models.Enseignant).where(models.Enseignant.email == EMAIL_DEMO)):
        return False

    enseignant = models.Enseignant(
        nom="Enseignant Démo",
        email=EMAIL_DEMO,
        mot_de_passe_hash=hacher_mot_de_passe(os.environ.get("PKP_DEMO_MOT_DE_PASSE", "demo-pkp-2026")),
    )
    session.add(enseignant)

    eleves: dict[str, models.Eleve] = {}
    for code, niveau, prenoms in CLASSES:
        classe = models.Classe(code=code, niveau=niveau, enseignant=enseignant)
        for prenom in prenoms:
            eleves[prenom] = models.Eleve(prenom=prenom, classe=classe)
        session.add(classe)
    session.flush()

    instant = datetime.now(UTC) - timedelta(days=1)
    for prenom, saisies in SEANCES:
        seance = models.Seance(eleve=eleves[prenom], debut=instant)
        session.add(seance)  # avant les requêtes : leur autoflush doit trouver la séance en session
        for code_question, saisie in saisies:
            question = session.scalar(select(models.Question).where(models.Question.code == code_question))
            instant += timedelta(minutes=1)
            seance.reponses.append(
                models.Reponse(
                    question=question,
                    reponse_donnee=saisie,
                    correcte=corriger(question_vers_domaine(question), saisie),
                    duree_s=45.0,
                    repondu_le=instant,
                )
            )
        seance.fin = instant

    session.commit()
    return True


def main() -> None:
    from app.db.session import SessionLocale

    with SessionLocale() as session:
        print("Données de démo chargées." if charger_demo(session) else "Contenu à jour, démo déjà présente.")


if __name__ == "__main__":
    main()
