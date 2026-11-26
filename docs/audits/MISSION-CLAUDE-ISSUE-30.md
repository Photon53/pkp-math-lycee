# Mission Claude Code — Audit différentiel PKP → Boussole (issue #30)

## Contexte
- Source fonctionnelle : `Photon53/pkp-math-lycee`.
- Cible : `Photon53/boussole-maitrise-plus` (environnement DEV GCP en cours de préparation).
- Issue : https://github.com/Photon53/boussole-maitrise-plus/issues/30
- Cette branche sert **uniquement à l'audit**. Aucun transfert de code applicatif avant validation de la matrice d'écarts.

## Consignes impératives
1. Ne modifier ni `main`, ni la production, ni les ressources GCP, ni les bases de données.
2. Ne pas copier de secrets, comptes, données d'élèves ou informations personnelles.
3. Ne pas supposer que le pipeline GitHub Actions ou le DEV GCP fonctionnent : vérifier et fournir les preuves.
4. Comparer les deux dépôts sur des commits identifiés, sans écraser les évolutions spécifiques à Boussole.
5. Ne pas lancer de migrations de base ni de déploiement ; proposer un plan de sauvegarde et rollback.
6. Toute modification ultérieure doit passer par branche dédiée, tests, PR en brouillon et approbation humaine.

## Procédure d'audit à exécuter avec Claude Code
- Vérifier l'accès en lecture aux deux dépôts et relever leurs branches et SHAs de référence.
- Comparer architecture, frameworks, dépendances, fonctionnalités, rôles, APIs, migrations PostgreSQL, exercices, corrigés, validations pédagogiques, tests et workflows CI/CD.
- Vérifier la séparation DEV/production et les dépendances GCP, IAM, Terraform et GitHub Actions sans afficher les secrets.
- Produire une matrice avec colonnes : domaine, fonction, état PKP, état Boussole, différence, preuves (chemins/commits), criticité, dépendances, effort, stratégie de reprise, test de validation.
- Distinguer clairement : « présent uniquement dans PKP », « présent uniquement dans Boussole », « divergent », « identique », « non vérifié ».
- Vérifier les 42 tickets PKP reportés dans Boussole et identifier les doublons, les tickets déjà traités et ceux restant ouverts. Ne fermer aucun ticket automatiquement.
- Proposer des lots de migration par priorité avec critères de recette, risques et retour arrière.

## Livrables attendus
- `docs/audits/delta-pkp-boussole.md` : constats **factuels** avec références vérifiables.
- `docs/audits/migration-pkp-vers-boussole.md` : ordre de reprise, dépendances, tests, sauvegardes et rollback.
- Un commentaire sur l'issue #30 avec synthèse, blocages et lien vers les livrables.

## Critère de fin de cette première PR
La PR contient **des documents d'audit uniquement** et reste en brouillon pour revue. La parité fonctionnelle et la migration ne sont pas présumées achevées.
