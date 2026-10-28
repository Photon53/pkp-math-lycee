# Contenu pédagogique — guide de rédaction

Tout le contenu (chapitres, cours, résumés, questions) vit dans `contenu/`, un fichier YAML
par chapitre. Il est **versionné**, **relu** (pull request sur GitHub) et **vérifié
automatiquement** avant d'arriver en base.

```
contenu/
  2nde/01-nombres-et-calculs.yaml
  2nde/02-calcul-litteral.yaml
  1re/01-second-degre.yaml
  tle/05-suites.yaml
  tle/09-logarithme-neperien.yaml
```

## Cycle de travail

1. Écrire ou modifier un fichier YAML.
2. Vérifier : tâche VS Code **Contenu : vérifier les fichiers YAML**
   (ou `python -m app.contenu verifier` depuis `api/`).
3. Importer dans la base locale : tâche **Contenu : importer dans la base de démo**, puis
   regarder le résultat dans l'onglet **Cours** et en séance d'exercices (classe `TLE-C-DEMO`, etc.).
4. Commit, pull request : la CI GitHub revérifie tout le contenu et lance les tests.
5. En production, l'import est automatique au démarrage de l'API.

L'import est **idempotent** : le relancer ne change rien. Une question retirée d'un fichier est
**archivée** (jamais supprimée : l'historique des élèves reste lisible). Les questions créées depuis
l'interface enseignant ne sont pas touchées.

## Format d'un fichier

```yaml
chapitre:
  code: TLE-LN                 # identifiant stable, MAJUSCULES-ET-TIRETS, ne jamais le changer
  niveau: Tle                  # 2nde | 1re | Tle
  ordre: 9                     # position dans l'année (unique par niveau)
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
