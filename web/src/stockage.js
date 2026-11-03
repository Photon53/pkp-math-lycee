// sessionStorage par défaut : sur un poste partagé du lycée, fermer l'onglet déconnecte l'élève.
// « Rester connecté » (appareil personnel) écrit dans localStorage, qui survit à la fermeture.

function zones() {
  try {
    return [sessionStorage, localStorage];
  } catch {
    return [];
  }
}

export function lire(cle) {
  for (const zone of zones()) {
    try {
      const valeur = zone.getItem(cle);
      if (valeur != null) return JSON.parse(valeur);
    } catch {
      // Valeur illisible ou stockage indisponible : on passe à la zone suivante.
    }
  }
  return null;
}

/** `durable` : conserver après la fermeture du navigateur (appareil personnel seulement). */
export function ecrire(cle, valeur, { durable = false } = {}) {
  try {
    for (const zone of zones()) zone.removeItem(cle);
    if (valeur == null) return;
    (durable ? localStorage : sessionStorage).setItem(cle, JSON.stringify(valeur));
  } catch {
    // Stockage indisponible (navigation privée stricte) : la session vit en mémoire.
  }
}
