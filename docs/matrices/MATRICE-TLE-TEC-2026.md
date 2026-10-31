# Matrice de couverture — Mathématiques, classe terminale de la voie technologique (programme 2026)

Fichier **généré** par `python -m app.contenu matrice` le 2026-10-31 : ne pas modifier à la main.
Source : Programme d'enseignement de mathématiques de la classe terminale de la voie technologique, BO n° 14 du 2 avril 2026 (`referentiels/sources/bo-2026-14-tle-technologique-515420.pdf`).

- Attendus saisis : **86**, dont 86 obligatoires (les approfondissements ne le sont pas).
- Obligatoires évalués ou validés : **44 %** · validés : 0 % · absents : 48.
- Légende : ✗ absent · ◐ partiel · ✎ enseigné, évaluation non automatisée · ● évalué · ✓ validé. « Évalué » = cours ou méthode, au moins 5 questions sur 3 difficultés.

La couverture ne porte que sur les thèmes déjà saisis dans `referentiels/` : un thème non saisi n'apparait pas.

## Suites, exponentielles, logarithme décimal et fonction inverse (Analyse)

| | Attendu | Type | Compétences PKP | Questions (validées) | Difficultés | Corrigées |
|:-:|---|---|---|:-:|:-:|:-:|
| ● | `TLE-TEC-2026-ANA-01` Suites arithmétiques : moyenne arithmétique de deux nombres ; expression en fonction de n du terme de rang n ; somme des n premiers termes d’une suite arithmétique ; notation Σ. | contenu | `TLE-TEC-ARITH` | 5 (0) | 12345 | 5 |
| ● | `TLE-TEC-2026-ANA-02` Suites géométriques à termes positifs : moyenne géométrique de deux nombres positifs ; expression en fonction de n du terme de rang n ; somme des n premiers termes d’une suite géométrique ; notation Σ. | contenu | `TLE-TEC-GEOM` | 5 (0) | 12345 | 5 |
| ● | `TLE-TEC-2026-ANA-03` Prouver que trois nombres sont (ou ne sont pas) les termes consécutifs d’une suite arithmétique ou géométrique. | capacite | `TLE-TEC-ARITH` | 5 (0) | 12345 | 5 |
| ● | `TLE-TEC-2026-ANA-04` Déterminer la raison d’une suite arithmétique ou géométrique modélisant une évolution. | capacite | `TLE-TEC-ARITH` | 5 (0) | 12345 | 5 |
| ● | `TLE-TEC-2026-ANA-05` Exprimer en fonction de n le terme général d’une suite arithmétique ou géométrique. | capacite | `TLE-TEC-ARITH` | 5 (0) | 12345 | 5 |
| ● | `TLE-TEC-2026-ANA-06` Calculer la somme des n premiers termes d’une suite arithmétique ou géométrique. | capacite | `TLE-TEC-ARITH` | 5 (0) | 12345 | 5 |
| ● | `TLE-TEC-2026-ANA-07` Reconnaitre une situation relevant du calcul d’une somme de termes consécutifs d’une suite arithmétique ou géométrique. | capacite | `TLE-TEC-ARITH` | 5 (0) | 12345 | 5 |
| ✗ | `TLE-TEC-2026-ANA-08` Écrire en langage Python une fonction qui calcule la somme des n premiers carrés, des n premiers cubes ou des n premiers inverses ; établir le lien entre l’écriture de la somme à l’aide du symbole Σ et les composantes de l’algorithme (initialisation, sortie de boucle, accumulateur, compteur) (situation algorithmique). | capacite | — | 0 (0) | — | 0 |
| ● | `TLE-TEC-2026-ANA-09` Définition de la fonction x ↦ aˣ pour x positif comme prolongement à des valeurs non entières positives de la suite géométrique (aⁿ)ₙ∈ℕ ; extension à ℝ₋ en posant a⁻ˣ = 1/aˣ. | contenu | `TLE-TEC-EXPA` | 5 (0) | 12345 | 5 |
| ● | `TLE-TEC-2026-ANA-10` Sens de variation selon les valeurs de a. Allure de la courbe représentative selon les valeurs de a. | contenu | `TLE-TEC-EXPA` | 5 (0) | 12345 | 5 |
| ● | `TLE-TEC-2026-ANA-11` Propriétés algébriques : a^(x+y) = aˣaʸ ; a^(x−y) = aˣ/aʸ ; a^(nx) = (aˣ)ⁿ pour n entier relatif. | contenu | `TLE-TEC-EXPA` | 5 (0) | 12345 | 5 |
| ● | `TLE-TEC-2026-ANA-12` Cas particulier de l’exposant 1/n pour calculer un taux d’évolution moyen équivalent à n évolutions successives. | contenu | `TLE-TEC-EXPA` | 5 (0) | 12345 | 5 |
| ● | `TLE-TEC-2026-ANA-13` Connaitre et utiliser le sens de variation des fonctions de la forme x ↦ k aˣ, selon le signe de k et les valeurs de a. | capacite | `TLE-TEC-EXPA` | 5 (0) | 12345 | 5 |
| ● | `TLE-TEC-2026-ANA-14` Connaitre les propriétés algébriques des fonctions exponentielles et les utiliser pour transformer des écritures numériques ou littérales. | capacite | `TLE-TEC-EXPA` | 5 (0) | 12345 | 5 |
| ● | `TLE-TEC-2026-ANA-15` Calculer le taux d’évolution moyen équivalent à des évolutions successives. | capacite | `TLE-TEC-EXPA` | 5 (0) | 12345 | 5 |
| ✗ | `TLE-TEC-2026-ANA-16` Intercaler entre deux points déjà construits un troisième point ayant pour abscisse (respectivement pour ordonnée) la moyenne arithmétique (respectivement géométrique) des abscisses (respectivement des ordonnées) des deux points initiaux (situation algorithmique). | capacite | — | 0 (0) | — | 0 |
| ● | `TLE-TEC-2026-ANA-17` Définition du logarithme décimal de b pour b > 0 comme l’unique solution de l’équation 10ˣ = b ; notation log. Sens de variation. | contenu | `TLE-TEC-LOG` | 5 (0) | 12345 | 5 |
| ● | `TLE-TEC-2026-ANA-18` Propriétés algébriques : log(ab) = log(a) + log(b), log(aⁿ) = n log(a) et log(a/b) = log(a) − log(b), pour n entier naturel, a et b réels strictement positifs. | contenu | `TLE-TEC-LOG` | 5 (0) | 12345 | 5 |
| ● | `TLE-TEC-2026-ANA-19` Utiliser le logarithme décimal pour résoudre une équation du type aˣ = b ou xᵃ = b d’inconnue x réelle, une inéquation du type aˣ < b ou xᵃ < b d’inconnue x réelle ou du type aⁿ < b d’inconnue n entier naturel. | capacite | `TLE-TEC-LOG` | 5 (0) | 12345 | 5 |
| ● | `TLE-TEC-2026-ANA-20` Utiliser les propriétés algébriques de la fonction logarithme décimal pour transformer des expressions numériques ou littérales. | capacite | `TLE-TEC-LOG` | 5 (0) | 12345 | 5 |
| ● | `TLE-TEC-2026-ANA-21` Comportement de la fonction inverse aux bornes de son ensemble de définition. Dérivée et sens de variation. Courbe représentative ; asymptotes. | contenu | `TLE-TEC-INV` | 5 (0) | 12345 | 5 |
| ● | `TLE-TEC-2026-ANA-22` Étudier et représenter des fonctions obtenues par combinaisons linéaires de la fonction inverse et de fonctions polynomiales de degré au maximum 3. | capacite | `TLE-TEC-INV` | 5 (0) | 12345 | 5 |

## Automatismes (Transversale)

| | Attendu | Type | Compétences PKP | Questions (validées) | Difficultés | Corrigées |
|:-:|---|---|---|:-:|:-:|:-:|
| ● | `TLE-TEC-2026-AUTO-01` Calculer, appliquer, exprimer une proportion sous différentes formes (décimale, fractionnaire, pourcentage). | automatisme | `TLE-TEC-INDICE` | 5 (0) | 12345 | 5 |
| ● | `TLE-TEC-2026-AUTO-02` Calculer la proportion d’une proportion. | automatisme | `TLE-TEC-INDICE` | 5 (0) | 12345 | 5 |
| ✗ | `TLE-TEC-2026-AUTO-03` Passer d’une formulation additive (« augmenter de 5 % », respectivement « diminuer de 5 % ») à une formulation multiplicative (« multiplier par 1,05 », respectivement « multiplier par 0,95 »). | automatisme | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-AUTO-04` Appliquer un taux d’évolution pour calculer une valeur finale ou initiale. | automatisme | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-AUTO-05` Calculer un taux d’évolution, l’exprimer en pourcentage. | automatisme | — | 0 (0) | — | 0 |
| ● | `TLE-TEC-2026-AUTO-06` Interpréter un indice de base 100. calculer un indice ; calculer le taux d’évolution entre deux valeurs. | automatisme | `TLE-TEC-INDICE` | 5 (0) | 12345 | 5 |
| ✗ | `TLE-TEC-2026-AUTO-07` Calculer le taux d’évolution équivalent à plusieurs évolutions successives. | automatisme | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-AUTO-08` Calculer un taux d’évolution réciproque. | automatisme | — | 0 (0) | — | 0 |
| ● | `TLE-TEC-2026-AUTO-09` Reconnaitre une situation contextualisée se modélisant par une suite géométrique dont on identifie la raison. | automatisme | `TLE-TEC-GEOM` | 5 (0) | 12345 | 5 |
| ✗ | `TLE-TEC-2026-AUTO-10` Effectuer des opérations et des comparaisons entre des fractions simples. | automatisme | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-AUTO-11` Effectuer des opérations sur les puissances. | automatisme | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-AUTO-12` Passer d’une écriture d’un nombre à une autre (décimale, fractionnaire, scientifique). | automatisme | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-AUTO-13` Estimer un ordre de grandeur. | automatisme | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-AUTO-14` Effectuer des conversions d’unités. | automatisme | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-AUTO-15` Résoudre une équation ou une inéquation du premier degré, une équation du type : x² = a. | automatisme | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-AUTO-16` Déterminer le signe d’une expression du premier degré, d’une expression factorisée du second degré. | automatisme | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-AUTO-17` Isoler une variable dans une égalité ou une inégalité qui en comporte plusieurs sur des exemples internes aux mathématiques ou issus des autres disciplines. | automatisme | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-AUTO-18` Effectuer une application numérique d’une formule (notamment pour les formules utilisées dans les autres disciplines). | automatisme | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-AUTO-19` Développer, factoriser, réduire une expression algébrique simple. | automatisme | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-AUTO-20` Calculer la dérivée d’une fonction polynomiale de degré inférieur ou égal à 3. | automatisme | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-AUTO-21` Calculer le coefficient directeur de la tangente en un point à une courbe à l’aide de la dérivée. | automatisme | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-AUTO-22` Déterminer graphiquement des images et des antécédents. | automatisme | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-AUTO-23` Résoudre graphiquement une équation, une inéquation du type : ƒ(x) = k, ƒ(x) < k, etc. | automatisme | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-AUTO-24` Déterminer le signe d’une expression factorisée du second degré à l’aide d’une image mentale de la courbe représentative de la fonction correspondante. | automatisme | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-AUTO-25` Déterminer graphiquement le signe d’une fonction ou son tableau de variations. | automatisme | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-AUTO-26` Exploiter une équation de courbe (appartenance d’un point, calcul de coordonnées). | automatisme | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-AUTO-27` Tracer une droite donnée par son équation réduite ou par un point et son coefficient directeur. | automatisme | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-AUTO-28` Lire graphiquement l’équation réduite d’une droite. | automatisme | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-AUTO-29` Déterminer l’équation réduite d’une droite à partir des coordonnées de deux de ses points. | automatisme | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-AUTO-30` Déterminer graphiquement le coefficient directeur d’une tangente à une courbe. | automatisme | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-AUTO-31` Lire un graphique, un histogramme, un diagramme en barres ou circulaire, un diagramme en boite ou toute autre représentation (repérer l’origine du repère, les unités de graduations ou les échelles, etc.). | automatisme | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-AUTO-32` Passer du graphique aux données et vice versa. | automatisme | — | 0 (0) | — | 0 |

## Statistiques et probabilités (Statistiques et probabilités)

| | Attendu | Type | Compétences PKP | Questions (validées) | Difficultés | Corrigées |
|:-:|---|---|---|:-:|:-:|:-:|
| ● | `TLE-TEC-2026-SP-01` Changement de variable dans l’étude graphique d’une série statistique à deux variables quantitatives. Ajustement se ramenant par changement de variable à un ajustement affine. | contenu | `TLE-TEC-AJUST` | 5 (0) | 12345 | 5 |
| ● | `TLE-TEC-2026-SP-02` Représenter un nuage de points en effectuant un changement de variable donné (par exemple x², 1/x, 1/y, log(y), etc.) afin de conjecturer une relation de linéarité entre de nouvelles variables. | capacite | `TLE-TEC-AJUST` | 5 (0) | 12345 | 5 |
| ✗ | `TLE-TEC-2026-SP-03` Automatiser le calcul de Σ(yᵢ − (axᵢ + b))². Rechercher un couple (a, b) minimisant cette expression parmi un ensemble fini de couples proposés par les élèves ou générés par balayage, tirage aléatoire, etc. (situations algorithmiques). | capacite | — | 0 (0) | — | 0 |
| ● | `TLE-TEC-2026-SP-04` Formule des probabilités totales pour une partition de l’univers. | contenu | `TLE-TEC-PROBA` | 5 (0) | 12345 | 5 |
| ● | `TLE-TEC-2026-SP-05` Construire un arbre de probabilités associé à une situation aléatoire donnée. | capacite | `TLE-TEC-PROBA` | 5 (0) | 12345 | 5 |
| ● | `TLE-TEC-2026-SP-06` Interpréter les pondérations de chaque branche d’un arbre en termes de probabilités, et notamment de probabilités conditionnelles. | capacite | `TLE-TEC-PROBA` | 5 (0) | 12345 | 5 |
| ● | `TLE-TEC-2026-SP-07` Faire le lien entre la définition des probabilités conditionnelles et la multiplication des probabilités des branches du chemin correspondant. | capacite | `TLE-TEC-PROBA` | 5 (0) | 12345 | 5 |
| ● | `TLE-TEC-2026-SP-08` Utiliser un arbre de probabilités pour calculer des probabilités. | capacite | `TLE-TEC-PROBA` | 5 (0) | 12345 | 5 |
| ● | `TLE-TEC-2026-SP-09` Calculer la probabilité d’un évènement connaissant ses probabilités conditionnelles relatives à une partition de l’univers. | capacite | `TLE-TEC-PROBA` | 5 (0) | 12345 | 5 |
| ● | `TLE-TEC-2026-SP-10` Espérance d’une variable aléatoire discrète. | contenu | `TLE-TEC-BINOM` | 5 (0) | 12345 | 5 |
| ● | `TLE-TEC-2026-SP-11` Loi binomiale B(n, p) ; espérance. Coefficients binomiaux (n k) ; triangle de Pascal. | contenu | `TLE-TEC-BINOM` | 5 (0) | 12345 | 5 |
| ● | `TLE-TEC-2026-SP-12` Calculer l’espérance d’une variable aléatoire discrète dans des cas simples et l’interpréter. | capacite | `TLE-TEC-BINOM` | 5 (0) | 12345 | 5 |
| ● | `TLE-TEC-2026-SP-13` Calculer des coefficients binomiaux (n k) à l’aide du triangle de Pascal pour n ⩽ 10. | capacite | `TLE-TEC-BINOM` | 5 (0) | 12345 | 5 |
| ● | `TLE-TEC-2026-SP-14` Reconnaitre une situation relevant de la loi binomiale et en identifier le couple de paramètres. | capacite | `TLE-TEC-BINOM` | 5 (0) | 12345 | 5 |
| ● | `TLE-TEC-2026-SP-15` Lorsque la variable aléatoire X suit une loi binomiale : interpréter l’évènement {X = k} sur un arbre de probabilité ; calculer les probabilités des évènements {X = 0}, {X = 1}, {X = n}, {X = n − 1} et de ceux qui s’en déduisent par réunion ; calculer la probabilité de l’évènement {X = k} à l’aide des coefficients binomiaux. | capacite | `TLE-TEC-BINOM` | 5 (0) | 12345 | 5 |
| ✗ | `TLE-TEC-2026-SP-16` Générer un triangle de Pascal de taille n donnée. Représenter par un diagramme en bâtons la loi de probabilité d’une loi binomiale B(n, p) ; faire le lien avec l’histogramme des fréquences observées des 1 lors de la simulation d’échantillons d'une loi de Bernoulli faite en classe de première (situations algorithmiques). | capacite | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-SP-17` Calculer l’espérance Σ xᵢpᵢ d’une variable aléatoire suivant une loi de probabilité donnée ; cas particulier d’une variable aléatoire suivant la loi binomiale B(n, p). Représenter graphiquement l’espérance de lois binomiales B(n, p) à n fixé et p variable, à p fixé et n variable puis faire le lien avec l’expression admise de l’espérance (situations algorithmiques). | capacite | — | 0 (0) | — | 0 |

## Logique, algorithmique et programmation (Transversale)

| | Attendu | Type | Compétences PKP | Questions (validées) | Difficultés | Corrigées |
|:-:|---|---|---|:-:|:-:|:-:|
| ✗ | `TLE-TEC-2026-TRANS-01` Utiliser correctement les connecteurs logiques « et », « ou ». | capacite | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-TRANS-02` Identifier le statut d’une égalité (identité, équation) et celui de la ou des lettres utilisées (variable, indéterminée, inconnue, paramètre). | capacite | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-TRANS-03` Utiliser un contre-exemple pour infirmer une proposition universelle. | capacite | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-TRANS-04` Distinguer une proposition de sa réciproque. | capacite | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-TRANS-05` Utiliser à bon escient les expressions « condition nécessaire », « condition suffisante », « équivalence logique ». | capacite | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-TRANS-06` Utiliser un générateur de nombres aléatoires entre 0 et 1 pour simuler une loi de Bernoulli de paramètre p. | capacite | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-TRANS-07` Utiliser la notion de compteur. | capacite | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-TRANS-08` Utiliser le principe d’accumulateur pour calculer une somme, un produit. | capacite | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-TRANS-09` Identifier les entrées et les sorties d’une fonction. | capacite | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-TRANS-10` Structurer un programme en ayant recours aux fonctions. | capacite | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-TRANS-11` Générer une liste (en extension, par ajouts successifs, en compréhension). | capacite | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-TRANS-12` Manipuler des éléments d’une liste (ajouter, supprimer, etc.) et leurs indices. | capacite | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-TRANS-13` Itérer sur les éléments d’une liste. | capacite | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-TRANS-14` Traiter un fichier contenant des données réelles pour en extraire de l’information et l’analyser. | capacite | — | 0 (0) | — | 0 |
| ✗ | `TLE-TEC-2026-TRANS-15` Réaliser un tableau croisé de données sur deux critères à partir de données brutes. | capacite | — | 0 (0) | — | 0 |
