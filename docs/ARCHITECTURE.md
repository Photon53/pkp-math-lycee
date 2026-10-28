# Architecture — PKP Math Lycée

## Décisions validées

| Décision | Conséquence dans le code |
|----------|--------------------------|
| Moteur pur, sans dépendance web/DB | `engine/` n'importe ni FastAPI ni SQLAlchemy ; il reçoit et renvoie des dataclasses. |
| 8 tables normalisées (+ `lecon`) | `api/app/db/models.py`. La 9e table, `lecon`, porte les cours (migration 0004). |
| Élève = prénom + code classe | Aucune donnée nominative complète, pas d'email, pas de mot de passe élève (RGPD mineurs). |
| Une question n'est jamais supprimée | Colonne `archivee` (booléen) au lieu d'un `DELETE` ; l'historique des réponses reste lisible. |
| Bonne réponse révélée après soumission | Le schéma `QuestionPublique` ne contient pas la solution ; seul `ResultatReponse` la renvoie. |
| 6 phases, une session de travail chacune | Voir le découpage ci-dessous. |

## Schéma de données (8 tables — `api/app/db/models.py`)

| Table          | Colonnes principales                                                        |
|----------------|-----------------------------------------------------------------------------|
| `enseignant`   | id, nom, email, mot_de_passe_hash                                           |
| `classe`       | id, code (unique, ex. `2NDE-B-7K3`), niveau (2nde/1re/Tle), enseignant_id   |
| `eleve`        | id, prenom, classe_id — unique (prenom, classe_id)                          |
| `chapitre`     | id, code, niveau, titre, ordre                                              |
| `competence`   | id, chapitre_id, code, libelle, ordre                                       |
| `question`     | id, code, competence_id, enonce, type, solution, difficulte, archivee, cree_le |
| `lecon`        | id, competence_id (unique), cours, resume (Markdown + LaTeX), maj_le        |
| `seance`       | id, eleve_id, debut, fin                                                    |
| `reponse`      | id, seance_id, question_id, reponse_donnee, correcte, duree_s, repondu_le   |

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

### `choisir_prochaine_question(candidates, historique) -> Question | None`
1. Questions archivées écartées ; plus rien → `None`.
2. Compétence la moins maîtrisée parmi les candidates.
3. Difficulté visée = 1 + arrondi(maîtrise × 4).
4. Ordre de préférence : pas la question qui vient d'être posée, pas déjà réussie,
   la moins posée, la difficulté la plus proche, le plus petit id. Résultat déterministe.

## API (phase 4)

Documentation interactive : `http://localhost:8000/docs`. Authentification par
`Authorization: Bearer <jeton>` ; jetons signés HMAC-SHA256 (`PKP_SECRET_KEY`), 12 h
pour un élève, 8 h pour un enseignant.

### Élève
| Route | Rôle |
|-------|------|
| `POST /eleves/connexion` | Prénom + code classe → jeton. Première connexion = création de l'élève. Prénom et code normalisés (`lina` = `Lina`). |
| `GET /eleves/moi`, `GET /eleves/moi/progression` | Profil, maîtrise par compétence du niveau |
| `POST /seances`, `POST /seances/{id}/fin` | Démarrer / terminer une séance |
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
| `GET /enseignants/classes/{id}/eleves` | Tableau de bord : réponses, taux de réussite, compétences maîtrisées |
| `GET /enseignants/eleves/{id}/progression` | Détail par compétence |
| `DELETE /enseignants/eleves/{id}` | Effacement RGPD (séances et réponses en cascade, jeton invalidé) |
| `GET /enseignants/competences`, `GET/POST /enseignants/questions` | Banque de questions commune ; solution vérifiée par le moteur à la création (422 sinon) |
| `POST /enseignants/questions/{id}/archiver` | Retire la question des tirages, sans la supprimer |

Cloisonnement : un enseignant ne voit que ses classes et leurs élèves ; sinon 404.

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
