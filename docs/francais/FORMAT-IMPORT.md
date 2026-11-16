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

### Partie `eleve`

| Champ | Contenu |
|---|---|
| `presentation`, `objectifs` | lignes de texte |
| `lecon` | sections `{titre, markdown}` (ex. « 1. Je comprends », « 2. Je mémorise ») ; au moins une |
| `textes` | `{code, titre, lignes[], mention}` ; les lignes sont numérotées à l'affichage (1, 2, …), comme `[01]`… dans la fiche |
| `consignes_questions` | consignes générales des questions |
| `questions` | `{code, partie, texte, difficulte_proposee, consigne, coup_de_pouce, reponse}` |
| `je_verifie` | Markdown |

Pour chaque question : `partie` = `entrainement` ou `transfert` ; `texte` = code d'un texte du dossier ;
`difficulte_proposee` = 1 à 5 ou vide, **proposition pédagogique** à confirmer (ni difficulté du moteur, ni taux de
maîtrise) ; `reponse` = `{"mode": "retour_humain"}`, **seule valeur acceptée**.

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
(`actif`, `public`), ni les maths, ni l'anglais. Il n'est **pas** lancé au démarrage :
c'est une commande explicite.

## Accès et circuit de validation

| Qui | Accès |
|---|---|
| Élève (maths ou anglais), enfant, parent, anonyme | **aucun** : 401 sur toutes les routes `/francais` ; il n'existe pas de route élève |
| Professeur de maths ou d'anglais sans habilitation française | 403 |
| Professeur ou validateur habilité Français collège (tout le domaine ou le niveau du dossier) | lecture : aperçu élève, supports professeur, historique |
| Administrateur (rôle `admin`, connexion professeur) | lecture ; **pas** de validation sans habilitation de validateur (EX.9-bis) |
| Validateur habilité pour le domaine et le niveau, distinct de l'auteur | valider ou refuser (motif obligatoire) une version `soumis` ; décision journalisée |

Le domaine doit être **actif** (préparation par l'équipe). Un dossier hors habilitation ou d'un domaine inactif
répond 404. Les réponses portent `Cache-Control: private, no-store`.

**Valider ne publie rien aux élèves.** Un dossier validé n'est pas compté comme contenu ouvert : l'ouverture
publique de Français collège reste refusée (409) tant qu'aucun module élève n'existe.

## Ce que le format ne fait pas

- Aucune saisie ni conservation de réponse d'élève, aucune correction automatique, aucune note, aucun score,
  aucun taux de maîtrise. La grille d'observation reste un support professeur, sans valeur importable.
- Pas de module élève : le support de saisie et le retour humain dans l'application restent à cadrer (V2-D12).

---

<sub>🤖 Contrat rédigé par **Claude** (Claude Code), issue #98, 14/11/2026. Contenu pédagogique : **Codex**, #55, PR #94.</sub>
