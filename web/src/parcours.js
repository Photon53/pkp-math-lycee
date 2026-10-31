// Niveaux et parcours (enseignements de mathématiques) : même règle que l'API, app/referentiel.py.

export const NIVEAUX = [
  ["2nde", "Seconde"],
  ["1re", "Première"],
  ["Tle", "Terminale"],
];

// Le libellé dit la voie : une classe de 1re générale et une de 1re technologique ne se confondent pas.
export const LIBELLES_PARCOURS = {
  "tronc-commun": "Tronc commun",
  specialite: "Spécialité maths (voie générale)",
  scientifique: "Enseignement scientifique (voie générale, sans spécialité maths)",
  complementaires: "Maths complémentaires (voie générale)",
  expertes: "Maths expertes (voie générale)",
  technologique: "Voie technologique (STMG, STI2D, STL, ST2S…)",
  "mise-a-niveau": "Mise à niveau (bases de l'année précédente)",
  excellence: "Excellence et olympiades (exercices très poussés)",
  examens: "Préparation aux examens (épreuve anticipée, bac blanc)",
};

// Ordre d'affichage : la voie générale, la voie technologique, puis les groupes de soutien et d'approfondissement.
export const PARCOURS_PAR_NIVEAU = {
  "2nde": ["tronc-commun", "mise-a-niveau", "excellence"],
  "1re": ["specialite", "scientifique", "technologique", "mise-a-niveau", "excellence", "examens"],
  Tle: ["specialite", "complementaires", "expertes", "technologique", "mise-a-niveau", "excellence", "examens"],
};

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
