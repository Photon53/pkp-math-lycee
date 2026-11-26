# Consignes pour un nouveau développeur — Boussole Maîtrise+

Ce document complète le modèle de consignes fourni par le propriétaire. Chaque point a été vérifié dans le
dépôt (`develop` au 13/11/2026). Quand le dépôt contredit le modèle, c'est le dépôt qui fait foi, et l'écart est
signalé.

## Contexte

**Projet** : Boussole Maîtrise+ (nom technique encore présent dans le code et les paquets : *PKP Math Lycée*,
`pkp-engine`, `pkp-api`, `pkp-web`). Une application qui permet aux élèves de comprendre, progresser, prendre
confiance : des cours clairs, des exercices corrigés pas à pas et un entraînement au rythme de l'élève. Avec la
**Méthode Spirale**, on revient sur les notions jusqu'à ce qu'elles tiennent : c'est viser la Maîtrise+.

**Utilisateurs** : élèves (mineurs, collège et lycée), parents, professeurs, validateurs, administrateurs.
Le modèle mentionnait « formateurs » : ce rôle n'existe pas dans le code. Les rôles réels sont `professeur`,
`validateur` et `admin` (`api/app/permissions.py`, table `habilitation`).

**Stade** : phase pilote. Ouverture B2C et B2B prévue en janvier 2027 (règle du cahier des charges : « préparer
la vente sans l'annoncer »). Environnement DEV sur GCP en cours de mise en service (ticket #65).

**Stack** (vérifiée dans `README.md`, `api/pyproject.toml`, `engine/pyproject.toml`, `web/package.json`) :

| Couche | Technologie | Dossier |
|---|---|---|
| Moteur pédagogique | Python ≥ 3.11, **pur** (aucune dépendance web ni base) | `engine/` |
| API | FastAPI, SQLAlchemy 2, Alembic, Pydantic Settings | `api/` |
| Base de données | PostgreSQL 16 en déploiement ; SQLite en développement local | `api/migrations/` (31 migrations) |
| Front | React 18, Vite 5, KaTeX, marked, DOMPurify | `web/` |
| Déploiement | Docker Compose (db, api, purge, web/Caddy), HTTPS automatique | `deploy/` |
| Hébergement | Google Cloud (projet DEV `mer-boussole-dev`, VM `boussole-dev`), Terraform | `infrastructure/terraform/dev/` |
| Intégration continue | GitHub Actions : pytest moteur et API, Vitest, `npm audit`, build, Terraform fmt/validate, bancs de scripts | `.github/workflows/` |

**Branches** : `main` est la branche par défaut (production) ; le travail se fait sur `develop` par PR. `main`
n'a pas de protection de branche active (dépôt privé en offre gratuite) : **ne jamais pousser directement sur
`main`**.

**Fichiers de référence** (le modèle citait `ARCHITECTURE.md`, `CONVENTIONS.md`, `DECISIONS.md` à la racine ;
voici ce qui existe) :

| Besoin | Fichier réel |
|---|---|
| Vue d'ensemble, démarrage local | `README.md` |
| Architecture, schéma de données, règles du moteur, API | `docs/ARCHITECTURE.md` |
| Périmètre V2, rôles, lots, décisions D7 à D14 | `docs/CAHIER-DES-CHARGES-V2.md` |
| Décisions D1 à D3 (sécurité) | `docs/audit/lot-a-securite.md` |
| Contenu pédagogique (format YAML, règles de rédaction) | `docs/CONTENU.md`, `docs/CONTENU-INVENTAIRE.md` |
| RGPD | `docs/RGPD.md` |
| Déploiement et exploitation | `docs/DEPLOIEMENT.md`, `docs/exploitation/` |
| Pipeline DEV (publication, droits, synchronisation VM) | `docs/exploitation/pipeline-dev-pr*.md` |
| Conventions de code | **Aucun fichier dédié** : `.editorconfig` et ce document |
| Registre des décisions | `docs/DECISIONS.md` : recense les décisions prises, en attente et écartées, avec renvoi vers la source (trois séries « D » préfixées `SEC-`, `V2-`, `DEV-`) |

## Domaine métier (vocabulaire à respecter)

Le modèle proposait un code en anglais (`Competency`, `MasteryLevel`, `Assessment`, `Path`). **Le dépôt est
intégralement en français** : tables, classes, fonctions, routes, tests, commentaires. On garde le français,
pour ne pas créer deux vocabulaires dans le même code.

| Terme | Définition dans le projet | Dans le code |
|---|---|---|
| **Compétence** | Unité d'apprentissage d'un chapitre, reconnue par son `code` ; porte une leçon et des questions | `Competence`, table `competence` |
| **Chapitre** | Regroupement de compétences d'un niveau et d'un parcours ; un fichier YAML par chapitre | `Chapitre`, `contenu/<niveau>/<parcours>/NN-*.yaml` |
| **Maîtrise** | **Taux entre 0 et 1**, calculé à partir des 10 dernières réponses de la compétence (pondération 0,9, a priori de 1). Seuil : 0,8, atteint après environ 5 réussites d'affilée. **Ce n'est pas une échelle à 4 niveaux** comme dans le modèle | `calculer_maitrise`, `est_maitrisee`, `SEUIL_MAITRISE` (`engine/src/pkp_engine/maitrise.py`) |
| **Difficulté** | Entier de 1 à 5 porté par chaque question ; la difficulté visée vaut `1 + arrondi(maîtrise × 4)` | `Question.difficulte`, `choisir_prochaine_question` |
| **Niveau** | Classe : `2nde`, `1re`, `Tle` (maths) ; `6e` à `3e` (anglais collège) | `Niveau` (enum du moteur), `NIVEAUX_COLLEGE` |
| **Parcours** | Spécialité ou groupe au sein d'un niveau : `tronc-commun`, `specialite`, `scientifique`, `technologique`, `complementaires`, `expertes`, `mise-a-niveau`, `excellence`, `examens` | `Classe.parcours`, `Chapitre.parcours` |
| **Domaine pédagogique** | Matière × cycle : Maths lycée, Anglais collège, puis Maths collège, Anglais lycée, Français | `DOMAINES` (`permissions.py`), table `domaine_pedagogique` |
| **Référentiel** | Programme officiel (BO) auquel la banque est rapportée ; matrices de couverture | `referentiels/`, `docs/matrices/` |
| **Séance** | Session de travail d'un élève, avec **une seule question en cours** | `Seance`, `seance.question_courante_id` |
| **Réponse** | Réponse d'un élève à une question, corrigée par le moteur | `Reponse`, `corriger`, `verifier` → `Verdict` |
| **Évaluation** | Le modèle citait auto-évaluation et évaluation par un tiers : **n'existent pas**. L'évaluation est la correction automatique des réponses par le moteur (QCM, numérique, expression) | `correction.py` |
| **Leçon** | Cours et résumé d'une compétence (Markdown + LaTeX), versionnés | `Lecon`, `LeconVersion` |
| **Validation** | Circuit d'un contenu : soumis → validé → publié. Personne ne valide un contenu dont il est l'auteur, admin compris (EX.9) | `contenu.valider`, `contenu.publier` |
| **Habilitation** | Rôle (`professeur`, `validateur`) accordé à un adulte, avec périmètre (domaine, niveau) | `Habilitation`, `exiger(permission, domaine)` |
| **Méthode Spirale** | Nom pédagogique du retour répété sur les notions jusqu'à maîtrise ; c'est le fonctionnement du moteur (fenêtre glissante, sélection de la compétence la moins maîtrisée), pas une entité du code | `web/src/Methode.jsx` |

Règles d'usage : utiliser ces termes exacts dans le code et dans les réponses, en français. Ne pas introduire de
traduction anglaise d'un concept qui a déjà un nom français dans le code.

## Conventions

- **Architecture** : trois couches à dépendances strictes. `engine/` ne dépend de rien ; `api/` dépend de
  `engine/` ; `web/` n'appelle `api/` que par HTTP. **Le moteur n'importe jamais FastAPI ni SQLAlchemy** :
  `api/app/db/conversions.py` traduit les lignes en objets du domaine. Pas de « feature folders » comme dans le
  modèle : l'API est organisée par modules (`app/<domaine>.py`, `app/routes/<rôle>.py`), le front par
  public (`web/src/eleve/`, `enseignant/`, `parent/`, `admin/`, `anglais/`).
- **Style** : code, commentaires, messages de commit et documentation **en français**. `.editorconfig` :
  UTF-8, LF, 4 espaces (2 pour JS, JSON, CSS, YAML). **Aucun linter ni formateur n'est configuré** (ni ruff, ni
  ESLint, ni Prettier) : suivre le style des fichiers voisins. Proposition d'amélioration, à décider : ajouter
  `ruff` (format + lint) et ESLint en CI, dans une PR dédiée, après formatage initial séparé du reste.
- **Tests** : pytest pour `engine/` et `api/`, Vitest pour `web/`. Tout nouveau code métier est testé, en
  priorité les règles de correction et de maîtrise du moteur. Toute modification d'un modèle exige une migration
  Alembic (`alembic revision --autogenerate`) **relue à la main** : le test `test_migrations_a_jour_avec_les_modeles`
  échoue sinon, et Alembic produit des défauts connus (`sa.text('0')` au lieu de `sa.false()` pour PostgreSQL).
  Les scripts d'exploitation ont leurs propres bancs simulés en CI (`scripts/tests/`, `deploy/vm/tests/`).
- **Données personnelles** : les utilisateurs sont **mineurs**. Minimisation stricte (élève = prénom + code
  classe + code personnel haché, jamais de nom ni d'e-mail), purge automatique des inactifs, effacement en cascade,
  export JSON. Aucun traceur ni script tiers (CSP `default-src 'self'`). **Aucune donnée réelle dans les exemples,
  les tests, les tickets ni les PR** : les comptes de démo sont dans `api/app/db/seed.py`. Aucun identifiant
  personnel dans les noms ou métadonnées des sauvegardes (décision D5). Lire `docs/RGPD.md` avant toute
  modification touchant `eleve`, `parent`, `enseignant`, `seance`, `reponse` ou la purge.
- **Sécurité** : jetons HMAC-SHA256 à durée limitée, mots de passe scrypt, cloisonnement par 404 (jamais 403
  révélant l'existence), messages d'erreur identiques que le compte existe ou non, limitation des tentatives.
  Toute nouvelle route passe par `exiger(permission, domaine)`. Jamais de secret dans le code, les journaux, les
  tickets ou les sorties de scripts ; les scripts d'exploitation masquent jetons et adresses.
- **Contenu pédagogique** : il vit dans `contenu/` (YAML), vérifié en CI (`python -m app.contenu verifier`),
  importé en base de façon idempotente ; une question n'est jamais supprimée, elle est archivée.

## Façon de travailler

- **Analyse** : lire d'abord `README.md`, `docs/ARCHITECTURE.md` et le chapitre concerné du cahier des charges ;
  puis le code voisin. Si un fichier manque ou si une règle n'est écrite nulle part, le dire plutôt que de la
  supposer.
- **Étude** : comparer deux ou trois options au plus, avec leurs compromis (coût, complexité, maintenabilité pour
  une petite équipe), puis recommander une option. Pas d'inventaire exhaustif.
- **Développement** : fournir le code complet du fichier modifié ou un diff clair, jamais de « reste inchangé »
  ambigu. Une PR par sujet, vers `develop`, en brouillon tant qu'elle n'est pas prête ; CI verte avant revue.
- **Impacts à indiquer** dans chaque PR : migration de base, dépendances, sécurité (droits par rôle et domaine),
  RGPD, performance des tableaux de bord et des tirages de questions, documentation d'exploitation.
- **Ne pas inventer** d'API, de règle métier ni de format de réponse d'un service externe : en cas de doute, le
  dire. Face à une API externe dont la réponse réelle n'est pas connue, **commencer par un appel unique
  instrumenté** avant d'écrire un contrôle complet (leçon du ticket #65).
- **Vérification réelle avant extension** : un banc simulé ne prouve pas le comportement réel (Docker, PostgreSQL,
  GCS). Tester une petite chaîne de bout en bout avant d'étendre le code ; conserver chaque réponse réelle,
  anonymisée, comme cas de test.
- **Un seul blocage à la fois**. Après deux tentatives infructueuses sur le même problème, arrêter les relances
  et produire un diagnostic ciblé avec des options. Compte rendu court : résultat, preuve, prochaine décision.
- **Actions soumises à accord explicite du propriétaire** : fusion vers `develop` ou `main`, `terraform apply`,
  tout changement IAM, toute intervention sur la VM, activation d'un timer, activation d'une API GCP (même
  temporaire). Une activation temporaire est un changement et se consigne.
- **Décisions structurantes** : proposer une entrée pour `docs/DECISIONS.md`, avec l'identifiant préfixé, la
  date, la décision, sa conséquence et la source. La discussion reste dans le ticket ou le document source. Trois
  séries « D » coexistent avec des numéros qui se chevauchent : toujours préfixer (`SEC-D1` ≠ `V2-D1` ≠ `DEV-D1`).
- **Tickets et PR** : en français, avec des preuves (commande, sortie anonymisée, lien de run). Distinguer
  « publié » de « déployé », « conforme selon l'analyse » de « confirmé par un essai réel », « défaut bloquant »
  d'« exception acceptée » et d'« amélioration ultérieure ».

## Écarts entre le modèle de consignes et le dépôt

| Modèle | Dépôt | Consigne retenue |
|---|---|---|
| Code en anglais (`Competency`, `MasteryLevel`…) | Tout en français | Français |
| Niveau de maîtrise sur une échelle 1 à 4 | Taux 0–1, seuil 0,8 | Taux et seuil du moteur |
| Évaluation : auto-évaluation, par un tiers, quiz | Correction automatique seulement | Ne pas introduire de concept absent |
| Utilisateurs : « formateurs » | Professeur, validateur, admin | Rôles du code |
| Feature folders par domaine | Trois couches, modules par public | Architecture existante |
| Linter/formateur imposé | Aucun configuré | `.editorconfig` ; proposition ruff/ESLint à décider |
| `ARCHITECTURE.md`, `CONVENTIONS.md`, `DECISIONS.md` à la racine | `docs/ARCHITECTURE.md` ; `docs/DECISIONS.md` (créé avec ce document) ; pas de `CONVENTIONS.md` | Tableau des fichiers réels ; ce document tient lieu de conventions |
