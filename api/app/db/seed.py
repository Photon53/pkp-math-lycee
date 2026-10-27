"""Données de démonstration. Usage, depuis `api/` : `python -m app.db.seed`

Idempotent : ne fait rien si l'enseignant de démo existe déjà.

Compte enseignant de démo (local uniquement) :
    email        : demo@pkp.test
    mot de passe : valeur de PKP_DEMO_MOT_DE_PASSE, sinon « demo-pkp-2026 »
"""

import os
from datetime import UTC, datetime, timedelta

from pkp_engine import Niveau, TypeQuestion, corriger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.db.conversions import question_vers_domaine
from app.security import hacher_mot_de_passe

EMAIL_DEMO = "demo@pkp.test"

QCM, NUM, EXPR = TypeQuestion.QCM, TypeQuestion.NUMERIQUE, TypeQuestion.EXPRESSION

# (niveau, ordre, titre, [(code compétence, libellé, [(énoncé, type, solution, difficulté[, archivée])])])
PROGRAMME = [
    (Niveau.SECONDE, 1, "Nombres et calculs", [
        ("2NDE-FRAC", "Calculer avec des fractions", [
            ("Calculer 1/2 + 1/3.", NUM, "5/6", 1),
            ("Calculer 3/4 × 2/9.", NUM, "1/6", 2),
            ("Calculer (2/3) ÷ (4/9).", NUM, "3/2", 3),
        ]),
        ("2NDE-PUIS", "Calculer avec des puissances", [
            ("Calculer 2⁵.", NUM, "32", 1),
            ("Quel est le signe de (−3)⁷ ? A) positif  B) négatif", QCM, "B", 2),
            ("Donner la valeur décimale de 10³ × 10⁻⁵.", NUM, "0.01", 3),
        ]),
    ]),
    (Niveau.SECONDE, 2, "Calcul littéral", [
        ("2NDE-DEV", "Développer une expression", [
            ("Développer (x + 3)².", EXPR, "x^2 + 6x + 9", 2),
            ("Développer (a + b)(a − b).", EXPR, "a^2 - b^2", 2),
            ("Développer (2x − 1)(x + 4).", EXPR, "2x^2 + 7x - 4", 3),
        ]),
        ("2NDE-EQ1", "Résoudre une équation du premier degré", [
            ("Résoudre 3x + 5 = 20. x = ?", NUM, "5", 1),
            ("Résoudre 2x − 7 = 4x + 1. x = ?", NUM, "-4", 2),
            ("Résoudre (x + 1)/3 = 2. x = ?", NUM, "5", 3),
            ("Résoudre 2x = 6. x = ? (ancienne version)", NUM, "3", 1, True),
        ]),
    ]),
    (Niveau.PREMIERE, 1, "Second degré", [
        ("1RE-DISC", "Utiliser le discriminant", [
            ("Calculer le discriminant de x² − 4x + 3.", NUM, "4", 1),
            ("Combien de solutions réelles a x² + x + 1 = 0 ? A) 0  B) 1  C) 2", QCM, "A", 2),
        ]),
    ]),
]

CLASSES = [("2NDE-A-DEMO", Niveau.SECONDE, ["Lina", "Yanis", "Inès"]), ("1RE-B-DEMO", Niveau.PREMIERE, ["Hugo"])]

# (prénom, [(code compétence, rang de la question, réponse saisie)])
SEANCES = [
    ("Lina", [("2NDE-FRAC", 0, "5/6"), ("2NDE-FRAC", 1, "1/5"), ("2NDE-DEV", 0, "x²+6x+9"),
              ("2NDE-DEV", 2, "2x²+7x+4"), ("2NDE-EQ1", 0, "5")]),
    ("Yanis", [("2NDE-FRAC", 0, "2/5"), ("2NDE-FRAC", 0, "5/6")]),
]


def charger_demo(session: Session) -> bool:
    """Insère les données de démo. Renvoie False si elles sont déjà présentes."""
    if session.scalar(select(models.Enseignant).where(models.Enseignant.email == EMAIL_DEMO)):
        return False

    enseignant = models.Enseignant(
        nom="Enseignant Démo",
        email=EMAIL_DEMO,
        mot_de_passe_hash=hacher_mot_de_passe(os.environ.get("PKP_DEMO_MOT_DE_PASSE", "demo-pkp-2026")),
    )
    session.add(enseignant)

    questions: dict[str, list[models.Question]] = {}
    for niveau, ordre, titre, competences in PROGRAMME:
        chapitre = models.Chapitre(niveau=niveau, ordre=ordre, titre=titre)
        session.add(chapitre)
        for code, libelle, items in competences:
            competence = models.Competence(chapitre=chapitre, code=code, libelle=libelle)
            questions[code] = [
                models.Question(
                    competence=competence,
                    enonce=enonce,
                    type=type_,
                    solution=solution,
                    difficulte=difficulte,
                    archivee=bool(reste and reste[0]),
                )
                for enonce, type_, solution, difficulte, *reste in items
            ]
            session.add_all(questions[code])

    eleves: dict[str, models.Eleve] = {}
    for code, niveau, prenoms in CLASSES:
        classe = models.Classe(code=code, niveau=niveau, enseignant=enseignant)
        for prenom in prenoms:
            eleves[prenom] = models.Eleve(prenom=prenom, classe=classe)
        session.add(classe)
    session.flush()  # attribue les id, nécessaires à la conversion vers le moteur

    instant = datetime.now(UTC) - timedelta(days=1)
    for prenom, saisies in SEANCES:
        seance = models.Seance(eleve=eleves[prenom], debut=instant)
        for code, rang, saisie in saisies:
            question = questions[code][rang]
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
        session.add(seance)

    session.commit()
    return True


def main() -> None:
    from app.db.session import SessionLocale

    with SessionLocale() as session:
        print("Données de démo chargées." if charger_demo(session) else "Données de démo déjà présentes.")


if __name__ == "__main__":
    main()
