# Contenu pédagogique — guide de rédaction

Tout le contenu (chapitres, cours, résumés, questions) vit dans `contenu/`, un fichier YAML
par chapitre. Il est **versionné**, **relu** (pull request sur GitHub) et **vérifié
automatiquement** avant d'arriver en base.

## Organisation de la banque

La banque s'ordonne ainsi : **niveau (classe) → parcours (spécialité) → chapitre (cours) →
compétence → difficulté (1 à 5)**. Le rangement des fichiers suit exactement cet ordre :

```
contenu/
  2nde/tronc-commun/01-nombres-et-calculs.yaml … 12-probabilites-et-echantillonnage.yaml   (12 chapitres)
  1re/specialite/01-second-degre.yaml … 10-variables-aleatoires.yaml                        (10 chapitres)
  1re/scientifique/01-evolutions-et-pourcentages.yaml … 06-variation-exponentielle.yaml     (6 chapitres)
  1re/technologique/01-automatismes.yaml … 07-variables-aleatoires.yaml                      (7 chapitres)
  tle/specialite/01-combinatoire.yaml … 15-loi-des-grands-nombres.yaml                      (15 chapitres)
  tle/complementaires/01-suites-modeles-discrets.yaml … 09-statistique-deux-variables.yaml  (9 chapitres)
  tle/expertes/01-complexes-forme-algebrique.yaml … 08-graphes-markov.yaml                  (8 chapitres)
  tle/technologique/01-proportions-indices.yaml … 08-loi-binomiale.yaml                      (8 chapitres)
```

| Niveau | Parcours permis |
|--------|-----------------|
| `2nde` | `tronc-commun` |
| `1re`  | `specialite`, `scientifique` (maths de l'enseignement scientifique), `technologique` |
| `Tle`  | `specialite`, `complementaires`, `expertes`, `technologique` |

La voie technologique a un seul programme de mathématiques commun à toutes les séries (STMG, STI2D,
STL, ST2S, STD2A, STHR, S2TMD) ; les activités géométriques propres à la STD2A ne sont pas couvertes.
Les maths expertes suivent le programme de 2019 : le BO n° 14 du 2 avril 2026 ne les a pas modifiées.

Chaque **classe** a un parcours : ses élèves ne voient que les cours et questions de leur niveau
**et** de leur parcours. Une classe de maths expertes ne reçoit pas les questions de spécialité.

Dans ce programme, l'enseignant **ouvre** les chapitres qu'il veut proposer (onglet Classes) et l'élève
**choisit** ceux qu'il travaille à chaque séance. Un nouveau fichier ajouté ici n'est pas ouvert
automatiquement aux classes existantes.

L'état de la banque (matrice de couverture, trous, validation, registre des sources) est dans
[CONTENU-INVENTAIRE.md](CONTENU-INVENTAIRE.md), **généré** par la commande `inventaire`.

## Cycle de travail

1. Écrire ou modifier un fichier YAML, rangé dans `contenu/<niveau>/<parcours>/`.
2. Vérifier : tâche VS Code **Contenu : vérifier les fichiers YAML**
   (ou `python -m app.contenu verifier` depuis `api/`).
3. Régénérer l'inventaire : `python -m app.contenu inventaire` (depuis `api/`). Un test échoue
   si l'inventaire commité ne correspond plus au contenu.
4. Importer dans la base locale : tâche **Contenu : importer dans la base de démo**, puis
   regarder le résultat dans l'onglet **Cours** et en séance d'exercices (classe `TLE-C-DEMO`, etc.).
5. Commit, pull request : la CI GitHub revérifie tout le contenu et lance les tests.
6. Relecture par un enseignant, puis passage des questions relues à `validation: {statut: validee, …}`.
7. En production, l'import est automatique au démarrage de l'API.

L'import est **idempotent** : le relancer ne change rien. Une question retirée d'un fichier est
**archivée** (jamais supprimée : l'historique des élèves reste lisible). Les questions créées depuis
l'interface enseignant ne sont pas touchées.

## Format d'un fichier

```yaml
chapitre:
  code: TLE-LN                 # identifiant stable, MAJUSCULES-ET-TIRETS, ne jamais le changer
  niveau: Tle                  # 2nde | 1re | Tle
  parcours: specialite         # tronc-commun | specialite | scientifique | complementaires | expertes | technologique
  ordre: 9                     # position dans l'année (unique par niveau et parcours)
  titre: Fonction logarithme népérien

competences:
  - code: TLE-LN-DEF           # identifiant stable de la compétence
    libelle: Définir la fonction logarithme népérien
    resume: |                  # l'essentiel, affiché en encadré (Markdown + LaTeX)
      - $\ln(1) = 0$ et $\ln(e) = 1$
    cours: |                   # le cours complet (Markdown + LaTeX)
      ## Définition
      Pour $x > 0$ : $$y = \ln(x) \iff e^y = x$$
    questions:
      - code: TLE-LN-DEF-01    # commence obligatoirement par le code de la compétence
        difficulte: 1          # 1 (application directe) à 5 (exigeant)
        type: numerique        # qcm | numerique | expression
        enonce: 'Calculer $\ln(1)$.'
        solution: 0
```

`cours` et `resume` sont facultatifs mais vont ensemble. Une compétence sans cours apparaît
« cours à venir » côté élève.

### Registre des sources et validation pédagogique

Chaque question peut porter, en plus des champs ci-dessus :

```yaml
      - code: 1RE-SUI-TERME-02
        # … champs habituels …
        source: MathALÉA                          # défaut : « PKP Math » (question originale)
        source_url: https://www.mathalea.fr/alea/ # adresse exacte de la ressource d'origine
        licence_source: CC BY-SA 4.0              # licence VÉRIFIÉE du contenu d'origine
        adaptation: inspiree                      # originale | inspiree | adaptee | reproduite
        validation:
          statut: validee                         # a-valider (défaut) | validee | a-corriger
          par: Mme Martin
          le: 2026-11-04
```

| `adaptation` | Signification | Exigences vérifiées |
|---|---|---|
| `originale` | Rédigée pour PKP | `source` = « PKP Math » |
| `inspiree` | Idée reprise, énoncé **et valeurs** entièrement réécrits | `source` renseignée |
| `adaptee` | Texte d'origine modifié : sa licence s'applique au résultat | `source`, `source_url`, licence **claire** |
| `reproduite` | Texte repris tel quel (licence libre ou autorisation écrite) | `source`, `source_url`, licence **claire** |

Une source **sans licence claire** (`licence_source` absente, « non clarifiée », « à vérifier »…)
ne peut servir que d'**inspiration** : la vérification refuse `adaptee` et `reproduite`.
Une question `validee` doit indiquer **qui** l'a validée (`par`) et **quand** (`le`), son `auteur`
(une autre personne que le relecteur) et une `correction` détaillée.

### Référentiel officiel, méthodes, erreurs fréquentes et corrections

Les attendus officiels sont saisis, mot pour mot depuis le BO, dans `referentiels/<programme>/`
(voir `api/app/programmes.py`). Les PDF officiels sont conservés dans `referentiels/sources/` avec leur
empreinte SHA-256. Une compétence déclare les attendus qu'elle couvre ; la vérification refuse un code inconnu.

```yaml
  - code: 1RE-SD-FACTO
    libelle: Factoriser une fonction polynôme du second degré
    attendus: [1RE-SPE-2026-SD-05]            # codes du référentiel
    objectifs: [Choisir la stratégie de factorisation la plus rapide.]
    prerequis: [2NDE-DEV]                     # compétences à revoir en cas de difficulté
    cours: |
      …
    resume: |
      …
    methodes:                                 # fiches « Comment résoudre… »
      - titre: Factoriser grâce à une racine évidente
        quand: Les coefficients sont entiers et 1 ou −1 annule le polynôme.
        etapes: [Tester $x = 1$ et $x = -1$., …]
        exemple:                              # exemple résolu, étape par étape
          enonce: Factoriser $x^2 - 5x + 4$.
          resolution: [$1 - 5 + 4 = 0$ donc $1$ est racine., …]
          resultat: $(x - 1)(x - 4)$
    erreurs_frequentes:
      - erreur: Oublier le coefficient $a$ dans $a(x - x_1)(x - x_2)$.
        explication: …
    questions:
      - code: 1RE-SD-FACTO-01
        # … champs habituels …
        auteur: R. Martin
        competences_secondaires: [2NDE-DEV]   # exercice de synthèse
        correction:                           # montrée à l'élève après sa réponse
          methode: Produit nul après factorisation.
          etapes: […]
          resultat: 4                         # obligatoire en numérique ou expression, équivalent à `solution`
          erreurs_frequentes: […]
```

Couverture du programme, générée et jamais écrite à la main :

```bash
python -m app.contenu matrice      # docs/matrices/MATRICE-<programme>.md
python -m app.contenu ecarts       # attendus absents ou incomplets, compétences non rattachées
```

Le réglage `PKP_SERVIR_QUESTIONS_NON_VALIDEES` (vrai par défaut) permet, une fois la banque relue,
de ne plus servir aux élèves que les questions validées.

### Sources externes : ce qu'on peut en faire

| Source | Licence | Usage dans PKP |
|---|---|---|
| MathALÉA | Code AGPL-3.0, textes CC BY-SA 4.0 | Inspiration ; une adaptation de texte impose de publier le résultat sous CC BY-SA 4.0 avec attribution |
| APMEP (annales) | Non clarifiée pour la réutilisation | Inspiration et analyse des attendus du bac seulement |
| STACK | Logiciel GPL ; licence des questions à vérifier au cas par cas | Inspiration ; référence pour la correction des expressions |
| math.ma | Aucune licence explicite ; programme marocain | Inspiration seulement, après vérification de la conformité au programme français |

### Écrire du LaTeX dans le YAML

- Dans `cours:` et `resume:` (bloc `|`), écrire le LaTeX tel quel.
- Pour un `enonce` sur une ligne, utiliser des **apostrophes simples** `'…'` : les `\` restent intacts.
  Une apostrophe française s'y écrit **doublée** : `'Résoudre l''équation $e^x = 5$.'`
- `$…$` dans le texte, `$$…$$` pour une formule centrée. `\$` pour un vrai symbole dollar.
- Décimales à la française dans une formule : `$0{,}9$`.

### Types de questions et syntaxe des solutions

| Type | Correction | Solution (exemples) | L'élève peut écrire |
|------|-----------|---------------------|---------------------|
| `qcm` | lettre exacte | `B` | clic sur un bouton |
| `numerique` | égalité de valeur | `5/6`, `-4`, `e^2`, `2ln(2)`, `sqrt(2)/2` | `0,5`, `1/2`, `ln 4`, `exp(2)` |
| `expression` | équivalence en 8 points, même domaine | `x^2 + 6x + 9`, `(1 - ln(x))/x^2` | `(x+3)²`, `1+lnx` |

Pour un QCM, les choix sont dans l'énoncé, séparés par **deux espaces** :
`'… ? A) $0$  B) $1$  C) $+\infty$'`. La vérification exige que la lettre solution y figure.

**Ce que le moteur ne sait pas encore corriger** (→ passer par un QCM) : limites infinies,
intervalles, ensembles de solutions, coordonnées, valeurs arrondies, démonstrations.

Dans un QCM, n'écrire **aucun** « A) », « B) »… ailleurs que devant les choix : `$P(A)$` serait lu
comme une option. La vérification refuse ces énoncés (« choix illisibles »).

### Échelle de difficulté

| | Attendu |
|---|---|
| 1 | Application immédiate du cours (une étape) |
| 2 | Application directe avec un calcul |
| 3 | Deux étapes ou une propriété à choisir |
| 4 | Méthode à mobiliser (lever une indétermination, poser un changement de variable) |
| 5 | Synthèse, plusieurs méthodes, niveau sujet de bac |

Le moteur propose d'abord les questions faciles, puis monte en difficulté avec la maîtrise :
**prévoir au moins une question par niveau 1 à 5** pour chaque compétence.

## Travailler avec une IA à partir d'un manuel

Les textes d'un manuel (cours, exercices, énoncés) sont protégés par le droit d'auteur de
l'éditeur. Ils ne doivent **ni être recopiés ni être reformulés de près** dans `contenu/`, et les
photos ne doivent jamais être commitées (le dossier `sources/` est ignoré par Git pour les y ranger).
Ce qui est libre : le **programme officiel** et les **notions mathématiques** elles-mêmes.

Méthode :
1. Depuis le sommaire ou les pages du manuel, relever seulement **le plan** : chapitres et
   savoir-faire (comme `tle/05-suites.yaml` d'après un sommaire de Terminale).
2. Demander à l'IA un contenu **original** sur ce plan, au format du dépôt.
3. **Relire chaque cours et chaque solution** : l'IA peut se tromper. La vérification automatique
   garantit qu'une solution est lisible, pas qu'elle est juste.

Consigne type à donner à l'IA (joindre un fichier existant comme modèle) :

> Rédige le fichier `contenu/tle/NN-<chapitre>.yaml` du dépôt PKP Math Lycée, au format du fichier
> joint, pour le chapitre « … » du programme de Terminale spécialité. Compétences : (liste des
> savoir-faire). Pour chaque compétence : un résumé de 3 à 5 points, un cours avec définitions,
> propriétés, un exemple rédigé et les erreurs fréquentes, puis 5 à 7 questions de difficulté 1 à 5.
> Contenu entièrement original : n'utilise aucun texte ni énoncé de manuel. Types de réponse
> possibles : qcm, numerique, expression (syntaxe : x^2, sqrt(), ln(), e^x). Utilise un QCM pour les
> limites infinies et les intervalles. Énoncés entre apostrophes simples, apostrophes françaises doublées.
