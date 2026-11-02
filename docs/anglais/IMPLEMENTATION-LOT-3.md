# PKP Anglais — intégration API, React et PDF (lot 3)

## Livré
- `GET /anglais/seances` : catalogue pilote 4e/3e (enseignant connecté).
- `GET /anglais/seances/{code}` : déroulé, parcours A/B/C et corrigés (enseignant connecté).
- `GET /anglais/seances/{code}/pdf/eleve` : PDF sans corrigés.
- `GET /anglais/seances/{code}/pdf/animateur` : PDF avec corrigés.
- Menu `/enseignant/anglais` dans l'espace professeur existant.
- Génération PDF côté serveur avec ReportLab.
- Tests unitaires du générateur PDF ajoutés.

## Installation / exécution
1. Installer le moteur Python (`pip install -e ./engine`), puis l'API (`pip install -e './api[dev]'`), depuis la racine du dépôt.
2. Installer les dépendances web (`cd web && npm install`).
3. Démarrer l'API et le front avec les commandes habituelles du projet.
4. Se connecter en tant qu'enseignant puis ouvrir `/enseignant/anglais`.

**Déploiement :** le répertoire `contenu/anglais/seances` doit être présent sur le serveur à l'emplacement du dépôt attendu par `api/app/routes/anglais.py`. Il n'est pas embarqué dans le paquet Python installé ; prévoir son packaging/configuration avant un déploiement indépendant du checkout Git.

## Sécurité et limites
- Routes protégées par `EnseignantCourant` ; les élèves ne peuvent pas accéder aux corrigés via ces endpoints.
- PDF servis en mémoire, sans URL publique ni fichier temporaire persistant.
- Séances pilotes en statut brouillon : aucune validation pédagogique humaine n'est encore enregistrée.
- Le contenu de la séance est limité à une liste explicite de codes pour éviter un accès arbitraire aux fichiers.
- Pas de base de données, de versionnement éditorial ni de workflow de validation dans ce lot.
- Tests ajoutés mais **non exécutés** ici ; vérifier `pytest`, `npm run build` et le rendu PDF avant fusion.
- À améliorer avant production : pack PDF enrichi (grille d'observation, erreurs fréquentes, pagination), contrôle du statut publié, gestion des rôles bénévoles et intégration CI.
