"""Phase 6 : configuration de production et limitation des tentatives de connexion."""

import pytest

from app import limitation
from app.config import CLE_DEV, Settings
from app.limitation import Limiteur
from tests.conftest import connecter_enseignant, corps_connexion, inscrire_eleves

PROD_VALIDE = {
    "environnement": "production",
    "secret_key": "x" * 48,
    "database_url": "postgresql+psycopg://pkp:mdp@db:5432/pkp",
    "cors_origins": ["https://maths.lycee.fr"],
}


def config(**valeurs) -> Settings:
    return Settings(_env_file=None, **valeurs)


class TestConfiguration:
    def test_dev_accepte_les_valeurs_par_defaut(self):
        assert config().secret_key == CLE_DEV

    def test_production_valide(self):
        assert config(**PROD_VALIDE).production

    @pytest.mark.parametrize(
        ("champ", "valeur", "message"),
        [
            ("secret_key", CLE_DEV, "PKP_SECRET_KEY"),
            ("secret_key", "trop-courte", "PKP_SECRET_KEY"),
            ("cors_origins", ["http://localhost:5173"], "PKP_CORS_ORIGINS"),
            ("cors_origins", ["*"], "PKP_CORS_ORIGINS"),
            ("database_url", "sqlite:///./pkp.db", "PKP_DATABASE_URL"),
        ],
    )
    def test_production_refuse_une_configuration_dangereuse(self, champ, valeur, message):
        with pytest.raises(ValueError, match=message):
            config(**{**PROD_VALIDE, champ: valeur})

    def test_lu_depuis_l_environnement(self, monkeypatch):
        monkeypatch.setenv("PKP_ENVIRONNEMENT", "production")
        with pytest.raises(ValueError):
            config()


class HorlogeFactice:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class TestLimiteur:
    def test_fenetre_glissante(self):
        limiteur, horloge = Limiteur(2, 60), HorlogeFactice()
        limiteur.horloge = horloge
        limiteur.enregistrer("a")
        horloge.t += 10
        limiteur.enregistrer("a")
        assert limiteur.attente("a") == pytest.approx(50)
        assert limiteur.attente("b") == 0  # clés indépendantes
        horloge.t += 50
        assert limiteur.attente("a") == 0

    def test_pas_d_accumulation_en_memoire(self):
        limiteur, horloge = Limiteur(5, 60), HorlogeFactice()
        limiteur.horloge = horloge
        for i in range(100):
            limiteur.enregistrer(f"ip-{i}")
        horloge.t += 61
        for i in range(100):
            limiteur.attente(f"ip-{i}")
        assert limiteur._evenements == {}


def tenter(client, mdp, email="demo@pkp.test"):
    return client.post("/enseignants/connexion", json={"email": email, "mot_de_passe": mdp})


class TestConnexionEnseignant:
    def test_compte_bloque_apres_5_echecs_meme_avec_le_bon_mot_de_passe(self, client):
        for _ in range(5):
            assert tenter(client, "mauvais").status_code == 401
        r = tenter(client, "demo-pkp-2026")
        assert r.status_code == 429
        assert 0 < int(r.headers["Retry-After"]) <= 15 * 60
        assert "Réessayez dans 15 minutes" in r.json()["detail"]

    def test_deblocage_apres_la_fenetre(self, client):
        horloge = HorlogeFactice()
        limitation.echecs_enseignant.horloge = horloge
        for _ in range(5):
            tenter(client, "mauvais")
        horloge.t += 15 * 60 + 1
        assert tenter(client, "demo-pkp-2026").status_code == 200

    def test_une_connexion_reussie_remet_le_compteur_a_zero(self, client):
        for _ in range(4):
            tenter(client, "mauvais")
        connecter_enseignant(client)
        for _ in range(4):
            assert tenter(client, "mauvais").status_code == 401
        assert tenter(client, "demo-pkp-2026").status_code == 200

    def test_blocage_limite_au_compte_vise(self, client, fabrique):
        for _ in range(5):
            tenter(client, "mauvais", "inconnu@pkp.test")
        assert tenter(client, "demo-pkp-2026").status_code == 200


class TestConnexionEleve:
    def test_recherche_de_codes_classe_freinee(self, client):
        for i in range(30):
            r = client.post("/eleves/connexion", json=corps_connexion("Lina", f"FAUX-{i}"))
            assert r.status_code == 401
        r = client.post("/eleves/connexion", json=corps_connexion("Lina"))
        assert r.status_code == 429

    def test_une_classe_entiere_derriere_la_meme_ip(self, client):
        """Le réseau du lycée : 35 élèves, une seule IP, quelques fautes de frappe."""
        prenoms = [f"Eleve {chr(65 + i % 26)}{chr(97 + i // 26)}" for i in range(35)]
        codes = inscrire_eleves(client, "2NDE-A-DEMO", prenoms)
        for i, prenom in enumerate(prenoms):
            if i % 5 == 0:  # faute de frappe sur le code classe, puis sur le code personnel
                client.post("/eleves/connexion", json=corps_connexion(prenom, "2NDE-A-DEMQ", codes[prenom]))
                client.post("/eleves/connexion", json=corps_connexion(prenom, "2NDE-A-DEMO", "ZZZZZZ"))
            r = client.post("/eleves/connexion", json=corps_connexion(prenom, "2NDE-A-DEMO", codes[prenom]))
            assert r.status_code == 200, r.text
