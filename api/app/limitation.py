"""Limitation des tentatives de connexion (fenêtre glissante, en mémoire).

Suffisant pour un processus unique (déploiement prévu : 1 worker uvicorn).
Avec plusieurs workers ou serveurs, chaque processus compterait séparément :
il faudrait alors un stockage partagé (Redis).
"""

import math
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.config import settings


class Limiteur:
    def __init__(self, max_evenements: int, fenetre_s: float):
        self.max_evenements = max_evenements
        self.fenetre_s = fenetre_s
        self.horloge = time.monotonic  # remplaçable en test
        self._evenements: dict[str, deque[float]] = defaultdict(deque)
        self._verrou = threading.Lock()

    def _purger(self, cle: str, maintenant: float) -> deque[float]:
        file = self._evenements[cle]
        while file and file[0] <= maintenant - self.fenetre_s:
            file.popleft()
        if not file:
            del self._evenements[cle]  # pas d'accumulation de clés en mémoire
        return file

    def attente(self, cle: str) -> float:
        """Secondes avant la prochaine tentative autorisée (0 si autorisée)."""
        with self._verrou:
            maintenant = self.horloge()
            file = self._purger(cle, maintenant)
            if len(file) < self.max_evenements:
                return 0.0
            return file[0] + self.fenetre_s - maintenant

    def enregistrer(self, cle: str) -> None:
        with self._verrou:
            self._evenements[cle].append(self.horloge())

    def effacer(self, cle: str) -> None:
        with self._verrou:
            self._evenements.pop(cle, None)

    def reinitialiser(self) -> None:
        with self._verrou:
            self._evenements.clear()


_fenetre = settings.connexion_fenetre_min * 60
par_ip = Limiteur(settings.connexion_max_par_ip, _fenetre)
echecs_enseignant = Limiteur(settings.connexion_enseignant_max_echecs, _fenetre)
codes_inconnus = Limiteur(settings.connexion_eleve_max_codes_inconnus, _fenetre)
# 5 essais par compte et par 15 min : deviner un code parmi 887 millions est hors de portée.
echecs_code_eleve = Limiteur(settings.connexion_eleve_max_echecs_code, _fenetre)

TOUS = (par_ip, echecs_enseignant, codes_inconnus, echecs_code_eleve)


def adresse_ip(request: Request) -> str:
    # Derrière Caddy, uvicorn --proxy-headers renseigne la vraie IP du client.
    return request.client.host if request.client else "inconnue"


def verifier(*controles: tuple[Limiteur, str]) -> None:
    """Lève 429 si l'un des couples (limiteur, clé) a atteint son plafond."""
    attente = max(limiteur.attente(cle) for limiteur, cle in controles)
    if attente > 0:
        minutes = math.ceil(attente / 60)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Trop de tentatives. Réessayez dans {minutes} minute{'s' if minutes > 1 else ''}.",
            headers={"Retry-After": str(math.ceil(attente))},
        )
