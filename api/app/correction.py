"""Mode de correction des quiz (#110, décisions du propriétaire du 14/11/2026, précision d'ARCH-4).

- « apres_chaque_question » (par défaut) : l'élève répond à une question, sa réponse est enregistrée, puis il en
  voit la correction ;
- « fin_du_quiz » : la correction n'est rendue qu'une fois chaque question répondue (#107).

Le professeur ou l'administrateur choisit le mode d'un groupe ; il peut le remplacer pour une séance donnée de ce
groupe (les séances sont communes à tous les groupes : le réglage d'une séance vaut pour ce groupe seulement).
Ordre de priorité : réglage de la séance, puis du groupe, puis le défaut.

Matières : anglais (groupe, séance) et français depuis #217 (classe, dossier : `Classe.mode_correction_de`), avec
les mêmes valeurs.
Les maths ne sont pas concernées (correction après chaque question, inchangée).
"""
# Issue #110 — Mode de correction choisi par le professeur (Claude)

from typing import Literal

from pydantic import BaseModel

APRES_CHAQUE_QUESTION = "apres_chaque_question"
FIN_DU_QUIZ = "fin_du_quiz"
MODES = (APRES_CHAQUE_QUESTION, FIN_DU_QUIZ)
DEFAUT = APRES_CHAQUE_QUESTION

ModeCorrection = Literal["apres_chaque_question", "fin_du_quiz"]


class ChoixMode(BaseModel):
    mode: ModeCorrection


class ChoixModeSeance(BaseModel):
    """`None` retire le réglage propre à la séance : le mode du groupe s'applique de nouveau."""

    mode: ModeCorrection | None


class ReglageCorrection(BaseModel):
    mode: ModeCorrection  # mode du groupe
    seances: dict[str, ModeCorrection]  # séances qui ont un réglage propre, par code (prioritaire)


def mode_effectif(mode_groupe: str | None, mode_seance: str | None) -> str:
    return mode_seance or mode_groupe or DEFAUT


# --- Réglage d'un groupe d'anglais ---------------------------------------------------------------------------


def reglage(groupe) -> ReglageCorrection:
    return ReglageCorrection(mode=groupe.mode_correction, seances={m.code: m.mode for m in groupe.modes_seances})


def regler_seance(session, groupe, code: str, mode: str | None) -> tuple[str | None, str | None]:
    """Fixe (ou retire, avec None) le mode d'une séance pour ce groupe ; renvoie (avant, après) pour le journal.

    La séance doit exister au niveau et dans le domaine du groupe (même règle que l'espace élève), sinon 404."""
    from fastapi import HTTPException, status

    from app import anglais_contenu
    from app.db import models

    seance = anglais_contenu.par_code(session, code)
    if seance is None or seance.niveau != groupe.niveau or seance.domaine_code != groupe.domaine_code:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Séance introuvable pour ce groupe.")
    actuel = next((m for m in groupe.modes_seances if m.code == seance.code), None)
    avant = actuel.mode if actuel else None
    if mode is None:
        # Réglage retiré : la séance suit de nouveau le mode du groupe.
        if actuel is not None:
            groupe.modes_seances.remove(actuel)
        return avant, None
    if actuel is None:
        groupe.modes_seances.append(models.ModeCorrectionSeanceAnglais(code=seance.code, mode=mode))
    else:
        actuel.mode = mode
    return avant, mode
