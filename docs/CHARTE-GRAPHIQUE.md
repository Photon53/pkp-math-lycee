<!-- Issue #149 — Refonte visuelle (Claude) -->
# Charte graphique : « instrument de précision »

Direction validée par le propriétaire le 16/11/2026 (issue #149). Le **cadre est sombre** (en-tête, pied de page,
accueil public, navigation des adultes) et le **travail reste clair** (cours, exercices, corrections, tableaux).
La refonte ne touche que la présentation : aucun élément, libellé, droit ni comportement n'a changé.

Jetons : `web/src/theme.css`. Composants : `web/src/styles.css`, section « Refonte « instrument de précision » (#149) ».
Maquette de conception : liée dans l'issue #149.

## Couleurs

| Jeton | Valeur | Usage | Contraste (WCAG 2.1) |
|---|---|---|---|
| `--nuit` | `#0b1426` | fond du cadre sombre | `--sur-nuit` 16,4:1 |
| `--nuit-claire` | `#1b2f55` | lueur, entrée de menu active | blanc 13,3:1 ; `--sur-nuit-doux` 6,5:1 |
| `--sur-nuit` / `--sur-nuit-doux` | `#eef2fa` / `#a9b6cf` | textes sur fond nuit | 16,4:1 / 9,0:1 |
| `--lien-nuit` | `#c9d5ff` | liens sur fond nuit | 12,7:1 |
| `--nord` | `#f2a65a` | bouton principal de l'accueil, anneau de focus sur fond sombre | texte `--nord-texte` 9,1:1 (survol 10,5:1) ; sur nuit 9,1:1 |
| `--bordure-nuit-forte` | `#5b6f96` | contour des boutons secondaires sur fond nuit | 3,6:1 (contraste non textuel ≥ 3:1) |
| `--primaire`, `--action`, `--accent` | inchangés | titres, boutons et liens clairs, décor | 10,6:1 ; 5,9:1 ; décor seulement (3,0:1 sur blanc) |

Les couleurs de sens (succès, alerte, erreur) et de matières sont inchangées. Une information n'est jamais portée par
la seule couleur.

## Typographie

| Police | Usage | Licence | Hébergement |
|---|---|---|---|
| Space Grotesk (variable) | titres, logo, chiffres clés | SIL Open Font License 1.1 | paquet `@fontsource-variable/space-grotesk` 5.3.0, servi par le site (CSP `font-src 'self'` inchangée) |
| Inter (variable) | texte courant, formulaires, exercices | SIL Open Font License 1.1 | `@fontsource-variable/inter`, déjà en place |

Les fichiers de police sont découpés par jeu de caractères (`unicode-range`) : un navigateur ne télécharge que le
sous-ensemble latin (22 Ko pour Space Grotesk) pour des pages en français. Aucun service tiers n'est appelé. Les
formules restent rendues par KaTeX.

## Mouvement et accessibilité

- Survol des cartes de profil : élévation de 2 px en 200 ms ; aucune information n'est accessible au seul survol.
- `prefers-reduced-motion: reduce` : toutes les transitions et animations sont neutralisées.
- Focus toujours visible : anneau orange (`--nord`) sur fond sombre, bleu (`--action`) sur fond clair.
- Rose des vents de l'accueil Boussole : décor SVG masqué aux lecteurs d'écran (`aria-hidden`), absent sous 900 px.
- Pleine largeur du cadre sombre sans changer le DOM : ombre portée de la couleur du fond, rognée en hauteur
  (`box-shadow` + `clip-path`), sans défilement horizontal.

## Variantes

PKP Éducation (`VITE_MARQUE=pkp`, voir `docs/MARQUES.md`) hérite du thème commun avec son identité propre : logo
texte, sans monogramme ni rose des vents, et ses textes.
