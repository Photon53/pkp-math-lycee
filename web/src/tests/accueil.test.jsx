import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
    expect(titres(prets)).toEqual(["Boussole Maths lycée", "Boussole Anglais collège"]);
    expect(within(prets).getByText("Seconde · Première · Terminale")).toBeInTheDocument();
    expect(within(prets).getByText("4e · 3e")).toBeInTheDocument();
    expect(within(prets).getAllByText("Ouvert")).toHaveLength(2);

    expect(titres(chantiers)).toEqual(["Boussole Maths collège", "Boussole Anglais lycée", "Boussole Français collège", "Boussole Français lycée"]);
    expect(within(chantiers).getAllByText("En construction")).toHaveLength(4);
  });

  it("suit l'état renvoyé par l'API : maths collège passe dans les prêts une fois public", async () => {
    const domaines = DOMAINES_PAR_DEFAUT.map((d) => (d.code === "maths-college" ? { ...d, etat: "ouvert" } : d));
    domaines[3] = { ...domaines[3], etat: "en_preparation" }; // anglais lycée en cours de rédaction
    fausseApi({ "GET /domaines/publics": { json: domaines } });
    render(<Accueil />);

    await waitFor(() => expect(titres(listes().prets)).toContain("Boussole Maths collège"));
    const { chantiers } = listes();
    expect(titres(chantiers)).toEqual(["Boussole Anglais lycée", "Boussole Français collège", "Boussole Français lycée"]);
    expect(within(chantiers).getByText("En préparation")).toBeInTheDocument();
  });

  it("garde l'état connu si l'API ne répond pas", async () => {
    fausseApi({ "GET /domaines/publics": { status: 500 } });
    render(<Accueil />);
    await new Promise((r) => setTimeout(r, 0));
    const { prets, chantiers } = listes();
    expect(titres(prets)).toEqual(["Boussole Maths lycée", "Boussole Anglais collège"]);
    expect(titres(chantiers)).toHaveLength(4);
  });
});

describe("page d'accueil : attirer élèves, parents et professeurs", () => {
  it("propose une entrée par profil dès le haut de la page", () => {
    fausseApi({});
    render(<Accueil />);
    for (const profil of ["Je suis élève", "Je suis parent", "Je suis professeur"]) {
      expect(screen.getByRole("heading", { level: 3, name: profil })).toBeInTheDocument();
    }
    const liens = {
      "Élève — Maths": "/eleve",
      "Élève — Anglais": "/anglais/eleve",
      "Parent — Espace parent": "/parent",
      "Professeur — Maths": "/enseignant",
      "Professeur — Anglais": "/anglais",
    };
    for (const [nom, href] of Object.entries(liens)) expect(screen.getByRole("link", { name: nom })).toHaveAttribute("href", href);
    // Les profils viennent avant les parcours dans l'ordre de lecture.
    const titres = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(titres.indexOf("Accéder à mon espace")).toBeLessThan(titres.indexOf("Les parcours"));
    expect(screen.getByRole("heading", { level: 2, name: "Comment ça marche" })).toBeInTheDocument();
  });

  it("présente Boussole et la Méthode Spirale", () => {
    fausseApi({});
    render(<Accueil />);
    expect(screen.getByText(/on revient sur les notions jusqu'à ce qu'elles tiennent/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Découvrir la Méthode Spirale" })).toHaveAttribute("href", "/methode");
    expect(document.body.textContent).not.toMatch(/\bPKP\b/);
  });

  it("affiche les chiffres clés renvoyés par l'API, sans les zéros", async () => {
    fausseApi({ "GET /domaines/chiffres": { json: { chapitres: 42, questions: 1234, seances_anglais: 0 } } });
    render(<Accueil />);
    const liste = await screen.findByText("questions corrigées en maths");
    const chiffres = liste.closest("ul.chiffres-cles");
    expect(within(chiffres).getByText("42")).toBeInTheDocument();
    expect(within(chiffres).getByText(/^1.234$/)).toBeInTheDocument(); // espace insécable fine en français
    expect(within(chiffres).queryByText(/séances d'anglais/)).not.toBeInTheDocument();
    expect(within(chiffres).getByText("Par des profs")).toBeInTheDocument();
  });

  it("laisse essayer une question sans compte, avec la correction", async () => {
    const appels = fausseApi({});
    render(<Accueil />);
    const verifier = await screen.findByRole("button", { name: "Vérifier ma réponse" }, { timeout: 15_000 }); // KaTeX chargé à la demande
    expect(verifier).toBeDisabled();
    const choix = screen.getAllByRole("radio");
    await userEvent.click(choix[0]); // x² + 9 : le piège
    await userEvent.click(verifier);
    expect(screen.getByText("Pas tout à fait.")).toBeInTheDocument();
    expect(screen.getByText(/oublie le double produit/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Réessayer" }));
    await userEvent.click(screen.getAllByRole("radio")[1]);
    await userEvent.click(screen.getByRole("button", { name: "Vérifier ma réponse" }));
    expect(screen.getByText("Bravo, c'est juste !")).toBeInTheDocument();
    // Rien n'est envoyé au serveur : seules les deux lectures publiques de l'accueil.
    expect(new Set(appels.map((a) => a.cle))).toEqual(new Set(["GET /domaines/publics", "GET /domaines/chiffres"]));
  });

  it("répond aux questions fréquentes des familles", async () => {
    fausseApi({});
    render(<Accueil />);
    const question = screen.getByText("Faut-il installer une application ?");
    await userEvent.click(question);
    expect(question.closest("details")).toHaveAttribute("open");
    expect(screen.getByText(/s'utilise dans le navigateur/)).toBeVisible();
    // Masquées pour l'instant, à la demande du professeur.
    expect(screen.queryByText("Quelles données sont enregistrées sur mon enfant ?")).not.toBeInTheDocument();
    expect(screen.queryByText("Qui prépare les cours et les exercices ?")).not.toBeInTheDocument();
    expect(screen.getAllByRole("group").filter((d) => d.tagName === "DETAILS")).toHaveLength(2);
  });
});
