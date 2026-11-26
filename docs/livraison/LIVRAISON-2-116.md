# Deuxième livraison `develop` → `main` — matrice, durcissement repris et plan de retour arrière (#116)

> État **en préparation**. Ce document ne vaut ni décision de fusion dans `main`, ni autorisation de
> déploiement (#116, § 5 et § 6). Les décisions marquées **Propriétaire** restent à prendre.
> La première livraison est décrite dans [MATRICE-SELECTION-116.md](MATRICE-SELECTION-116.md) (PR #120, puis #163).

## 0. Instantané (19/11/2026, à recalculer avant la PR de livraison)

| Élément | Valeur |
|---|---|
| `origin/main` | `98ae6658f780c14f69154dd3fe1c2b90440f9633` (fusion de la PR #163, en production) |
| `origin/develop` | `44a7e739a6d864af61acf486219cffe4f558640e` (fusion de la PR #187) |
| Base commune | `6fac6c3d6f49a36a039de46ac4ad35a13132f1a2` |
| Divergence `main...develop` | **1** commit propre à `main` (le commit de fusion de #163, **sans contenu** : `git diff origin/develop...origin/main` est vide), **35** propres à `develop` (10 entrées en premier parent) |
| Branche de travail | `claude/happy-ritchie-eg3ovk` (issue de `develop` `44a7e73`) |

```bash
git fetch origin main develop
git rev-list --left-right --count origin/main...origin/develop
git log --first-parent --format='%h %s' origin/main..origin/develop
git diff --stat origin/develop...origin/main   # doit rester vide
```

## 1. Constat principal : le durcissement de la PR #118 n'a jamais été intégré

La PR #118 a été fusionnée (`059efb5`) sur son commit `ac75033`, **avant** que ses quatre derniers commits soient
poussés sur la branche `claude/funny-faraday-u0we0q` :

| Commit | Objet | Dans `develop` | Dans `main` |
|---|---|---|---|
| `1f69440` | démonstration refusée en production, `python -m app.production verifier`, CORS `https://` | non | non |
| `80a5864` | image API en deux étapes (sans tests, PDF officiels, résidus, outils de rechargement) | non | non |
| `107b1b0` | migrations et import hors du démarrage de l'API (service `preparation`) | non | non |
| `eddbb87` | preuves dans la matrice | non | non |

Le commentaire du 15/11 dans #116 les présentait comme faits. **La production tourne donc toujours avec** :
`alembic upgrade head` et l'import dans la commande de démarrage de l'API, une image en une seule étape (tests et
PDF compris) et un `app.db.seed` qui ne refuse pas la production.

**Cette branche les reporte** par `cherry-pick -x` (sans conflit), puis ajoute deux corrections (§ 4).

## 2. Matrice du delta (PR fusionnées dans `develop` depuis #163)

Légende : **Inclure** = dans `main` et actif ; **Inclure (fermé)** = code et schéma livrés, fonction fermée à
l'exécution par un réglage ou une décision ; **Git seulement** = jamais dans une image ni exécuté.

| PR (issue) | Contenu | Décision | Verrou d'exécution | Migration | Risque |
|---|---|---|---|---|---|
| #164, #168 (#162) | diagnostic des acquis antérieurs : 9 chapitres, choix multiples, rédactions en attente, passation adaptative | **Inclure (fermé)** | passation ouverte par le professeur, classe par classe (`classe.diagnostic_ouvert`, faux par défaut) ; questions soumises à `PKP_SERVIR_QUESTIONS_NON_VALIDEES` | **0040**, **0041** | moyen : 0040 modifie la contrainte `question.type` ; **downgrade bloqué** dès que du diagnostic est importé (§ 3) |
| #167 (#166) | Vite 8, plugin React 5, Vitest 4 ; Dependabot vers `develop` | **Inclure** | dépendances de développement : absentes de l'image web (fichiers statiques seulement) | — | faible ; corrige les alertes #127 à #141 côté outillage |
| #173 (#126) | télémétrie FastAPI désactivée ; `opentelemetry-api>=1.45.2` | **Inclure** (sécurité) | — | — | faible |
| #174 (#3) | vérification des liens protégée contre la SSRF (`app/liens_sortants.py`) | **Inclure** (sécurité, bloquant) | — | — | faible |
| #181 (#178) | PDF d'un chapitre : élève sans corrigé, professeur avec corrigé | **Inclure** | PDF professeur soumis aux habilitations (ARCH-4) | — | moyen : vérifier en recette qu'un élève n'obtient jamais la version professeur |
| #182 (#176) | classes pilotes (SEC-D6) : domaine actif mais fermé réservé aux classes inscrites | **Inclure** (sécurité) | `permissions.refus_acces_classe`, route par route | **0042** | **élevé à l'exploitation** : une classe active d'un domaine fermé non inscrite **perd la lecture du contenu**, qu'elle conservait dans `main` (§ 5, étape 3) |
| #185 (#177) | rubriques des chapitres de français | **Inclure (fermé)** | domaines Français fermés ou réservés aux classes pilotes | **0043** | faible : colonne nullable |
| #186 (#180) | « Mon cours » : liens de la professeure | **Inclure (fermé)** | PDF de français refusés tant que `PKP_PDF_FRANCAIS_OUVERT` est faux ; refus de démarrer en production s'il est activé sans `CONTROLE_PDF_RENFORCE` (#4) | — | faible |
| #187 (#179) | rédaction en ligne et correction humaine (RGPD-2) | **Inclure (fermé)** | `PKP_REDACTION_ACTIVE` faux par défaut : routes refusées | **0044** | moyen (données de mineurs) : **ne pas activer** avant la levée des points ouverts de RGPD-2 (#183) |
| documentation (`docs/diagnostic/`, `DECISIONS.md`, `RGPD.md`…) | — | **Git seulement** | `docs/` hors du contexte de construction (`.dockerignore`) | — | nul |

Navigation « Français (préparation) » (#102) : toujours affichée sans condition sur l'accueil public et l'espace
professeur. Écart signalé lors de la première livraison, **toujours ouvert** : décision du **Propriétaire**
(garder l'annonce ou conditionner l'affichage au domaine actif).

## 3. Migrations 0040 à 0044

Chaîne linéaire `0039 (main) → 0040 → 0041 → 0042 → 0043 → 0044`, toutes additives à la montée.

| | Effet à la montée | Retour arrière (`downgrade`) |
|---|---|---|
| 0040 | `question.type` élargi (contrainte recréée), `chapitre.nature/publics/programme_prerequis`, table `observation_diagnostic` | **refusé** si des chapitres ou questions de diagnostic existent (garde explicite) ; or l'import les crée |
| 0041 | table `passation_diagnostic`, `classe.diagnostic_ouvert` (faux), colonnes d'observation | supprime passations et observations |
| 0042 | table `classe_pilote` | supprime la liste des classes pilotes |
| 0043 | `chapitre.rubrique` (nullable) | supprime les rubriques |
| 0044 | table `redaction` | supprime les rédactions des élèves |

**Essai réel** (Docker 29, `postgres:16-alpine`, projet Compose isolé, secrets générés pour l'essai puis
supprimés, base détruite après) :

- base vierge → `0044 (head)` par le service `preparation`, import de 164 chapitres et 1 928 questions
  (dont 2 `choix_multiples` et 11 `redaction`, 9 chapitres de diagnostic) ;
- `alembic downgrade 0039` → **refus** : « Des chapitres ou questions de diagnostic existent : les retirer avant
  de revenir en 0039 ». Une question ne se supprime pas (ARCH-3) : ce retour est donc fermé en pratique.

Conséquence pour le retour arrière, **après** la migration :
- revenir aux images de `main` ne démarre pas : leur commande de démarrage lance `alembic upgrade head`, qui ne
  connaît pas `0044` (même constat qu'à la première livraison) ;
- **le seul retour complet est la restauration de la sauvegarde prise juste avant** (`deploy/sauvegarde-prod.sh`,
  #122, SEC-D4), avec perte des saisies faites depuis le déploiement. Le délai de décision doit donc être court ;
- un retour d'application **sans** retour de base reste possible vers une image de cette version (même schéma).

Non exécuté ici : montée `0039 → 0044` sur une **copie de la base de production** (restauration isolée de #122).
**Recommandé avant le déploiement**, par le propriétaire.

## 4. Changements de cette branche

| Commit | Contenu |
|---|---|
| report de `1f69440` | `app.db.seed` refusé en production ; `python -m app.production verifier` (code 1 si un compte de démonstration existe) ; CORS `https://` seulement |
| report de `80a5864` | `deploy/Dockerfile.api` en deux étapes ; `.dockerignore` élargi (`.github`, `.claude`, `docs`, `infrastructure`, `scripts`, `sources`, `deploy/vm`, état Terraform, tests) ; référentiels lus sans les PDF |
| report de `107b1b0` | `CMD` réduit à Uvicorn ; service ponctuel `preparation` (migrations, import, contrôle) dont l'API attend la réussite |
| nouveau | `app.production verifier` **avertit**, sans bloquer, des classes actives d'un domaine fermé absentes des classes pilotes (comptes par domaine, aucune donnée nominative) |
| nouveau | `deploy/retour-v3-*.sh` : `docker compose run --rm --no-deps` pour `alembic current/downgrade` ; sans cela, `run` aurait d'abord lancé `preparation`, donc un `upgrade head` avant le `downgrade` |

### Contrôle de l'image API candidate (construite localement, non publiée)

| Contrôle | Résultat |
|---|---|
| Taille | 363 Mo |
| Utilisateur | `pkp` (uid 10001) |
| Contenu de `/app` | `api/{app,migrations,alembic.ini}`, `contenu/`, `referentiels/` (YAML et `sources.yaml` seulement) |
| Tests, PDF, `*.egg-info`, `.env`, `*.tfstate` | absents |
| `watchfiles`, `websockets`, `pytest`, `httpx` | absents |
| `app/db/seed.py` | **présent** (importé par `app.production` pour la liste des comptes de démo) ; refuse de s'exécuter en production |

Limite de l'essai : le proxy de l'environnement d'essai impose son certificat ; la construction locale a utilisé
une copie du Dockerfile qui l'ajoute à l'étape de préparation seulement (non copiée dans l'image finale). Le
Dockerfile du dépôt n'est pas modifié. **Image web non reconstruite** ici.

### Essai Compose de production (même projet isolé)

| Essai | Résultat |
|---|---|
| `up db preparation api` | `preparation` : sortie 0 ; API saine ; `alembic current` = `0044 (head)` |
| `/docs`, `/openapi.json`, `/redoc` | 404 ; `/health` 200 |
| `docker compose restart api` | aucune migration relancée |
| `python -m app.db.seed` en production | refus, code 1 |
| classe active de `francais-college` (actif, non public) hors pilote | `preparation` sortie 0, avec `AVERTISSEMENT : 1 classe(s) active(s) du domaine fermé francais-college…` |
| compte `demo@pkp.test` présent | `REFUS`, `up` en échec (`service "preparation" didn't complete successfully: exit 1`) ; **l'API déjà en service n'est pas recréée** |

## 5. Plan de déploiement proposé (à autoriser séparément par le propriétaire)

1. Fusion de cette branche dans `develop`, CI verte, puis PR de livraison `develop` → `main` en brouillon sur un
   SHA figé ; contrôle `git diff --stat origin/develop...origin/main` vide.
2. Restauration isolée d'une copie de la production (#122) et essai `0039 → 0044` avec ce code ; lire les
   avertissements de `python -m app.production verifier`.
3. **Avant** la mise en service, en lecture sur la production : lister les classes actives des domaines fermés.
   Pour chacune, décision du **Propriétaire** : l'inscrire comme classe pilote dès le déploiement (écran
   « Classes pilotes »), l'archiver, ou ouvrir le domaine. Sinon ses élèves perdent l'accès au contenu.
4. Sauvegarde préalable chiffrée (`deploy/sauvegarde-prod.sh`), vérifiée.
5. Déploiement : `docker compose up -d --build` ; vérifier `docker compose logs preparation` (sortie 0, aucun
   `REFUS`), `/api/health`, `alembic current` = `0044`.
6. Réglages à confirmer dans `.env` : `PKP_REDACTION_ACTIVE` absent ou faux, `PKP_PDF_FRANCAIS_OUVERT` absent ou faux,
   `PKP_SERVIR_QUESTIONS_NON_VALIDEES` choisi explicitement.
7. Recette rapide par rôle : élève (pas de corrigé avant réponse, pas de PDF professeur), professeur (PDF chapitre,
   ouverture du diagnostic), parent, administrateur (classes pilotes).
8. Retour arrière : application seule vers une image de cette version ; sinon **restauration de la sauvegarde de
   l'étape 4** (§ 3), jamais `downgrade` automatique.

## 6. Risques résiduels

| Risque | Gravité | Preuve / état | Traitement proposé | Responsable |
|---|---|---|---|---|
| Classes de domaines fermés privées de contenu après livraison (SEC-D6) | haute (service) | § 4, avertissement de `preparation` | étape 3 du § 5 | Propriétaire |
| Retour arrière de base impossible sans restauration | haute | § 3, essai réel | sauvegarde préalable vérifiée, délai de décision court | Propriétaire |
| Rédactions de mineurs ouvertes par erreur | haute (RGPD) | fermé par défaut (`PKP_REDACTION_ACTIVE`) | ajouter un refus de démarrage en production tant que RGPD-2 n'est pas levé ? | Propriétaire (#183) |
| Contrôle renforcé des PDF (#4) non livré | moyenne | verrou `CONTROLE_PDF_RENFORCE = False` pour le français ; autres PDF inchangés | #4 | — |
| Navigation Français annoncée sans condition (#102) | faible (sécurité), moyenne (image) | § 2 | décision | Propriétaire |
| Montée non essayée sur une copie de la production | moyenne | § 3 | étape 2 du § 5 | Propriétaire |
| Image web, scans d'images et de dépendances Python non exécutés ici | moyenne | — | sous-ticket « construction reproductible et scans » de #116 | — |
| Circuit de livraison automatisé (#116, § 6) non commencé | — | — | sous-ticket dédié, après accord | Propriétaire |

---
<sub>🤖 Rédigé par **Claude** (Claude Code) pour l'issue #116, 19/11/2026.</sub>
