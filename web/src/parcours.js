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
};

// Ordre d'affichage : la voie générale d'abord, la voie technologique ensuite.
export const PARCOURS_PAR_NIVEAU = {
  "2nde": ["tronc-commun"],
  "1re": ["specialite", "scientifique", "technologique"],
  Tle: ["specialite", "complementaires", "expertes", "technologique"],
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
