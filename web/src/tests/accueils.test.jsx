// Issue #148 — Accueils Boussole et PKP (Claude)
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import Accueil from "../Accueil.jsx";
import Exercice from "../eleve/Exercice.jsx";
import { MARQUES, marqueDe } from "../marque.js";
import { DOMAINES_PAR_DEFAUT } from "../parcoursPublics.js";
import { fausseApi } from "./setup.js";

const QUESTION = { id: 7, competence_id: 4, enonce: "Développer (x + 3)².", type: "expression", difficulte: 2 };
// Routes et ancres réellement servies par l'application (App.jsx) : aucun lien de l'accueil ne sort de cette liste.
const ROUTES = ["/eleve", "/anglais/eleve", "/parent", "/enseignant", "/anglais", "/francais", "/methode", "#titre-methode", "#titre-exemple"];

describe("choix de la variante", () => {
  it("prend Boussole par défaut, y compris pour une valeur inconnue", () => {
    expect(marqueDe(undefined)).toBe(MARQUES.boussole);
    expect(marqueDe("")).toBe(MARQUES.boussole);
    expect(marqueDe("autre")).toBe(MARQUES.boussole);
    expect(marqueDe(" PKP ")).toBe(MARQUES.pkp);
  });
});

describe.each([
  ["boussole", "Comprendre, progresser, prendre confiance !", "Boussole Maths lycée", /\bPKP\b/],
  ["pkp", "Apprendre à son rythme, accompagné par des professeurs", "PKP Maths lycée", /Boussole|Spirale|Maîtrise\+/],
])("accueil public %s", (code, titre, parcours, absent) => {
  const marque = marqueDe(code);

  it("met en avant une seule action principale vers l'espace élève", () => {
    fausseApi({});
    render(<Accueil marque={marque} />);
    expect(screen.getByRole("heading", { level: 1, name: titre })).toBeInTheDocument();
    const hero = screen.getByRole("heading", { level: 1 }).closest("section");
    const principales = within(hero).getAllByRole("link").filter((l) => !l.classList.contains("secondaire"));
    expect(principales).toHaveLength(1);
    expect(principales[0]).toHaveTextContent("Commencer à travailler");
    expect(principales[0]).toHaveAttribute("href", "/eleve");
  });

  it("présente la méthode en cinq étapes courtes", () => {
    fausseApi({});
    render(<Accueil marque={marque} />);
    const section = screen.getByRole("heading", { level: 2, name: "La méthode en cinq étapes" }).closest("section");
    const etapes = within(section).getAllByRole("listitem").map((li) => li.querySelector("strong").textContent);
    expect(etapes).toEqual(["Je comprends", "Je mémorise", "Je m'entraîne", "Je me dépasse", "Je vérifie"]);
    expect(within(section).getByRole("link")).toHaveAttribute("href", "/methode");
  });

  it("garde sa propre identité, sans tarif ni lien mort", async () => {
    fausseApi({ "GET /domaines/publics": { json: DOMAINES_PAR_DEFAUT } });
    render(<Accueil marque={marque} />);
    expect(await screen.findByRole("heading", { level: 4, name: parcours })).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(absent);
    expect(document.body.textContent).not.toMatch(/€|tarif|abonnement|\bprix\b/i);
    for (const lien of screen.getAllByRole("link")) expect(ROUTES).toContain(lien.getAttribute("href"));
  });

  it("n'ouvre pas le français aux élèves ni aux parents", () => {
    fausseApi({});
    render(<Accueil marque={marque} />);
    const francais = screen.getAllByRole("link").filter((l) => l.getAttribute("href") === "/francais");
    expect(francais).toHaveLength(1);
    expect(francais[0]).toHaveAccessibleName("Professeur — Français (préparation)");
  });
});

describe("accueil élève connecté", () => {
  it("sans séance : « Commencer à travailler » ouvre une séance sur les chapitres cochés", async () => {
    const appels = fausseApi({
      "POST /seances": { status: 201, json: { id: 3 } },
      "GET /seances/3/question": { json: QUESTION },
    });
    render(<Exercice jeton="j" onExpire={vi.fn()} />);
    expect(screen.queryByRole("button", { name: "Reprendre ma séance" })).not.toBeInTheDocument();
    await screen.findByRole("checkbox", { name: /Chapitre test/ });
    expect(screen.getByText("Comment bien travailler ?")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Commencer à travailler" }));
    expect(await screen.findByText("Développer (x + 3)².")).toBeInTheDocument();
    expect(appels.find((a) => a.cle === "POST /seances").corps).toEqual({ chapitre_ids: [1] });
  });

  it("avec séance : « Reprendre ma séance » rouvre la même question, sans nouvelle séance", async () => {
    sessionStorage.setItem("pkp.seance", "3");
    sessionStorage.setItem("pkp.bilan", JSON.stringify({ reponses: 2, reussies: 1 }));
    const appels = fausseApi({ "GET /seances/3/question": { json: QUESTION } });
    render(<Exercice jeton="j" onExpire={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "Ta séance t'attend" })).toBeInTheDocument();
    expect(screen.getByText(/déjà répondu à 2 questions/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Choisir un autre chapitre" })).toBeInTheDocument();
    expect(appels).toHaveLength(0); // rien n'est demandé avant le choix de l'élève

    await userEvent.click(screen.getByRole("button", { name: "Reprendre ma séance" }));
    expect(await screen.findByText("Développer (x + 3)².")).toBeInTheDocument();
    expect(appels.map((a) => a.cle)).toEqual(["GET /seances/3/question"]);
    expect(sessionStorage.getItem("pkp.seance")).toBe("3");
  });

  it("« Choisir un autre chapitre » garde la reprise possible, puis close l'ancienne séance avant d'en ouvrir une", async () => {
    sessionStorage.setItem("pkp.seance", "3");
    const appels = fausseApi({
      "POST /seances/3/fin": { json: { id: 3 } },
      "POST /seances": { status: 201, json: { id: 8 } },
      "GET /seances/8/question": { json: QUESTION },
    });
    render(<Exercice jeton="j" onExpire={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Choisir un autre chapitre" }));
    await screen.findByRole("checkbox", { name: /Chapitre test/ });
    expect(screen.getByRole("button", { name: "Reprendre ma séance" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Commencer à travailler" }));
    await screen.findByText("Développer (x + 3)².");
    const cles = appels.map((a) => a.cle);
    expect(cles.indexOf("POST /seances/3/fin")).toBeLessThan(cles.indexOf("POST /seances"));
    expect(sessionStorage.getItem("pkp.seance")).toBe("8");
  });

  it("séance close entre-temps : l'élève est prévenu et revient au choix des chapitres", async () => {
    sessionStorage.setItem("pkp.seance", "3");
    fausseApi({ "GET /seances/3/question": { status: 404, json: { detail: "Séance introuvable." } } });
    render(<Exercice jeton="j" onExpire={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Reprendre ma séance" }));
    expect(await screen.findByText(/Ta séance précédente est terminée/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Commencer à travailler" })).toBeInTheDocument();
    expect(sessionStorage.getItem("pkp.seance")).toBeNull();
  });
});

describe("conseils contextualisés", () => {
  it("avant la réponse : essayer d'abord, relire le cours ; aucune solution affichée", async () => {
    fausseApi({ "POST /seances": { status: 201, json: { id: 3 } }, "GET /seances/3/question": { json: QUESTION } });
    const onVoirCours = vi.fn();
    render(<Exercice jeton="j" onExpire={vi.fn()} onVoirCours={onVoirCours} />);
    await userEvent.click(screen.getByRole("button", { name: "Commencer à travailler" }));
    await screen.findByText("Développer (x + 3)².");
    expect(screen.getByText(/Cherche d'abord seul·e/)).toBeInTheDocument();
    expect(screen.queryByText(/Réponse attendue/)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Relire le cours de cette notion" }));
    expect(onVoirCours).toHaveBeenCalledWith(4);
  });

  it("après une erreur : inviter à reprendre l'erreur", async () => {
    fausseApi({
      "POST /seances": { status: 201, json: { id: 3 } },
      "GET /seances/3/question": { json: QUESTION },
      "POST /seances/3/reponses": { json: { correcte: false, solution: "x^2 + 6x + 9", maitrise: 0.2, maitrisee: false } },
    });
    render(<Exercice jeton="j" onExpire={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Commencer à travailler" }));
    await userEvent.type(await screen.findByLabelText("Ta réponse"), "x{Enter}");
    await screen.findByText("Pas tout à fait.");
    expect(screen.getByText(/Reprends ton erreur/)).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText(/Cherche d'abord seul·e/)).not.toBeInTheDocument());
  });
});
