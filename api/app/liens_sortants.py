# Issue #3 — Prévenir les requêtes serveur vers des destinations internes (Claude)
"""Requêtes sortantes de vérification des liens, protégées contre la SSRF.

Une URL saisie par un adulte ne doit jamais faire contacter par l'API une adresse interne :
réseau privé, boucle locale, lien local (dont 169.254.169.254, métadonnées du cloud), plages réservées.

- le nom est résolu **une seule fois** ; toutes les adresses obtenues doivent être publiques ;
- la connexion TCP vise l'adresse validée (épinglage, contre le rebinding DNS), tandis que
  l'en-tête `Host` et la vérification du certificat portent sur le nom d'origine ;
- les redirections ne sont jamais suivies automatiquement : chaque saut est revalidé
  (https, pas d'identifiants, port 443, domaine autorisé, adresse publique) avant connexion ;
- durée totale, nombre de sauts et lecture de la réponse sont bornés (seuls le statut et
  l'en-tête `Location` sont lus, jamais le corps).
"""

import http.client
import ipaddress
import socket
import ssl
import time
from collections.abc import Callable
from urllib.parse import urljoin, urlsplit

PORT_HTTPS = 443
MAX_REDIRECTIONS = 5
AGENT = "PKP-Math-Lycee-verification-liens"


class DestinationInterdite(Exception):
    """L'URL ou l'adresse résolue ne peut pas être contactée par le serveur."""


def adresse_publique(adresse: str) -> bool:
    """Vrai pour une adresse routable sur Internet ; faux pour toute adresse interne ou réservée."""
    ip = ipaddress.ip_address(adresse.split("%", 1)[0])  # « fe80::1%eth0 » : zone retirée
    if isinstance(ip, ipaddress.IPv6Address):
        # ::ffff:10.0.0.1, 64:ff9b::7f00:1 (NAT64), 2002:7f00:1:: (6to4) : juger l'IPv4 embarquée.
        embarquee = ip.ipv4_mapped or ip.sixtofour
        if embarquee is None and ip in ipaddress.ip_network("64:ff9b::/96"):
            embarquee = ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
        if embarquee is not None:
            return adresse_publique(str(embarquee))
    return ip.is_global and not ip.is_multicast


def controler_url(url: str) -> tuple[str, str]:
    """https, nom d'hôte, port 443, sans identifiants. Renvoie (hôte, chemin et requête)."""
    morceaux = urlsplit(url)
    try:
        port = morceaux.port
    except ValueError as erreur:
        raise DestinationInterdite("port invalide") from erreur
    if morceaux.scheme != "https" or not morceaux.hostname or morceaux.username or morceaux.password:
        raise DestinationInterdite("URL non https ou avec identifiants")
    if port not in (None, PORT_HTTPS):
        raise DestinationInterdite("port non standard")
    chemin = morceaux.path or "/"
    if morceaux.query:
        chemin += "?" + morceaux.query
    return morceaux.hostname, chemin


def resoudre(hote: str) -> str:
    """Résout le nom une fois ; refuse si l'une des adresses obtenues n'est pas publique."""
    try:
        infos = socket.getaddrinfo(hote, PORT_HTTPS, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)
    except (OSError, UnicodeError) as erreur:
        raise DestinationInterdite("nom introuvable") from erreur
    adresses = list(dict.fromkeys(info[4][0] for info in infos))
    if not adresses or not all(adresse_publique(a) for a in adresses):
        raise DestinationInterdite("adresse non publique")
    return adresses[0]


class ConnexionEpinglee(http.client.HTTPSConnection):
    """Connexion HTTPS vers une adresse déjà validée ; certificat et `Host` vérifiés sur le nom."""

    def __init__(self, hote: str, adresse: str, delai_s: float):
        super().__init__(hote, PORT_HTTPS, timeout=delai_s, context=ssl.create_default_context())
        self.adresse = adresse

    def connect(self) -> None:
        brut = socket.create_connection((self.adresse, self.port), self.timeout)
        try:
            self.sock = self._context.wrap_socket(brut, server_hostname=self.host)
        except BaseException:
            brut.close()
            raise


def requete(url: str, methode: str, delai_s: float) -> tuple[int, str | None]:
    """Un seul échange, sans suivre de redirection. Renvoie (statut, en-tête Location)."""
    hote, chemin = controler_url(url)
    connexion = ConnexionEpinglee(hote, resoudre(hote), delai_s)
    try:
        connexion.request(methode, chemin, headers={"User-Agent": AGENT, "Accept": "*/*", "Connection": "close"})
        reponse = connexion.getresponse()
        return reponse.status, reponse.getheader("Location")
    finally:
        connexion.close()


def lien_repond(url: str, delai_s: float = 8, url_autorisee: Callable[[str], bool] | None = None) -> bool:
    """Le lien répond-il (2xx, ou 3xx sans destination) ? HEAD d'abord, GET si le site refuse HEAD.

    `url_autorisee` complète les contrôles pour chaque redirection (domaines interdits en base).
    """
    fin = time.monotonic() + 2 * delai_s
    for methode in ("HEAD", "GET"):
        courante = url
        for _ in range(MAX_REDIRECTIONS + 1):
            restant = fin - time.monotonic()
            if restant <= 0:
                return False
            try:
                statut, destination = requete(courante, methode, min(delai_s, restant))
            except (DestinationInterdite, OSError, http.client.HTTPException, ValueError):
                return False
            if 300 <= statut < 400 and destination:
                courante = urljoin(courante, destination)
                if url_autorisee is not None and not url_autorisee(courante):
                    return False
                continue
            if statut < 400:
                return True
            if statut in (403, 405, 501):
                break  # le site refuse peut-être HEAD : on retente en GET
            return False
        else:
            return False  # trop de redirections
    return False
