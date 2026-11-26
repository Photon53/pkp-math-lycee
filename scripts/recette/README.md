# Recette automatisée du Français (#217)

Issue #217 — Recette multi-rôles dans un vrai navigateur (Claude), 23/11/2026.

Le script `recette-francais.mjs` rejoue, écran par écran, le parcours de chaque rôle et écrit un rapport
(`rapport.md`, `rapport.json`) avec une capture par étape. Il remplace la vérification manuelle de chaque rôle :
la personne qui valide la recette lit le rapport et les captures.

| Rôle | Ce qui est vérifié |
|---|---|
| Système | API joignable, version testée consignée, dossier importé, domaine Français collège actif |
| Professeur hors périmètre (6e) | Aucun dossier de 3e ; 404 par adresse directe |
| Validateur | Lien « Boussole Français : dossiers et validation » depuis `/enseignant` ; file de validation et boutons Valider / Refuser |
| Administrateur | Connexion à l'écran, accès au Français depuis l'administration sans nouvelle connexion, supports professeur, PDF élève, validation (V2-D15) |
| Professeur 3e | Dossier, PDF professeur, ouverture à la classe pilote |
| Élève pilote | Connexion à l'écran, dossier lisible dans « Cours », **aucun corrigé** dans la page |
| Élève d'une classe retirée du pilote | Rien dans « Cours » ; 403 par adresse directe |
| Simulation | L'élève fictif du professeur voit le dossier ouvert et n'accède à aucune route adulte |
| Non-régression | Listes Maths et Anglais de l'administration |

## 1. Pile locale jetable (agents et CI)

```bash
bash scripts/recette/pile-locale.sh /chemin/du/rapport
```

Base SQLite temporaire (jamais `api/pkp.db`), migrations, démo et import du contenu comme au déploiement, API et front
locaux, puis la recette en **mode complet** (validation et ouverture comprises). Aucun accès cloud. Prérequis :
`bash scripts/preparer-environnement.sh` et Playwright avec Chromium sur le poste.

## 2. Instance DEV (propriétaire uniquement)

Après le déploiement, tunnel IAP ouvert (`scripts/tester-ihm-gcp.ps1`) :

```bash
BASE_URL=http://127.0.0.1:<port du tunnel> VERSION=<SHA actif de boussole-dev-sync --etat> \
  ADMIN_EMAIL=<compte admin> ADMIN_MDP=<mot de passe> ADMIN_TOTP=<code à 6 chiffres> \
  node scripts/recette/recette-francais.mjs
```

- **Mode lecture par défaut** : rien n'est validé, ouvert ou réglé. Les étapes de validation et d'ouverture sont
  notées « N/A ». La recette crée seulement trois comptes professeurs fictifs et deux classes pilotes de recette,
  préfixés `recette-<horodatage>` et rappelés dans le rapport.
- `MODE=complet` valide le dossier et l'ouvre à la classe de recette. Sur une instance partagée, valider un contenu
  réel est une décision pédagogique humaine : à n'utiliser qu'avec l'accord du propriétaire.
- Le code TOTP expire en 30 secondes : lancer la commande juste après l'avoir lu.
- Joindre `rapport.md` et les captures à #217.
