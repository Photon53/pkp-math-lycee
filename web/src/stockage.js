// sessionStorage plutôt que localStorage : sur un poste partagé du lycée,
// fermer l'onglet déconnecte l'élève.

export function lire(cle) {
  try {
    return JSON.parse(sessionStorage.getItem(cle));
  } catch {
    return null;
  }
}

export function ecrire(cle, valeur) {
  try {
    if (valeur == null) sessionStorage.removeItem(cle);
    else sessionStorage.setItem(cle, JSON.stringify(valeur));
  } catch {
    // Stockage indisponible (navigation privée stricte) : la session vit en mémoire.
  }
}
