# Issue #35 — gabarit des corrigés du périmètre pilote (DeepSeek)
"""Contrôle de qualité des corrigés du périmètre pilote de l'issue #35.

L'inventaire `corriges_pilote.json` grandit à chaque lot : on y ajoute les codes
traités. Quand toute la banque sera reprise, le contrôle pourra viser toutes les
questions de difficulté 3 ou plus, comme le fait déjà `python -m app.contenu corrections`.

Ce test ne dit rien de la justesse mathématique d'un corrigé : il vérifie que le
gabarit est respecté. La validation pédagogique reste humaine (AGENTS.md § 8).
"""

import json
from functools import lru_cache
from pathlib import Path

import pytest

from app import contenu

# Gabarit défini dans docs/CONTENU.md, section « Gabarit d'un corrigé étape par étape ».
ETAPES_MIN = 3
LONGUEUR_ETAPE_MIN = 20
INVENTAIRE = Path(__file__).with_name("corriges_pilote.json")


@lru_cache(maxsize=1)
def _codes() -> tuple[str, ...]:
    return tuple(json.loads(INVENTAIRE.read_text(encoding="utf-8"))["codes"])


@lru_cache(maxsize=1)
def _questions() -> dict[str, contenu.QuestionYaml]:
    fichiers = contenu.charger(contenu.DOSSIER_PAR_DEFAUT)
    return {q.code: q for _, f in fichiers for c in f.competences for q in c.questions}


def _etapes_utiles(correction: contenu.CorrectionYaml) -> list[str]:
    return [etape for etape in correction.etapes if len(etape.strip()) >= LONGUEUR_ETAPE_MIN]


def test_inventaire_non_vide():
    assert len(_codes()) >= 19, "l'inventaire du périmètre pilote ne doit pas régresser"


def test_les_codes_pilotes_existent():
    manquants = sorted(set(_codes()) - set(_questions()))
    assert not manquants, f"codes absents du contenu : {manquants}"


@pytest.mark.parametrize("code", _codes())
def test_gabarit_du_corrige(code: str):
    question = _questions()[code]
    correction = question.correction

    assert correction is not None, "corrigé absent"
    assert correction.methode, "méthode absente : nommer la notion et la formule utilisée"
    assert len(_etapes_utiles(correction)) >= ETAPES_MIN, (
        f"{len(_etapes_utiles(correction))} étape(s) utile(s), {ETAPES_MIN} attendues"
    )
    assert correction.erreurs_frequentes, "au moins une erreur fréquente est attendue"

    # Une réponse numérique ou une expression se contrôle : la vérification est exigée.
    if question.type is not contenu.TypeQuestion.QCM:
        assert any("Vérification" in etape for etape in correction.etapes), (
            "étape de vérification absente (substitution, ordre de grandeur, unité, signe)"
        )
