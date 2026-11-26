# Français 3e — installation et vérification du premier dossier en DEV

Issue #98 — Procédure rédigée par Claude, 14/11/2026. Refs #55, #24. DEV uniquement : rien en production, aucune
ouverture du Français aux élèves, aucune validation pédagogique par un agent.

## États à ne pas confondre

| État | Preuve attendue | Qui |
|---|---|---|
| **Préparé** | PR en brouillon vers `develop`, CI verte sur le SHA exact | Claude |
| **Fusionné** | PR fusionnée dans `develop` (SHA de fusion) | propriétaire |
| **Publié** | run « DEV - publication des versions » réussi, `releases/desired.json` = SHA de fusion | GitHub Actions |
| **Déployé en DEV** | `boussole-dev-sync --etat` : version active = SHA de fusion, révision Alembic `0037` | VM (timer ou `--appliquer`) |
| **Importé en DEV** | sortie de `python -m app.francais importer`, puis seconde exécution « 1 inchangé(s) » | propriétaire (commande ci-dessous) |
| **Vérifié en DEV** | contrôles des étapes 4 à 6 relevés et transmis dans #98 | propriétaire, puis relecture |

Un run GitHub réussi ne prouve pas le déploiement ; un domaine **actif** ne prouve pas qu'un dossier est importé ;
un dossier importé n'est **pas** ouvert aux élèves.

## 0. Ce que la fusion change en DEV

- Migration `0037` : deux tables vides (`dossier_francais`, `dossier_francais_version`), appliquée par
  `boussole-dev-sync` comme toute migration. Aucune donnée existante modifiée, aucun domaine activé.
- Nouvelles routes `/api/francais/...` (adultes habilités seulement) et page `/francais`.
- **Import automatique depuis #217** : `python -m app.contenu importer`, rejoué à chaque déploiement par
  `boussole-dev-sync` et au démarrage du `docker-compose` de production, importe aussi les dossiers de
  `contenu/francais/` (versions « soumis » seulement, idempotent). Rien n'est validé, ouvert aux élèves ni rendu
  public par l'import ; les domaines ne sont pas modifiés. L'empreinte de données suivie par la synchronisation ne
  couvre pas les tables françaises. Avant #217, l'import était manuel (§ 3), ce qui laissait une base neuve ou
  recréée sans aucun dossier : cause probable du symptôme de #212.
- Retour arrière : après `0037`, `boussole-dev-sync --version <sha antérieur>` sera refusé (pas de migration
  descendante, règle existante). Pour « retirer » le Français, désactiver le domaine (étape 6), sans supprimer.

## 1. Sur la VM : déploiement effectif

Depuis Cloud Shell ou un poste autorisé (IAP + OS Login), puis sur la VM :

```bash
gcloud compute ssh boussole-dev --project mer-boussole-dev --zone europe-west9-a --tunnel-through-iap
```

```bash
sudo boussole-dev-sync --etat
```

Attendu : version active = SHA de fusion de la PR ; révision `0037`. Si le timer n'est pas actif, suivre la
procédure existante (`docs/exploitation/pipeline-dev-pr3b-deploiement.md` : `--simulation`, relecture, puis
`--appliquer`) ; ne rien forcer.

## 2. Sur la VM : état initial, lecture seule

Raccourci Compose DEV, identique à celui de `boussole-dev-sync` (le fichier `.env` est lu par Compose, pas affiché) :

```bash
DC="sudo docker compose -p boussole --env-file /opt/boussole-dev/deploy/.env --env-file /var/lib/boussole-deploy/images-active.env -f /etc/boussole-dev-sync/docker-compose.dev.yml"
```

```bash
$DC exec -T db psql -U pkp -d pkp -c "SELECT version_num FROM alembic_version;" -c "SELECT code, actif, public FROM domaine_pedagogique ORDER BY ordre;" -c "SELECT count(*) AS chapitres_francais FROM chapitre WHERE domaine_code LIKE 'francais%';" -c "SELECT count(*) AS seances_francais FROM seance_anglais WHERE domaine_code LIKE 'francais%';" -c "SELECT count(*) AS dossiers FROM dossier_francais;" -c "SELECT domaine_code, role, niveau, count(*) FROM habilitation WHERE domaine_code LIKE 'francais%' GROUP BY 1, 2, 3;"
```

À transmettre dans #98 (aucune donnée personnelle dans ces requêtes). Attendu avant import : `0037`, Français
collège `public = f`, aucun chapitre ni séance français, `dossiers = 0`. Un chapitre français en base serait un
contenu inconnu du dépôt : le signaler avant d'aller plus loin.

## 3. Sur la VM : import, puis répétition

Depuis #217, cette étape est faite par le déploiement (§ 0) : la sortie de `boussole-dev-sync` se termine par la
ligne « Dossiers de français : … ». Les commandes ci-dessous restent utiles pour contrôler ou rejouer l'import.

```bash
$DC exec -T api python -m app.francais importer --simulation
```

```bash
$DC exec -T api python -m app.francais importer
```

```bash
$DC exec -T api python -m app.francais importer
```

Attendu : simulation « 1 créé(s) » sans écriture ; import « 1 créé(s) » ; seconde exécution « 0 créé(s), 0 nouvelle(s)
version(s), 1 inchangé(s) ». Contrôle :

```bash
$DC exec -T db psql -U pkp -d pkp -c "SELECT d.code, d.domaine_code, d.niveau, v.numero, v.statut, left(v.empreinte, 12) AS empreinte, v.auteur_id, v.validateur_id FROM dossier_francais d JOIN dossier_francais_version v ON v.dossier_id = d.id;" -c "SELECT code, actif, public FROM domaine_pedagogique WHERE code LIKE 'francais%';"
```

Attendu : une seule ligne `FR3-DNB27-01 | francais-college | 3e | 1 | soumis | … | (vide) | (vide)` ; domaines
français inchangés.

## 4. Dans l'application (tunnel IAP) : préparation sans ouverture

Ouvrir l'IHM DEV par le tunnel habituel (`scripts/tester-ihm-gcp.ps1`, exécuté par le propriétaire).

1. Administration → **Domaines** : Français collège **actif = oui, public = non**. Ne pas cocher « public » (l'API
   le refuse de toute façon : 409).
2. Administration → **Équipe** : habiliter un professeur **Français collège, 3e** ; désigner, pour la relecture,
   un **validateur Français collège (3e)** distinct de l'auteur. Comptes de test seulement, aucune donnée réelle
   d'élève.
3. Se connecter avec ce compte sur `/francais` : le dossier apparaît « Soumis à validation », « Non visible des
   élèves », rédaction Codex (#55), intégration Claude (#98).

### 4 bis. Validation et ouverture à une classe pilote (#212, même circuit que l'anglais)

1. Administration → Domaines → **Classes pilotes** : créer une classe pilote Français collège 3e pour le professeur
   habilité (motif obligatoire), puis y inscrire un élève de test.
2. Le validateur se connecte sur `/francais` → onglet **Validation** : relire la version soumise (partie élève,
   supports professeur, historique), puis valider, ou refuser avec motif. Il ne peut pas valider sa propre version.
3. Le professeur ouvre le dossier → onglet **Mes classes** → « Ouvrir à cette classe » (refusé sans version validée).
4. L'élève de la classe pilote → **Mon cours** → « Mes dossiers » : le dossier est lu dans sa version validée, sans
   corrigé. Un élève d'une autre classe de français, non pilote, ne le voit pas, et
   `GET /api/francais/eleve/dossiers/FR3-DNB27-01` lui répond 403.
5. Non-régression : un professeur d'anglais voit toujours ses séances et sa file de validation.

### 4 ter. Export PDF, statut « À corriger » et simulation (#217)

1. Dans un dossier : « PDF élève (sans corrigé) » et « PDF professeur (avec corrigés) »
   (`GET /api/francais/dossiers/{code}/pdf/eleve|professeur`). Tant qu'aucune version n'est validée, chaque page
   porte « NON VALIDÉ ». Professeur hors périmètre : 404 ; jeton élève ou d'administration : 401.
2. Un refus du validateur affiche « À corriger » et son motif ; la version validée déjà ouverte reste servie.
3. Simulation : espace professeur (ou Administration) → « Voir comme un élève » sur la classe pilote ; l'élève
   fictif lit le dossier ouvert ; il n'apparaît pas dans la liste des élèves de la classe.
4. Administrateur : Administration → « Boussole Français » ouvre l'espace avec sa session d'administration, sans
   nouvelle connexion. Il consulte, exporte, et valide ou refuse dans l'onglet « Validation » (V2-D15,
   décision du 23/11), jamais une version dont il est l'auteur.
5. Professeur ou validateur depuis `/enseignant` : lien « Boussole Français : dossiers et validation » en bas du menu.
6. Élève pilote : le dossier ouvert apparaît dans « Cours » et dans « Mon cours ». Il n'existe encore **aucun
   exercice interactif de français** (chapitres de #177) : « S'entraîner » reste vide et le dit.

### 4 quater. Activité des élèves au niveau de l'anglais (#217, migration `0049`)

Le déploiement importe la **version 2** de `FR3-DNB27-01` (quiz de six questions et phrases « Je sais »), en
« soumis » : la v1 validée reste servie jusqu'à la validation de la v2.

1. Validateur (ou administrateur qui n'en est pas l'auteur) : onglet « Validation », relire le quiz (réponses dans
   « Supports professeur »), valider la v2.
2. Élève pilote, « Cours » → le dossier : répondre au quiz. Par défaut, chaque réponse est corrigée aussitôt et la
   première compte ; le score s'affiche à la fin (« Terminer le quiz »). Remplir « Je fais le point ».
3. Professeur : onglet « Suivi des classes » → la classe pilote : meilleur score, premier essai, essais,
   auto-évaluation. Régler « À la fin du quiz » pour la classe ou pour le dossier ; l'élève ne voit alors la
   correction qu'après avoir répondu à tout.
4. Réponses rédigées : seulement si `PKP_REDACTION_ACTIVE=true` (RGPD-2, information préalable #183). L'élève
   enregistre un brouillon, remet ; le professeur lit la réponse remise et envoie un retour ; l'élève le lit et peut
   réécrire. L'administrateur n'a pas accès aux textes.
5. Administrateur : détail du dossier → onglet « Modifier » : enregistrer un brouillon (même format que le fichier
   d'import, contrôlé), le soumettre ; un **autre** validateur le valide. Le brouillon ne remplace pas la version
   diffusée.
6. Non-régression : un élève d'anglais fait un quiz ; un élève de maths fait une séance.

## 5. Vérifications à relever

| Contrôle | Attendu |
|---|---|
| Onglet « Aperçu élève » | Leçon (Je comprends, Je mémorise), texte de 20 lignes, texte de transfert de 5 lignes, Q1–Q8, T1–T3, Je vérifie ; **aucun corrigé** ; mention « retour du professeur » |
| Onglet « Supports professeur » | Déroulement, principes, 11 corrigés en regard des questions, grille, contrôle avant utilisation, retour de séance |
| Professeur de maths ou d'anglais seul sur `/francais` | « Espace réservé aux adultes habilités en français » |
| Espaces élève maths et anglais | aucun contenu français |
| Sur la VM : `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/api/francais/dossiers` | `401` (sans jeton) |
| Page d'accueil | Français collège « en préparation », pas « ouvert » |

Ne pas valider le dossier pour « tester » : la validation est la décision du validateur habilité, après la
relecture du protocole #24.

## 6. Retrait, si nécessaire

Retirer les habilitations françaises, puis désactiver Français collège dans Domaines : les routes répondent 403,
le dossier et son historique restent en base (aucune suppression).

## Ce qui reste à la charge du professeur

- Relire leçon, textes, Q1–Q8, T1–T3 et corrigés selon `docs/PROTOCOLE-RELECTURE-PEDAGOGIQUE.md`, sur la
  **version 1** importée (empreinte relevée à l'étape 3) ; confirmer difficultés proposées et durées.
- Valider ou refuser (motif) dans l'onglet « Validation », par un validateur habilité distinct de l'auteur ; puis
  ouvrir le dossier à sa classe pilote (onglet « Mes classes »).
- Corrections éventuelles : modifier le fichier JSON **et** les fiches Markdown par PR ; le nouvel import crée une
  version 2 à relire.
- Essais en séance sur support imprimé ou projeté, retours agrégés sans donnée nominative.
- Décider (V2-D12) du module élève : saisie des réponses, retour humain dans l'application, droits d'accès des
  élèves. Rien de cela n'existe aujourd'hui.

---

<sub>🤖 Procédure rédigée par **Claude** (Claude Code), issue #98, 14/11/2026.</sub>
