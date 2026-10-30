// Point d'accès unique à l'API : toutes les requêtes passent par ici.

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

function messageErreur(status, data) {
  const detail = data?.detail;
  if (typeof detail === "string") return detail;
  // Erreur de validation FastAPI : liste d'erreurs, on garde la première.
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg.replace(/^Value error, /, "");
  if (status >= 500) return "Le serveur a rencontré un problème. Réessaie dans un instant.";
  return `Erreur ${status}`;
}

async function envoyer(chemin, { methode, entetes, corps }) {
  try {
    return await fetch(`/api${chemin}`, { method: methode, headers: entetes, body: corps });
  } catch {
    throw new ApiError(0, "Impossible de joindre le serveur. Vérifie ta connexion.");
  }
}

async function erreurSiEchec(reponse) {
  if (reponse.ok) return;
  const data = await reponse.json().catch(() => null);
  throw new ApiError(reponse.status, messageErreur(reponse.status, data));
}

export async function api(chemin, { methode = "GET", corps, jeton } = {}) {
  const entetes = {};
  if (corps !== undefined) entetes["Content-Type"] = "application/json";
  if (jeton) entetes.Authorization = `Bearer ${jeton}`;

  const reponse = await envoyer(chemin, {
    methode,
    entetes,
    corps: corps === undefined ? undefined : JSON.stringify(corps),
  });
  if (reponse.status === 204) return null;
  const data = await reponse.json().catch(() => null);
  if (!reponse.ok) throw new ApiError(reponse.status, messageErreur(reponse.status, data));
  return data;
}

/** Envoie un fichier PDF brut (corps de la requête), comme l'attend l'API. */
export async function envoyerPdf(chemin, fichier, jeton) {
  const reponse = await envoyer(chemin, {
    methode: "PUT",
    entetes: { "Content-Type": "application/pdf", Authorization: `Bearer ${jeton}` },
    corps: fichier,
  });
  await erreurSiEchec(reponse);
  return reponse.json();
}

/**
 * Ouvre un PDF protégé dans un nouvel onglet : le jeton ne peut pas voyager dans un simple lien,
 * on télécharge donc le fichier avec l'en-tête Authorization puis on l'ouvre localement.
 */
export async function ouvrirPdf(ressourceId, jeton) {
  const onglet = window.open("", "_blank");
  try {
    const reponse = await envoyer(`/ressources/${ressourceId}/fichier`, {
      methode: "GET",
      entetes: { Authorization: `Bearer ${jeton}` },
    });
    await erreurSiEchec(reponse);
    const url = URL.createObjectURL(await reponse.blob());
    if (onglet) onglet.location.href = url;
    else window.location.href = url;
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  } catch (err) {
    onglet?.close();
    throw err;
  }
}

/** Compte l'ouverture d'un lien externe (sans identifier l'élève), puis l'ouvre. */
export function ouvrirLien(ressource, jeton) {
  envoyer(`/ressources/${ressource.id}/ouverture`, {
    methode: "POST",
    entetes: { Authorization: `Bearer ${jeton}` },
  }).catch(() => {});
}
