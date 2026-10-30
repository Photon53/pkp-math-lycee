from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

CLE_DEV = "dev-uniquement-a-changer"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="PKP_")

    environnement: Literal["dev", "production"] = "dev"
    database_url: str = "sqlite:///./pkp.db"
    cors_origins: list[str] = ["http://localhost:5173"]
    # Clé de signature des jetons. Générer : python -c "import secrets; print(secrets.token_urlsafe(48))"
    secret_key: str = CLE_DEV
    duree_jeton_eleve_h: int = 12
    duree_jeton_enseignant_h: int = 8
    # Espace administrateur : session courte (cahier des charges V2, EA2.4).
    duree_jeton_admin_min: int = 30
    # Second facteur des administrateurs. Toujours exigé en production (voir `totp_requis`).
    totp_admin_obligatoire: bool = False

    # Ressources : fichiers PDF, hors de la racine web, servis par l'API après contrôle des droits.
    dossier_fichiers: str = "./fichiers"
    pdf_taille_max_mo: int = 10
    pdf_max_par_enseignant: int = 50
    # Vérifier qu'un lien répond au moment où il est enregistré (désactivé en test).
    verifier_liens: bool = True

    # Limitation des tentatives de connexion, sur une fenêtre glissante.
    # Les plafonds par IP restent larges : une classe entière sort souvent par
    # la même adresse (réseau du lycée).
    connexion_fenetre_min: int = 15
    connexion_enseignant_max_echecs: int = 5  # par compte enseignant
    connexion_eleve_max_codes_inconnus: int = 30  # codes classe inconnus, par IP
    connexion_eleve_max_echecs_code: int = 5  # codes personnels faux, par compte élève
    connexion_max_par_ip: int = 300  # toutes tentatives confondues

    # Banque de questions : servir aussi les questions pas encore validées par un enseignant.
    # À passer à False dès que la validation pédagogique de la banque est faite.
    servir_questions_non_validees: bool = True

    # RGPD : un élève sans activité depuis ce délai est supprimé par la purge.
    retention_jours: int = 365

    @property
    def production(self) -> bool:
        return self.environnement == "production"

    @property
    def totp_requis(self) -> bool:
        return self.production or self.totp_admin_obligatoire

    @model_validator(mode="after")
    def _verifier_production(self) -> "Settings":
        """En production, l'API refuse de démarrer avec une configuration dangereuse
        (pydantic transforme la ValueError en ValidationError au chargement)."""
        if not self.production:
            return self
        problemes = []
        if self.secret_key == CLE_DEV or len(self.secret_key) < 32:
            problemes.append("PKP_SECRET_KEY doit être définie (32 caractères minimum, aléatoire).")
        if any("localhost" in o or o == "*" for o in self.cors_origins):
            problemes.append("PKP_CORS_ORIGINS ne doit contenir que le domaine public du site.")
        if self.database_url.startswith("sqlite"):
            problemes.append("PKP_DATABASE_URL doit pointer vers PostgreSQL en production.")
        if problemes:
            raise ValueError("Configuration de production invalide :\n- " + "\n- ".join(problemes))
        return self


settings = Settings()
