// Issue #148 — Accueils Boussole et PKP (Claude)
// Deux présentations publiques d'une même application : Boussole Maîtrise+ (offre commerciale, en préparation)
// et PKP Éducation (projet associatif). Seuls les textes et l'identité changent ; les écrans, les droits et
// l'API restent communs. La variante se choisit à la construction : `VITE_MARQUE=pkp npm run build`.
// Sans réglage, ou avec une valeur inconnue, c'est Boussole (comportement actuel). Voir docs/MARQUES.md.

export const MARQUES = {
  boussole: {
    code: "boussole",
    nom: "Boussole",
    suffixe: "Maîtrise+",
    monogramme: true,
    titreDocument: "Boussole — Maîtrise+",
    // Préfixe des parcours affichés sur l'accueil : « Boussole Maths lycée ».
    prefixeParcours: "Boussole",
    badge: "Collège · Lycée",
    titre: "Comprendre, progresser, prendre confiance !",
    accroche:
      "Des cours clairs, des exercices corrigés pas à pas et un entraînement à ton rythme, à travailler en autonomie ou avec tes professeurs.",
    publics: "Pour les élèves, leurs familles et les professionnels de l'éducation.",
    spirale: true,
    conclusion: [
      "On ne réussit pas parce qu'on est né fort : on progresse en comprenant, en pratiquant et en persévérant.",
      "Comprendre aujourd'hui, réussir demain !",
    ],
  },
  pkp: {
    code: "pkp",
    nom: "PKP",
    suffixe: "Éducation",
    monogramme: false,
    titreDocument: "PKP Éducation",
    prefixeParcours: "PKP",
    badge: "Projet associatif · Collège · Lycée",
    titre: "Apprendre à son rythme, accompagné par des professeurs",
    accroche:
      "PKP Éducation met à la disposition des élèves des cours clairs, des exercices corrigés pas à pas et un entraînement à leur rythme, à travailler en autonomie ou avec leurs professeurs.",
    publics: "Pour les élèves, leurs familles et les équipes qui les accompagnent.",
    spirale: false,
    conclusion: ["Comprendre, s'entraîner, vérifier : chacun progresse à son rythme."],
  },
};

/** Variante choisie à la construction ; Boussole par défaut, y compris pour une valeur inconnue. */
export function marqueDe(code) {
  return MARQUES[String(code ?? "").trim().toLowerCase()] ?? MARQUES.boussole;
}

export const MARQUE = marqueDe(import.meta.env?.VITE_MARQUE);
