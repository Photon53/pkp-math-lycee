// Issue #148 — Accueils Boussole et PKP (Claude)
// Les cinq étapes de la méthode, sans dépendance à KaTeX : la page Méthode, l'accueil public et l'espace élève
// les affichent. `court` : la phrase de présentation rapide (accueil, aide « Comment bien travailler ? »).

/** Les cinq étapes de la méthode, et où l'élève les trouve dans chaque leçon. */
export const ETAPES = [
  {
    cle: "comprendre",
    titre: "Je comprends",
    court: "Je lis le cours et les objectifs de la leçon.",
    dans: "Objectifs et cours structuré de chaque leçon.",
    critere: "Je sais expliquer la notion avec mes propres mots et reconnaitre ce qu'on me demande.",
  },
  {
    cle: "memoriser",
    titre: "Je mémorise",
    court: "Je retiens l'essentiel, les méthodes et les pièges.",
    dans: "« L'essentiel », les méthodes avec exemple résolu, l'encadré « Attention à… ».",
    critere: "Ma fiche contient les définitions, propriétés, formules, un exemple résolu et les erreurs classiques.",
  },
  {
    cle: "entrainer",
    titre: "Je m'entraîne",
    court: "J'applique la méthode sur des exercices progressifs.",
    dans: "Exercices des niveaux 1 à 3, avec la réponse attendue et la partie du cours à utiliser.",
    critere: "J'applique une méthode connue, puis je gagne en autonomie.",
  },
  {
    cle: "depasser",
    titre: "Je me dépasse",
    court: "Je combine plusieurs notions sur des exercices plus difficiles.",
    dans: "Exercices des niveaux 4 et 5 : synthèse et problèmes.",
    critere: "Je choisis une méthode, je combine plusieurs notions, je cherche une solution.",
  },
  {
    cle: "verifier",
    titre: "Je vérifie",
    court: "Je regarde ma maîtrise et je reprends mes erreurs.",
    dans: "Ma maîtrise de la compétence et mon historique.",
    critere: "Je contrôle mes résultats, j'identifie mes erreurs et je retravaille ce qui n'est pas acquis.",
  },
];

/** Conseils fixes, sans personnalisation ni production régulière : ils s'affichent au bon moment de la séance. */
export const CONSEILS = {
  essayer: "Cherche d'abord seul·e : une erreur bien comprise fait plus progresser qu'une correction lue trop tôt.",
  rappel: "Bloqué·e ? Relis la partie du cours de cette notion, puis reviens à la question : elle t'attend.",
  erreur: "Reprends ton erreur : compare ta réponse à la correction, repère l'étape qui coince, puis refais un exercice semblable.",
};
