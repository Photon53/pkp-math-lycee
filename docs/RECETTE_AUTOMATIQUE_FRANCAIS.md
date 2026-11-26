# Porte de recette automatique — Français

## Objectif
Le propriétaire ne doit intervenir que pour la validation finale. Ce dispositif est une **première porte CI** : il ne certifie **pas** le déploiement GCP ni la navigation réelle dans le navigateur.

## Déjà automatisé par ce changement
- Exécution explicite des tests API Français existants (`api/tests/test_francais.py`) sur base SQLite jetable, avec rapport JUnit téléchargeable.
- Exécution des tests front existants et compilation.
- Échec de la PR si un de ces jobs échoue, sous réserve de rendre les checks obligatoires dans la protection de branche.
- Aucun identifiant GCP, aucune base DEV et aucune donnée élève réelle utilisés.

## Prochaine étape obligatoire avant toute recette humaine
1. Vérifier que GitHub Actions exécute les jobs (les incidents antérieurs de facturation/CI peuvent empêcher leur démarrage).
2. Ajouter une suite Playwright sur environnement isolé avec comptes fictifs : admin, professeur habilité, validateur, élève et professeur non habilité.
3. Préparer des données de test déterministes : matière active, dossier importé, cours validé, classe pilote, élève inscrit. Aucun secret dans le dépôt.
4. Exécuter Playwright sur la version réellement déployée en DEV GCP, via un accès réseau sécurisé. Fournir SHA, URL d'environnement, captures, traces et résultats.
5. Tester les cas négatifs : domaine inactif, niveau non autorisé, refus de validation par l'auteur, corrigés non visibles par l'élève, version non validée non publiée.
6. Activer la protection de branche pour rendre les jobs obligatoires ; ne pas fusionner ni clore l'incident #217 sans preuve de recette sur DEV.

## Définition de « prêt pour validation humaine »
- Tous les checks obligatoires verts et preuves disponibles.
- Version GCP DEV identifiée par SHA et concordante avec la PR livrée.
- Parcours navigateur des quatre rôles réussi sur la même version et le même cours.
- Absence de fuite de corrigés et contrôle des habilitations démontrés.
- Une synthèse lisible des écarts et des risques résiduels est jointe au ticket #217.

## Limites
La suite API existante vérifie déjà de nombreuses règles, mais une réussite locale ne prouve ni la présence des données en DEV, ni le bon déploiement, ni l'ergonomie. Tant que les étapes Playwright/GCP ne sont pas implémentées et exécutées, le statut reste « automatisation partielle ».
