# PKP Anglais — Plan d'intégration GitHub

**Dépôt :** `Photon53/pkp-math-lycee`  
**Branche de base vérifiée :** `retours-classes`  
**Branche de travail proposée :** `feature/pkp-anglais-v1.8-cadrage`  
**Objectif :** intégrer un domaine anglais isolé sans régression sur PKP Math.

## 1. État de référence technique observé

La branche `retours-classes` existe. Au moment de la vérification du 02/11/2026, son HEAD était :

```text
d689ab50099ab24351ac18d8871c8ca9665218d5
```

Dernier commit observé : « Test de recherche des cours : suivre le contenu au lieu d'un plafond fixe ».

Fichiers consultés :
- `README.md`
- `docs/ARCHITECTURE.md`
- `api/app/main.py`
- `api/app/db/models.py`

Constats vérifiés :
- `web/` : React + Vite ;
- `api/` : FastAPI ;
- `engine/` : moteur pédagogique Python pur, indépendant du web et de la base ;
- SQLAlchemy et Alembic côté API ;
- SQLite en développement et configuration PostgreSQL prévue ;
- routes API enregistrées explicitement dans `api/app/main.py` ;
- modèles SQLAlchemy regroupés dans `api/app/db/models.py` ;
- rôles, ressources et validations de contenu existent déjà dans le domaine mathématique.

**Important :** ce constat n'est pas un audit exhaustif du dépôt. Avant toute migration ou réutilisation de classe, inspecter les routes, schémas, migrations, permissions, tests et composants UI réellement présents sur la branche de travail.

## 2. Stratégie d'intégration

Intégrer PKP Anglais dans le même dépôt, mais garder des frontières explicites :

- ne pas mélanger les contenus anglais avec les banques de questions mathématiques ;
- ne pas détourner les modèles `Seance` individuels de Math pour représenter un atelier collectif ;
- ne pas changer le comportement des routes et interfaces Math ;
- ne pas dupliquer l'authentification, la gestion des comptes ou l'audit sans nécessité ;
- réutiliser les briques communes après vérification de leurs contrats ;
- ajouter des migrations Alembic réversibles et des tests dédiés ;
- isoler les interfaces et routes anglaises dans leur propre domaine.

## 3. Arborescence cible proposée

L'arborescence ci-dessous est une cible logique, pas une affirmation sur l'arborescence actuellement existante. Adapter les chemins après inspection complète.

```text
engine/
  pkp_engine/                 # moteur Math existant, inchangé
  pkp_anglais/                 # nouveau moteur pédagogique pur

api/app/
  routes/                      # routes Math existantes, inchangées
    anglais.py                 # routes anglais (ou package anglais/)
  anglais/
    models.py                  # modèles SQLAlchemy anglais
    schemas.py                 # schémas API
    services.py                # orchestration métier
    permissions.py             # autorisations domaine anglais
    pdf/                       # génération des packs
  db/
    models.py                  # intégrer imports/modèles selon convention du dépôt
    migrations/                # nouvelles migrations Alembic

web/src/
  math/                        # existant, sans régression
  anglais/
    pages/
    components/
    services/
    types/

contenu/
  anglais/
    referentiels/
      4e/
      3e/
    sequences/
      4e/
      3e/
    seances/
      4e/
      3e/

docs/anglais/
  CDC-V1.8.md
  PLAN-INTEGRATION-GITHUB.md
  MODELE-DONNEES.md
  PLAN-TESTS.md
  VALIDATION-PEDAGOGIQUE.md
```

Ne pas créer une seconde application React/FastAPI ni une deuxième authentification pour ce MVP.

## 4. Réutilisation / séparation

| Brique | Décision | Condition |
|---|---|---|
| Authentification adulte | Réutiliser | Vérifier activation de compte, reset, rôles et sessions |
| Utilisateurs / rôles | Réutiliser ou étendre | Permissions RBAC/relations testées côté API |
| Journal d'audit | Réutiliser | Couvrir validation, export, reset, parent et suppression |
| Configuration / base | Réutiliser | Même settings, sessions DB et conventions Alembic |
| Moteur Python pur | Garder le principe | Nouveau package anglais indépendant du package Math |
| Modèles Math | Ne pas réutiliser directement | Le modèle de séance Math est individuel |
| Groupes / classes | Évaluer la réutilisation | Sémantique classe scolaire vs groupe d'atelier à clarifier |
| Ressources / validation | Réutiliser si générique | Vérifier portée, statut, version, auteur et validateur |
| Génération PDF | Nouveau service partagé possible | Gabarits anglais séparés, test de séparation animateur/élève |
| Front React | Réutiliser l'application | Routes, layout et composants anglais isolés |

## 5. Modèle de domaine anglais à concevoir

Éviter d'implémenter le schéma final avant la cartographie des modèles existants. Le modèle conceptuel minimal est :

- `anglais_curriculum_version` : version du référentiel par classe et année ;
- `anglais_domain` / `anglais_skill` / `anglais_objective` : compétences et objectifs ;
- `anglais_sequence` : regroupement pédagogique ;
- `anglais_session_template` : séance modèle, fork et version ;
- `anglais_session_step` : déroulement minuté ;
- `anglais_activity_sheet` : fiches A/B/C et corrigés ;
- `anglais_assessment_grid` : critères et niveaux ;
- `anglais_group` : groupe animé par un bénévole ;
- `anglais_group_student` : inscription élève au groupe ;
- `anglais_group_plan_item` : progression ordonnée ;
- `anglais_workshop` : occurrence réelle d'une séance collective ;
- `anglais_observation` : observation individuelle liée à un objectif ;
- `anglais_validation_event` : validation/refus par élément si le journal existant ne suffit pas.

Toutes les tables doivent suivre les conventions réelles du dépôt (noms, types, timestamps, contraintes, clés étrangères, index et cascade). Ne pas introduire une table si une entité générique existante couvre déjà exactement le besoin.

Distinguer explicitement :
- le modèle de séance (template) ;
- l'atelier collectif réellement animé ;
- l'inscription d'un élève à un groupe ;
- l'observation/évaluation individuelle.

## 6. Phasage technique

### Phase 0 — Audit ciblé et contrats
1. Repartir du HEAD réel de `retours-classes`, pas d'un SHA mémorisé.
2. Lire les modèles, routes, schémas, dépendances, migrations et tests.
3. Cartographier les rôles et les permissions existantes.
4. Identifier les composants React réutilisables.
5. Confirmer les conventions de contenu YAML/JSON et les scripts de validation.
6. Produire le schéma de correspondance « existant / réutilisable / nouveau ».

**Sortie :** note d'audit et modèle de données validé avant migration.

### Phase 1 — Référentiel et contenu statique
1. Ajouter les référentiels 4e/3e en fichiers versionnés.
2. Ajouter les sources officielles, dates d'effet, licences et identifiants stables.
3. Ajouter les deux séances pilotes après adaptation à 90 minutes.
4. Créer des validateurs de structure et de cohérence.
5. Tester l'absence de contenus hors périmètre.

**Sortie :** contenus importables et contrôlés sans interface.

### Phase 2 — Moteur pédagogique pur
1. Créer un package `pkp_anglais` indépendant de FastAPI/SQLAlchemy.
2. Modéliser objectifs, séquences, séances, étapes et parcours A/B/C.
3. Calculer les durées et détecter un déroulé qui dépasse 90 minutes.
4. Vérifier qu'une fiche élève n'inclut jamais les corrigés.
5. Tester la validation progressive et les forks sans mutation de l'original.

**Sortie :** moteur testable par pytest, sans dépendance à l'API.

### Phase 3 — Persistance et API
1. Ajouter les modèles SQLAlchemy après revue du schéma.
2. Ajouter une migration Alembic ; relire le SQL et tester SQLite/PostgreSQL.
3. Ajouter les routes dans un module séparé et les enregistrer dans `main.py`.
4. Appliquer les permissions à chaque route et chaque objet.
5. Ajouter tests d'accès inter-groupes, rôle et statut de validation.
6. Réutiliser les services d'authentification et d'audit existants.

**Sortie :** API anglaise documentée et testée, Math inchangé.

### Phase 4 — Génération PDF
1. Concevoir deux gabarits séparés : animateur et élève.
2. Générer depuis une version figée des contenus.
3. Ajouter version, date, statut et identifiant sur chaque page.
4. Vérifier l'absence de corrigés et notes internes dans le pack élève.
5. Tester pagination, caractères accentués, tableaux et impression A4.
6. Journaliser la génération sans conserver inutilement le PDF ou des données nominatives.

**Sortie :** packs imprimables autosuffisants.

### Phase 5 — Interface bénévole et référent
1. Ajouter une entrée « Anglais » dans la navigation sans modifier les écrans Math.
2. Créer groupes et gérer les inscriptions.
3. Composer la progression du groupe.
4. Consulter, créer, forker et soumettre une séance.
5. Générer les packs.
6. Saisir les évaluations après séance.
7. Construire la file de validation référent.

**Sortie :** parcours de bout en bout utilisable par un bénévole.

### Phase 6 — Coordinateur, parents et durcissement
1. Ajouter les vues de suivi limitées aux groupes affectés.
2. Ajouter rattachement parent avec validation et révocation.
3. Ajouter demandes de suppression et traitement tracé.
4. Vérifier droits et tests de non-divulgation.
5. Finaliser rétention, purge et procédures RGPD avec le responsable de traitement.
6. Réaliser recette fonctionnelle et test pilote.

**Sortie :** MVP complet selon les options de périmètre confirmées.

## 7. Stratégie Git et pull requests

- Branche de base : `retours-classes`.
- Branche de cadrage : `feature/pkp-anglais-v1.8-cadrage`.
- Développement : branches courtes par phase, issues associées.
- Une PR par lot cohérent ; pas de gros commit mêlant contenu, migration, API et UI.
- La PR de cadrage ne doit contenir que la documentation.
- Les PR suivantes doivent être relues et testées avant merge.
- Ne jamais pousser directement sur `retours-classes` pendant le développement.
- Rebaser/mettre à jour depuis la branche de base avant recette.
- Garder la possibilité de désactiver l'entrée Anglais par configuration si la livraison est progressive.

## 8. Tests et non-régression obligatoires

Avant chaque PR :
- tests unitaires du moteur Math ;
- tests API Math ;
- tests front Math ;
- tests moteur anglais ;
- tests API anglais ;
- tests PDF animateur/élève ;
- test migrations à jour ;
- tests permissions et accès inter-groupes ;
- contrôle des secrets et données de test ;
- lint/type-check/build selon les scripts présents.

Scénarios de sécurité minimum :
- bénévole non activé ne peut pas se connecter/agir ;
- bénévole A ne lit ni ne modifie les groupes de B ;
- parent non rattaché n'accède à aucune donnée élève ;
- demande de rattachement en attente ne donne aucun droit ;
- code expiré ou déjà utilisé est refusé ;
- auteur ne peut pas s'auto-valider si la règle du dépôt l'interdit ;
- contenu soumis/refusé n'est pas partagé ;
- pack élève ne contient ni corrigés ni commentaires animateur ;
- suppression/révocation invalide les accès concernés.

## 9. Définition of Done par phase

Une phase est terminée seulement si :
- le code est dans une PR dédiée ;
- les tests nouveaux et non-régression passent ;
- les migrations sont vérifiées ;
- la documentation est mise à jour ;
- les permissions ont des tests négatifs ;
- aucun changement non voulu du domaine Math n'est constaté ;
- le contenu pédagogique est validé par une personne compétente avant publication.

## 10. Première séquence de travail

Ordre immédiat recommandé :
1. audit complet des routes, rôles, migrations, ressources et composants front ;
2. rédiger `MODELE-DONNEES.md` et `PLAN-TESTS.md` ;
3. faire valider le référentiel 4e/3e et les deux séances à 90 minutes ;
4. ajouter les contenus structurés ;
5. développer le moteur anglais ;
6. seulement ensuite, ajouter les tables et routes.

**Ne pas commencer par une migration de base de données** avant d'avoir déterminé ce qui est réellement réutilisable dans la branche cible.
