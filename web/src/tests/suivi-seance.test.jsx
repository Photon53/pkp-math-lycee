import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import EnDirect, { INTERVALLE_MS } from "../enseignant/EnDirect.jsx";
import { AideExercice, AvisCours } from "../eleve/Comprehension.jsx";
import { fausseApi } from "./setup.js";

// Ticket #28 : tableau du professeur en séance, avis « compris / pas compris » des élèves.
const TABLEAU = {
  genere_le: "2026-11-09T09:00:00Z", depuis: "2026-11-09T07:00:00Z", jusqua: "2026-11-09T09:00:00Z",
  compteurs: { demandes_cours: 1, demandes_exercices: 0, demandes_corriges: 1, resolues: 0, eleves_actifs: 2 },
  notions: [{ competence_id: 3, competence: "Fonctions affines", chapitre: "Fonctions", nb_eleves_en_difficulte: 2, taux_erreur: 0.5, nb_demandes: 2 }],
  demandes_cours: [{ id: 11, objet: "cours", statut: "ouverte", eleve: "Lina", classe: "2NDE-A", competence_id: 3, competence: "Fonctions affines", chapitre: "Fonctions", cree_le: "2026-11-09T08:50:00Z" }],
  demandes_exercices: [{ id: 12, objet: "corrige", statut: "ouverte", eleve: "Yanis", classe: "2NDE-A", competence_id: 3, competence: "Fonctions affines", chapitre: "Fonctions", question_id: 7, question_code: "AFF-04", cree_le: "2026-11-09T08:55:00Z" }],
  questions: [{
    question_id: 7, code: "AFF-04", enonce: "Calculer f(10).", solution: "21", correction: null, competence_id: 3, competence: "Fonctions affines",
    chapitre: "Fonctions", nb_tentatives: 4, nb_eleves: 2, nb_reussites: 2, nb_erreurs: 2, taux_erreur: 0.5,
    eleves_en_echec: ["Yanis"], nb_reussies_apres_erreur: 1, eleves_sans_reponse: ["Lina"],
  }],
};

afterEach(() => vi.useRealTimers());

describe("séance en direct (professeur)", () => {
  it("affiche notions, demandes et questions, puis traite une demande", async () => {
    const appels = fausseApi({
      "GET /enseignants/classes": { json: [{ id: 1, code: "2NDE-A" }] },
      "POST /enseignants/demandes/12": { json: { ...TABLEAU.demandes_exercices[0], statut: "resolue" } },
    });
    const routeTableau = (cle) => cle.startsWith("GET /enseignants/seance-en-direct?");
    const fetchAvant = globalThis.fetch;
    globalThis.fetch = vi.fn(async (url, opts = {}) => {
      const cle = `${opts.method ?? "GET"} ${url.replace(/^\/api/, "")}`;
      if (routeTableau(cle)) {
        appels.push({ cle });
        return { ok: true, status: 200, json: async () => TABLEAU };
      }
      return fetchAvant(url, opts);
    });
    render(<EnDirect jeton="j" onExpire={vi.fn()} />);
    expect(await screen.findByText("Fonctions affines", { selector: "strong" })).toBeInTheDocument();
    expect(screen.getByText("Yanis", { exact: false, selector: "strong" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Lina" })).toBeInTheDocument(); // sans réponse
    await userEvent.click(screen.getByRole("checkbox", { name: /Erreurs uniquement/ }));
    expect(appels.filter((a) => routeTableau(a.cle)).at(-1).cle).toContain("erreurs_uniquement=true");
    const demande = screen.getByText("Yanis", { selector: "strong" }).closest("li");
    await userEvent.click(within(demande).getByRole("button", { name: "Résolue" }));
    expect(appels.some((a) => a.cle === "POST /enseignants/demandes/12" && a.corps.statut === "resolue")).toBe(true);
  });

  it("s'actualise tout seul", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let n = 0;
    fausseApi({ "GET /enseignants/classes": { json: [] } });
    const fetchAvant = globalThis.fetch;
    globalThis.fetch = vi.fn(async (url, opts = {}) => {
      if (url.includes("/enseignants/seance-en-direct?")) {
        n += 1;
        return { ok: true, status: 200, json: async () => TABLEAU };
      }
      return fetchAvant(url, opts);
    });
    render(<EnDirect jeton="j" onExpire={vi.fn()} />);
    await screen.findByText(/Actualisé à/);
    const avant = n;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(INTERVALLE_MS + 100);
    });
    expect(n).toBeGreaterThan(avant);
  });
});

describe("avis des élèves", () => {
  it("j'ai compris / je n'ai pas compris un cours, et changer d'avis", async () => {
    const appels = fausseApi({
      "GET /eleves/moi/comprehension/3": { json: { competence_id: 3, compris: null } },
      "POST /eleves/moi/comprehension": (corps) => ({ json: { competence_id: 3, compris: corps.compris } }),
    });
    render(<AvisCours competenceId={3} jeton="j" />);
    await userEvent.click(await screen.findByRole("button", { name: "Je n'ai pas compris" }));
    expect(await screen.findByText(/Ton professeur est prévenu/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "J'ai compris" }));
    expect(screen.getByRole("button", { name: "J'ai compris" })).toHaveAttribute("aria-pressed", "true");
    expect(appels.filter((a) => a.cle === "POST /eleves/moi/comprehension").map((a) => a.corps.compris)).toEqual([false, true]);
  });

  it("je n'ai pas compris la correction d'un exercice", async () => {
    const appels = fausseApi({ "POST /seances/5/aide": { status: 201, json: { id: 1, objet: "corrige", statut: "ouverte", cree_le: "" } } });
    render(<AideExercice seanceId={5} questionId={7} jeton="j" avecCorrection />);
    await userEvent.click(screen.getByRole("button", { name: "Je n'ai pas compris la correction" }));
    expect(appels.at(-1).corps).toEqual({ question_id: 7, objet: "corrige" });
    expect(await screen.findByRole("button", { name: "Demande envoyée à ton professeur" })).toBeDisabled();
  });
});
