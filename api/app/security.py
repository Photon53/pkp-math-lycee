"""Hachage des mots de passe enseignant et jetons d'accès signés.

Les élèves n'ont pas de mot de passe : ils se connectent avec prénom + code classe.
Bibliothèque standard uniquement (scrypt, HMAC-SHA256).
"""

import base64
import hashlib
import hmac
import secrets
import threading
import time

from app.config import settings

# Coût scrypt : recommandation OWASP (Password Storage Cheat Sheet) N = 2^17, r = 8, p = 1,
# soit 128 Mo de mémoire par hachage (audit A-06). Les paramètres sont enregistrés dans
# chaque empreinte : une empreinte plus faible est re-hachée à la connexion (doit_rehacher).
_N, _R, _P = 2**17, 8, 1
# Python limite scrypt à 32 Mo par défaut : on autorise jusqu'à 2^18 (256 Mo). Une empreinte
# demandant davantage est refusée plutôt que de laisser saturer la mémoire.
_MEMOIRE_MAX = 300 * 1024 * 1024
# Au plus 2 hachages simultanés (≈ 256 Mo) : sans cette borne, une rafale de connexions
# parallèles (jusqu'à 40 dans le pool de threads d'uvicorn) réclamerait ≈ 5 Go.
_CALCULS_SIMULTANES = threading.BoundedSemaphore(2)


def _b64(donnees: bytes) -> str:
    return base64.urlsafe_b64encode(donnees).decode().rstrip("=")


def _deb64(texte: str) -> bytes:
    return base64.urlsafe_b64decode(texte + "=" * (-len(texte) % 4))


def _scrypt(mot_de_passe: str, sel: bytes, n: int, r: int, p: int) -> bytes:
    with _CALCULS_SIMULTANES:
        return hashlib.scrypt(mot_de_passe.encode(), salt=sel, n=n, r=r, p=p, maxmem=_MEMOIRE_MAX)


def hacher_mot_de_passe(mot_de_passe: str) -> str:
    sel = secrets.token_bytes(16)
    return f"scrypt${_N}${_R}${_P}${_b64(sel)}${_b64(_scrypt(mot_de_passe, sel, _N, _R, _P))}"


def verifier_mot_de_passe(mot_de_passe: str, stocke: str) -> bool:
    try:
        algo, n, r, p, sel, empreinte = stocke.split("$")
        if algo != "scrypt":
            return False
        calcul = _scrypt(mot_de_passe, _deb64(sel), int(n), int(r), int(p))
    except (ValueError, MemoryError):
        return False
    return hmac.compare_digest(calcul, _deb64(empreinte))


def doit_rehacher(stocke: str) -> bool:
    """Vrai si l'empreinte a été calculée avec des paramètres plus faibles que les actuels."""
    try:
        _, n, r, p, _, _ = stocke.split("$")
        return (int(n), int(r), int(p)) < (_N, _R, _P)
    except ValueError:
        return True


def version_mot_de_passe(empreinte_stockee: str) -> str:
    """Empreinte courte du hachage du mot de passe, embarquée dans les jetons enseignant.
    Changer le mot de passe change cette valeur et invalide tous les jetons émis avant (audit A-09)."""
    return hashlib.sha256(empreinte_stockee.encode()).hexdigest()[:16]


def creer_jeton(role: str, sujet_id: int, duree_h: int, version: str = "") -> str:
    """Jeton `charge.signature` où charge = « role:id:expiration:version »."""
    charge = f"{role}:{sujet_id}:{int(time.time()) + duree_h * 3600}:{version}".encode()
    return f"{_b64(charge)}.{_b64(_signer(charge))}"


def lire_jeton(jeton: str, role_attendu: str) -> tuple[int, str] | None:
    """Renvoie (id du sujet, version) si le jeton est authentique, non expiré et du bon rôle."""
    try:
        charge_b64, signature_b64 = jeton.split(".")
        charge = _deb64(charge_b64)
        if not hmac.compare_digest(_signer(charge), _deb64(signature_b64)):
            return None
        role, sujet_id, expiration, version = charge.decode().split(":")
        if role != role_attendu or int(expiration) < time.time():
            return None
        return int(sujet_id), version
    except (ValueError, UnicodeDecodeError):
        return None


def _signer(charge: bytes) -> bytes:
    return hmac.new(settings.secret_key.encode(), charge, hashlib.sha256).digest()
