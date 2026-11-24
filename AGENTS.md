# AGENTS.md — instructions aux agents IA

Ce fichier s'applique à **tout agent IA** (DeepSeek, Claude, Codex ou autre) qui modifie ce dépôt.
Chaque production est attribuée à **l'agent qui l'a réellement produite** (§ 2). L'attribution déclarative ne constitue pas une signature cryptographique.

> Version consolidée — 13/11/2026 — issue #83, préparation pour la PR #86.

## Historique

| Version | Date | Contribution |
|---|---|---|
| v1 | 13/11/2026 | DeepSeek : rédaction initiale, PR #84 fusionnée |
| v2 | 13/11/2026 | DeepSeek : proposition de révision ; revues de Claude et Codex |
| Correctifs PR #86 | 13/11/2026 | Claude : consignes, modèle de PR et transcription de la décision du propriétaire RGPD-1 |
| Consolidation | 13/11/2026 | Codex : intégration documentaire des apports et corrections ; intégrée dans la PR #86 par Claude |

---

## 0. Hiérarchie des consignes

| Document | Responsabilité |
|---|---|
| `AGENTS.md` (ce fichier) | Règles propres aux agents IA : interdits, traçabilité, commandes, définition de « terminé » |
| `docs/CONSIGNES-DEVELOPPEUR.md` | Façon de travailler et vocabulaire métier, pour tout développeur, humain ou agent |
| `docs/ARCHITECTURE.md`, `docs/RGPD.md`, `docs/CONTENU.md`, `docs/DEPLOIEMENT.md` | Règles de leur domaine ; ils font foi sur ce domaine |
| `docs/DECISIONS.md` | Décisions prises, en attente ou écartées (`ARCH-`, `SEC-D`, `V2-D`, `DEV-D`, `RGPD-`) |
| `CLAUDE.md` ou autre fichier propre à un outil | **Complément sans duplication** : réglages de l'outil, renvoi vers ce fichier |

Ce fichier résume certaines règles des documents métier ; en cas d'écart, **le document du domaine fait foi** et
ce fichier doit être corrigé. Une contradiction entre documents, ou entre un document et le code, **ne se tranche
pas par l'agent** : il la signale dans l'issue (§ 9), avec les options et une recommandation, avant d'agir. Choisir
« la règle la plus restrictive » ne suffit pas toujours (deux règles peuvent être incompatibles) et ne remplace
pas le signalement.

---

## 1. Règles absolues

Ces points ne se négocient pas et ne demandent pas d'arbitrage : ils sont déjà tranchés.

| Interdit | Pourquoi |
|---|---|
| `git push` direct sur `main` ou `develop` | toute modification passe par une PR relue |
| `terraform apply`, `terraform init` avec backend, `terraform plan` sur l'état réel | le déploiement DEV passe par GitHub Actions et WIF, jamais par un poste |
| Lancer un script d'exploitation (liste ci-dessous) | ces scripts agissent sur GCP, la VM, l'IAM ou les sauvegardes |
| Lire ou écrire un secret : `deploy/.env`, tout `.env`, `PKP_SECRET_KEY` hors démo, clé de compte de service, état Terraform (`*.tfstate`, sauvegardes et exports) | l'agent n'en a pas besoin |
| Modifier `.github/workflows/**` sans issue dédiée | la CI est le contrat de qualité du dépôt |
| Supprimer une question | une question s'archive (`archivee`), elle ne disparaît jamais |
| Ajouter `eval`, `exec`, `os.system`, `subprocess` dans `engine/` ou `api/` | la correction est un parseur `ast` à liste blanche |
| Renommer `pkp` / `PKP_*` | conservés pour compatibilité (voir `MIGRATION.md`) |
| Versionner `sources/` | photos et extraits de manuels : droit d'auteur (voir § 5) |

**Scripts d'exploitation — interdits** (ils supposent Cloud Shell, des identifiants GCP ou la VM) :

- `deploy/*.sh` (dont `deploy/sauvegarde-prod.sh`, sauf son banc simulé) et `deploy/vm/boussole-dev-sync` ;
- `scripts/audit-dev-compte-compute.sh`, `scripts/bootstrap-gcp-dev.sh`, `scripts/boussole-dev.sh`,
  `scripts/controle-acces-sauvegardes.sh`, `scripts/deployer-dev-iap.sh`, `scripts/dev-publier-version.sh`,
  `scripts/reprise-terraform-dev.sh`, `scripts/terraform-dev-cloudshell.sh`, `scripts/wif-dev-comptes-separes.sh` ;
- `scripts/tester-ihm-gcp.ps1` (Windows : SSH via IAP sur la VM DEV, lecture de l'état des conteneurs, tunnel ; peut démarrer la VM après accord) ;
- `scripts/troubleshooter_iam.py` (peut interroger Policy Troubleshooter) ;
- `scripts/comparer-politique-bucket.py` (comparaison locale de fichiers IAM et de plan Terraform ; exécution réservée au propriétaire dans ce périmètre).
- `scripts/recette/recette-francais.mjs` **pointé vers une instance partagée** (`BASE_URL` autre que la pile locale) : il y crée des comptes fictifs et, en `MODE=complet`, valide et ouvre un contenu ; exécution réservée au propriétaire (#217).

Un nouveau script qui touche au cloud, à la VM ou aux secrets s'ajoute à cette liste dans la même PR.

**Tests simulés — autorisés** (aucun accès cloud : faux `gcloud`, faux GCS, faux `docker`, faux services) :

- `scripts/test-dev-publier-version.sh` ;
- `deploy/vm/tests/test-boussole-dev-sync.sh`, `deploy/vm/tests/test-refus-deploiement-manuel.sh` ;
- `scripts/tests/test-controle-acces-sauvegardes.sh` ;
- `deploy/sauvegarde/tests/test-sauvegarde-prod.sh` (faux `docker` et faux `gcloud`, vrai `age`) ;
- `scripts/recette/pile-locale.sh` (base SQLite temporaire, API et front locaux, recette Français multi-rôles dans Chromium ; aucun accès cloud, ne touche pas `api/pkp.db`) ;
- `bash -n <script>` sur n'importe quel script (vérification de syntaxe, rien n'est exécuté).

**Autres scripts** : lire et vérifier leurs effets ; demander une décision uniquement s'ils dépassent le périmètre autorisé ou restent ambigus. Le nom seul ne permet pas de décider : `installer-dev.sh` et `deployer-dev-iap.sh` ont des effets différents. Les interdictions explicites ci-dessus restent applicables.

**Autres commandes autorisées** :

- `scripts/tests.sh`, `scripts/tests.ps1` ; `scripts/preparer-environnement.sh` (outils et dépendances, sans
  identifiant cloud ni base ; peut recréer `.venv`, télécharger des outils et réinstaller les dépendances) ;
- `terraform fmt`, `terraform init -input=false -backend=false`, `terraform validate` ;
- `scripts/charge_classe.py` et `scripts/mesure_import.py` **uniquement contre une API ou une base locale de
  démonstration** ;
- les commandes `gh` en lecture, la création d'issues et de PR.

**Autorisé sous condition — `scripts/installer-dev.sh` / `installer-dev.ps1`** : ces scripts **suppriment puis
recréent `api/pkp.db`**. Avant de les lancer, l'agent vérifie que `api/pkp.db` n'existe pas ou n'est qu'une base de
démonstration jetable (aucune donnée saisie à conserver). En cas de doute, il ne les lance pas et utilise
`scripts/preparer-environnement.sh`, qui ne touche pas à la base.

---

## 2. Traçabilité — exigence du propriétaire

Chaque production d'un agent (code, configuration, documentation) est **référencée à l'issue traitée et attribuée
à l'agent qui l'a réellement produite**. Dans les exemples ci-dessous, `<Agent>` vaut le nom de cet agent :
`DeepSeek`, `Claude`, `Codex`… Un humain qui reprend le travail d'un agent conserve l'attribution d'origine et ajoute
la sienne. L'attribution historique d'un fichier ou d'un commit existant ne se réécrit pas.

### 2.1 Le commit

```
type(portée): description courte (#N)

Corps facultatif : ce qui change, pourquoi, ce qui n'est pas fait.

Agent: <Agent>
Refs: #N
```

- Types utilisés dans l'historique : `feat`, `fix`, `infra`, `ci`, `docs`, `test`, `ops`, `security`.
- Messages en **français**, accents compris.
- Le numéro d'issue est **obligatoire** dès qu'il existe.
- `Agent: <Agent>` est une attribution déclarative, pas une signature cryptographique.
- Si l'outil de l'agent impose ses propres lignes d'attribution (par exemple `Co-Authored-By`), elles s'ajoutent
  à `Agent:` sans la remplacer.

### 2.2 L'en-tête du fichier nouveau

Tout fichier **source ou de configuration créé** porte, en tête, une référence courte dans la syntaxe de
commentaire du format :

```python
# Issue #65 — Pipeline DEV (<Agent>)
```

```javascript
// Issue #65 — Pipeline DEV (<Agent>)
```

L'en-tête **ne déplace jamais une déclaration technique** qui doit rester en première ligne : il se place juste
après le shebang de tout fichier qui en possède un (shell ou Python, par exemple `#!/usr/bin/env bash` ou `#!/usr/bin/env python3`), la déclaration d'encodage, la ligne `<!doctype html>` ou la docstring de
module exigée par l'outil.

Cas particuliers :

| Fichier | Traçabilité |
|---|---|
| Migration Alembic (`api/migrations/versions/`) | Préserver les métadonnées générées (`revision`, `down_revision`, docstring d'en-tête) ; la référence `Issue #N (<Agent>)` s'ajoute dans la docstring, après le message de révision |
| Format sans commentaire (JSON) | Par le commit et la PR seulement |
| Fichier généré (`package-lock.json`, `docs/CONTENU-INVENTAIRE.md`, sorties de build ; hors migrations Alembic) | Par le commit et la PR seulement |
| Données pédagogiques (`contenu/**/*.yaml`) | Par le commit, la PR et le registre des sources (§ 5) ; pas d'en-tête dans chaque fichier |
| Fichier modifié (non créé) | Par le commit et la PR ; ne pas ajouter d'en-tête |

### 2.3 La pull request

Titre identique au commit. Corps rempli avec `.github/pull_request_template.md`, section « Agent IA » renseignée
avec le nom de l'agent. **Base : `develop`**, jamais `main`.

### 2.4 Le commentaire dans l'issue

Après ouverture de la PR, poster un commentaire sur l'issue traitée, dans ce format :

```markdown
## Traitement — PR #<numéro>

**Ce qui a été fait**
- …

**Fichiers modifiés**
- `chemin/fichier.py`

**Tests exécutés**
- `(cd engine && pytest -q)` → N passed
- `(cd web && npm test)` → N passed
- `…` → **non exécuté** : <raison> ; vérifié par la CI (job « … »)

**Reste à faire / limites**
- …

---
<sub>🤖 Produit par **<Agent>** (<outil>), <date>.</sub>
```

L'agent ne ferme jamais une issue lui-même.

### 2.5 `Closes` ou `Refs`

- `Refs #N` pour référencer l'issue ; obligatoire pour les tickets de décision, de pilotage ou traités en plusieurs PR, jusqu'à décision explicite du propriétaire.
- `Closes #N` exprime que la PR traite entièrement l'issue. La fermeture automatique par ce mot-clé ne fonctionne que pour une PR ciblant la branche par défaut. Ici, la branche par défaut est `main` et les PR de travail ciblent `develop` : ne pas attendre une clôture automatique à la fusion dans `develop`.
- Après intégration dans `develop`, une personne vérifie les critères de clôture et ferme l'issue si nécessaire. L'agent ne fusionne ni ne ferme lui-même.

---

## 3. Environnement et commandes

| Élément | Version |
|---|---|
| Python | **3.12** (`.python-version`, comme la CI) ; 3.11 minimum (`pyproject.toml`) |
| Node.js | **20** (`.nvmrc`) |
| Outils et dépendances | `bash scripts/preparer-environnement.sh` (sans base ni identifiant cloud) |
| Base de démonstration | `bash scripts/installer-dev.sh` — **supprime `api/pkp.db`**, voir § 1 |
| Tests applicatifs | `bash scripts/tests.sh` (moteur, API, front) |

Avant chaque PR, exécuter **depuis la racine du dépôt** les commandes de la CI (`.github/workflows/ci.yml`). Chaque
ligne est un sous-shell : elle ne change pas le dossier courant.

### 3.1 Installation

```bash
pip install -e "./engine[dev]" -e "./api[dev]"
(cd web && npm ci --no-audit --no-fund)
```

Utiliser l'environnement virtuel du projet pour ces commandes.

### 3.2 Job « Moteur, API et contenu »

```bash
(cd api && python -m app.contenu verifier)
(cd engine && pytest -q)
(cd api && pytest -q -W ignore::DeprecationWarning)
```

Après modification de `contenu/`, régénérer l'inventaire avant les contrôles, puis inclure le diff généré :

```bash
(cd api && python -m app.contenu inventaire)
```

### 3.3 Job « Front »

```bash
(cd web && npm audit --omit=dev --audit-level=high)
(cd web && npm test)
(cd web && npm run build)
```

### 3.4 Job « Terraform DEV » et bancs simulés (sans accès GCP)

```bash
(cd infrastructure/terraform/dev && terraform fmt -check -recursive)
(cd infrastructure/terraform/dev && terraform init -input=false -backend=false && terraform validate)
for f in scripts/*.sh deploy/*.sh infrastructure/terraform/dev/*.sh; do bash -n "$f"; done
bash scripts/test-dev-publier-version.sh
bash -n deploy/vm/boussole-dev-sync
bash deploy/vm/tests/test-boussole-dev-sync.sh
bash deploy/vm/tests/test-refus-deploiement-manuel.sh
bash scripts/tests/test-controle-acces-sauvegardes.sh
bash deploy/sauvegarde/tests/test-sauvegarde-prod.sh
```

Si la CI évolue, `ci.yml` fait foi et cette liste doit être mise à jour dans la même PR.

### 3.5 Tests impossibles en local

**Test impossible en local** (outil absent, réseau fermé, plateforme différente) : ne jamais le cocher comme
réussi. Ouvrir la PR **en brouillon**, indiquer « non exécuté », la raison, et le job de CI qui le vérifiera ; ne
demander la relecture qu'une fois la CI verte.

Une PR dont la CI est rouge ne se demande pas en relecture.

---

## 4. Git

| Règle | Valeur |
|---|---|
| Branche de base | `develop` |
| Nom de branche | `<type>/issue-<n>-<sujet>` — ex. `fix/issue-65-liste-releases` |
| Taille | **une PR = une issue**, petite et relisible |
| Fusion | jamais par l'agent : une personne relit et fusionne |
| Force-push | interdit sur une branche partagée (une PR ouverte) |
| Attribution | `Agent: <nom>` obligatoire ; attribution déclarative, pas signature cryptographique |

---

## 5. Invariants du projet

Ces règles sont vérifiées par les tests, la CI ou la relecture. Le document cité fait foi.

| Invariant | Détail |
|---|---|
| `engine/` reste pur | n'importe ni FastAPI ni SQLAlchemy ; la conversion passe par `api/app/db/conversions.py` (`ARCH-1`) |
| Modèle modifié ⇒ migration | `alembic revision --autogenerate`, **relue à la main** ; utiliser `sa.false()` et non `sa.text('0')`, sinon PostgreSQL refuse ; `test_migrations_a_jour_avec_les_modeles` échoue sinon (`ARCH-2`) |
| Question jamais supprimée | colonne `archivee`, garde ORM `SuppressionInterdite` (qui déclenche l'erreur vérifiée par les tests de suppression), clé étrangère `RESTRICT` depuis `reponse` (`ARCH-3`) |
| Solution protégée | **aucune solution transmise à l'élève avant sa réponse** : `QuestionPublique` n'a pas de champ `solution`. Après réponse, `ResultatReponse` et `ReponseHistorique` la contiennent ; côté adultes, `QuestionEnseignant` la contient, et son accès est soumis aux habilitations (`exiger(permission, domaine)`) (`ARCH-4`) |
| Correction sans `eval` | parseur `ast`, liste blanche de nœuds, saisie ≤ 200 caractères |
| Données personnelles | **minimisation** (`docs/RGPD.md`) : élève identifié par prénom + code classe + code personnel haché, aucun e-mail élève. Décision **RGPD-1** : un enfant n'a **aucun nom de famille**, les nouveaux comptes reçoivent un identifiant prénom sans accents + numéro, sans séparateur (`Lina1`), unique sur la plateforme, comparé sans casse ni accents, limité à 40 caractères ; numéro jamais réattribué. Les identifiants déjà émis sont conservés. Le parent garde nom et prénom. **Appliquée** (#87, migration `0039`) : `Enfant.nom` n'existe plus ; l'agent ne réintroduit aucun nom de famille d'enfant ni aucune autre donnée nominative d'enfant, et crée les identifiants avec `enfants.identifiant_libre` |
| Droit d'auteur | ne jamais versionner `sources/` (photos, extraits de manuels) ; exception : `referentiels/sources/` (textes officiels BO). Tout contenu de `contenu/**/*.yaml` remplit le registre des sources : `source`, `source_url`, `licence_source`, `adaptation` (`docs/CONTENU.md`) |
| Style | UTF-8, fins de ligne LF, indentation 4 espaces (Python), 2 (JS/JSX/JSON/CSS/HTML/YAML), CRLF pour `.ps1`/`.bat` (`.editorconfig`) |
| Langue | code métier, documentation, commits et messages d'interface **en français** (`ARCH-6`) |

---

## 6. Lecture obligatoire avant d'agir

1. `README.md`
2. `docs/CONSIGNES-DEVELOPPEUR.md` — façon de travailler, vocabulaire métier
3. `docs/ARCHITECTURE.md`
4. `docs/DECISIONS.md` — décisions prises et en attente ; toujours citer un identifiant **préfixé** :
   `SEC-D` (sécurité), `V2-D` (cahier des charges V2), `DEV-D` (pipeline DEV, #65), `ARCH-` (architecture), `RGPD-` (données personnelles).
   « D1 » seul est ambigu.
5. `docs/CONTENU.md`
6. `docs/RGPD.md`
7. `docs/CAHIER-DES-CHARGES-V2.md` — périmètre

Et selon le sujet : `docs/DEPLOIEMENT.md` (infra), `docs/audit/` (sécurité), `docs/exploitation/` (exploitation).

---

## 7. Définition de « terminé »

- [ ] Les contrôles des § 3.2 et § 3.3 passent ; les preuves locales ou les jobs CI équivalents sur le SHA exact sont indiqués. Un contrôle requis encore sans résultat laisse le travail en préparation
- [ ] Le § 3.4 est vérifié si la PR touche `infrastructure/`, `scripts/` ou `deploy/` ; la CI complète reste requise pour toute PR
- [ ] Après modification de `contenu/`, l'inventaire est régénéré (§ 3.2)
- [ ] La CI est verte sur la PR
- [ ] Migration fournie et relue si un modèle a changé
- [ ] Aucun secret, aucune donnée personnelle réelle, aucun fichier `sources/` dans le diff, sauf les textes officiels autorisés dans `referentiels/sources/`
- [ ] Le registre des sources est rempli pour tout contenu ajouté
- [ ] Commit, en-tête de fichier, PR et commentaire d'issue conformes au § 2, **au nom de l'agent réel**
- [ ] La PR est liée à l'issue (`Closes #N` ou `Refs #N`, § 2.5)

---

## 8. Ce que l'agent ne décide pas seul

- Les choix produit, tarifaires et juridiques (offres, licence, RGPD, CGI) : ce sont des décisions du propriétaire,
  éventuellement avec un conseil externe.
- La fusion d'une PR et la fermeture d'une issue.
- La modification des protections de branche, des secrets, des règles IAM ou des environnements.
- La validation pédagogique d'un contenu : un agent peut signaler, jamais valider à la place d'un professeur.
- La résolution d'une contradiction entre documents ou entre un document et le code (§ 0).

---

## 9. Signaler un blocage

Si une règle empêche d'avancer, **ne pas contourner** : ouvrir un commentaire dans l'issue avec le blocage, les
options et la recommandation. Le propriétaire tranche.

---

<sub>🤖 Version initiale rédigée par **DeepSeek** (DeepSeek Harness) pour l'issue #83, 13/11/2026 (PR #84).
Correctifs de relecture et transcription de RGPD-1 : **Claude** (Claude Code), PR #86.
Consolidation documentaire : **Codex**, intégrée dans la PR #86, issue #83, 13/11/2026.</sub>
