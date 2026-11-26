// Issue #180 — Mon cours : fiches de la professeure au fil du cours (Claude)
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import EspaceEleve from "../eleve/EspaceEleve.jsx";
import MonCours from "../eleve/MonCours.jsx";
import { fausseApi } from "./setup.js";

const LIEN = {
  id: 9, type: "lien", titre: "Tableau de conjugaison", description: "", url: "https://fr.wikipedia.org/wiki/Conjugaison",
  domaine: "fr.wikipedia.org", taille_octets: null, portee: "classe",
};

describe("Mon cours (#180)", () => {
  it("montre les chapitres ouverts dans l'ordre, avec les liens de la professeure", async () => {
    fausseApi({
      "GET /cours/mon-cours": {
        json: [
          { id: 1, titre: "Le présent", ressources: [LIEN] },
          { id: 2, titre: "L'imparfait", ressources: [] },
        ],
      },
    });
    render(<MonCours jeton="j" onExpire={vi.fn()} />);
    expect(await screen.findByRole("heading", { name: "Le présent" })).toBeInTheDocument();
    const lien = screen.getByRole("link", { name: "Tableau de conjugaison" });
    expect(lien).toHaveAttribute("href", "https://fr.wikipedia.org/wiki/Conjugaison");
    expect(lien).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.getByRole("heading", { name: "L'imparfait" })).toBeInTheDocument();
    expect(screen.getByText("Pas encore de fiche pour ce chapitre.")).toBeInTheDocument();
  });

  it("annonce qu'aucun chapitre n'est encore ouvert", async () => {
    fausseApi({ "GET /cours/mon-cours": { json: [] } });
    render(<MonCours jeton="j" onExpire={vi.fn()} />);
    expect(await screen.findByText("Ta professeure n'a pas encore ouvert de chapitre.")).toBeInTheDocument();
  });
});

describe("onglet « Mon cours » selon la matière (#180)", () => {
  const session = (matiere) =>
    sessionStorage.setItem(
      "pkp.eleve",
      JSON.stringify({ jeton: "j", eleve: { id: 1, prenom: "Lina", code_classe: "5E-FR-AAAAA", niveau: "5e", matiere } }),
    );

  it("apparaît pour une classe de français", async () => {
    session("francais");
    fausseApi({});
    render(<EspaceEleve />);
    expect(await screen.findByRole("tab", { name: "Mon cours" })).toBeInTheDocument();
    sessionStorage.clear();
  });

  it("les dossiers ouverts à la classe apparaissent aussi dans « Cours » (#217)", async () => {
    session("francais");
    fausseApi({
      "GET /francais/eleve/dossiers": { json: [{ code: "FR3-DNB27-01", titre: "Comprendre un texte", niveau: "3e", version: 1 }] },
      "GET /eleves/moi/cours": { json: [] },
    });
    render(<EspaceEleve />);
    expect(await screen.findByText(/les questions de tes dossiers se trouvent dans l'onglet « Cours »/)).toBeInTheDocument();
    await userEvent.click(await screen.findByRole("tab", { name: "Cours" }));
    expect(await screen.findByRole("heading", { name: "Mes dossiers" })).toBeInTheDocument();
    expect(screen.getByText(/Comprendre un texte/)).toBeInTheDocument();
    sessionStorage.clear();
  });

  it("n'apparaît pas pour une classe de maths", async () => {
    session("maths");
    fausseApi({});
    render(<EspaceEleve />);
    expect(await screen.findByRole("tab", { name: "S'entraîner" })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Mon cours" })).not.toBeInTheDocument();
    sessionStorage.clear();
  });
});
