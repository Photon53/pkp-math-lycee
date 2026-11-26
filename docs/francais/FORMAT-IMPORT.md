# Français — contrat du fichier d'import des dossiers

Issue #98 — Contrat retenu pour l'intégration en DEV du premier dossier Français 3e (Claude), 14/11/2026.
Refs #55 (audit Français), #24 (protocole de relecture). Proposition minimale et révisable : elle ne tranche pas
**V2-D12** (cadrage du français : types d'exercices, textes, auteurs), toujours en attente dans `docs/DECISIONS.md`.

## Pourquoi un format propre au français

La banque de questions des maths (`contenu/**/*.yaml`, table `question`) n'accepte que des QCM, valeurs
numériques et expressions **corrigées automatiquement** par le moteur, avec une `solution` de 200 caractères.
Les questions du premier dossier sont des **réponses rédigées et interprétatives** : les y ranger obligerait à
inventer une solution « exacte » et une correction par mots-clés, ce qui est exclu. Le format anglais (séance
chronométrée, quiz QCM, cahier) ne convient pas non plus. Le dossier de français reprend donc **le circuit des
séances d'anglais** (versions, statuts, validateur distinct de l'auteur) avec un contenu propre.

## Emplacement

`contenu/francais/<niveau>/<fichier>.json` — un fichier par dossier, UTF-8. Le fichier est rangé dans le dossier de
son niveau (`3e/` pour un dossier de troisième). Extension `.json` : `python -m app.contenu`, qui lit les
`*.yaml` des maths, ne le voit pas.

## Structure

Tous les objets refusent les champs inconnus : un `solution`, `bareme`, `points`, `note` ou `mots_cles` fait
échouer le contrôle.

| Champ | Contenu | Règle |
|---|---|---|
| `format` | `"boussole-francais-dossier/1"` | obligatoire, valeur exacte |
| `code` | identifiant stable, ex. `FR3-DNB27-01` | `FR` + 2 à 28 caractères `A-Z 0-9 -` ; ne change jamais |
| `domaine`, `niveau` | `francais-college` + `6e`…`3e`, ou `francais-lycee` + `2nde`/`1re` | niveau du domaine ; ne changent plus après le premier import |
| `titre`, `cible` | titre ; cible (ex. « DNB général, session 2027 ») | |
| `competences_locales` | codes documentaires de la matrice (`FR3-L01`…) | identifiants locaux, ni officiels ni importés comme compétences |
| `attribution` | `redaction`, `redaction_issue`, `redaction_pr`, `redaction_le`, `integration`, `integration_issue`, `sources_markdown` | attribution d'origine conservée (ici Codex, #55, PR #94) ; intégration (ici Claude, #98) |
| `registre` | `source`, `source_url`, `licence_source`, `adaptation` (`originale`, `adaptee`, `reprise`), `mention` | registre des sources, comme `docs/CONTENU.md` |
| `eleve` | partie destinée aux élèves (ci-dessous) | **aucun corrigé** |
| `professeur` | supports professeur (ci-dessous) | jamais transmis côté élève |
| `quiz` | facultatif (#217) : `[{question, texte, choix[], reponse, explication}]`, 30 questions au plus | QCM corrigé par la plateforme ; `reponse` = rang du bon choix (à partir de 0), 2 à 6 choix distincts ; `texte` facultatif = code d'un texte du dossier. Bonne réponse et explication jamais transmises à l'élève avant sa réponse (ARCH-4) |

### Partie `eleve`

| Champ | Contenu |
|---|---|
| `presentation`, `objectifs` | lignes de texte |
| `lecon` | sections `{titre, markdown}` (ex. « 1. Je comprends », « 2. Je mémorise ») ; au moins une |
| `textes` | `{code, titre, lignes[], mention}` ; les lignes sont numérotées à l'affichage (1, 2, …), comme `[01]`… dans la fiche |
| `consignes_questions` | consignes générales des questions |
| `questions` | `{code, partie, texte, difficulte_proposee, consigne, coup_de_pouce, reponse}` |
| `je_verifie` | Markdown |
| `je_sais` | facultatif (#217) : phrases « Je sais… » (10 au plus) pour l'auto-évaluation à quatre niveaux, comme le « I can » de l'anglais |

Pour chaque question : `partie` = `entrainement` ou `transfert` ; `texte` = code d'un texte du dossier ;
`difficulte_proposee` = 1 à 5 ou vide, **proposition pédagogique** à confirmer (ni difficulté du moteur, ni taux de
maîtrise) ; `reponse` = `{"mode": "retour_humain"}`, **seule valeur acceptée** : ces questions ne sont jamais
corrigées par la plateforme. Depuis #217, l'élève peut y répondre en ligne et son professeur lui fait un retour.

**Empreinte** : un `quiz` vide et une liste `je_sais` vide n'entrent pas dans l'empreinte ; un dossier importé avant
#217 ne crée donc aucune nouvelle version. Ajouter un quiz crée une nouvelle version « soumis », à valider.

### Partie `professeur`

`presentation`, `deroulement` (`titre`, `etapes[{duree, activite, observation}]`, `adaptations`),
`principes_correction`, `corriges[{question, intitule, paragraphes[]}]`, `grille` (`titre`,
`criteres[{critere, questions, indice}]`, `consignes`), `controle_avant_utilisation`, `remarques`, `retour_seance`.

## Contrôles à la lecture (`python -m app.francais verifier`)

- domaine français et niveau du domaine ; fichier rangé dans le dossier de son niveau ;
- codes de textes, de questions et de dossiers uniques ; chaque question cite un texte existant ;
- **exactement un corrigé par question**, aucun corrigé sans question ;
- **aucun paragraphe de corrigé (40 caractères ou plus) recopié dans la partie élève** ;
- mode de réponse `retour_humain` uniquement ; champs inconnus refusés.

## Import idempotent (`python -m app.francais importer [--simulation]`)

L'empreinte d'une version est le SHA-256 du contenu validé, normalisé (clés triées, sans mise en forme) : réindenter
le fichier ne crée pas de version.

| Situation | Effet |
|---|---|
| Dossier absent | Créé, version 1, statut `soumis` (à relire), auteur vide (= import du dépôt) |
| Empreinte déjà connue pour ce dossier (quelle que soit la version) | **Rien** : une seconde exécution ne crée aucun doublon |
| Fichier modifié | Nouvelle version `soumis` ; les versions existantes ne sont jamais modifiées, une version validée reste validée |
| Domaine ou niveau changé pour un code existant | Refusé |

Garanties en base : `UNIQUE (code)` sur `dossier_francais`, `UNIQUE (dossier_id, numero)` et
`UNIQUE (dossier_id, empreinte)` sur `dossier_francais_version`. L'import ne modifie ni les domaines
(`actif`, `public`), ni les maths, ni l'anglais. Il n'est **pas** lancé au démarrage ni par `boussole-dev-sync` :
c'est une commande explicite.

## Accès et circuit de validation

| Qui | Accès |
|---|---|
| Enfant, parent, élève d'anglais, anonyme | **aucun** : 401 sur toutes les routes `/francais` |
| Élève d'une classe de français | `/francais/eleve/*` seulement : partie élève de la **version validée** des dossiers que son professeur a ouverts à sa classe, si la classe a accès au domaine (classe pilote, SEC-D6) ; quiz corrigé, auto-évaluation, réponses rédigées (#217) ; 401 sur toutes les autres routes `/francais` |
| Professeur de maths ou d'anglais sans habilitation française | 403 |
| Professeur ou validateur habilité Français collège (tout le domaine ou le niveau du dossier) | lecture : aperçu élève, supports professeur, historique |
| Administrateur (session professeur ou d'administration) | lecture ; validation et refus (V2-D15), jamais de sa propre version ; **édition** d'un dossier dans l'application (brouillon puis soumission, #217) ; suivi de toutes les classes de français, sans accès aux textes rédigés des élèves (RGPD-2) |
| Validateur habilité pour le domaine et le niveau, distinct de l'auteur | file `/francais/validation` : relire, valider ou refuser (motif obligatoire) une version `soumis` ; décision journalisée |
| Professeur habilité au domaine et au niveau, pour **ses** classes actives de ce niveau | ouvrir ou retirer un dossier dont une version est validée ; journalisé. Suivi de la classe (#217) : progression par dossier, mode de correction du quiz, lecture des réponses rédigées remises et retour |

Le domaine doit être **actif** (préparation par l'équipe). Un dossier hors habilitation ou d'un domaine inactif
répond 404. Les réponses portent `Cache-Control: private, no-store`.

**Même circuit que l'anglais (#212).** Valider rend une version diffusable ; elle n'est lue que dans les classes
auxquelles le professeur ouvre le dossier. Une révision soumise ou refusée ne remplace pas la version validée déjà
diffusée. Un dossier validé n'est pas compté comme contenu ouvert au public : l'ouverture publique de Français
collège reste refusée (409) ; pendant le pilote, seules les classes pilotes y accèdent (SEC-D6).

## Ce que le format ne fait pas

- Aucune correction automatique des questions rédigées, aucune note, aucun taux de maîtrise. Seul le quiz donne un
  score (meilleur score, score du premier essai, nombre d'essais), comme en anglais. La grille d'observation reste un
  support professeur, sans valeur importable.
- Réponses rédigées en ligne (#217) : mêmes règles que les rédactions (RGPD-2, `docs/RGPD.md` § 8), fermées tant que
  `PKP_REDACTION_ACTIVE` est faux.

---

<sub>🤖 Contrat rédigé par **Claude** (Claude Code), issue #98, 14/11/2026. Contenu pédagogique : **Codex**, #55, PR #94.</sub>
