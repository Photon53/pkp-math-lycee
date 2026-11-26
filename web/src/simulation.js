// Issue #184 — Vue élève simulée (Claude)
// Partagé par les espaces professeur, administrateur et élève, sans charger l'un dans l'autre.
import { ecrire } from "./stockage.js";

// Clés de session de l'espace élève (EspaceEleve.jsx, EspaceEnfant.jsx, Exercice.jsx) : vidées en entrant et
// en sortant d'une simulation, pour qu'aucune séance fictive ne se mélange à une vraie, ni l'inverse.
export const CLE_ELEVE = "pkp.eleve";
const CLES_ELEVE = [CLE_ELEVE, "pkp.enfant", "pkp.eleve.anglais", "pkp.seance", "pkp.bilan", "pkp.cible"];

export const ORIGINES = {
  enseignant: { vers: "/enseignant", libelle: "Revenir à mon espace professeur" },
  admin: { vers: "/admin", libelle: "Revenir à mon espace administrateur" },
};

export function viderSessionEleve() {
  for (const cle of CLES_ELEVE) ecrire(cle, null);
}

/** Ouvre l'espace élève avec le jeton de l'élève fictif : session de l'onglet seulement, jamais durable. */
export function entrerEnSimulation(reponse) {
  viderSessionEleve();
  ecrire(CLE_ELEVE, { jeton: reponse.jeton, eleve: reponse.eleve, simulation: reponse.simulation, durable: false });
}
