# PKP Anglais — lot 1 : moteur de séances

Branche : `PKP-Anglais`. Périmètre : 4e/3e, 90 minutes, parcours A/B/C.

## Livré
- Package Python pur `pkp_anglais`, découvert par la configuration setuptools existante (`engine/src`).
- Modèles immuables `Seance`, `Etape`, `Fiche`.
- Validation des durées, du niveau, des consignes et de la présence des trois parcours.
- Packs structurés distincts : élève sans corrigés/consignes internes, animateur avec corrigés.
- Tests pytest dédiés.

## À développer
- Référentiels 4e/3e alignés sur les programmes officiels applicables.
- Contenus pédagogiques réels et validation humaine.
- Sérialisation/versionnement, persistance SQLAlchemy, migrations Alembic, routes FastAPI et permissions.
- PDF imprimables, interface bénévole, groupes, évaluations et suivi.
- Tests d'intégration et exécution de toute la suite CI.

Ce lot ne modifie pas les routes ni les modèles mathématiques. Les fonctions `generer_pack_*` renvoient des dictionnaires et ne produisent pas encore de PDF.
