"""Non-régression des constats Élevés de l'audit de sécurité (docs/audit/lot-a-securite.md)."""

import base64

import pytest
from sqlalchemy import select

from app import security
from app.admin import changer_mot_de_passe, creer_enseignant
from app.db import models
from tests.conftest import connecter_enseignant, entete

# Valeurs réelles, capturées avant que la fixture `scrypt_rapide` n'abaisse le coût pour les tests.
N_REEL, R_REEL, P_REEL = security._N, security._R, security._P


class TestA06HachageDesMotsDePasse:
    def test_parametres_au_niveau_owasp(self):
        assert (N_REEL, R_REEL, P_REEL) >= (2**17, 8, 1)

    def test_hachage_reel_sans_depasser_la_limite_memoire(self, monkeypatch):
        """128 Mo par hachage : sans `maxmem`, Python refuserait (limite par défaut 32 Mo)."""
        monkeypatch.setattr(security, "_N", N_REEL)
        empreinte = security.hacher_mot_de_passe("un-mot-de-passe-solide")
        assert empreinte.startswith(f"scrypt${N_REEL}${R_REEL}${P_REEL}$")
        assert security.verifier_mot_de_passe("un-mot-de-passe-solide", empreinte)
        assert not security.verifier_mot_de_passe("autre", empreinte)

    def test_hachages_simultanes_bornes(self, monkeypatch):
        """Une rafale de connexions ne doit pas lancer plus de 2 calculs de 128 Mo à la fois."""
        import threading
        import time

        en_cours, maximum, verrou = 0, 0, threading.Lock()
        vrai_scrypt = security.hashlib.scrypt

        def scrypt_observe(*args, **kwargs):
            nonlocal en_cours, maximum
            with verrou:
                en_cours += 1
                maximum = max(maximum, en_cours)
            time.sleep(0.05)
            with verrou:
                en_cours -= 1
            return vrai_scrypt(*args, **kwargs)

        monkeypatch.setattr(security.hashlib, "scrypt", scrypt_observe)
        fils = [threading.Thread(target=security.hacher_mot_de_passe, args=("x",)) for _ in range(10)]
        for f in fils:
            f.start()
        for f in fils:
            f.join()
        assert maximum == 2

    def test_empreinte_demandant_trop_de_memoire_refusee(self):
        demesuree = "scrypt$" + str(2**22) + "$8$1$" + "A" * 22 + "$" + "A" * 43
        assert security.verifier_mot_de_passe("x", demesuree) is False

    def test_empreinte_faible_rehachee_a_la_connexion(self, client, fabrique, monkeypatch):
        monkeypatch.setattr(security, "_N", 2**4)
        with fabrique() as s:
            creer_enseignant(s, "ancien@pkp.test", "Ancien", "mot-de-passe-ancien")
        monkeypatch.setattr(security, "_N", 2**8)  # coût actuel (abaissé pour les tests)
        connecter_enseignant(client, "ancien@pkp.test", "mot-de-passe-ancien")
        with fabrique() as s:
            stocke = s.scalar(select(models.Enseignant.mot_de_passe_hash).where(models.Enseignant.email == "ancien@pkp.test"))
        assert stocke.startswith("scrypt$256$")
        assert not security.doit_rehacher(stocke)

    def test_echec_de_connexion_ne_rehache_pas(self, client, fabrique, monkeypatch):
        monkeypatch.setattr(security, "_N", 2**4)
        with fabrique() as s:
            creer_enseignant(s, "ancien@pkp.test", "Ancien", "mot-de-passe-ancien")
        monkeypatch.setattr(security, "_N", 2**8)
        r = client.post("/enseignants/connexion", json={"email": "ancien@pkp.test", "mot_de_passe": "mauvais"})
        assert r.status_code == 401
        with fabrique() as s:
            stocke = s.scalar(select(models.Enseignant.mot_de_passe_hash).where(models.Enseignant.email == "ancien@pkp.test"))
        assert stocke.startswith("scrypt$16$")


class TestA09RevocationDesJetons:
    def test_jeton_emis_avant_changement_de_mot_de_passe_refuse(self, client, fabrique):
        ancien = connecter_enseignant(client)
        assert client.get("/enseignants/classes", headers=ancien).status_code == 200
        with fabrique() as s:
            changer_mot_de_passe(s, "demo@pkp.test", "nouveau-mot-de-passe")
        assert client.get("/enseignants/classes", headers=ancien).status_code == 401
        nouveau = connecter_enseignant(client, mot_de_passe="nouveau-mot-de-passe")
        assert client.get("/enseignants/classes", headers=nouveau).status_code == 200

    def test_version_falsifiee_refusee(self, client):
        jeton = connecter_enseignant(client)["Authorization"].removeprefix("Bearer ")
        role, sujet, expiration, _ = base64.urlsafe_b64decode(jeton.split(".")[0] + "==").decode().split(":")
        refait = security.creer_jeton(role, int(sujet), 1, "0" * 16)  # bien signé, mauvaise version
        assert client.get("/enseignants/classes", headers=entete(refait)).status_code == 401

    def test_jeton_de_l_ancien_format_refuse(self, client):
        charge = b"enseignant:1:9999999999"  # format sans version, antérieur à la correction
        ancien = f"{security._b64(charge)}.{security._b64(security._signer(charge))}"
        assert client.get("/enseignants/classes", headers=entete(ancien)).status_code == 401

    @pytest.mark.parametrize("route", ["/eleves/moi", "/cours"])
    def test_jetons_eleves_inchanges(self, client, route):
        r = client.post("/eleves/connexion", json={"prenom": "Lina", "code_classe": "2NDE-A-DEMO"})
        assert client.get(route, headers=entete(r.json()["jeton"])).status_code == 200
