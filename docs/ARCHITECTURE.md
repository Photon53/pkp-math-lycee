# Architecture — PKP Math Lycée

## Décisions validées

| Décision | Conséquence dans le code |
|----------|--------------------------|
| Moteur pur, sans dépendance web/DB | `engine/` n'importe ni FastAPI ni SQLAlchemy ; il reçoit et renvoie des dataclasses. |
| 8 tables normalisées (+ `lecon`) | `api/app/db/models.py`. La 9e table, `lecon`, porte les cours (migration 0004). |
| Élève = prénom + code classe + code personnel | Aucune donnée nominative complète, pas d'email. Le code personnel (généré par l'enseignant, stocké haché) empêche un camarade d'usurper le compte (audit A-07, décision D1). |
| Une question n'est jamais supprimée | Colonne `archivee` (booléen) au lieu d'un `DELETE` ; l'historique des réponses reste lisible. |
| Bonne réponse révélée après soumission | Le schéma `QuestionPublique` ne contient pas la solution ; seul `ResultatReponse` la renvoie. |
| 6 phases, une session de travail chacune | Voir le découpage ci-dessous. |

## Schéma de données (8 tables — `api/app/db/models.py`)

| Table          | Colonnes principales                                                        |
|----------------|-----------------------------------------------------------------------------|
| `enseignant`   | id, nom, email, mot_de_passe_hash                                           |
| `classe`       | id, code (unique, ex. `2NDE-B-7K3`), niveau (2nde/1re/Tle), parcours (spécialité), enseignant_id |
| `eleve`        | id, prenom, classe_id — unique (prenom, classe_id)                          |
| `chapitre`     | id, code, niveau, parcours, titre, ordre                                    |
| `competence`   | id, chapitre_id, code, libelle, ordre                                       |
| `question`     | id, code, competence_id, enonce, type, solution, difficulte, archivee, registre des sources (source, source_url, licence_source, adaptation), validation (statut, par, le), cree_le |
| `lecon`        | id, competence_id (unique), cours, resume (Markdown + LaTeX), maj_le        |
| `seance`       | id, eleve_id, debut, fin, question_courante_id                              |
| `reponse`      | id, seance_id, question_id, reponse_donnee, correcte, duree_s, repondu_le   |
| `classe_chapitre` | classe_id, chapitre_id — chapitres **proposés** par l'enseignant à la classe (migration 0007) |
| `seance_chapitre` | seance_id, chapitre_id — chapitres **choisis** par l'élève pour sa séance (migration 0007) |

La maîtrise par compétence est **calculée** par le moteur à partir de `reponse`
(pas de table dérivée tant que les performances ne l'exigent pas).

### Règles portées par la base (phase 3)

| Règle | Mécanisme |
|-------|-----------|
| Prénom unique dans une classe | `UNIQUE (prenom, classe_id)` |
| Difficulté de 1 à 5, niveaux et types fermés | Contraintes `CHECK` |
| Question jamais supprimée | Garde ORM (`SuppressionInterdite`) + clé étrangère `RESTRICT` depuis `reponse` |
| Purge RGPD | Supprimer une classe → élèves → séances → réponses en cascade (`ON DELETE CASCADE`) |
| Programme stable | `chapitre`, `competence`, `enseignant` en `RESTRICT` : rien ne disparaît par effet de bord |
| Mot de passe enseignant | Haché avec scrypt (`app/security.py`), jamais stocké en clair |

Le moteur ne voit jamais SQLAlchemy : `app/db/conversions.py` traduit les lignes en
objets du domaine (`question_vers_domaine`, `historique_eleve`).

Toute modification d'un modèle exige une nouvelle migration :
`alembic revision --autogenerate -m "..."`. Le test `test_migrations_a_jour_avec_les_modeles`
échoue sinon. Relire chaque migration générée : Alembic écrit par exemple
`server_default=sa.text('0')` pour un booléen, ce que PostgreSQL refuse (utiliser `sa.false()`).

## Règles du moteur (phase 2)

### `corriger(question, reponse_donnee) -> bool`
- **QCM** : libellé identique, sans tenir compte de la casse ni des espaces.
- **Numérique** : la valeur compte, pas l'écriture (`0,5` = `1/2` = `.5`, `1 000`, `3²`, `sqrt(2)`).
- **Expression** : équivalence vérifiée en évaluant les deux expressions en 8 points
  (`(x+1)(x+1)` = `x² + 2x + 1`). Un point où une seule des deux est définie rend la
  réponse fausse (`2ln(x)` ≠ `ln(x²)`). La forme (développée, factorisée) n'est pas contrôlée.
- Saisie élève illisible ou dangereuse → `False`, jamais d'exception. Aucun `eval` :
  analyse par `ast` avec liste blanche, saisie limitée à 200 caractères.
- Solution enseignant illisible → `ExpressionInvalide` (erreur de données à corriger).

### `calculer_maitrise(historique, competence_id) -> float`
- Les 10 dernières réponses de la compétence, la plus récente avec un poids de 1, chaque
  précédente ×0,9. Un a priori « 0 » de poids 1 freine les conclusions hâtives.
- Seuil de maîtrise : 0,8, atteint après 5 réussites d'affilée (4 ne suffisent pas).

### `choisir_prochaine_question(candidates, historique, espacement=20) -> Question | None`
1. Questions archivées écartées.
2. Une question réussie est « au repos » pendant `ESPACEMENT_REVISION` (20) réponses : elle ne revient pas
   tout de suite (ticket #26). Ensuite elle redevient disponible (révision espacée). Une question ratée reste
   disponible pour être retravaillée, jamais deux fois de suite s'il y a autre chose.
3. Compétence la moins maîtrisée parmi celles qui ont une question disponible.
4. Tout est au repos : repli sur une question à valeurs variables (autres nombres) ; sinon `None`. L'API
   répond alors 204 et `GET /seances/{id}/epuisement` donne le motif (`aucune-question` ou
   `toutes-reussies`) ; l'élève peut réviser (`GET /seances/{id}/question?revision=true`, `espacement=0`)
   ou terminer la séance.
5. Difficulté visée = 1 + arrondi(maîtrise × 4).
6. Ordre de préférence : pas la question qui vient d'être posée, pas déjà réussie,
   la moins posée, la difficulté la plus proche, le plus petit id. Résultat déterministe.

## API (phase 4)

Documentation interactive : `http://localhost:8000/docs`. Authentification par
`Authorization: Bearer <jeton>` ; jetons signés HMAC-SHA256 (`PKP_SECRET_KEY`), 12 h
pour un élève, 8 h pour un enseignant.

### Élève
| Route | Rôle |
|-------|------|
| `POST /eleves/connexion` | Prénom + code classe → jeton. Première connexion = création de l'élève. Prénom et code normalisés (`lina` = `Lina`). |
| `GET /eleves/moi`, `GET /eleves/moi/progression` | Profil, maîtrise par compétence des chapitres ouverts |
| `GET /eleves/moi/chapitres` | Chapitres ouverts par l'enseignant, avec leur nombre de questions servables |
| `POST /seances`, `POST /seances/{id}/fin` | Démarrer une séance sur les chapitres choisis (`{"chapitre_ids": [...]}` ; vide = tous les chapitres ouverts ; 409 si aucun n'est ouvert, 422 si un chapitre n'est pas proposé) / la terminer |
| `GET /seances/{id}/question` | Question en cours, ou nouvelle question choisie par le moteur (204 si aucune). Jamais de solution. |
| `POST /seances/{id}/reponses` | Réponse à la question en cours → correction, solution, nouvelle maîtrise |

Une séance a **une seule question en cours** (`seance.question_courante_id`, migration 0002) :
redemander renvoie la même (pas de « joker »), répondre à une autre question donne 409,
et la durée est mesurée par le serveur, pas déclarée par le navigateur.

### Enseignant
| Route | Rôle |
|-------|------|
| `POST /enseignants/connexion` | Email + mot de passe → jeton. Même message d'erreur et même durée que le compte existe ou non. |
| `GET/POST /enseignants/classes` | Ses classes ; création avec code généré (`2NDE-7KQ4M`, sans 0/O/1/I/L) |
| `GET/PUT /enseignants/classes/{id}/chapitres` | Programme de la classe (niveau + parcours) et chapitres ouverts ; `PUT {"chapitre_ids": [...]}` remplace la sélection (422 hors programme) |
| `GET /enseignants/classes/{id}/eleves` | Tableau de bord : réponses, taux de réussite, compétences maîtrisées |
| `GET /enseignants/eleves/{id}/progression` | Détail par compétence |
| `DELETE /enseignants/eleves/{id}` | Effacement RGPD (séances et réponses en cascade, jeton invalidé) |
| `GET /enseignants/competences`, `GET/POST /enseignants/questions` | Banque de questions commune ; solution vérifiée par le moteur à la création (422 sinon) |
| `POST /enseignants/questions/{id}/archiver` | Retire la question des tirages, sans la supprimer |

Cloisonnement : un enseignant ne voit que ses classes et leurs élèves ; sinon 404.

### Parents
Le professeur crée le compte d'un parent depuis la fiche de l'élève (bouton « Parents ») : e-mail et mot de passe
provisoire affiché une seule fois, à transmettre par l'établissement (PKP n'envoie aucun courriel). Le parent
remplace ce mot de passe à sa première connexion sur `/parent`. Un même compte peut suivre plusieurs enfants.

| Route | Rôle |
|-------|------|
| `GET/POST /enseignants/eleves/{id}/parents` | Comptes parents de l'élève ; création (ou rattachement d'un compte existant, sans nouveau mot de passe), 4 au plus |
| `DELETE /enseignants/eleves/{id}/parents/{parent_id}` | Le parent ne suit plus l'élève ; compte supprimé s'il ne suit plus personne |
| `POST /enseignants/parents/{id}/mot-de-passe` | Mot de passe oublié : nouveau mot de passe provisoire (professeur d'un de ses enfants) |
| `GET /admin/parents?q=`, `POST /admin/parents/{id}/reinitialiser` | Recherche par e-mail et réinitialisation par un administrateur (journalisée) |
| `POST /parents/connexion`, `POST /parents/mot-de-passe` | Connexion (jeton « parent », 12 h) et changement de mot de passe |
| `GET /parents/enfants` | Enfants suivis (et leurs inscriptions reliées), tant que le professeur est actif |
| `GET /parents/enfants/{id}` | Tableau de bord : synthèse, activité et temps de travail sur 14 jours, chapitres ouverts, progression par compétence |
| `GET /parents/enfants/{id}/historique` | Historique des réponses avec corrections |
| `PUT /parents/enfants/{id}/code` | Code personnel choisi par le parent (8 à 16 lettres et chiffres) ; vaut pour les inscriptions reliées, ferme les sessions de l'enfant |

### Identifiants des enfants (décision RGPD-1, #87)

Un enfant n'a **aucun nom de famille** : la colonne `enfant.nom` a été supprimée par la migration `0039`.

- **Nouveaux comptes** : `enfants.identifiant_libre` attribue `<Prénom><n>`, par exemple `Lina1`, `JeanPierre1` ou `Aegir1`.
  - La base est le prénom sans accents, sans espace, tiret ni apostrophe. Les lettres `æ ø ß ð þ œ` sont translittérées.
  - Le numéro vient de la table `compteur_identifiant` : une ligne par base en minuscules, tronquée à 35 caractères. L'incrément est atomique et la ligne reste verrouillée jusqu'à la fin de la transaction. Le compteur ne recule jamais : un numéro n'est pas réattribué, même après purge.
  - L'identifiant fait 40 caractères au plus : la base est tronquée à 40 − (nombre de chiffres du numéro).
  - Un identifiant déjà pris dans `enfant`, `eleve` ou `eleve_anglais` est sauté. Le nombre d'essais est borné.
- **Comparaison** sans casse ni accents (`security.cle_identifiant`). Des index uniques sur `lower(identifiant)` existent dans les trois tables.
- **Anciens identifiants** (`lina-k7m4`) : conservés et toujours acceptés. Le nouveau format, sans tiret, ne peut pas les rencontrer.
- **Homonymes** dans une classe ou un groupe : le second s'affiche avec son identifiant à la place du prénom (`Lina2`). La connexion prénom + code classe + code personnel (SEC-D1) accepte cette forme.
- **Saisie** : un champ `nom` est refusé par l'API (`extra="forbid"`) ; un classeur d'import qui remplit la colonne « Nom » est refusé ; un prénom sans aucune lettre est refusé.
- **Limitation des tentatives** : voir `docs/audit/rgpd-1-limitation-connexion.md`.

### Vue élève simulée (#184)
Un professeur ou un administrateur ouvre l'espace élève d'une classe avec un élève fictif (`eleve.simulation_par_id`,
migration `0045`) et un jeton élève ordinaire. Un filtre ORM global (`app/db/simulation.py`) retire ces élèves et
tout leur travail de toutes les autres lectures. Détails, limites et purge : [SIMULATION-ELEVE.md](SIMULATION-ELEVE.md).

### Accueil et demandes (#172, #171)
Les adultes qui ne sont pas encore inscrits : `contact_adulte` porte une ou plusieurs `demande_accueil` (migration
`0047`, qui reprend les demandes de `demande_collaboration`, migration `0046` de #171), chacune dans une file (famille, information, candidature, partenariat) avec statut et issue explicite.
Aucun lien vers un compte, un enfant ou une donnée pédagogique. Routes `/admin/accueil/*` (administrateurs seulement,
`app/routes/accueil.py`) ; formulaire public `/collaboration/*` (`app/routes/collaboration.py`) ; règles communes,
rattachement par e-mail identique et purge par file dans `app/accueil.py`. Détails RGPD : `docs/RGPD.md` § 9.

### Ajouter une matière (#215)
Parcours par rôle, mécanismes communs (domaines, habilitations, classes pilotes, circuit versionné
`app/circuit_validation.py`), divergences à arbitrer et procédure : [MATIERES.md](MATIERES.md).

### Français (préparation #98, validation et diffusion #212)
Tables `dossier_francais` et `dossier_francais_version` (migration 0037) : parties élève et professeur séparées,
empreinte du fichier source, circuit de validation des séances d'anglais. Contrat et accès :
[francais/FORMAT-IMPORT.md](francais/FORMAT-IMPORT.md) ; procédure DEV : [francais/INTEGRATION-DEV.md](francais/INTEGRATION-DEV.md).

| Route | Rôle |
|-------|------|
| `GET /francais/dossiers` | Dossiers lisibles par l'adulte (domaine actif, habilitation au domaine et au niveau, ou administrateur) |
| `GET /francais/dossiers/{code}/eleve` | Aperçu de la partie élève, sans corrigé ; version validée, sinon courante « NON VALIDÉ » (comme l'anglais) |
| `GET /francais/dossiers/{code}/professeur` | Corrigés, déroulement, grille d'observation ; même version affichée |
| `GET /francais/dossiers/{code}/historique` | Versions et décisions |
| `GET /francais/validation`, `GET /francais/validation/{code}` | File de validation (#212) : versions soumises que le validateur peut relire, en entier ; `est_auteur` signale les siennes |
| `POST /francais/validation/{code}/valider`, `/refuser` | Validateur habilité, distinct de l'auteur ; motif obligatoire pour refuser ; journalisé. Anciennes adresses `/francais/dossiers/{code}/valider`, `/refuser` conservées |
| `GET /francais/dossiers/{code}/classes` ; `PUT`, `DELETE …/classes/{classe_id}` | Le professeur ouvre ou retire le dossier à l'une de ses classes du même domaine et niveau (#212) ; ouverture refusée (409) sans version validée ; journalisé |
| `GET /francais/eleve/dossiers`, `GET /francais/eleve/dossiers/{code}` | Élève : partie élève de la **version validée** des dossiers ouverts à sa classe, si la classe a accès au domaine (SEC-D6) ; 403 sinon, 404 pour un dossier non ouvert ou jamais validé |

| `POST /francais/eleve/dossiers/{code}/quiz/{rang}`, `POST …/corriger` | Quiz (#217) : réponse enregistrée puis corrigée (mode « après chaque question »), ou correction de tout le quiz une fois chaque question répondue ; meilleur score, premier essai figé, essais |
| `PUT /francais/eleve/dossiers/{code}/auto-evaluation` | « Je sais » à quatre niveaux (#217) |
| `PUT /francais/eleve/dossiers/{code}/reponses/{question}`, `POST …/remise` | Réponses rédigées (#217, RGPD-2) ; 403 tant que `PKP_REDACTION_ACTIVE` est faux |
| `GET /francais/classes`, `GET …/{classe_id}/progression`, `GET`/`PUT …/correction`, `PUT …/dossiers/{code}/correction` | Suivi de la classe (#217) : progression par dossier, mode de correction (#110) |
| `GET /francais/classes/{classe_id}/reponses`, `PUT /francais/reponses/{id}/retour` | Réponses remises et retour, pour le seul professeur de la classe (RGPD-2) |
| `GET /francais/dossiers/{code}/source`, `PUT …/brouillon`, `POST …/soumettre` | Édition par l'administrateur (#217) : brouillon contrôlé par le contrat d'import, puis soumission |

Tables `ouverture_dossier_francais` (migration 0048), puis `progression_francais`, `reponse_quiz_francais`,
`reponse_redigee_francais`, `mode_correction_dossier_francais`, colonnes `dossier_francais_version.quiz` et
`classe.mode_correction` (migration 0049). Une révision soumise ou refusée ne remplace pas la version validée
diffusée ; une nouvelle validation la remplace dans les classes déjà ouvertes. Seul le quiz est corrigé par la
plateforme ; les questions rédigées relèvent du retour du professeur ; aucun corrigé servi à l'élève avant sa
réponse (ARCH-4).

### Chapitres proposés et choisis
L'enseignant **ouvre** des chapitres du programme de sa classe ; l'élève **choisit**, parmi eux, ceux qu'il travaille
dans une séance. Le cours, la progression et les tirages du moteur sont limités aux chapitres ouverts (et, en séance,
aux chapitres choisis). Une classe créée reçoit tout son programme ouvert ; un chapitre ajouté plus tard à `contenu/`
n'est **pas** ouvert automatiquement : l'enseignant le coche dans l'onglet Classes.

### Migrations SQLite
`migrations/env.py` migre **sans** `PRAGMA foreign_keys=ON` : le mode batch de SQLite
recrée les tables, et un `DROP TABLE` avec clés étrangères actives déclencherait les
`ON DELETE CASCADE` (constaté sur la 0002 : toutes les réponses effacées). Test de
non-régression : `test_migration_conserve_les_donnees`.

### Production (phase 6)
Clé secrète forte, PostgreSQL et CORS restreint exigés au démarrage (`PKP_ENVIRONNEMENT=production`),
limitation des tentatives de connexion (`app/limitation.py`), export et purge RGPD
(`app/purge.py`), comptes enseignant en ligne de commande (`app/admin.py`).
Voir [DEPLOIEMENT.md](DEPLOIEMENT.md) et [RGPD.md](RGPD.md).
Non fait : révocation individuelle des jetons (un jeton reste valide jusqu'à expiration,
sauf suppression de l'élève ou de l'enseignant).

## Front (phase 5)

React 18 + Vite, sans routeur ni bibliothèque d'état : `/` = espace élève, `/enseignant` = espace enseignant.

| Fichier | Rôle |
|---------|------|
| `src/api.js` | Seul point d'appel HTTP ; messages d'erreur lisibles (y compris validation FastAPI) |
| `src/stockage.js` | `sessionStorage` : fermer l'onglet déconnecte (postes partagés au lycée) |
| `src/eleve/Exercice.jsx` | Séance : question → réponse → correction + jauge de maîtrise → question suivante → bilan. QCM en boutons (options extraites de l'énoncé « A) … B) … »). Séance et compteur repris après rechargement. |
| `src/eleve/Progression.jsx` | Maîtrise par compétence, groupée par chapitre (réutilisée côté enseignant) |
| `src/enseignant/Classes.jsx` | Classes, création avec code, tableau de bord, détail par élève, effacement RGPD avec confirmation |
| `src/enseignant/Questions.jsx` | Ajout (refus du moteur affiché), filtre, archivage |

Accessibilité : libellés sur tous les champs, `role="alert"` pour les erreurs, jauges
`role="progressbar"`, focus placé sur le champ de réponse puis sur « Question suivante ».
Thème clair/sombre suivant le système.

Tests : `npm test` (Vitest + Testing Library, API simulée) couvre connexion, séance complète,
QCM, reprise, expiration du jeton, bilan, tableau de bord, confirmation RGPD, refus de solution.

## Découpage en 6 phases

| # | Phase | Livrable | Critère de fin |
|---|-------|----------|----------------|
| 1 | Squelette | Arborescence, outillage, tests de fumée | `pytest` vert dans `engine/` et `api/`, `npm run dev` affiche la page |
| 2 | Moteur | Correction des réponses, calcul de maîtrise, choix de la prochaine question | Tests unitaires couvrant chaque règle |
| 3 | Base de données | Modèles SQLAlchemy des 8 tables + migrations Alembic + données de démo | `alembic upgrade head` sur base vide |
| 4 | API | Routes élève (connexion par code, séance, réponse) et enseignant | Tests d'API, OpenAPI à jour |
| 5 | Front | Parcours élève complet + tableau de bord enseignant | Parcours testé de bout en bout |
| 6 | Mise en production | Auth enseignant durcie, RGPD (purge, export), déploiement | Checklist RGPD validée |
