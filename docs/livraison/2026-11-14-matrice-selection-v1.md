# Matrice de sélection — première livraison `develop` → `main`

Issue #116 — Matrice de sélection, dépendances des migrations et découpage (Claude), 14/11/2026.
Document de **préparation** : il n'autorise ni fusion dans `main`, ni construction d'images de production, ni
déploiement. Les décisions marquées « propriétaire » restent à prendre.

Légende des états, à ne pas confondre (`docs/CONSIGNES-DEVELOPPEUR.md`) : **constaté par essai** (commande exécutée,
sortie relevée) · **constaté à la lecture** (code ou fichier lu, sans exécution) · **à vérifier** (hypothèse).

## 1. Référence figée

| Élément | Valeur |
|---|---|
| Source : `develop` | `805e3af6d6bf30c3e2061124ee36e088683f37d5` (fusion de la PR #113) |
| Cible : `main` | `90901642773a8e7bc30ec1684f215d0a2363dd8c` |
| Ancêtre commun | `2a614051aae097d58bde9fa6e4991bfe43d547c4` (fusion de la PR #58) |
| Divergence | 114 commits propres à `develop` (78 hors fusions, 43 en premier parent), 1 propre à `main` |
| Volume du delta | 165 fichiers, +13 595 / −566 lignes ; 77 fichiers de contenu, 88 autres |

Ces valeurs sont un instantané : elles sont à recalculer sur le SHA de `develop` figé pour la branche `release/*`.

```bash
git rev-list --left-right --count origin/main...origin/develop
```

## 2. Quatre niveaux à distinguer

La version actualisée de #116 autorise la présence des outils DEV dans Git, y compris sur `main`, s'ils sont utiles
et sans secret. **L'exclusion se fait dans les images et à l'exécution, pas par suppression de chemins dans `main`.**
Aucun script de suppression systématique n'est proposé.

| Niveau | Ce qui le définit | Règle visée |
|---|---|---|
| **Git (`main`)** | arborescence fusionnée | tout ce qui est utile et sans secret : code, tests, CI, outillage DEV, documentation |
| **Contexte de construction** | `.dockerignore`, `context:` de Compose | exclure ce qui n'a rien à faire dans une image (outillage, documents, tests) |
| **Image livrée** | instructions `COPY` des `Dockerfile`, étapes de construction | dépendances d'exécution et contenus retenus seulement |
| **Exécution PROD** | `PKP_ENVIRONNEMENT`, variables, état de la base (domaines actifs, validations) | aucune fonction DEV active ; fonctions différées inaccessibles côté serveur |

État constaté à la lecture sur `develop` :

| Élément | Git | Contexte | Image API | Image web | Exécution PROD |
|---|---|---|---|---|---|
| `engine/`, `api/app/` | oui | oui | oui | — | oui |
| `api/tests/` (dont `corriges_pilote.json`) | oui | oui | **oui** (copié avec `api/`) | — | non exécuté, mais présent |
| `contenu/` maths et anglais | oui | oui | oui | — | importé au démarrage (§ 6) |
| `contenu/francais/` | oui | oui | **oui** | — | inerte : aucun import automatique, domaine inactif |
| `referentiels/` | oui | oui | oui | — | lu par la vérification du contenu |
| `web/src/` (dont `francais/`, `tests/`) | oui | oui | — | bundle compilé ; les tests tournent à la construction | page `/francais` présente dans le bundle, API refusée (§ 5) |
| `scripts/`, `deploy/vm/`, `infrastructure/`, `.github/`, `.claude/`, `docs/` | oui | oui (non filtré) | non (aucun `COPY`) | non | non |
| `deploy/docker-compose.dev.yml` | oui | — | non | non | à ne jamais utiliser en PROD |

Le `.dockerignore` actuel n'exclut que des artefacts (`node_modules`, `dist`, `.venv`, `.env`, `.git`…). Les
outils DEV ne finissent pas dans les images **parce que les `COPY` sont sélectifs**, pas parce que le contexte est filtré.
Le lot B (§ 9) rend cette exclusion explicite et vérifiable.

## 3. Commit propre à `main`

| Commit | Contenu | Décision |
|---|---|---|
| `9090164` « Fix formatting in dependabot.yml comments » (Photon53) | ajoute `.github/dependabot.yml` | **Préserver.** Reporté sur cette branche par `git cherry-pick -x`, auteur d'origine conservé, pour l'amener dans `develop` par cette PR |

Pourquoi le reporter maintenant : une fusion à trois branches classique conserverait le fichier, mais une stratégie
qui reprend l'arborescence de `develop` (fusion en écrasement, réinitialisation, copie) le supprimerait. Une fois
le fichier dans `develop`, l'arborescence de la future branche `release/*` peut être **identique** à celle de `main`
après fusion. C'est la condition pour vérifier que l'arborescence fusionnée est bien celle qui a été testée (#116 § 6).

**Constat à la lecture** : le fichier est le modèle par défaut de GitHub, avec `package-ecosystem: ""`. Dependabot
le signalera comme invalide et ne fera aucune mise à jour. Le compléter relève de #78 (Dependabot). Il n'est **pas
modifié** ici. Proposition pour #78 : écosystèmes `pip` (`/engine`, `/api`), `npm` (`/web`), `docker` (`/deploy`) et
`github-actions` (`/`).

## 4. Matrice par changement (premier parent de `develop`)

Colonnes : **Git** = présent dans `main` après livraison ; **Image** = embarqué dans une image finale ;
**Exécution** = actif en production. Valeurs : *inclure*, *exclure*, *différer* (présent mais inactif), *n/a*.

### 4.1 Code applicatif, sécurité et tests

| PR (ticket) | Objet | Git | Image | Exécution | Migration | Tests | Dépendances | Risque / remarque |
|---|---|---|---|---|---|---|---|---|
| #112 (#110) | Mode de correction des quiz d'anglais choisi par le professeur ; réponses par question ; score du premier essai | inclure | inclure | inclure | **0033** | `test_mode_correction.py`, `test_migrations.py`, `test_isolement_acces.py` | 0032 (chaîne Alembic), #109 | nouvelle donnée élève `reponse_anglais` : rétention à vérifier (§ 5.3) |
| #109 (#107) | Quiz d'anglais : corrigé seulement après une réponse à chaque question (ARCH-4) | inclure | inclure | inclure | — | `test_anglais_validation.py` | — | **correctif de sécurité** : bloquant pour la livraison |
| #105 (#17, #30) | PKP Math : corrigé visible par l'élève seulement après sa réponse ; matrice des droits et isolement | inclure | inclure | inclure | — | `test_isolement_acces.py` (plus de 150 routes), `pkp-math.test.jsx` | — | **correctif de sécurité** ; le test garantit que toute nouvelle route est classée |
| #106 (#16) | Scénarios de tableaux de bord professeur, élève, parent | inclure | exclure (test) | n/a | — | `test_tableaux_de_bord.py` | — | — |
| #99 (#98) | Dossiers de Français 3e : modèle, import manuel, routes adultes, page `/francais` | inclure | inclure le code ; `contenu/francais` à exclure (lot B) | **différer** : domaine `francais-*` inactif | **0032** | `test_francais.py`, `francais.test.jsx`, `test_migrations.py` | 0023 (domaines `francais-college`, `francais-lycee` créés inactifs) | vérifier que l'API reste fermée tant que le domaine est inactif (§ 5.2) |
| #103 (#102) | Lien vers la préparation du Français dans la navigation adulte, réservé aux professeurs | inclure | inclure | différer (suit l'état du domaine) | — | `navigation-francais.test.jsx`, `accueil.test.jsx`, `lot-a-domaines.test.jsx` | #99 | la navigation n'est pas une protection : c'est le serveur qui refuse |
| #90 (#62) | `pkp-anglais-beta.yml` : jeton GitHub en lecture seule | inclure | n/a | n/a | — | CI | — | **absent de `main` aujourd'hui** ; #62 peut être requalifié « corrigé dans `develop` » |

### 4.2 Contenus pédagogiques

| PR (ticket) | Objet | Git | Image | Exécution | Tests | Risque / remarque |
|---|---|---|---|---|---|---|
| #92, #95, #101, #104, #108 (#35) | Corrigés pas à pas (méthode, étapes, erreurs fréquentes) : Tle spécialité, collège 6e–3e, 1re, 2nde | inclure | inclure | **selon la validation** | `test_corriges_pilote.py`, `app.contenu verifier` | **0 question validée dans les YAML** (toutes « Brouillon IA (Claude) »). En production, les élèves ne voient que les questions validées si `PKP_SERVIR_QUESTIONS_NON_VALIDEES=false` (V2-D3). Choix du propriétaire, avec V2-D8 et #14 |
| #94, #100 (#55) | Fiches Français 3e (élève, professeur, matrice) | inclure | exclure (`docs/`) | n/a | — | documents de travail, non publiés |
| #91 (#24) | Protocole de relecture pédagogique | inclure | exclure | n/a | — | — |

Les validations faites dans l'interface d'administration ne sont pas écrasées par l'import au démarrage. La route
de validation renseigne `modifiee_admin_le`, et l'import saute alors la question (`rapport.protegees`). Constaté à
la lecture (`api/app/routes/admin_contenu.py`, `api/app/contenu.py`) ; à confirmer par un test dédié dans le lot C.

### 4.3 Documentation et gouvernance

| PR (ticket) | Objet | Git | Image | Remarque |
|---|---|---|---|---|
| #84, #86, #88 (#83) | `AGENTS.md`, modèle de PR, correctifs, transcription de RGPD-1 | inclure | exclure | — |
| #75 | `docs/CONSIGNES-DEVELOPPEUR.md`, `docs/DECISIONS.md`, `.nvmrc`, `.python-version`, `.claude/settings.json`, `scripts/preparer-environnement.sh` | inclure | exclure | `.claude/settings.json` : autorisations locales d'agent, sans secret (lu) |
| #82 (#80) | Analyse DeepSeek du 13/11 et script de comptage | inclure | exclure | **propriétaire** : garder dans `main` ou laisser à `develop` ; aucun effet sur les images |
| #113 (#111) | Cadrage du parcours guidé en Français ; mise à jour de V2-D12 | inclure | exclure | — |

### 4.4 Outillage et infrastructure DEV (#65 et suivants)

Tous : **Git inclure, Image exclure, Exécution PROD exclure.** Aucun n'est copié dans une image (aucun `COPY`
correspondant). Ils restent dans `main` parce que la CI en dépend. `ci.yml` vérifie la syntaxe de `scripts/*.sh`,
`deploy/*.sh` et `infrastructure/terraform/dev/*.sh`, et exécute les bancs simulés (`scripts/test-dev-publier-version.sh`,
`deploy/vm/tests/*`, `scripts/tests/*`) ainsi que `terraform validate`. Les retirer de `main` casserait la CI.

| PR (ticket) | Fichiers | Remarque |
|---|---|---|
| #67, #69, #70 (#65) | `.github/workflows/dev-deploy.yml`, `scripts/dev-publier-version.sh`, banc associé | workflow DEV ; à vérifier : déclenché seulement depuis `develop`, sans secret PROD |
| #66, #71 (#65) | `infrastructure/terraform/dev/*`, scripts WIF et Terraform DEV, `scripts/audit-dev-compte-compute.sh`, `scripts/comparer-politique-bucket.py` | projet `mer-boussole-dev` uniquement |
| #72, #89 (#65) | `deploy/vm/*` (synchronisation de la VM DEV), `deploy/docker-compose.dev.yml`, contrôle d'accès aux sauvegardes, `scripts/troubleshooter_iam.py` | `docker-compose.dev.yml` est une surcharge DEV : ne jamais l'utiliser en PROD |
| #64 (#59) | `scripts/deployer-dev-iap.sh`, compte rendu d'essai | — |
| #97 (#96) | `scripts/tester-ihm-gcp.ps1` | — |
| commits directs du 10/11 (`591b289` à `47c2a24`) | `gcp-dev-terraform.yml`, `scripts/boussole-dev.sh`, `infrastructure/terraform/dev/main.tf` | commits sans PR, messages en anglais ; non relus ici en détail |

Aucune dispense de TOTP n'existe dans `develop`. Le script de bascule demandé dans #93 n'est pas livré.
`totp_requis` vaut toujours vrai en production (`api/app/config.py`, constaté à la lecture).

## 5. Migrations 0032 et 0033

### 5.1 Chaîne et dépendances

`main` s'arrête à `0031`. `develop` ajoute `0031 → 0032 → 0033`, sans branche Alembic. La chaîne est donc **linéaire
et indivisible** : livrer 0033 (anglais, #110) impose 0032 (français, #98), même si le Français est différé.

| Migration | Crée / modifie | Dépend de | Utilisée par | Retour arrière |
|---|---|---|---|---|
| **0032** | tables `dossier_francais`, `dossier_francais_version` (vides) | `0031` ; clé étrangère vers `domaine_pedagogique.code`, dont les lignes `francais-*` sont créées par `0023` | `models.DossierFrancais*`, `app/francais.py`, `routes/francais.py` | `downgrade` supprime les deux tables ; sans perte tant qu'aucun dossier n'est importé |
| **0033** | tables `mode_correction_seance_anglais`, `reponse_anglais` ; colonnes `groupe_anglais.mode_correction` (non nulle, valeur par défaut serveur `apres_chaque_question`) et `progression_anglais.premier_score` (nullable) | `0032` | `app/correction.py`, `routes/anglais*.py`, `routes/admin.py`, `archives.py` | `downgrade` **détruit** les réponses par question et les modes choisis : à ne jamais lancer sans sauvegarde et décision explicite |

Les deux migrations n'ajoutent que des tables et des colonnes (aucune suppression, aucune réécriture de données
existantes). D'après la lecture, l'**ancien code** peut fonctionner sur le **nouveau schéma** : la nouvelle colonne non
nulle a une valeur par défaut côté serveur, l'autre est nullable. Ce point reste **à vérifier** par un essai (lot C).

Remarque cosmétique : le nom de contrainte `ck_dossier_francais_version_ck_dossier_francais_version_statut` répète
le préfixe (convention de nommage appliquée deux fois). Il fait 62 caractères, sous la limite de 63 de PostgreSQL,
et le test `test_migrations_a_jour_avec_les_modeles` passe. Ne pas le renommer : une migration déjà appliquée en DEV
ne se réécrit pas.

### 5.2 Le Français reste fermé tant que son domaine est inactif

Constaté à la lecture dans `api/app/routes/francais.py` :

- sans domaine `francais-*` actif ou sans habilitation, l'API répond 403 ;
- un dossier introuvable, de domaine inactif ou hors habilitation renvoie toujours la même réponse 404 ;
- aucune route élève ; « valider ne publie rien aux élèves » ;
- import manuel seulement (`python -m app.francais importer`), jamais au démarrage (`docs/francais/INTEGRATION-DEV.md`).

À **prouver** sur le SHA candidat par un test de non-régression (lot C) : domaine inactif ⇒ toutes les routes
`/francais/*` refusées, y compris pour un administrateur ; aucune route élève.

### 5.3 Rétention de `reponse_anglais` (à vérifier)

`reponse_anglais` est effacée en cascade avec `eleve_anglais`. En revanche, `app/purge.py` ne parcourt que les élèves
de maths (`models.Eleve`). Il faut vérifier, avec `docs/RGPD.md`, comment les élèves d'anglais inactifs sont purgés.
0033 ajoute des réponses détaillées par question, ce qui rend ce point plus sensible.

### 5.4 Retour arrière : essai réel

**Constaté par essai** (SQLite, 14/11) : une base passée à `0033` par `develop`, puis ouverte avec le code de `main`,
fait échouer `alembic upgrade head` (`Can't locate revision identified by '0033'`). L'image API lançant
`alembic upgrade head && … && exec uvicorn`, **une image antérieure ne démarre plus** sur une base migrée. Le retour
arrière applicatif seul est donc impossible tant que la migration reste dans la commande de démarrage. C'est
l'argument principal du lot B3 (§ 9).

## 6. Constats prioritaires pour les images et la production

Classés selon la priorité demandée.

### P1 — Verrouillage du mode production

| # | Constat (lecture) | Effet | Correctif proposé |
|---|---|---|---|
| P1-a | `environnement` vaut `"dev"` par défaut (`config.py`) ; seul Compose fixe `PKP_ENVIRONNEMENT=production` | une image lancée sans cette variable démarre en DEV : clé `CLE_DEV` acceptée, `/docs` et `/openapi.json` publics, TOTP admin non exigé, SQLite accepté | l'image de production ne démarre que si `PKP_ENVIRONNEMENT` est défini explicitement ; tests de refus |
| P1-b | `.env` lu dans le dossier courant (`env_file=".env"`) | exclu de l'image par `.dockerignore` (`**/.env`), sans effet aujourd'hui | test qui vérifie l'absence de `.env` dans l'image |
| P1-c | Les contrôles de production existants (clé ≥ 32 caractères, CORS, PostgreSQL, choix explicite de `PKP_SERVIR_QUESTIONS_NON_VALIDEES`) | correctement refusés | compléter les tests de refus si nécessaire (lot B1) |

### P2 — Réduction du contenu des images

| # | Constat (lecture) | Correctif proposé |
|---|---|---|
| P2-a | `Dockerfile.api` en une seule étape ; `pip install` sur des sources complètes ; `api/tests/` copié | construction multiétape (roues construites, puis image d'exécution avec ces seules roues) ; aucun test ni outil de développement |
| P2-b | `contenu/francais/` copié alors que son import est manuel et le domaine inactif | ne copier que les contenus retenus (`contenu/<niveaux maths>`, `contenu/anglais`) ; liste explicite, contrôlée en CI |
| P2-c | `.dockerignore` limité aux artefacts | ajouter `docs/`, `scripts/`, `infrastructure/`, `deploy/vm/`, `.github/`, `.claude/`, `**/tests/` (sauf ce que la construction du front exige) |
| P2-d | `Dockerfile.web` : multiétape, tests à la construction, Caddy avec en-têtes de sécurité et CSP stricte | déjà bon ; vérifier que le bundle ne contient ni carte des sources (`.map`) ni texte DEV |
| P2-e | Images étiquetées `pkp-api:latest` | identifier par digest (lot D) |

### P3 — Migrations et imports hors du démarrage de l'API

| # | Constat | Correctif proposé |
|---|---|---|
| P3-a | `CMD` : `alembic upgrade head && python -m app.contenu importer && exec uvicorn …` | séparer trois commandes : `migrer` (tâche unique, après sauvegarde, sérialisée), `importer` (tâche unique, contenus retenus), `servir` (API seule, refuse de démarrer si le schéma n'est pas à la révision attendue, sans migrer) |
| P3-b | Le service `purge` réutilise l'image API avec sa propre commande | aucun changement de fond : vérifier qu'il ne lance jamais de migration |
| P3-c | `boussole-dev-sync` (DEV) applique déjà migrations et import en étapes séparées | réutiliser ce découpage ; ne pas casser le pipeline DEV (#65) |

## 7. Preuves exécutées sur `develop` (`805e3af`)

Environnement de cette session : Python 3.13 (la CI utilise 3.12), Node 22 (la CI utilise 20). La CI sur la PR fait foi.

| Contrôle | Résultat |
|---|---|
| `(cd api && python -m app.contenu verifier)` | Contenu valide : 154 chapitres, 1 776 questions |
| `(cd engine && pytest -q)` | 139 passed |
| `(cd api && pytest -q -W ignore::DeprecationWarning)` | 1 001 passed |
| `(cd web && npm test)` | 20 fichiers, 112 tests passed |
| `(cd web && npm audit --omit=dev --audit-level=high)` | 0 vulnerabilities |
| `(cd web && npm run build)` | réussi |
| Chaîne Alembic `0001 → 0033` sur SQLite | réussie ; essai sur PostgreSQL 16 : **non exécuté** (lot C) |
| Code de `main` sur une base à `0033` | échec attendu, voir § 5.4 |
| Bancs simulés et Terraform (§ 3.4 d'`AGENTS.md`) | non exécutés : cette PR ne touche ni `scripts/`, ni `deploy/`, ni `infrastructure/` ; vérifiés par la CI |

## 8. Requalification des tickets liés

État GitHub au 14/11/2026 : tous ouverts. Un ticket fermé ne prouverait pas la présence du correctif dans le candidat.

| Ticket | Lien avec la livraison | État dans `develop` (lecture) | Bloquant pour `main` ? |
|---|---|---|---|
| #114 (C-1), #115 (C-2) | prise de contrôle de comptes parent et de carte d'enfant par un professeur | en cours (Claude) ; non relus ici pour ne pas dupliquer | **oui** |
| #107 | ARCH-4 anglais | correctif fusionné (#109) | oui, à confirmer sur le candidat |
| #17 | isolement et droits | matrice de routes et correctif PKP Math fusionnés (#105) | oui |
| #62 | permissions de `pkp-anglais-beta.yml` | corrigé dans `develop` (#90), absent de `main` | non, livré par cette version |
| #3 à #7 | SSRF, PDF, révocation des sessions, jetons, limitation | à réévaluer un par un | #3 (P1) oui ; #4 à #7 (P2) : décision propriétaire |
| #87 | RGPD-1, retrait du nom des enfants | non appliqué | décision propriétaire |
| #8 | sauvegarde et restauration testées | ouvert | **oui** (critère de clôture de #116) |
| #20 | supervision | ouvert | à cadrer (lot F) |
| #29 | propagation des validations entre environnements | ouvert | à cadrer avec V2-D8 |
| #65 | pipeline DEV | en cours ; ne pas régresser | non |
| #78 | Dependabot, ruff, ESLint | `dependabot.yml` invalide (§ 3) | non |
| #79 | découpage d'`admin.py` | ouvert | non |
| #80, #83 | audit, gouvernance | — | non |
| #93 | bascule et dispense de TOTP | non livré dans `develop` | doit le rester hors PROD |
| #98, #102, #111 | Français | différé (§ 5.2) | non, tant que le domaine reste inactif |

## 9. Découpage proposé

#116 reste le ticket principal. Chaque lot correspond à une PR petite et relisible vers `develop`, sauf indication contraire.
Quand un ticket existant couvre déjà le sujet, il est réutilisé plutôt que d'en créer un nouveau.

| Lot | Contenu | Ticket porteur | Dépend de |
|---|---|---|---|
| **A** | Cette matrice ; report de `dependabot.yml` | #116 | — |
| **B1** | P1 : refus de démarrer sans `PKP_ENVIRONNEMENT` explicite dans l'image de production ; tests de refus | nouveau sous-ticket de #116 | A |
| **B2** | P2 : `Dockerfile.api` multiétape, `.dockerignore` élargi, liste explicite des contenus copiés, contrôle CI du contenu réel de l'image | nouveau sous-ticket de #116 | A |
| **B3** | P3 : commandes séparées `migrer` / `importer` / `servir` ; `docker-compose.yml` adapté ; `boussole-dev-sync` vérifié | nouveau sous-ticket, coordonné avec #65 | B2 |
| **C** | Tests : migrations sur PostgreSQL 16 en CI, ancien code sur nouveau schéma, Français fermé, protection des validations à l'import, contrôle final requis | nouveau sous-ticket (modifie `ci.yml` : issue dédiée exigée par `AGENTS.md` § 1) | B1, B2 |
| **D** | Workflow de préparation `release/*`, manifeste, digests, rapport dans la PR | nouveau sous-ticket | C ; décision sur le jeton (§ 10) |
| **E** | Protections et mécanisme d'autorisation adaptés à l'offre | #83 (gouvernance Git) | § 10 |
| **F** | Sauvegarde préalable, restauration testée, retour arrière, supervision | #8, #20 | B3 |
| **Sécurité** | Correctifs C-1/C-2 et réévaluation de #3 à #7 | #114, #115, #3–#7 | — (en parallèle) |

Ordre recommandé : A → B1 → B2 → B3 → C, avec les correctifs de sécurité en parallèle, puis D, E et F.

## 10. Décisions demandées au propriétaire

1. **Contenus servis en production** : `PKP_SERVIR_QUESTIONS_NON_VALIDEES` à `false` (aucune question tant que rien
   n'est validé) ou `true` pendant une phase pilote annoncée (V2-D3, V2-D8, #14).
2. **Français** : confirmer qu'il est livré **inactif**, avec son code et ses tables, et sans les fichiers
   `contenu/francais` dans l'image.
3. **`docs/analyses/`** : garder dans `main` ou non.
4. **Offre GitHub** : `docs/CONSIGNES-DEVELOPPEUR.md` indique « dépôt privé en offre gratuite ». Si c'est toujours
   le cas, il n'y a ni protection de branche ni environnement protégé. L'autorisation de déploiement reposera alors
   sur l'identité GCP PROD détenue par le propriétaire seul, avec vérification du manifeste (lot E). À confirmer.
5. **Compte `Mautic53`** (droit d'écriture sur le dépôt) : qui l'utilise, et ce droit doit-il être conservé ? Il peut
   lancer tout `workflow_dispatch`.
6. **Jeton du workflow de livraison** : une PR créée avec `GITHUB_TOKEN` ne déclenche pas la CI. Il faut une
   GitHub App ou un jeton dédié (lot D).
7. **Commits directs sur `develop` du 10/11** (`591b289` à `47c2a24`) : accepter tels quels (outillage DEV) ou les
   relire avant la livraison.

---
<sub>🤖 Produit par **Claude** (Claude Code), 14/11/2026, pour l'issue #116.</sub>
