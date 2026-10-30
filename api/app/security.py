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


def _hacher(secret: str, n: int) -> str:
    sel = secrets.token_bytes(16)
    return f"scrypt${n}${_R}${_P}${_b64(sel)}${_b64(_scrypt(secret, sel, n, _R, _P))}"


def hacher_mot_de_passe(mot_de_passe: str) -> str:
    return _hacher(mot_de_passe, _N)


# --- Code personnel des élèves (audit A-07, décision D1) ----------------------
# 6 caractères sans 0/O ni 1/I/L (recopiés à la main) : 31^6 ≈ 887 millions de codes.
# Coût de hachage modéré (4 Mo, quelques ms) : 35 élèves doivent pouvoir se connecter
# ensemble ; la protection contre les essais vient du blocage par compte (limitation.py).
ALPHABET_CODE = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
LONGUEUR_CODE_ELEVE = 6
_N_CODE = 2**12


def generer_code_eleve() -> str:
    return "".join(secrets.choice(ALPHABET_CODE) for _ in range(LONGUEUR_CODE_ELEVE))


def normaliser_code(code: str) -> str:
    """« k7m 4qp », « K7M-4QP » et « K7M4QP » désignent le même code."""
    return "".join(c for c in code.upper() if c not in " -")


def hacher_code_eleve(code: str) -> str:
    return _hacher(normaliser_code(code), _N_CODE)


def verifier_code_eleve(code: str, stocke: str) -> bool:
    return verifier_mot_de_passe(normaliser_code(code), stocke)


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
    """Empreinte courte du hachage d'un secret (mot de passe enseignant, code personnel élève),
    embarquée dans les jetons. Changer le secret change cette valeur et invalide tous les jetons
    émis avant (audit A-09, et régénération d'un code élève)."""
    return hashlib.sha256(empreinte_stockee.encode()).hexdigest()[:16]


def creer_jeton(role: str, sujet_id: int, duree_h: float, version: str = "") -> str:
    """Jeton `charge.signature` où charge = « role:id:expiration:version »."""
    charge = f"{role}:{sujet_id}:{int(time.time() + duree_h * 3600)}:{version}".encode()
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


# --- Second facteur des administrateurs (TOTP, RFC 6238) -----------------------
# Compatible avec les applications d'authentification courantes : SHA-1, 6 chiffres, 30 s.
_TOTP_PAS_S = 30
_TOTP_CHIFFRES = 6


def generer_secret_totp() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode()


def code_totp(secret: str, instant: float | None = None) -> str:
    compteur = int((time.time() if instant is None else instant) // _TOTP_PAS_S)
    cle = base64.b32decode(secret.upper() + "=" * (-len(secret) % 8))
    mac = hmac.new(cle, compteur.to_bytes(8, "big"), hashlib.sha1).digest()
    decalage = mac[-1] & 0x0F
    valeur = int.from_bytes(mac[decalage : decalage + 4], "big") & 0x7FFFFFFF
    return str(valeur % 10**_TOTP_CHIFFRES).zfill(_TOTP_CHIFFRES)


def verifier_totp(secret: str, code: str, instant: float | None = None) -> bool:
    """Accepte le pas courant et ses deux voisins (décalage d'horloge du téléphone)."""
    maintenant = time.time() if instant is None else instant
    code = code.replace(" ", "")
    return any(
        hmac.compare_digest(code_totp(secret, maintenant + d * _TOTP_PAS_S), code) for d in (-1, 0, 1)
    )


def uri_totp(secret: str, email: str) -> str:
    """À transformer en QR code ou à saisir dans l'application d'authentification."""
    return f"otpauth://totp/PKP%20Math%20Lyc%C3%A9e:{email}?secret={secret}&issuer=PKP%20Math%20Lyc%C3%A9e"


def generer_mot_de_passe_provisoire() -> str:
    # 16 caractères sans caractères ambigus : recopié à la main par le professeur.
    return "".join(secrets.choice(ALPHABET_CODE + "abcdefghjkmnpqrstuvwxyz") for _ in range(16))


def _signer(charge: bytes) -> bytes:
    return hmac.new(settings.secret_key.encode(), charge, hashlib.sha256).digest()
