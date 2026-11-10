# Prévalidation IA des exercices (ticket #48)

Premier contrôle automatique des exercices, en particulier ceux générés par IA. Il est **réservé aux administrateurs**
et **distinct de la validation pédagogique humaine** : il ne valide pas, ne publie pas et ne modifie jamais un exercice.
Deux IA peuvent partager la même erreur : un rapport « aucune anomalie détectée » ne dispense pas de la relecture.

## Qui voit quoi

| Qui | Accès |
|---|---|
| Administrateur (rôle `admin`, permission `prevalidation.ia`) | Page *Pédagogie › Prévalidation IA* : lancer, lire les rapports, bilan, jetons du service |
| Professeur, validateur pédagogique non administrateur, parent, élève | Rien : routes refusées (401/403), aucune donnée IA dans leurs vues |
| Compte de service IA (jeton `pkpia_…`) | Seulement `/service-ia/*` : lire les exercices **demandés**, déposer les rapports |

L'autorisation est vérifiée par l'API à chaque appel, y compris l'accès direct à un rapport (`GET /admin/prevalidation-ia/{id}`).
Aucune habilitation (professeur, validateur) ne donne `prevalidation.ia`.

## Déroulé

1. L'administrateur lance un contrôle sur des exercices choisis (numéros) ou un échantillon tiré au hasard (au plus
   50 par lot, deux par compétence tant que possible ; par défaut, les exercices dont l'auteur est une IA). Chaque
   exercice reçoit une demande `en-attente`, rattachée à un lot `L-AAAAMMJJ-XXXXXX`, avec la **version** examinée
   (empreinte SHA-256 de l'énoncé, du type, de la réponse, de la forme, de la difficulté, de la correction, des
   paramètres et des compétences) et, pour une question à valeurs variables, l'exemplaire tiré.
2. Le service IA :
   - `GET /service-ia/prevalidations?limite=10` : demandes en attente et à jour ;
   - `GET /service-ia/prevalidations/{id}/enonce` : énoncé, contexte (niveau, parcours, chapitre, compétence et
     compétences secondaires) et **attendus officiels du programme** (texte du BO) — sans réponse ni correction ;
   - il résout l'énoncé seul et note sa réponse ;
   - `GET /service-ia/prevalidations/{id}/corrige` (refusé tant que l'énoncé n'a pas été lu) : réponse attendue,
     étapes de correction, gabarit, méthodes et erreurs fréquentes du cours ;
   - il compare, vérifie par calcul ou outil symbolique quand c'est pertinent (SymPy…), puis
   - `POST /service-ia/prevalidations/{id}/rapport` (schéma ci-dessous).
3. L'administrateur lit le rapport. Les heures de lecture de l'énoncé puis du corrigé sont conservées.

Toute modification ultérieure de l'exercice rend le rapport **obsolète** (badge dans la liste, filtre `obsolete=true`).
Un rapport déposé pour une version dépassée est refusé (409) et la demande disparaît de la file du service.

## Rapport

```json
{
  "version": "<empreinte reçue avec l'énoncé>",
  "modele": "claude-opus-5-5", "version_modele": "2026-06",
  "resultat": "aucune-anomalie | a-revoir | erreur-detectee | incertain",
  "synthese": "…",
  "reponse_independante": "réponse trouvée sans le corrigé",
  "remarques_enonce": "…", "remarques_reponse": "…", "controle_programme": "niveau, compétences, attendus",
  "etapes": [{"numero": 1, "avis": "correcte | a-revoir | erronee | non-verifiee", "remarque": "…"}],
  "anomalies": [{"element": "enonce | reponse | etape | methode | niveau | competence | ambiguite | autre",
                 "etape": 2, "gravite": "erreur | a-revoir | mineure",
                 "description": "…", "justification": "…", "suggestion": "proposition de correction"}],
  "verifications": [{"nature": "calcul | symbolique | programme | autre", "description": "…", "outil": "sympy",
                     "issue": "confirme | ecart | impossible | incertain"}],
  "points_incertains": ["ce qui n'a pas pu être vérifié"]
}
```

Cohérence exigée (sinon 422) : « aucune anomalie » sans anomalie « erreur » ni « à revoir » ; « erreur détectée » avec au
moins une anomalie « erreur » ; « à revoir » avec au moins une anomalie ; « incertain » avec au moins un point incertain.
Champ inconnu refusé. Rapport limité à 60 Ko.

## Compte de service et sécurité

- **Compte dédié**, distinct des comptes humains : *Prévalidation IA › Compte de service › Créer un jeton*. Le jeton
  (`pkpia_<n>_<secret>`) n'est montré **qu'une fois** ; le serveur n'en garde qu'une empreinte HMAC (clé `PKP_SECRET_KEY`).
- Le jeton se range dans le **gestionnaire de secrets** du service IA (variable d'environnement injectée au
  lancement), jamais dans un navigateur, un dépôt ou un prompt.
- **Durée limitée** (90 jours au plus, `PKP_SERVICE_IA_DUREE_MAX_J`), **révocation** immédiate et **renouvellement**
  (nouveau jeton, ancien révoqué dans la même opération).
- Le jeton n'ouvre que `/service-ia/*` : les routes élèves, comptes, administration, validation et publication le
  refusent (format différent des jetons humains → 401). Il n'existe aucune route du service qui écrive ailleurs que
  dans les rapports.
- **Limites** : 60 requêtes par minute et par compte (`PKP_SERVICE_IA_REQUETES_PAR_MINUTE`), 20 jetons refusés par
  adresse et par quart d'heure, 20 demandes par lecture de file, 50 exercices par lot.
- **Journal** : chaque appel du service, accepté ou refusé, dans `acces_service_ia` (compte, action, demande, code
  HTTP, adresse), visible dans *Compte de service › Journal des accès* ; chaque action d'administrateur (demande,
  annulation, jetons, vérité humaine) dans le journal d'administration.
- En production, l'API n'est servie qu'en HTTPS (Caddy, voir `docs/DEPLOIEMENT.md`).

La mise en place de cette fonction ne crée aucun compte : c'est un administrateur qui crée le jeton, quand il le décide.

## Mesurer avant de généraliser

Première étape : un essai sur une dizaine d'exercices variés, dont certains contiennent des erreurs connues relevées
par des professeurs. Pour chaque rapport rendu, l'administrateur indique dans le détail si l'exercice était
**erroné** ou **correct**. L'onglet *Bilan de l'essai* (par lot) donne : erreurs connues, détectées, **non détectées**
(taux et numéros), avis incertains et fausses alertes. Ne généraliser que si le taux d'erreurs non détectées est jugé
acceptable.
