# Issue #171 — Candidatures de professeurs et demandes de partenariat (Claude)
"""Candidatures et partenariats : ouverture du formulaire et CV (issue #171).

Les demandes elles-mêmes sont des demandes d'« Accueil et demandes » (`app.accueil`, #172).

Le CV est un **PDF seulement**, de `PKP_CV_TAILLE_MAX_MO` au plus. Il passe par le contrôle renforcé des PDF (#4,
`app.controle_pdf`) : vérification du type réel (en-tête puis analyse complète, liste blanche), refus des PDF
chiffrés ou porteurs de contenu actif. Un fichier refusé n'est jamais écrit. Le fichier accepté est enregistré sous
un nom aléatoire, en lecture-écriture pour le seul processus de l'API, dans `PKP_DOSSIER_CANDIDATURES` : un dossier
privé, distinct des ressources pédagogiques (`PKP_DOSSIER_FICHIERS`), qu'aucune route publique ne sert. Il n'est lu
que par la route de téléchargement des administrateurs.
"""

import base64
import binascii
import os
import secrets
from pathlib import Path

from fastapi import HTTPException, status

from app import controle_pdf
from app.config import settings
from app.db import models

FORMATS_CV = ("pdf",)


def taille_max_cv() -> int:
    return settings.cv_taille_max_mo * 1024 * 1024


def taille_max_corps() -> int:
    """Corps JSON d'une candidature : CV encodé en base64 (+ 33 %) et champs texte."""
    return taille_max_cv() * 4 // 3 + 64 * 1024


# --- CV ---------------------------------------------------------------------------------------------------


def dossier() -> Path:
    chemin = Path(settings.dossier_candidatures)
    chemin.mkdir(parents=True, exist_ok=True, mode=0o700)
    return chemin


def decoder_cv(cv_base64: str) -> bytes:
    """Décodage strict ; la taille est contrôlée avant l'analyse."""
    if len(cv_base64) > taille_max_cv() * 4 // 3 + 4:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"Le CV dépasse {settings.cv_taille_max_mo} Mo.")
    try:
        contenu = base64.b64decode(cv_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Le CV n'a pas pu être lu. Réessayez.") from None
    if not contenu:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Le CV est vide.")
    if len(contenu) > taille_max_cv():
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"Le CV dépasse {settings.cv_taille_max_mo} Mo.")
    return contenu


def controler_cv(contenu: bytes) -> None:
    """Type réel : en-tête PDF, puis analyse isolée (#4). Appel bloquant : passer par `run_in_threadpool`."""
    if not contenu.startswith(b"%PDF-"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Le CV doit être un fichier PDF.")
    try:
        controle_pdf.analyser_isole(contenu)
    except controle_pdf.PdfRefuse as refus:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"CV refusé : {refus}") from None


def ecrire_cv(contenu: bytes) -> str:
    """Écrit le CV déjà contrôlé sous un nom aléatoire ; renvoie ce nom (jamais montré au public)."""
    nom = secrets.token_hex(16) + ".pdf"
    chemin = dossier() / nom
    descripteur = os.open(chemin, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descripteur, "wb") as f:
        f.write(contenu)
    return nom


def chemin_cv(demande: models.DemandeAccueil) -> Path:
    if not demande.cv_fichier:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucun CV pour cette demande.")
    chemin = dossier() / demande.cv_fichier
    if not chemin.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "CV introuvable.")
    return chemin


def supprimer_cv(nom: str | None) -> None:
    if nom:
        (dossier() / Path(nom).name).unlink(missing_ok=True)
