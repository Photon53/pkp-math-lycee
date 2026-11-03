// Après une mise à jour du site, une page restée ouverte réclame d'anciens fichiers (leur nom contient
// l'empreinte de leur contenu) qui n'existent plus : on recharge pour obtenir la nouvelle version.
// Une seule fois par minute, pour ne pas boucler si le fichier manque vraiment.
const CLE = "pkp-rechargement";
const DELAI_MS = 60_000;

export function rechargerApresMiseAJour(evenement, maintenant = Date.now(), recharger = () => window.location.reload()) {
  let dernier = 0;
  try {
    dernier = Number(sessionStorage.getItem(CLE)) || 0;
    if (maintenant - dernier < DELAI_MS) return;
    sessionStorage.setItem(CLE, String(maintenant));
  } catch {
    // Stockage indisponible (navigation privée stricte) : on recharge quand même, une fois.
  }
  evenement.preventDefault();
  recharger();
}
