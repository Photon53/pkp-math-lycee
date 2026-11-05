// Parcours affichés sur la page d'accueil. L'état vient de GET /domaines/publics (réglages de l'administrateur) ;
// la liste ci-dessous ne sert que de repli si l'API ne répond pas, et garde les textes de présentation.

const NOMS_NIVEAUX = { "2nde": "Seconde", "1re": "Première", Tle: "Terminale" };

export const MATIERES = { maths: "Maths", anglais: "Anglais", francais: "Français" };
export const CYCLES = { college: "collège", lycee: "lycée" };

/** Textes propres aux parcours ouverts ; `niveaux` remplace ceux du domaine quand le contenu n'en couvre qu'une partie. */
const PRESENTATIONS = {
  "maths-lycee": {
    description:
      "Tout le programme du lycée, chapitre par chapitre : leçons, méthodes, exercices corrigés et entraînement adapté au niveau de chaque élève.",
  },
  "maths-college": {
    description: "Le programme du collège, de la 6e à la 3e : leçons, méthodes et exercices progressifs pour consolider les bases.",
  },
  "anglais-college": {
    niveaux: ["4e", "3e"],
    description:
      "Des séances de 90 minutes, une par objectif du programme : compréhension, expression orale et écrite, avec un pack élève et un pack animateur.",
  },
};

/** Repli : l'état connu au lancement de la bêta. */
export const DOMAINES_PAR_DEFAUT = [
  { code: "maths-college", matiere: "maths", cycle: "college", libelle: "Maths collège", niveaux: ["6e", "5e", "4e", "3e"], etat: "en_chantier" },
  { code: "maths-lycee", matiere: "maths", cycle: "lycee", libelle: "Maths lycée", niveaux: ["2nde", "1re", "Tle"], etat: "ouvert" },
  { code: "anglais-college", matiere: "anglais", cycle: "college", libelle: "Anglais collège", niveaux: ["6e", "5e", "4e", "3e"], etat: "ouvert" },
  { code: "anglais-lycee", matiere: "anglais", cycle: "lycee", libelle: "Anglais lycée", niveaux: ["2nde", "1re", "Tle"], etat: "en_chantier" },
  { code: "francais-college", matiere: "francais", cycle: "college", libelle: "Français collège", niveaux: ["6e", "5e", "4e", "3e"], etat: "en_chantier" },
  { code: "francais-lycee", matiere: "francais", cycle: "lycee", libelle: "Français lycée", niveaux: ["2nde", "1re"], etat: "en_chantier" },
];

export const ETATS = {
  ouvert: { libelle: "Ouvert", detail: "Ouvert aux élèves" },
  en_preparation: { libelle: "En préparation", detail: "Contenus en cours de rédaction et de validation par l'équipe" },
  en_chantier: { libelle: "En construction", detail: "Cours et exercices en cours de construction" },
};

export function niveauxLisibles(niveaux) {
  return niveaux.map((n) => NOMS_NIVEAUX[n] ?? n).join(" · ");
}

/** Répartit les domaines en parcours prêts et en chantiers, avec leurs textes d'affichage. */
export function repartirParcours(domaines) {
  const vues = domaines.map((d) => {
    const presentation = PRESENTATIONS[d.code] ?? {};
    return {
      ...d,
      matiereLisible: MATIERES[d.matiere] ?? d.libelle,
      cycleLisible: CYCLES[d.cycle] ?? d.cycle,
      niveauxLisibles: niveauxLisibles(d.etat === "ouvert" && presentation.niveaux ? presentation.niveaux : d.niveaux),
      description: presentation.description,
    };
  });
  return {
    prets: vues.filter((d) => d.etat === "ouvert"),
    chantiers: vues.filter((d) => d.etat !== "ouvert"),
  };
}
