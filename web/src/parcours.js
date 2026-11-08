// Niveaux et parcours (enseignements de mathématiques) : même règle que l'API, app/referentiel.py.

// Ordre scolaire : collège (domaine Maths collège), puis lycée (Maths lycée).
export const NIVEAUX = [
  ["6e", "Sixième"],
  ["5e", "Cinquième"],
  ["4e", "Quatrième"],
  ["3e", "Troisième"],
  ["2nde", "Seconde"],
  ["1re", "Première"],
  ["Tle", "Terminale"],
];

// Le libellé dit la voie : une classe de 1re générale et une de 1re technologique ne se confondent pas.
export const LIBELLES_PARCOURS = {
  "tronc-commun": "Tronc commun",
  // Ticket #25 : seconde préparant au bac pro (BO spécial n° 5 du 11 avril 2019), distincte de la voie technologique.
  professionnel: "Voie professionnelle (seconde bac pro)",
  specialite: "Spécialité maths (voie générale)",
  scientifique: "Enseignement scientifique (voie générale, sans spécialité maths)",
  complementaires: "Maths complémentaires (voie générale)",
  expertes: "Maths expertes (voie générale)",
  technologique: "Voie technologique (STMG, STI2D, STL, ST2S…)",
  "mise-a-niveau": "Mise à niveau (bases de l'année précédente)",
  excellence: "Excellence et olympiades (exercices très poussés)",
  examens: "Préparation aux examens (brevet, épreuve anticipée, bac blanc)",
};

// Ordre d'affichage : la voie générale, la voie technologique ou professionnelle, puis les groupes de soutien et d'approfondissement.
export const PARCOURS_PAR_NIVEAU = {
  "6e": ["tronc-commun", "mise-a-niveau", "excellence"],
  "5e": ["tronc-commun", "mise-a-niveau", "excellence"],
  "4e": ["tronc-commun", "mise-a-niveau", "excellence"],
  "3e": ["tronc-commun", "mise-a-niveau", "excellence", "examens"],
  "2nde": ["tronc-commun", "professionnel", "mise-a-niveau", "excellence"],
  "1re": ["specialite", "scientifique", "technologique", "mise-a-niveau", "excellence", "examens"],
  Tle: ["specialite", "complementaires", "expertes", "technologique", "mise-a-niveau", "excellence", "examens"],
};

export const NIVEAUX_COLLEGE = ["6e", "5e", "4e", "3e"];
/** Français (F1) : de la 6e à la 1re, en tronc commun ; même règle que `refus_matiere` de l'API. */
export const NIVEAUX_FRANCAIS = [...NIVEAUX_COLLEGE, "2nde", "1re"];
export const MATIERES_CLASSES = { maths: "Mathématiques", francais: "Français" };
/** Libellé d'une classe dans la liste du professeur : le français n'a pas de parcours à afficher. */
export const libelleClasse = (classe, libellesParcours) =>
  classe.matiere === "francais" ? "Français" : libellesParcours[classe.parcours];
/** Domaine des maths d'un niveau : même règle que `domaine_maths` de l'API. */
export const domaineMaths = (niveau) => (NIVEAUX_COLLEGE.includes(niveau) ? "maths-college" : "maths-lycee");

const RANG_NIVEAU = Object.fromEntries(NIVEAUX.map(([v], i) => [v, i]));

/** Trie des chapitres par niveau, parcours puis ordre dans l'année. */
export function trierChapitres(chapitres) {
  const rang = (ch) => [RANG_NIVEAU[ch.niveau] ?? 9, PARCOURS_PAR_NIVEAU[ch.niveau]?.indexOf(ch.parcours) ?? 9];
  return [...chapitres].sort((a, b) => {
    const [na, pa] = rang(a);
    const [nb, pb] = rang(b);
    return na - nb || pa - pb || (a.ordre ?? 0) - (b.ordre ?? 0);
  });
}

export const libelleNiveauParcours = (niveau, parcours) =>
  `${NIVEAUX.find(([v]) => v === niveau)?.[1] ?? niveau} — ${LIBELLES_PARCOURS[parcours] ?? parcours}`;
