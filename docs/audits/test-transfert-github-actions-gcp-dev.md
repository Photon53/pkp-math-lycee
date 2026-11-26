# Test du transfert GitHub Actions → GCP DEV (ticket #59)

> **Instantané du 11 novembre 2026, partiellement dépassé.** Ce rapport décrit l'état constaté le 11/11/2026
> (avant et pendant la PR 1 du ticket #65). Depuis : comptes WIF séparés (`boussole_role`), compte
> `boussole-dev-deployer`, bucket `mer-boussole-dev-deploiement`, rôles de `boussole-dev-tf-plan` modifiés
> (dont `roles/viewer`), pipeline de publication DEV en service et Artifact Registry alimenté (PR #66, #67,
> #69, #70). L'état à jour est suivi dans le ticket #65 ; ne pas se fier aux constats ci-dessous sur ces points.

- **Date :** 11 novembre 2026
- **Exécutant :** Claude Code (poste local, accès en lecture seule à GCP, jeton GitHub limité)
- **Branche de test :** `test/issue-59-transfert-gha-gcp-dev`, depuis `develop` @ `47c2a24`
- **Pull request :** [#64](https://github.com/Photon53/boussole-maitrise-plus/pull/64), PR normale (pas en brouillon), ouverte, non fusionnée, vers `develop`.
- **Périmètre :** DEV uniquement. Aucune action sur `main`, sur PROD, sur des données réelles ni sur des secrets. Aucun `terraform apply`.

## Verdict

**Transfert GitHub Actions → GCP DEV : authentification et PLAN démontrés côté GCP le 11/11 (voir « Mise à jour du 11/11/2026, 13:05 UTC ») ; déploiement applicatif BLOQUÉ (pipeline inexistant).**

- La **fédération d'identité GitHub OIDC → GCP** est en place, restreinte à `develop`, sans clé longue durée. Elle a déjà été utilisée avec succès par le workflow Terraform PLAN (jetons émis le 10/11/2026 entre 17:38 et 18:03 UTC, d'après Cloud Audit Logs).
- **Aucun pipeline applicatif** (build → Artifact Registry → déploiement DEV) n'existe encore : le dépôt Artifact Registry `boussole-dev` est vide.
- L'application DEV tourne grâce à un **déploiement manuel** par IAP (`scripts/deployer-dev-iap.sh`, ajouté par cette PR), et non par GitHub Actions.
- Les exécutions GitHub Actions **n'ont pas pu être déclenchées ni lues** depuis le poste : le jeton GitHub est à droits limités et renvoie HTTP 403 sur Actions, les environnements, les variables, les statuts et les protections.

## Résultats par test

| # | Test du ticket | Résultat | Preuve et constat |
|---|---|---|---|
| 1 | Projet GCP DEV, région, service, statut Terraform | **PASS** | Projet `mer-boussole-dev` (n° 948330391026), actif, facturation activée. Région `europe-west9`, zone `-a`. VM `boussole-dev` en e2-medium, RUNNING, **sans IP externe**, sortie via Cloud NAT `boussole-dev-router`. Dépôt Artifact Registry `boussole-dev` en Docker (vide). État Terraform dans `gs://mer-boussole-dev-tfstate` (versioning activé, accès public interdit). Les ressources existent, mais aucun workflow ne fait d'`apply` : elles ont été appliquées hors CI. À confirmer par un PLAN sans modification. |
| 2a | Workflows et permissions minimales | **PASS avec réserves** | `ci.yml` : `contents: read`, déclenché sur push `main` et sur PR. `gcp-dev-terraform.yml` : déclenchement manuel, garde `refs/heads/develop`, environnement `development`, `id-token: write`, **plan uniquement**, contrôle explicite du projet `mer-boussole-dev`. `import-pkp-main.yml` : `contents: write`, limité à la branche de migration. **`pkp-anglais-beta.yml` n'a aucun bloc `permissions`** et hérite donc des droits par défaut du dépôt : ajouter `permissions: contents: read`. |
| 2b | `main` et PROD protégés | **BLOQUÉ / risque** | La lecture des protections de branche renvoie 403 (jeton). L'API des règles (rulesets) répond *« Upgrade to GitHub Pro or make this repository public »* : sur un dépôt **privé en offre gratuite**, ni les rulesets ni les protections de branche ne sont disponibles. Il faut donc considérer **`main` comme non protégé**. Constat : la PR #28 (`develop` → `main`) a été fusionnée le 10/11/2026 à 15:34 UTC. |
| 3 | OIDC → WIF, sans clé longue durée | **PASS** | Pool `github-dev`, fournisseur `github` (émetteur `token.actions.githubusercontent.com`), condition `assertion.repository=='Photon53/boussole-maitrise-plus' && assertion.ref=='refs/heads/develop'`. Seul `boussole-dev-tf-plan` accorde `roles/iam.workloadIdentityUser` au dépôt. L'ancien compte `boussole-dev-terraform` n'a plus de liaison WIF. **0 clé gérée par l'utilisateur** sur les 4 comptes de service. Aucun secret affiché dans ce rapport. |
| 4 | Branche dédiée, modification inoffensive, PR en brouillon | **PASS avec écart** | Cette branche ajoute uniquement ce rapport et le script de déploiement DEV. Elle n'a aucun effet sur l'exécution. **État réel : PR #64, PR normale (pas en brouillon), ouverte, non fusionnée, vers `develop`.** Le jeton du poste ne permettait pas de créer la PR : elle a été ouverte manuellement, sans l'option brouillon. Elle ne doit pas être fusionnée sans revue. |
| 5 | Déclencher le workflow DEV autorisé (lint, tests, build, artefact, déploiement DEV) | **BLOQUÉ** | (a) Jeton GitHub du poste : HTTP 403 sur `actions/runs`, `actions/variables` et `environments`, donc impossible de lancer `gcp-dev-terraform.yml` ou de lire les runs. (b) La CI (`ci.yml`) se déclenche automatiquement sur cette PR : lint, tests moteur, API, front et build. Résultat visible dans l'onglet *Checks* de la PR. (c) **Aucun workflow ne construit ni ne publie d'image et aucun ne déploie en DEV.** Le compte fédéré n'a que `artifactregistry.reader`, et la condition WIF limite l'accès GCP à `develop`, donc une PR ne peut pas atteindre GCP. Conformément au ticket, aucun déploiement improvisé. |
| 6a | Accès à l'application DEV | **PASS (déploiement manuel)** | Sur la VM : commit `47c2a24` dans `/opt/boussole-dev`. Conteneurs `db` (healthy), `api`, `web` et `purge` démarrés depuis 12 h. `http://127.0.0.1:8080/api/health` renvoie `{"status":"ok"}`. Application exposée uniquement sur 127.0.0.1 et accessible par tunnel SSH IAP. |
| 6b | Isolation de PROD | **PASS** | Projet PROD `pkp-math-lycee` : aucun pool WIF, aucun membre IAM `boussole`, `github` ou `principal`. Le WIF DEV ne peut emprunter qu'un compte de service de `mer-boussole-dev`. |
| 6c | Coûts et quotas | **PASS partiel** | Budget « Boussole DEV - 50 EUR », alertes à 50, 80 et 100 % (non bloquantes). Coût réel non mesuré dans ce test. Postes de coût actifs : VM e2-medium 24 h/24, disque de 30 Go, Cloud NAT et son IP (`NAT_AUTO`). Quotas non audités. |
| 7 | Blocages documentés, corrections en PR en brouillon | **PASS** | Voir « Prochaines actions ». Les corrections d'infrastructure (nouveau compte de déploiement) demandent un `terraform apply` approuvé : elles ne font pas partie de cette PR. |
| 8 | Rollback et données d'élèves | **PASS partiel** | Code : retour arrière en redéployant un commit antérieur (`deployer-dev-iap.sh` vérifie le commit). `.env` et le volume PostgreSQL sont conservés à chaque relance. **Pas de sauvegarde PostgreSQL hors VM** ni de restauration testée. Données : base DEV neuve, contenu pédagogique uniquement, **aucune donnée d'élève réelle importée**. |

## Mise à jour du 11/11/2026, 13:05 UTC : Terraform PLAN corrigé et relancé

Les deux runs `GCP DEV Terraform` ont été lancés manuellement par le propriétaire sur `develop`. Vérifications faites côté GCP, dans les journaux d'audit Cloud Logging :

| Heure (UTC) | Événement | Constat |
|---|---|---|
| 12:47:49 → 12:47:55 | 4 × `GenerateAccessToken` → `boussole-dev-tf-plan` | 1er run : **authentification WIF réussie** |
| 13:01:31 | `SetIamPolicy` sur le projet (par le propriétaire) | **Correction** : ajout de `roles/browser` à `boussole-dev-tf-plan` |
| 13:02:05 → 13:02:14 | 4 × `GenerateAccessToken` → `boussole-dev-tf-plan` | 2e run : **authentification WIF réussie** |
| Toute la journée | Appels de `boussole-dev-tf-plan` en erreur | **Aucun** |
| — | `gs://mer-boussole-dev-tfstate/dev/default.tfstate` | Inchangé depuis le 10/11 à 20:05 UTC : **aucun apply** |

**Effet sur le test 5 :** le volet GitHub Actions → authentification GCP (OIDC/WIF) → Terraform PLAN en lecture seule est **démontré côté GCP (PASS)**. Restent non vérifiables depuis le poste, faute d'accès à Actions avec le jeton : la conclusion du run et la sortie du plan (attendu : `No changes`). Le pipeline applicatif (build → Artifact Registry → déploiement) reste **BLOQUÉ**, car il n'existe pas.

Rôles actuels de `boussole-dev-tf-plan` : `artifactregistry.reader`, `browser`, `compute.viewer`, `iam.serviceAccountViewer`, plus `storage.objectAdmin` sur le seul bucket d'état. Tous sont en lecture, sauf l'écriture sur l'état, qui est nécessaire au verrou Terraform.

## Constats de sécurité annexes (DEV)

1. **Réseau `default`** : il porte encore les règles `default-allow-ssh` (tcp:22) et `default-allow-rdp` (tcp:3389) ouvertes à `0.0.0.0/0`. Aucune VM n'y est rattachée (la VM est sur `boussole-dev-vpc`), mais ces règles devraient être supprimées.
2. **Compte Compute par défaut** (`…-compute@developer`) : il a `roles/editor` sur le projet. Il n'est pas utilisé par la VM, qui a son propre compte `boussole-dev-vm`. Retirer ce rôle.
3. `boussole-dev-terraform` a des rôles d'administration (`projectIamAdmin`, `compute.admin`, etc.). C'est acceptable tant qu'aucun workflow ne peut l'emprunter, ce qui est le cas aujourd'hui.

## Commandes utilisées (lecture seule)

```text
gcloud projects describe / services list / compute instances|addresses|firewall-rules|routers list
gcloud artifacts repositories list
gcloud iam service-accounts list / keys list --managed-by=user / get-iam-policy
gcloud iam workload-identity-pools list / providers list
gcloud projects get-iam-policy mer-boussole-dev | pkp-math-lycee
gcloud storage buckets describe / get-iam-policy gs://mer-boussole-dev-tfstate
gcloud billing budgets list
gcloud logging read 'protoPayload.methodName:"GenerateAccessToken"' --freshness=7d
gcloud compute ssh boussole-dev --tunnel-through-iap --command "docker ps; curl /api/health; git log -1"
gh api repos/…/branches/{main,develop}/protection | rulesets | environments | actions/*   → 403
```

## Prochaines actions

| Priorité | Action | Effet |
|---|---|---|
| P0 | Donner au jeton GitHub les droits Actions en lecture/écriture et Administration, Environments, Variables, Checks et Statuses en lecture, ou se reconnecter avec `gh auth login --web --scopes workflow`. | Permet de lancer `gcp-dev-terraform.yml` sur `develop`, de lire les runs et de clore les tests 2b et 5. |
| P0 | Lancer `GCP DEV Terraform` sur `develop` et vérifier un plan **sans modification**. | Prouve que l'état Terraform correspond aux ressources réelles. |
| P0 | Décider de la protection de `main` : passer à GitHub Pro, ou rendre la règle « pas de push direct sur `main` » organisationnelle et contrôlée. | Critère d'acceptation « `main` protégé ». |
| P1 | Pipeline applicatif DEV : nouveau compte `boussole-dev-deployer` avec `artifactregistry.writer` sur le seul dépôt `boussole-dev`, lié au WIF `develop`. Workflow : tests → build des images `api`/`web` → push vers Artifact Registry. La VM **tire** l'image (compte `boussole-dev-vm`, `artifactregistry.reader`), ce qui évite tout accès SSH entrant depuis GitHub. | Déploiement DEV reproductible depuis `develop`, avec retour arrière par tag d'image. Demande un `terraform apply` approuvé. |
| P1 | Ajouter `permissions: contents: read` à `pkp-anglais-beta.yml`. | Moindre privilège. |
| P1 | Sauvegarde `pg_dump` quotidienne vers un bucket GCS DEV versionné, puis test de restauration. | Retour arrière des données. |
| P2 | Supprimer les règles `default-allow-*` (ou le réseau `default`) et retirer `roles/editor` du compte Compute par défaut. | Réduction de la surface d'attaque. |
| P2 | Arrêter la VM hors des périodes de test et mesurer le coût réel après 7 jours. | Tenir l'objectif de 150 € sur 3 mois. |
