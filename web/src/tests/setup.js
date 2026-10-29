import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

// jsdom n'implémente pas le défilement de la fenêtre.
window.scrollTo = () => {};

afterEach(() => {
  cleanup();
  sessionStorage.clear();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

/**
 * Remplace fetch par une fausse API : `routes` associe « MÉTHODE /chemin » à
 * une réponse { status, json } ou à une fonction (corps) => réponse.
 */
export function fausseApi(routesDuTest) {
  // Par défaut, la classe a un chapitre ouvert avec des questions (écran d'accueil des séances).
  const routes = {
    "GET /eleves/moi/chapitres": { json: [{ id: 1, code: "CH-TEST", titre: "Chapitre test", nb_questions: 5 }] },
    ...routesDuTest,
  };
  const appels = [];
  const fetch = vi.fn(async (url, { method = "GET", body } = {}) => {
    const cle = `${method} ${url.replace(/^\/api/, "")}`;
    const corps = body ? JSON.parse(body) : undefined;
    appels.push({ cle, corps });
    let route = routes[cle];
    if (typeof route === "function") route = route(corps);
    if (!route) throw new Error(`Route non simulée : ${cle}`);
    const { status = 200, json = null } = route;
    return { ok: status < 400, status, json: async () => json };
  });
  vi.stubGlobal("fetch", fetch);
  return appels;
}
