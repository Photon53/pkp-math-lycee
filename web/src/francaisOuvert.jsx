import { useEffect, useState } from "react";
import { api } from "./api.js";

/**
 * Vrai si un domaine Français est actif (en préparation par l'équipe ou ouvert), d'après l'état calculé par le serveur.
 * Tant qu'aucun domaine Français n'est activé, la navigation n'annonce pas cet espace ; le serveur refuse de toute façon
 * l'accès aux dossiers d'un domaine inactif.
 */
export function francaisActif(domaines) {
  return Array.isArray(domaines) && domaines.some((d) => d.matiere === "francais" && d.etat !== "en_chantier");
}

/** Lit l'état public des domaines ; faux tant que la réponse n'est pas arrivée ou si l'API ne répond pas. */
export function useFrancaisActif() {
  const [actif, setActif] = useState(false);
  useEffect(() => {
    let monte = true;
    api("/domaines/publics")
      .then((domaines) => {
        if (monte) setActif(francaisActif(domaines));
      })
      .catch(() => {});
    return () => {
      monte = false;
    };
  }, []);
  return actif;
}

/** N'affiche `children` que si un domaine Français est actif. */
export function SiFrancaisActif({ children }) {
  return useFrancaisActif() ? children : null;
}
