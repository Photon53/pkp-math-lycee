# Lot A — Sécurité et protection des données

**État : exécuté le 28/10/2026 (14 contrôles : 6 réussis, 4 échoués, 2 partiels, 2 non exécutés) — constats à valider par le référent sécurité.** Méthode, grille de gravité et rôles : [README.md](README.md).

| Champ | Valeur |
|-------|--------|
| Commit audité | `977cad2271bacdceec0905161c47167969c12130` (fusion de la PR #1) |
| Date d'exécution | 28/10/2026, environnement isolé : clone GitHub sur C:, venvs dédiés, base SQLite de démo neuve |
| Exécuté par / validé par | Claude (assistant de développement) / *référent sécurité à désigner* |
| Versions des outils | bandit 1.9.4, pip-audit 2.10.1, gitleaks 8.30.1 (SHA-256 vérifié), semgrep 1.182.1 (inopérant), npm 11.16.0 — détail : `preuves/environnement.txt` |

## Périmètre

22 routes HTTP, dont 3 publiques (`GET /health`, `POST /eleves/connexion`, `POST /enseignants/connexion`).
Inventaire relevé dans le schéma OpenAPI au moment de la rédaction ; à revérifier à l'exécution :

```
élève       GET /cours, /cours/{competence_id}, /eleves/moi, /eleves/moi/progression
            POST /seances, /seances/{id}/fin, /seances/{id}/reponses ; GET /seances/{id}/question
enseignant  GET/POST /enseignants/classes ; DELETE /enseignants/classes/{id}
            GET /enseignants/classes/{id}/eleves, /enseignants/competences
            DELETE /enseignants/eleves/{id} ; GET /enseignants/eleves/{id}/export, .../progression
            GET/POST /enseignants/questions ; POST /enseignants/questions/{id}/archiver
```

## Préparation de l'environnement isolé

```bash
git clone <dépôt> audit-a && cd audit-a && git checkout <commit>
python -m venv .venv-audit
.venv-audit/Scripts/python -m pip install -e ./engine -e "./api[dev]" bandit pip-audit semgrep
cd api && ../.venv-audit/Scripts/python -m alembic upgrade head && ../.venv-audit/Scripts/python -m app.db.seed
cd ../web && npm ci
mkdir -p docs/audit/preuves
```

Gitleaks est un binaire à télécharger depuis ses publications officielles (github.com/gitleaks/gitleaks/releases),
avec vérification de la somme de contrôle. `pip-audit` et `npm audit` interrogent des bases de vulnérabilités
en ligne : l'environnement isolé a besoin d'un accès réseau sortant pour ces deux contrôles seulement.

## Contrôles

### A-01 — Analyse statique du code Python (Bandit)

| | |
|---|---|
| Procédure | `bandit -r engine/src api/app -f json -o docs/audit/preuves/A-01-bandit.json` puis `bandit -r engine/src api/app` pour la lecture |
| Réussite | Aucune alerte de sévérité HIGH non justifiée ; chaque alerte MEDIUM examinée et classée (avérée / faux positif / risque accepté) |
| Échec | Une alerte HIGH avérée, ou une alerte non examinée |
| Gravité si échec | Selon l'alerte (exécution de code ou injection : Critique) |
| Résultat / preuve | **RÉUSSI** — 0 constat sur 1 746 lignes (engine/src, api/app) / `A-01-bandit.json` |

### A-02 — Analyse statique complémentaire (Semgrep, Python + React)

| | |
|---|---|
| Procédure | `semgrep scan --config p/python --config p/react --config p/secrets --json -o docs/audit/preuves/A-02-semgrep.json` |
| Réussite | Aucune alerte ERROR non justifiée ; `dangerouslySetInnerHTML` (rendu des cours) examiné : le contenu passe par DOMPurify (`web/src/maths.jsx`) |
| Échec | Une alerte ERROR avérée |
| Gravité si échec | Selon l'alerte (XSS exploitable : Critique) |
| Résultat / preuve | **NON EXÉCUTÉ** — `semgrep-core` échoue au démarrage sous Windows natif sur les trois jeux de règles (`A-02-semgrep-*.log`). Revue manuelle de substitution : un seul point d'injection HTML (`web/src/maths.jsx:29`), alimenté par les cours YAML **et par les énoncés créés par tout enseignant** ; DOMPurify y est appelé avec `ADD_TAGS`/`ADD_ATTR` en tableau, sans `IN_PLACE` ni `RETURN_DOM`. À exécuter sous Linux (CI ou Docker). |

### A-03 — Vulnérabilités connues des dépendances Python

| | |
|---|---|
| Procédure | `pip-audit --desc -f json -o docs/audit/preuves/A-03-pip-audit.json` (dans `.venv-audit`) ; refaire avec l'extra `postgres` |
| Réussite | Aucune vulnérabilité connue dans une dépendance utilisée à l'exécution (FastAPI, Starlette, SQLAlchemy, Uvicorn, PyYAML, Pydantic, psycopg), ou vulnérabilité examinée et non applicable, avec justification écrite |
| Échec | Vulnérabilité applicable avec correctif disponible non appliqué |
| Gravité si échec | Élevée (Critique si exploitable à distance sans authentification) |
| Résultat / preuve | **RÉUSSI** — 0 vulnérabilité connue sur 35 paquets (dépendances d'exécution et de test, extra `postgres` inclus) / `A-03-pip-audit.json`, `A-03-requirements-app.txt` |

### A-04 — Vulnérabilités connues des dépendances JavaScript

| | |
|---|---|
| Procédure | `npm audit --omit=dev --json > ../docs/audit/preuves/A-04-npm-prod.json` puis `npm audit --json > ../docs/audit/preuves/A-04-npm-tout.json` (depuis `web/`) |
| Réussite | 0 vulnérabilité high/critical dans les dépendances livrées au navigateur (React, KaTeX, marked, DOMPurify) ; celles des outils de développement examinées |
| Échec | Une vulnérabilité high/critical applicable dans une dépendance livrée |
| Gravité si échec | Élevée (Critique si XSS exploitable via le rendu des cours) |
| Résultat / preuve | **ÉCHOUÉ** — livré au navigateur : `dompurify` 3.2.3 (*high*, série d'avis XSS, corrigés après 3.4.16) et `katex` 0.16.11 (*moderate*, `\htmlData` ; l'option `trust` n'étant pas activée, avis probablement non applicable). Outils de développement seulement : `vitest` et `tinypool` (*critical*), `vite` (*high*), `esbuild`, `@vitest/mocker`, `vite-node` (*moderate*). / `A-04-npm-prod.json`, `A-04-npm-tout.json` |

### A-05 — Secrets dans le dépôt et son historique (Gitleaks)

| | |
|---|---|
| Procédure | `gitleaks git . --report-format json --report-path docs/audit/preuves/A-05-gitleaks.json -v` (tout l'historique) |
| Réussite | Aucun secret réel. Exceptions connues, à confirmer comme non sensibles : mot de passe de démo `demo-pkp-2026` (`api/app/db/seed.py`, usage local), valeur `CLE_DEV` (refusée en production, cf. A-10) |
| Échec | Un secret réel (clé, jeton, mot de passe de production) présent dans l'arbre ou l'historique |
| Gravité si échec | Critique (rotation du secret obligatoire, réécrire l'historique ne suffit pas) |
| Résultat / preuve | **RÉUSSI** — 0 secret dans tout l'historique (≈ 414 Ko analysés) ; le mot de passe de démo et `CLE_DEV` ne sont pas signalés / `A-05-gitleaks.json` |

### A-06 — Hachage des mots de passe enseignant

| | |
|---|---|
| Procédure | 1. Lire `_N, _R, _P` dans `api/app/security.py`. 2. Lire le préfixe d'une empreinte en base : `SELECT mot_de_passe_hash FROM enseignant` (format `scrypt$N$r$p$sel$empreinte`). 3. Mesurer le temps d'un hachage. |
| Réussite | N ≥ 2¹⁷, r = 8, p = 1 (recommandation OWASP *Password Storage Cheat Sheet* pour scrypt) ; sel aléatoire de 16 octets ; comparaison en temps constant (`hmac.compare_digest`) ; paramètres stockés dans l'empreinte |
| Échec | N < 2¹⁷, sel fixe ou absent, comparaison non constante |
| Observation préalable (code lu à la rédaction, à confirmer) | `_N = 2**14`. Les paramètres étant stockés dans chaque empreinte, une montée en coût est possible sans invalider les comptes, mais aucun re-hachage à la connexion n'est implémenté. |
| Gravité si échec | Élevée |
| Résultat / preuve | **ÉCHOUÉ** — N = 2¹⁴ (16 384) dans le code et dans l'empreinte stockée, sous le minimum N = 2¹⁷ ; r = 8, p = 1, sel de 16 octets, comparaison `hmac.compare_digest` : conformes. Hachage mesuré : 211 ms. Pas de re-hachage à la connexion. / `A-dynamiques.json` |

### A-07 — Isolation entre élèves

| | |
|---|---|
| Procédure | Avec deux élèves A et B de la **même** classe de démo (Lina, Yanis) : (a) B appelle `GET /seances/{séance_A}/question`, `POST /seances/{séance_A}/reponses`, `POST /seances/{séance_A}/fin` ; (b) B parcourt `GET /seances/{id}/question` pour id = 1…200 ; (c) vérifier dans OpenAPI qu'aucune route élève n'accepte un identifiant d'élève ; (d) **usurpation** : se connecter avec `{"prenom": "Lina", "code_classe": "2NDE-A-DEMO"}` depuis le poste de B, puis `GET /eleves/moi/progression` |
| Réussite | (a)(b) : 404 pour toute séance qui n'est pas à B ; (c) : aucune route concernée ; (d) : l'accès au compte de Lina est refusé sans un secret qu'elle seule possède |
| Échec | Une réponse 200 sur la séance d'un autre élève, ou (d) possible |
| Observation préalable | Par conception (« élève = prénom + code classe »), (d) **réussit aujourd'hui** : un camarade connaissant le code de la classe accède à la progression et peut répondre à la place d'un autre élève. → **Décision D1** : changer le modèle (code personnel distribué par l'enseignant, par exemple) ou accepter formellement le risque. Les tests automatisés existants couvrent (a) partiellement (`test_seance_d_un_autre_eleve`). |
| Gravité si échec | Critique, sauf acceptation écrite du risque (D1) |
| Résultat / preuve | **ÉCHOUÉ (d)** — (a) 404 sur les 3 routes de la séance de Lina ; (b) énumération 1–200 : 198 × 404 et 1 × 409, ce 409 étant la propre séance terminée de Yanis (vérifié sur base neuve, `A-07-verification-409.txt`) ; (c) seuls `seance_id` et `competence_id` en paramètre ; **(d) connexion « Lina » sans secret → 200, même identifiant que Lina, ses 5 réponses lisibles.** / `A-dynamiques.json` |

### A-08 — Isolation entre enseignants et entre rôles

| | |
|---|---|
| Procédure | Créer un second enseignant (`python -m app.admin creer`). Avec son jeton : `GET /enseignants/classes/{classe_A}/eleves`, `GET .../eleves/{eleve_A}/progression`, `GET .../eleves/{eleve_A}/export`, `DELETE .../eleves/{eleve_A}`, `DELETE .../classes/{classe_A}`. Puis jeton élève sur chaque route enseignant, jeton enseignant sur chaque route élève. Puis `POST /enseignants/questions/{id}/archiver` sur une question quelconque. |
| Réussite | 404 sur toutes les ressources d'un autre enseignant (sans révéler leur existence) ; 401 sur toute route d'un autre rôle ; archivage conforme à la décision D3 |
| Échec | Une réponse 200/204 sur la ressource d'un autre enseignant, ou une route accessible au mauvais rôle |
| Observation préalable | La banque de questions est commune : tout enseignant peut archiver toute question (D3). |
| Gravité si échec | Critique |
| Résultat / preuve | **RÉUSSI** (sous réserve de D3) — enseignant B : 404 sur les 5 ressources de A, liste de classes vide ; jeton élève sur 11 routes enseignant → 401 ; jeton enseignant sur 8 routes élève → 401 ; B archive la question 1 → 200 (banque commune, D3). / `A-dynamiques.json` |

### A-09 — Jetons : signature, expiration, révocation

| | |
|---|---|
| Procédure | (a) jeton expiré ; (b) charge modifiée avec l'ancienne signature ; (c) jeton élève présenté comme enseignant ; (d) jeton d'un élève supprimé ; (e) jeton enseignant émis **avant** un changement de mot de passe (`python -m app.admin mot-de-passe`) ; (f) changement de `PKP_SECRET_KEY` ; (g) comparer les durées réelles (charge décodée) à la documentation (12 h élève, 8 h enseignant) |
| Réussite | (a)–(d), (f) : 401 ; (e) : 401 ; (g) : durées conformes |
| Échec | Un jeton accepté dans l'un de ces cas |
| Observation préalable | Le code ne contient pas de mécanisme de révocation : (e) devrait être accepté jusqu'à expiration. À confirmer. |
| Gravité si échec | (a)–(d), (f) : Critique ; (e) : Élevée |
| Résultat / preuve | **ÉCHOUÉ (e)** — (a) expiré 401, (b) charge modifiée 401, (c) rôle réécrit 401, (d) élève supprimé 401, (f) clé changée 401, (g) 12,00 h et 8,00 h conformes ; **(e) jeton émis avant changement de mot de passe → 200.** / `A-dynamiques.json` |

### A-10 — Configuration de production

| | |
|---|---|
| Procédure | (a) `PKP_ENVIRONNEMENT=production python -c "import app.main"` avec : clé par défaut / clé de 20 caractères / SQLite / CORS `*` → doit échouer. (b) Avec une configuration valide (clé de 48 caractères, URL PostgreSQL fictive, CORS `https://exemple.fr`) : `TestClient(app).get(...)` sur `/docs`, `/redoc`, `/openapi.json` |
| Réussite | (a) : refus au démarrage avec message explicite pour chaque cas ; (b) : 404 sur les trois routes |
| Échec | Démarrage accepté avec une configuration dangereuse, ou documentation exposée |
| Gravité si échec | Élevée |
| Résultat / preuve | **RÉUSSI** — démarrage refusé avec message explicite pour clé par défaut, clé de 20 caractères, SQLite, CORS `*` ; configuration valide : `/docs`, `/redoc`, `/openapi.json` → 404, 404, 404. / `A-dynamiques.json` |

### A-11 — Limitation des tentatives de connexion

| | |
|---|---|
| Procédure | (a) 5 mots de passe faux pour un compte, puis le bon → 429 + `Retry-After` ; (b) 30 codes classe inconnus depuis une IP, puis un code valide → 429 ; (c) 35 connexions d'élèves valides depuis une même IP (réseau du lycée) → aucune refusée ; (d) redémarrer l'API pendant un blocage |
| Réussite | (a)(b) bloqués ; (c) aucun blocage ; (d) comportement documenté (compteurs en mémoire remis à zéro) |
| Échec | (a) ou (b) non bloqués, (c) bloqué |
| Gravité si échec | Élevée |
| Résultat / preuve | **RÉUSSI** — (a) 429, `Retry-After: 899` ; (b) 429 ; (c) 35 × 200 ; (d) compteurs en mémoire du processus, remis à zéro au redémarrage (comportement documenté). / `A-dynamiques.json` |

### A-12 — Journaux et données personnelles

| | |
|---|---|
| Procédure | Lancer API + Caddy (Docker), jouer un parcours complet (connexion élève, séance, réponses, connexion enseignant, export), puis rechercher dans les journaux (`docker compose logs`) : jetons (`Bearer`, `eyJ`, motif `\.[A-Za-z0-9_-]{20,}`), mots de passe, prénoms des élèves, réponses saisies. Relever ce qui est journalisé (IP, chemin, user-agent) et la rotation configurée. |
| Réussite | Aucun jeton, mot de passe, prénom ni réponse d'élève dans les journaux ; jetons jamais dans une URL ; rotation bornée (3 × 10 Mo par service) |
| Échec | Une de ces données présente dans un journal |
| Gravité si échec | Élevée (jeton ou mot de passe), Moyenne (prénom) |
| Résultat / preuve | **PARTIEL** — API seule (uvicorn réel, parcours complet) : le journal contient IP, méthode, chemin, statut ; 0 occurrence de jeton, `Bearer`, mot de passe (bon ou faux), prénom, réponse saisie, email. Journaux Caddy et rotation Docker **non vérifiés** (Docker arrêté). / `A-12-journal-uvicorn.log` |

### A-13 — Export, suppression, restauration

| | |
|---|---|
| Procédure | (a) Exporter Lina, comparer au contenu de la base (séances, réponses) ; (b) supprimer Lina, compter en SQL ses séances et réponses restantes ; (c) supprimer une classe ; (d) `python -m app.purge --simulation` puis réel, avec une date d'activité forcée ; (e) `pg_dump`, restauration dans une base vide isolée, comparaison des comptes par table et des clés étrangères |
| Réussite | (a) export complet et limité à l'élève ; (b)(c) 0 ligne restante ; (d) seuls les inactifs sont supprimés ; (e) comptes identiques, contraintes valides, durée notée ; présence des données supprimées dans les sauvegardes antérieures documentée dans la politique de rétention |
| Échec | Donnée résiduelle après suppression, export incomplet ou débordant, restauration incomplète |
| Gravité si échec | Élevée (Critique si l'export inclut les données d'un autre élève) |
| Résultat / preuve | **PARTIEL** — (a) export : 5 réponses exportées = 5 en base, seul prénom présent « Lina » ; (b) suppression de Lina : 0 séance, 0 réponse, 0 élève restant ; (c) suppression de classe : 0 élève, 0 séance restants ; (d) purge : seule l'élève inactive (500 j) est listée puis supprimée. **(e) sauvegarde/restauration PostgreSQL non exécutée** (Docker arrêté). / `A-dynamiques.json` |

### A-14 — En-têtes HTTP en production

| | |
|---|---|
| Procédure | Déploiement Docker local (`deploy/`) avec un domaine de test, puis `curl -sI https://<domaine>/` et `curl -sI https://<domaine>/api/health` |
| Réussite | Présents : `Strict-Transport-Security`, `Content-Security-Policy` (sans `unsafe-eval`), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy` ; absent : `Server` ; CORS limité au domaine |
| Échec | En-tête manquant ou CORS ouvert |
| Observation préalable | La CSP contient `style-src 'unsafe-inline'`, ajouté pour KaTeX : risque à examiner et à consigner. |
| Gravité si échec | Moyenne |
| Résultat / preuve | **NON EXÉCUTÉ** — nécessite le déploiement Docker (Docker Desktop arrêté). / — |

## Corrections et contre-vérification (28/10/2026)

Corrections faites sur la branche `audit/lot-a-protocole` (code non encore fusionné dans `main`).
Contre-vérification en conditions réelles (coût de hachage réel, base de démo neuve et temporaire) :
`preuves/A-correctifs-contre-verification.txt`.

| Contrôle | Correction | Non-régression | Contre-vérification |
|----------|-----------|----------------|---------------------|
| A-04 | `dompurify` 3.2.3 → **3.4.17**, `katex` 0.16.11 → **0.18.11** (version de plus de deux semaines, hors plage vulnérable, même branche 0.18) | Étape CI `npm audit --omit=dev --audit-level=high` ; 23 tests front (rendu, neutralisation de `<script>` et `onerror`) | **RÉUSSI** : 0 vulnérabilité dans les dépendances livrées |
| A-06 | scrypt **N = 2¹⁷**, r = 8, p = 1 ; `maxmem` relevé (128 Mo requis, limite Python par défaut 32 Mo) ; **re-hachage à la connexion** des empreintes plus faibles ; **au plus 2 hachages simultanés** | `tests/test_audit_lot_a.py` : paramètres, hachage réel à 128 Mo, empreinte démesurée refusée, re-hachage après succès seulement, concurrence bornée | **RÉUSSI** : empreinte neuve N = 2¹⁷ ; empreinte héritée N = 2¹⁴ re-hachée en N = 2¹⁷ à la connexion ; connexion mesurée à 4 050 ms |
| A-09 (e) | Le jeton enseignant embarque une empreinte courte (SHA-256, 16 caractères) du hachage du mot de passe, comparée à chaque requête ; jetons de l'ancien format refusés | `tests/test_audit_lot_a.py` : jeton antérieur au changement refusé, version falsifiée refusée, ancien format refusé, jetons élèves inchangés | **RÉUSSI** : 200 avant changement, 401 après, nouvelle connexion 200 |

Effet de bord identifié pendant la correction, et traité : avec 128 Mo par hachage, une rafale de connexions
parallèles (jusqu'à 40 threads uvicorn) aurait réclamé ≈ 5 Go ; borne de 2 calculs simultanés ajoutée
(ajoutée après la contre-vérification ci-dessus, couverte par `test_hachages_simultanes_bornes`).

Conséquences à connaître : déploiement de cette version = **déconnexion de tous les enseignants** (format de jeton
changé) ; chaque changement de mot de passe déconnecte l'enseignant de tous ses appareils ; le premier login de
chaque enseignant après mise à jour re-hache son mot de passe (et invalide ses jetons précédents).

Suites de tests au moment de la correction : moteur 77, API 136 puis 137 (tests de sécurité, enseignant,
production relancés après l'ajout de la borne : 45 réussis), front 23.

## Correction de A-07 (d) — décision D1 (29/10/2026)

**Décision D1** : option 1 retenue — chaque élève a un **code personnel** généré et distribué par l'enseignant.

| Élément | Mise en œuvre |
|---------|---------------|
| Connexion | Prénom + code classe + code personnel ; un seul message d'échec, quel que soit l'élément faux |
| Code | 6 caractères sans 0/O/1/I/L (31⁶ ≈ 887 millions) ; stocké **haché** (scrypt N = 2¹², quelques ms pour qu'une classe se connecte ensemble), affiché en clair une seule fois, à la génération |
| Essais | 5 codes faux par compte et par 15 min, puis blocage du compte seul (les camarades derrière la même IP ne sont pas bloqués) |
| Comptes | Créés par l'enseignant (liste de prénoms) ; plus de création automatique à la première connexion |
| Régénération | « Nouveau code » : l'ancien code et les sessions ouvertes avec lui cessent de fonctionner |
| Élèves existants | Sans code après la migration 0005 : ils ne peuvent pas se connecter tant que l'enseignant n'a pas cliqué « Générer les codes manquants » |

Non-régression : `api/tests/test_audit_lot_a.py` (classes `TestA07UsurpationEntreEleves` et `TestGestionDesCodes`).
Contre-vérification en conditions réelles : `preuves/A-07-contre-verification.txt` — **RÉUSSI** :

- prénom + code classe sans code personnel → 422 ; avec le code d'un autre élève → 401 ;
- prénom inconnu et classe inconnue → 401 avec le même message (l'existence des élèves n'est pas révélée) ;
- après 5 échecs sur le compte de Lina (dont l'essai avec le code de Yanis), le bon code → 429 ; Yanis, même
  classe et même IP → 200 ;
- empreintes en base au format scrypt, aucun code en clair ;
- code régénéré : ancienne session 401, ancien code 401, nouveau code 200 ;
- (a) inchangé : séance d'un autre élève → 404.

Suites de tests : API 150 (9 fichiers), front 26.

## Synthèse

Les gravités ci-dessous sont **proposées** par l'exécutant selon la grille commune ; elles doivent être validées
par le référent sécurité (aucun reclassement à la baisse sans justification écrite).

| Contrôle | Résultat | Gravité proposée | Responsable | Action corrective proposée | Non-régression |
|----------|----------|------------------|-------------|----------------------------|----------------|
| A-07 (d) | Échoué → **corrigé, contre-vérifié** (D1 : code personnel) | Critique | Produit + sécurité + DPO | Fait : code personnel par élève, haché, blocage par compte | `tests/test_audit_lot_a.py` |
| A-04 | Échoué → **corrigé, contre-vérifié** | Élevée | Développement | Fait : `dompurify` 3.4.17, `katex` 0.18.11. Reste : montée de `vite`/`vitest` (outils de développement, versions majeures) | Étape CI `npm audit --omit=dev --audit-level=high` |
| A-06 | Échoué → **corrigé, contre-vérifié** | Élevée | Développement | Fait : N = 2¹⁷, re-hachage à la connexion, 2 hachages simultanés au plus | `tests/test_audit_lot_a.py` |
| A-09 (e) | Échoué → **corrigé, contre-vérifié** | Élevée | Développement | Fait : empreinte du mot de passe dans le jeton enseignant | `tests/test_audit_lot_a.py` |
| A-02 | Non exécuté | — | Développement | Ajouter Semgrep à la CI GitHub (Linux) | Job CI |
| A-12 | Partiel | — | Développement | Vérifier journaux Caddy et rotation sur déploiement Docker | — |
| A-13 (e) | Partiel | — | Développement | Exécuter sauvegarde/restauration PostgreSQL (lien Lot G) | — |
| A-14 | Non exécuté | — | Développement | Exécuter sur déploiement Docker | — |
| A-01, A-03, A-05, A-08, A-10, A-11 | Réussis | — | — | A-08 : trancher D3 (archivage dans la banque commune) | Tests existants |

**Conclusion du lot à ce stade** : le constat Critique (A-07 d) et les trois constats Élevés (A-04, A-06, A-09 e)
sont corrigés et contre-vérifiés ; leur validation par le référent sécurité reste à faire avant la mise en service. Trois contrôles restent à
compléter avec Docker (A-12, A-13 e, A-14) et un sous Linux (A-02).
