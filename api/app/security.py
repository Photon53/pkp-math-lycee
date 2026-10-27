"""Hachage des mots de passe enseignant et jetons d'accès signés.

Les élèves n'ont pas de mot de passe : ils se connectent avec prénom + code classe.
Bibliothèque standard uniquement (scrypt, HMAC-SHA256).
"""

import base64
import hashlib
import hmac
import secrets
import time

from app.config import settings

# Coût scrypt. Les paramètres sont enregistrés dans chaque empreinte, on peut donc
# les augmenter plus tard sans invalider les mots de passe existants.
_N, _R, _P = 2**14, 8, 1


def _b64(donnees: bytes) -> str:
    return base64.urlsafe_b64encode(donnees).decode().rstrip("=")


def _deb64(texte: str) -> bytes:
    return base64.urlsafe_b64decode(texte + "=" * (-len(texte) % 4))


def hacher_mot_de_passe(mot_de_passe: str) -> str:
    sel = secrets.token_bytes(16)
    empreinte = hashlib.scrypt(mot_de_passe.encode(), salt=sel, n=_N, r=_R, p=_P)
    return f"scrypt${_N}${_R}${_P}${_b64(sel)}${_b64(empreinte)}"


def verifier_mot_de_passe(mot_de_passe: str, stocke: str) -> bool:
    try:
        algo, n, r, p, sel, empreinte = stocke.split("$")
        if algo != "scrypt":
            return False
        calcul = hashlib.scrypt(mot_de_passe.encode(), salt=_deb64(sel), n=int(n), r=int(r), p=int(p))
    except ValueError:
        return False
    return hmac.compare_digest(calcul, _deb64(empreinte))


def creer_jeton(role: str, sujet_id: int, duree_h: int) -> str:
    """Jeton `charge.signature` où charge = « role:id:expiration »."""
    charge = f"{role}:{sujet_id}:{int(time.time()) + duree_h * 3600}".encode()
    return f"{_b64(charge)}.{_b64(_signer(charge))}"


def lire_jeton(jeton: str, role_attendu: str) -> int | None:
    """Renvoie l'id du sujet si le jeton est authentique, non expiré et du bon rôle."""
    try:
        charge_b64, signature_b64 = jeton.split(".")
        charge = _deb64(charge_b64)
        if not hmac.compare_digest(_signer(charge), _deb64(signature_b64)):
            return None
        role, sujet_id, expiration = charge.decode().split(":")
        if role != role_attendu or int(expiration) < time.time():
            return None
        return int(sujet_id)
    except (ValueError, UnicodeDecodeError):
        return None


def _signer(charge: bytes) -> bytes:
    return hmac.new(settings.secret_key.encode(), charge, hashlib.sha256).digest()
