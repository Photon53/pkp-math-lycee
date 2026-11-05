import { render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Accueil from "../Accueil.jsx";
import { DOMAINES_PAR_DEFAUT } from "../parcoursPublics.js";
import { fausseApi } from "./setup.js";

const titres = (liste) => within(liste).getAllByRole("heading", { level: 4 }).map((h) => h.textContent);
const listes = () => ({
  prets: screen.getByRole("list", { name: /Prêts/ }),
  chantiers: screen.getByRole("list", { name: "En chantier" }),
});

describe("page d'accueil : état des parcours", () => {
  it("affiche les parcours prêts et les chantiers sous des titres hiérarchisés", async () => {
    const appels = fausseApi({ "GET /domaines/publics": { json: DOMAINES_PAR_DEFAUT } });
    render(<Accueil />);

    expect(screen.getByRole("heading", { level: 2, name: "Les parcours" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3, name: /Prêts/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3, name: "En chantier" })).toBeInTheDocument();
    await waitFor(() => expect(appels.some((a) => a.cle === "GET /domaines/publics")).toBe(true));

    const { prets, chantiers } = listes();
    expect(titres(prets)).toEqual(["PKP Maths lycée", "PKP Anglais collège"]);
    expect(within(prets).getByText("Seconde · Première · Terminale")).toBeInTheDocument();
    expect(within(prets).getByText("4e · 3e")).toBeInTheDocument();
    expect(within(prets).getAllByText("Ouvert")).toHaveLength(2);

    expect(titres(chantiers)).toEqual(["PKP Maths collège", "PKP Anglais lycée", "PKP Français collège", "PKP Français lycée"]);
    expect(within(chantiers).getAllByText("En construction")).toHaveLength(4);
  });

  it("suit l'état renvoyé par l'API : maths collège passe dans les prêts une fois public", async () => {
    const domaines = DOMAINES_PAR_DEFAUT.map((d) => (d.code === "maths-college" ? { ...d, etat: "ouvert" } : d));
    domaines[3] = { ...domaines[3], etat: "en_preparation" }; // anglais lycée en cours de rédaction
    fausseApi({ "GET /domaines/publics": { json: domaines } });
    render(<Accueil />);

    await waitFor(() => expect(titres(listes().prets)).toContain("PKP Maths collège"));
    const { chantiers } = listes();
    expect(titres(chantiers)).toEqual(["PKP Anglais lycée", "PKP Français collège", "PKP Français lycée"]);
    expect(within(chantiers).getByText("En préparation")).toBeInTheDocument();
  });

  it("garde l'état connu si l'API ne répond pas", async () => {
    fausseApi({ "GET /domaines/publics": { status: 500 } });
    render(<Accueil />);
    await new Promise((r) => setTimeout(r, 0));
    const { prets, chantiers } = listes();
    expect(titres(prets)).toEqual(["PKP Maths lycée", "PKP Anglais collège"]);
    expect(titres(chantiers)).toHaveLength(4);
  });
});
