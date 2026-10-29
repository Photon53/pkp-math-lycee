# Audit PKP Math Lycée — méthode commune

Ce dossier rend l'audit **exécutable et vérifiable** : chaque contrôle est écrit avec sa procédure
et ses critères **avant** d'être exécuté, puis complété par le résultat observé et sa preuve.

> Tant qu'un contrôle n'a pas été exécuté et documenté ici, aucune conclusion n'est tirée sur le
> point qu'il couvre — y compris quand la documentation du projet affirme que c'est « fait ».

## Lots

| Lot | Objet | Protocole | État |
|-----|-------|-----------|------|
| A | Sécurité et protection des données | [lot-a-securite.md](lot-a-securite.md) | **Exécuté** le 28/10/2026 : 1 Critique et 3 Élevés corrigés et contre-vérifiés (validation à faire) ; 4 contrôles à compléter |
| B | Exactitude du moteur mathématique | — | Bloqué par la décision D2 (politique de correction) |
| C | Banque de questions et couverture du programme | — | À rédiger |
| E | Performance et robustesse | — | À rédiger (seuils à fixer avant mesure) |
| F | Accessibilité | — | À rédiger |
| G | Sauvegarde et restauration | — | À rédiger |
| H | Documentation vs comportement réel | — | À rédiger |

## Décisions préalables (à prendre par les personnes désignées, pas par l'outil)

| # | Décision | Pourquoi elle bloque | Qui décide |
|---|----------|----------------------|------------|
| D1 | **Tranchée le 29/10/2026 : code personnel par élève** (option 1). Question initiale : prénom + code classe suffisent-ils ? | Avec ce modèle, un camarade qui connaît le code de la classe peut se connecter sous le prénom d'un autre élève et voir sa progression (voir contrôle A-07). Le critère « aucun accès non autorisé » ne peut pas être atteint sans changer ce modèle ou accepter formellement ce risque. | Responsable produit + référent sécurité + DPO |
| D2 | Politique de correction : forme exigée (développée, factorisée, simplifiée, libre) par question | Le moteur ne vérifie aujourd'hui que l'équivalence ; le Lot B ne peut pas définir « correct » sans cette règle. | Référent pédagogique |
| D3 | Banque de questions commune : tout enseignant peut-il archiver n'importe quelle question ? | C'est le comportement actuel ; c'est un choix, pas un défaut, tant qu'il est assumé (contrôle A-08). | Responsable produit |
| D4 | Seuils de performance (Lot E) | À fixer d'après l'usage attendu, avant toute mesure. | Responsable produit |

## Format de chaque contrôle

| Champ | Contenu |
|-------|---------|
| Contrôle | Identifiant `X-NN` et objet |
| Procédure | Commande exacte ou étapes manuelles reproductibles |
| Réussite | Condition observable, fixée avant exécution |
| Échec | Condition observable, fixée avant exécution |
| Résultat observé | Rempli à l'exécution uniquement |
| Preuve | Fichier dans `preuves/` (sortie brute de l'outil, capture, journal) |
| Gravité | Selon la grille ci-dessous, en cas d'échec |
| Responsable | Personne qui valide le constat |
| Action corrective | Correction prévue, puis contrôle de non-régression |

Une alerte d'outil (scanner, linter) est **examinée** avant d'être classée : vulnérabilité avérée,
faux positif justifié, ou risque accepté par écrit. Chaque exception est consignée avec sa justification.

## Grille de gravité

| Gravité | Définition | Exemples dans PKP | Règle |
|---------|-----------|-------------------|-------|
| **Critique** | Accès non autorisé aux données d'un autre utilisateur, exécution de code, fuite de secret de production | Un élève lit les réponses d'un autre ; clé de signature des jetons dans le dépôt ; un enseignant accède aux classes d'un autre | Bloque toute mise en service. Correction immédiate, contrôle relancé, validation du référent sécurité. |
| **Élevée** | Affaiblissement significatif d'une protection, sans exploitation directe démontrée | Hachage des mots de passe sous les recommandations ; jeton non révoqué après changement de mot de passe ; dépendance avec CVE exploitable | Bloque la mise en service auprès d'élèves, sauf acceptation écrite du risque. |
| **Moyenne** | Défaut de robustesse ou de conformité avec contournement raisonnable | Journal conservant des IP plus longtemps que prévu ; en-tête de sécurité manquant | Corrigée avant généralisation. |
| **Faible** | Amélioration souhaitable, sans risque identifié | Message d'erreur peu clair ; dépendance obsolète sans vulnérabilité connue | Planifiée. |

**Escalade** : tout constat Critique est signalé au responsable produit et au référent sécurité le
jour même ; il n'est jamais reclassé à la baisse sans justification écrite des deux.

## Rôles

| Rôle | Personne | Responsabilité |
|------|----------|----------------|
| Développement | *à désigner* | Exécute les contrôles techniques, corrige |
| Référent sécurité | *à désigner* | Valide les constats du Lot A |
| Référent pédagogique | *à désigner* | Valide questions, solutions, règles de correction (Lots B, C) |
| Responsable produit | *à désigner* | Arbitre les décisions D1–D4 et les priorités |
| Responsable du pilote | *à désigner* | Protocole expérimental et analyse |
| DPO | *de l'établissement* | Protection des données des mineurs |

## Environnement d'audit

Tous les contrôles s'exécutent sur une **copie isolée** : clone du dépôt au commit audité, `.venv`
et `node_modules` dédiés, base SQLite créée par `python -m app.db.seed` (données synthétiques
uniquement), clé secrète de test, aucune donnée d'élève réel. Le commit audité est noté en tête de
chaque rapport, avec les versions des outils.
