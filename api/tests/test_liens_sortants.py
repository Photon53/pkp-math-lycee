# Issue #3 — Prévenir les requêtes serveur vers des destinations internes (Claude)
"""Tests de contournement de la vérification des liens, sans aucun accès réseau.

La résolution DNS (`socket.getaddrinfo`) et la connexion HTTPS (`ConnexionEpinglee`) sont simulées :
les tests vérifient quelles destinations seraient contactées, et avec quelle adresse.
"""
import socket
import ssl

import pytest

from app import liens_sortants, ressources
from app.db import models
from app.liens_sortants import DestinationInterdite, adresse_publique, lien_repond, resoudre

DNS = {
    "exemple.test": ["93.184.216.34"],
    "autre.test": ["2606:4700:4700::1111"],
    "interne.test": ["10.0.0.5"],
    "local.test": ["127.0.0.1"],
    "mixte.test": ["93.184.216.34", "192.168.1.10"],
    "metadonnees.test": ["169.254.169.254"],
    "interdit.test": ["93.184.216.35"],
}


@pytest.fixture
def reseau(monkeypatch):
    """DNS simulé et serveurs scriptés : réponses[(hôte, chemin)] = (statut, Location) ou liste par méthode."""
    contacts = []
    reponses = {}
    resolutions = []

    def getaddrinfo(hote, port, *args, **kwargs):
        resolutions.append(hote)
        try:
            adresse = [hote] if adresse_brute(hote) else DNS[hote]
        except KeyError:
            raise socket.gaierror("nom inconnu") from None
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (a, port)) for a in adresse]

    class FausseConnexion:
        def __init__(self, hote, adresse, delai_s):
            self.hote, self.adresse = hote, adresse

        def request(self, methode, chemin, headers):
            contacts.append((methode, self.hote, self.adresse, chemin))
            reponse = reponses.get((self.hote, chemin), (200, None))
            self.reponse = reponse.get(methode, (200, None)) if isinstance(reponse, dict) else reponse

        def getresponse(self):
            statut, location = self.reponse
            return type("R", (), {"status": statut, "getheader": lambda _self, nom: location})()

        def close(self):
            pass

    monkeypatch.setattr(liens_sortants.socket, "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(liens_sortants, "ConnexionEpinglee", FausseConnexion)
    return type("Reseau", (), {"contacts": contacts, "reponses": reponses, "resolutions": resolutions})


def adresse_brute(hote: str) -> bool:
    try:
        adresse_publique(hote)
        return True
    except ValueError:
        return False


# --- Adresses -------------------------------------------------------------------------------------------


@pytest.mark.parametrize("adresse", [
    "127.0.0.1", "10.0.0.5", "172.16.0.1", "192.168.1.1", "169.254.169.254", "100.64.0.1", "0.0.0.0",
    "198.18.0.1", "224.0.0.1", "255.255.255.255", "::1", "::", "fe80::1", "fe80::1%eth0", "fc00::1",
    "::ffff:127.0.0.1", "::ffff:10.0.0.1", "::ffff:169.254.169.254", "64:ff9b::7f00:1", "2002:7f00:1::",
    "ff02::1",
])
def test_adresses_internes_refusees(adresse):
    assert not adresse_publique(adresse)


@pytest.mark.parametrize("adresse", ["93.184.216.34", "8.8.8.8", "2606:4700:4700::1111", "::ffff:8.8.8.8"])
def test_adresses_publiques_acceptees(adresse):
    assert adresse_publique(adresse)


def test_un_nom_qui_resout_aussi_vers_une_adresse_privee_est_refuse(reseau):
    with pytest.raises(DestinationInterdite):
        resoudre("mixte.test")
    assert resoudre("exemple.test") == "93.184.216.34"


# --- Destinations refusées avant toute connexion -------------------------------------------------------


@pytest.mark.parametrize("url", [
    "https://interne.test/",            # nom qui résout vers un réseau privé
    "https://local.test/",              # nom qui résout vers la boucle locale
    "https://metadonnees.test/",        # nom qui résout vers les métadonnées du cloud
    "https://mixte.test/",              # une adresse publique, une privée
    "https://127.0.0.1/",               # adresse littérale
    "https://169.254.169.254/computeMetadata/v1/",
    "https://[::1]/",
    "https://[::ffff:10.0.0.1]/",
    "https://exemple.test:8443/",       # port non standard
    "https://u:mdp@exemple.test/",      # identifiants
    "http://exemple.test/",             # pas https
    "https://inconnu.test/",            # nom introuvable
])
def test_destination_interdite_jamais_contactee(reseau, url):
    assert lien_repond(url) is False
    assert reseau.contacts == []


def test_lien_public_contacte_sur_l_adresse_validee(reseau):
    assert lien_repond("https://exemple.test/page?x=1") is True
    assert reseau.contacts == [("HEAD", "exemple.test", "93.184.216.34", "/page?x=1")]
    assert reseau.resolutions == ["exemple.test"]  # une seule résolution : pas de rebinding possible


def test_lien_public_ipv6(reseau):
    assert lien_repond("https://autre.test/") is True


# --- Redirections -----------------------------------------------------------------------------------------


@pytest.mark.parametrize("location", [
    "https://interne.test/admin",
    "https://169.254.169.254/latest/meta-data/",
    "http://exemple.test/",
    "https://exemple.test:8080/",
    "https://u:p@exemple.test/",
    "ftp://exemple.test/",
])
def test_redirection_vers_destination_interdite_non_suivie(reseau, location):
    reseau.reponses[("exemple.test", "/")] = (302, location)
    assert lien_repond("https://exemple.test/") is False
    assert [c[1] for c in reseau.contacts] == ["exemple.test"]


def test_redirection_relative_puis_publique_suivie(reseau):
    reseau.reponses[("exemple.test", "/ancien")] = (301, "/nouveau")
    reseau.reponses[("exemple.test", "/nouveau")] = (302, "https://autre.test/fin")
    assert lien_repond("https://exemple.test/ancien") is True
    assert [(c[1], c[3]) for c in reseau.contacts] == [
        ("exemple.test", "/ancien"), ("exemple.test", "/nouveau"), ("autre.test", "/fin"),
    ]


def test_redirection_vers_domaine_interdit_non_suivie(reseau):
    reseau.reponses[("exemple.test", "/")] = (302, "https://interdit.test/")
    assert lien_repond("https://exemple.test/", url_autorisee=lambda u: "interdit.test" not in u) is False
    assert [c[1] for c in reseau.contacts] == ["exemple.test"]


def test_boucle_de_redirections_bornee(reseau):
    reseau.reponses[("exemple.test", "/")] = (302, "/")
    assert lien_repond("https://exemple.test/") is False
    assert len(reseau.contacts) == liens_sortants.MAX_REDIRECTIONS + 1


def test_head_refuse_puis_get(reseau):
    reseau.reponses[("exemple.test", "/")] = {"HEAD": (405, None), "GET": (200, None)}
    assert lien_repond("https://exemple.test/") is True
    assert [c[0] for c in reseau.contacts] == ["HEAD", "GET"]


def test_lien_mort(reseau):
    reseau.reponses[("exemple.test", "/")] = (404, None)
    assert lien_repond("https://exemple.test/") is False


# --- Épinglage de l'adresse dans la vraie connexion --------------------------------------------------------


def test_connexion_epinglee_vise_l_adresse_et_verifie_le_certificat_du_nom(monkeypatch):
    appels = {}

    class FauxContexte:
        def wrap_socket(self, brut, server_hostname):
            appels["server_hostname"] = server_hostname
            return brut

    monkeypatch.setattr(liens_sortants.socket, "create_connection",
                        lambda adresse, delai: appels.setdefault("connexion", adresse) and object())
    connexion = liens_sortants.ConnexionEpinglee("exemple.test", "93.184.216.34", 3)
    assert connexion._context.check_hostname and connexion._context.verify_mode == ssl.CERT_REQUIRED
    connexion._context = FauxContexte()
    connexion.connect()
    assert appels == {"connexion": ("93.184.216.34", 443), "server_hostname": "exemple.test"}
    assert connexion.host == "exemple.test"  # en-tête Host


# --- Intégration avec les ressources ------------------------------------------------------------------------


def test_ressources_revalident_les_domaines_interdits_en_base(reseau, session):
    session.add(models.DomaineInterdit(domaine="interdit.test"))
    session.commit()
    reseau.reponses[("exemple.test", "/")] = (302, "https://www.interdit.test/")
    assert ressources.lien_repond("https://exemple.test/", session) is False
    assert [c[1] for c in reseau.contacts] == ["exemple.test"]
