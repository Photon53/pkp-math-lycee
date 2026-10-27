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

export async function api(chemin, { methode = "GET", corps, jeton } = {}) {
  const entetes = {};
  if (corps !== undefined) entetes["Content-Type"] = "application/json";
  if (jeton) entetes.Authorization = `Bearer ${jeton}`;

  let reponse;
  try {
    reponse = await fetch(`/api${chemin}`, {
      method: methode,
      headers: entetes,
      body: corps === undefined ? undefined : JSON.stringify(corps),
    });
  } catch {
    throw new ApiError(0, "Impossible de joindre le serveur. Vérifie ta connexion.");
  }
  if (reponse.status === 204) return null;
  const data = await reponse.json().catch(() => null);
  if (!reponse.ok) throw new ApiError(reponse.status, messageErreur(reponse.status, data));
  return data;
}
