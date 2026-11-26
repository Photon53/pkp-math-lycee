# Ajouter une matière — parcours par rôle et circuit commun

Issue #215 — Cartographie et procédure rédigées par Claude, 21/11/2026. Refs #17, #110, #176, #212.

Ce document décrit ce que Maths, Anglais et Français partagent, où ils divergent, et comment déclarer une nouvelle
matière en réutilisant le circuit commun. Le Français sert de premier cas de recette (#212, #175, #176, #177). Les
documents de domaine font foi : `ARCHITECTURE.md`, `DECISIONS.md`, `RGPD.md`, `CONTENU.md`.

## 1. Mécanismes communs (à réutiliser tels quels)

| Mécanisme | Où | Règle |
|---|---|---|
| **Domaine pédagogique** | `permissions.DOMAINES`, table `domaine_pedagogique` | Une matière = un ou plusieurs domaines (`<matiere>-college`, `<matiere>-lycee`), chacun avec ses niveaux. `actif` : visible de l'équipe ; `public` : ouvert aux élèves (EX.1 à EX.4). Activation et visibilité : Administration → Domaines, journalisées |
| **Habilitations** | `permissions` (`Portee`, `appliquer`, `enseigne`, `peut_valider`, `refus_validation`) | Professeur ou validateur, par domaine et éventuellement par niveau. L'administrateur valide dans toutes les matières sans habilitation, jamais son propre contenu (V2-D15, remplace EX.9-bis pour lui) |
| **Permissions** | `permissions.exiger(permission, domaine)` | Table de correspondance dans le code (EX.7) |
| **Classes pilotes** | `permissions.refus_acces_classe`, `/admin/classes-pilotes` | Domaine actif mais fermé : seules les classes pilotes y accèdent, contrôle côté API route par route, révocation immédiate, rien supprimé (SEC-D6) |
| **Domaine fermé** | `permissions.refus_domaine_ferme` | Ni nouvelle séance, ni nouvelle classe ou groupe dans un domaine non public (EX.4) |
| **Circuit versionné** | `app/circuit_validation.py` | Version soumise → validée ou refusée (motif), jamais par l'auteur ; valider archive l'ancienne version validée ; refuser laisse en place la version diffusée. Utilisé par l'anglais et le français |
| **Journal** | `journal.noter` | Toute décision de validation, toute ouverture et toute action d'administration |
| **Corrigés** | ARCH-4 | Jamais transmis à l'élève avant sa réponse ; supports professeur réservés aux adultes |
| **Isolement des espaces** | `api/tests/test_isolement_acces.py` (`ESPACES`) | Chaque route protégée est rattachée à un espace ; un jeton d'un autre espace est refusé |

## 2. Parcours par rôle et par matière

| Rôle | Maths | Anglais | Français |
|---|---|---|---|
| **Administrateur** | Domaines, habilitations, classes, contenus (`/admin/chapitres`, `/admin/questions`, `/admin/lecons`), import | Domaines, habilitations (cases historiques + habilitations), séances (`/admin/anglais/*`) | Domaines, habilitations, classes pilotes ; état des contenus importés (`GET /francais/etat`, #212) ; consultation et export PDF des dossiers (`/francais/dossiers`, `/francais/dossiers/{code}/pdf/{eleve,professeur}`, #217) ; édition d'un dossier dans l'application (`/francais/dossiers/{code}/source|brouillon|soumettre`, #217) ; suivi de toutes les classes |
| **Professeur** | Classes (`/enseignants/classes`), banque, cours, ouverture des chapitres à la classe, suivi | Séances (`/anglais/seances`), version validée sinon « NON VALIDÉ », groupes (`/anglais/groupes`), progression | Classes (même espace que les maths), chapitres YAML (#177) ; dossiers : consultation de la version validée, ouverture à ses classes (`/francais/dossiers/{code}/classes`, #212) ; suivi de la classe : progression, mode de correction, réponses rédigées et retours (`/francais/classes/*`, #217) |
| **Validateur** | Page « Validation » (`/enseignants/validation/*`, #29) : question par question | File `/anglais/validation` : version soumise, valider ou refuser avec motif | File `/francais/validation` (#212) : mêmes règles que l'anglais ; chapitres YAML : même page que les maths, à confirmer (voir D2) |
| **Élève** | Séances, cours et « PKP Math » des chapitres ouverts à sa classe | Espace séparé (`/anglais/eleve/*`) : séances **validées** de son niveau, quiz corrigés | Mêmes routes que les maths pour les chapitres ; dossiers validés ouverts à sa classe (`/francais/eleve/dossiers`, #212) : quiz corrigé, auto-évaluation « Je sais », réponses rédigées (#217) ; rédactions (#179) |
| **Parent** | Progression et historique de ses enfants ; fiches PKP Math des niveaux de ses enfants (domaines publics) | Progression d'anglais de ses enfants | Progression de ses enfants ; **aucun contenu pilote** (SEC-D6, option b : énoncés et corrections retirés de l'historique si l'accès de la classe est refusé) |

## 3. Divergences et décisions à prendre

L'agent ne tranche pas ces points (AGENTS.md § 0 et § 8). Recommandation entre parenthèses.

| Id | Divergence | Effet | Recommandation |
|---|---|---|---|
| D1 | **Inscription des élèves** : classes (`classe`, `eleve`) en maths et en français ; groupes séparés (`groupe_anglais`, `eleve_anglais`, connexion propre) en anglais | Une nouvelle matière doit choisir l'un des deux modèles | Classes, comme le français : connexion, classes pilotes, parents et archivage déjà en place |
| D2 | **Deux circuits de validation** : par question (`statut_validation`, page de validation des maths) pour les chapitres YAML ; par version (`circuit_validation`) pour les séances d'anglais et les dossiers de français | Le français utilise les deux : chapitres interactifs (#177) et dossiers | Chapitres YAML pour les activités corrigées automatiquement ; contenu versionné pour les supports longs. Ouvrir la page de validation par question aux validateurs de français |
| D3 | **Diffusion** : l'anglais ouvre automatiquement toute séance validée aux groupes de son niveau ; le français exige l'ouverture par le professeur (dossiers et chapitres) | Comportements différents pour un professeur qui enseigne les deux | Ouverture explicite par le professeur (contrôle pédagogique, pilote) |
| D4 | **Questions non validées servies** : `PKP_SERVIR_QUESTIONS_NON_VALIDEES` (vrai pendant la relecture) sert aux élèves des questions « à valider » des chapitres ouverts, alors que l'anglais et les dossiers ne servent que des versions validées | Un chapitre de français ouvert à une classe pilote servirait des questions non relues | Ne pas ouvrir de chapitre avant sa validation, ou passer le réglage à faux, ou le rendre réglable par domaine (décision du propriétaire) |
| D5 | **Cases historiques** : `enseigne_maths`, `enseigne_anglais`, `referent_anglais` coexistent avec les habilitations ; le français n'a que des habilitations | Accès aux espaces décidé par des règles différentes (`enseignant_courant`, `enseignant_anglais`) | Nouvelle matière : habilitations seulement, comme le français |
| D6 | **Lien dossier ↔ chapitre** (#177) : un dossier de français est ouvert directement à une classe, sans chapitre | Le critère « lien entre le contenu relu et le chapitre pilote » de #212 n'est pas rempli | À trancher dans #212 |
| D7 | **Enfant de famille** : l'espace enfant affiche le français « bientôt disponible » | Pas d'accès par niveau au français, conforme à SEC-D6 tant que le domaine est fermé | À reprendre à l'ouverture publique |

## 4. Procédure d'ajout d'une matière

### 4.1 Paramétrage (une PR)

1. **Domaines** : ajouter les `Domaine(...)` dans `permissions.DOMAINES` (code `<matiere>-<cycle>`, libellé, niveaux,
   `actif=False`, `public=False`) et une migration qui insère les lignes de `domaine_pedagogique` (modèle :
   migration du français). `test_chaque_domaine_declare_existe_en_base_avec_ses_niveaux` le vérifie.
2. **Matière et niveaux** : `referentiel.domaine_de`, `refus_matiere`, et `ChapitreYaml.matiere` dans
   `app/contenu.py` si la matière a des chapitres YAML. `test_le_domaine_d_une_classe_est_un_domaine_declare`.
3. **Accès des professeurs** : ajouter la matière à `enseignant_courant` (espace des classes) ou créer sa
   dépendance, sur le modèle de `permissions.enseigne_francais` ; habilitations seulement (D5).
4. **Contenu** : choisir le format (D2). Chapitres YAML : `contenu/<matiere>/<niveau>/tronc-commun/`, registre des
   sources. Contenu versionné : un modèle à versions (`courante`, `versions`), les fonctions de
   `app/circuit_validation.py`, une file `/<matiere>/validation`, l'import idempotent (empreinte, jamais de version
   existante modifiée).
5. **Diffusion** : version validée seulement ; ouverture par le professeur à ses classes (D3) ; contrôle
   `permissions.refus_acces_classe` sur **chaque** route élève, y compris par adresse directe ; aucun corrigé (ARCH-4).
6. **Espaces** : classer les nouvelles routes dans `ESPACES` de `test_isolement_acces.py` ; navigation du front par
   rôle (administration, espace professeur, validation, espace élève).
7. **Documentation** : `ARCHITECTURE.md`, `DECISIONS.md` (décisions de la matière), `RGPD.md` si une donnée nouvelle
   apparaît, procédure d'import en DEV.

### 4.2 Points de contrôle par rôle (tests API et interface)

| Rôle | Autorisé | Refus attendus |
|---|---|---|
| Administrateur | État des contenus, consultation, domaines, habilitations, classes pilotes ; validation dans toutes les matières (V2-D15) | Sa propre version ou question (409 ou 422) |
| Professeur habilité | Contenus de son domaine et niveau, ouverture à **ses** classes d'une version validée | Autre niveau ou domaine (404), classe d'un autre professeur (404), version jamais validée (409) |
| Validateur | File de son domaine et niveau, décision motivée | Hors niveau (404), sa propre version (409), mot de passe provisoire (403) |
| Élève pilote | Version validée des contenus ouverts à sa classe, sans corrigé | Contenu non ouvert ou non validé (404) |
| Élève hors pilote, classe révoquée | — | 403 par adresse directe, liste vide |
| Parent, enfant de famille | Progression de ses enfants | Contenu d'un domaine fermé (401 ou 404 selon l'espace), enfant d'un autre parent (404) |

Le cas Français est couvert par `api/tests/test_francais.py` (`TestAcces`, `TestCircuitAligneSurLAnglais`),
`api/tests/test_classes_pilotes.py`, `api/tests/test_matieres_parcours.py`, `api/tests/test_parents.py` (`test_pas_d_acces_aux_autres_eleves`) et `web/src/tests/francais-dossiers.test.jsx`.

### 4.3 Recette en DEV

1. Déploiement vérifié (`boussole-dev-sync --etat` : version active = SHA de `develop`).
2. Import du contenu : chapitres YAML et dossiers de français sont importés au déploiement par
   `python -m app.contenu importer` (#217) ; contrôle dans `docs/francais/INTEGRATION-DEV.md` § 3.
3. Domaine actif, non public ; habilitations professeur et validateur, comptes distincts.
4. Classe pilote ; validation humaine ; ouverture par le professeur.
5. Vérification des cinq profils (§ 4.2) et non-régression Maths et Anglais, avec la version testée consignée dans
   l'issue.
