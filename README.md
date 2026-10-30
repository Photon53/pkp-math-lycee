# PKP Math Lycée

Plateforme de soutien scolaire en mathématiques pour le lycée.

```
web/ (React + Vite)  ──HTTP/JSON──▶  api/ (FastAPI)  ──▶  base de données
                                        │
                                        └──▶ engine/ (moteur Python pur)
```

| Dossier   | Rôle                                                        | Dépend de        |
|-----------|-------------------------------------------------------------|------------------|
| `engine/` | Moteur pédagogique pur : aucune dépendance web ni BDD       | rien             |
| `api/`    | API FastAPI : persistance, sécurité, orchestration du moteur | `engine/`        |
| `web/`    | Interface élève / enseignant                                | `api/` (HTTP)    |

Voir [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) pour les décisions, le schéma
des 8 tables et le découpage en 6 phases.

- Mise en production : [docs/DEPLOIEMENT.md](docs/DEPLOIEMENT.md) (Docker, PostgreSQL, HTTPS)
- Protection des données : [docs/RGPD.md](docs/RGPD.md) (checklist à valider avec le DPO)
- Rédiger cours et exercices : [docs/CONTENU.md](docs/CONTENU.md) (fichiers `contenu/<niveau>/<parcours>/*.yaml`)
- État de la banque (matrice de couverture, trous, sources) : [docs/CONTENU-INVENTAIRE.md](docs/CONTENU-INVENTAIRE.md)
- Audit (protocoles, grille de gravité, résultats) : [docs/audit/README.md](docs/audit/README.md)
- Version 2 commerciale (périmètre, exigences, recette, décisions) : [docs/CAHIER-DES-CHARGES-V2.md](docs/CAHIER-DES-CHARGES-V2.md)

## Développement avec VS Code

Prérequis : [Python 3.11+](https://www.python.org/downloads/), [Node.js 20+](https://nodejs.org/), [VS Code](https://code.visualstudio.com/).

1. Installer l'environnement (une fois) — crée `.venv`, installe les dépendances, crée la base de démo :
   - Windows : `powershell -ExecutionPolicy Bypass -File scripts\installer-dev.ps1`
   - Mac/Linux : `bash scripts/installer-dev.sh`
2. Dans VS Code : **Fichier > Ouvrir l'espace de travail à partir d'un fichier** → `pkp-math-lycee.code-workspace`.
   Accepter l'installation des extensions recommandées.
3. **Exécuter et déboguer** (Ctrl+Maj+D) → **▶ Application complète (API + Front)** : API sur le port 8010 avec points d'arrêt,
   front sur http://localhost:5173 (accueil `/`, élève `/eleve`, professeur `/enseignant`, administration `/admin` ; comptes de démo décrits dans `api/app/db/seed.py`).
   Élèves de démo : prénom + code classe + code personnel, par exemple **Lina / 2NDE-A-DEMO / PKP222**
   (tous les codes de démo sont dans `CODES_DEMO`, `api/app/db/seed.py` ; usage local uniquement).
4. Tests : panneau **Tests** (pytest pour `moteur` et `api`, Vitest pour `web`), ou
   **Terminal > Exécuter la tâche de test** pour tout lancer.

Tâches utiles (**Terminal > Exécuter la tâche**) : *Réinitialiser la base de démo*, *Tests : tout le projet*.

## Démarrage en ligne de commande

```bash
# Moteur
cd engine && python -m venv .venv && .venv/Scripts/activate && pip install -e ".[dev]" && pytest

# API (http://localhost:8000/docs)
cd api && python -m venv .venv && .venv/Scripts/activate && pip install -e ../engine -e ".[dev]" && pytest
alembic upgrade head        # crée pkp.db (SQLite) ; PKP_DATABASE_URL pour PostgreSQL
python -m app.db.seed       # données de démo, compte décrit dans app/db/seed.py
uvicorn app.main:app --reload

# Front (http://localhost:5173 ; élève : /eleve, professeur : /enseignant, administration : /admin)
cd web && npm install && npm test && npm run dev
# Si le port 8000 est déjà pris : lancer l'API avec --port 8010
# et le front avec PKP_API_URL=http://localhost:8010
```
