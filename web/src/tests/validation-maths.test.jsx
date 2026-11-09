import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import Exercices from "../admin/Exercices.jsx";
import { fausseApi } from "./setup.js";

// Ticket #29 : le bouton « Valider » ne s'affiche qu'à qui peut valider, et chaque décision a un retour visible.
const QUESTION = {
  id: 7, code: "2NDE-MOY-01", competence_id: 3, competence: "Moyenne", chapitre: "Statistiques", niveau: "2nde",
  enonce: "Moyenne de 8 et 12 ?", type: "numerique", solution: "10", difficulte: 1, archivee: false, forme: null,
  source: "PKP Math", source_url: null, licence_source: null, adaptation: "originale", statut_validation: "a-valider",
  valide_par: null, valide_le: null, auteur: "Brouillon IA (Claude)", nb_reponses: 0, taux_reussite: null, peut_valider: true,
};
const PAGE = (q) => ({ json: { total: 1, elements: [q] } });

describe("validation des exercices de maths", () => {
  it("espace validateur : valide sur son périmètre, sans création ni archivage", async () => {
    const appels = fausseApi({
      "GET /enseignants/validation/questions?page=1&archivees=false": PAGE(QUESTION),
      "GET /enseignants/validation/contenu": { json: [] },
      "POST /enseignants/validation/questions/7/validation": { json: { ...QUESTION, statut_validation: "validee" } },
    });
    render(<Exercices jeton="j" onExpire={vi.fn()} base="/enseignants/validation" />);
    const ligne = (await screen.findByText("2NDE-MOY-01", { exact: false })).closest("tr");
    expect(screen.queryByRole("button", { name: /Nouvelle question/ })).toBeNull();
    expect(within(ligne).queryByRole("button", { name: "Archiver" })).toBeNull();
    await userEvent.click(within(ligne).getByRole("button", { name: "Valider" }));
    expect(appels.find((a) => a.cle === "POST /enseignants/validation/questions/7/validation").corps).toEqual({ statut: "validee" });
    expect(await within(ligne).findByRole("status")).toHaveTextContent("Question validée.");
  });

  it("un refus de l'API s'affiche sur la ligne de la question", async () => {
    fausseApi({
      "GET /admin/questions?page=1&archivees=false": PAGE(QUESTION),
      "GET /admin/contenu": { json: [] },
      "POST /admin/questions/7/validation": { status: 422, json: { detail: "Vous êtes l'auteur de cette question." } },
    });
    render(<Exercices jeton="j" onExpire={vi.fn()} />);
    const ligne = (await screen.findByText("2NDE-MOY-01", { exact: false })).closest("tr");
    await userEvent.click(within(ligne).getByRole("button", { name: "Valider" }));
    expect(await within(ligne).findByRole("alert")).toHaveTextContent("auteur");
  });

  it("sans habilitation de validateur, pas de bouton Valider", async () => {
    fausseApi({
      "GET /admin/questions?page=1&archivees=false": PAGE({ ...QUESTION, peut_valider: false }),
      "GET /admin/contenu": { json: [] },
    });
    render(<Exercices jeton="j" onExpire={vi.fn()} />);
    const ligne = (await screen.findByText("2NDE-MOY-01", { exact: false })).closest("tr");
    expect(within(ligne).queryByRole("button", { name: "Valider" })).toBeNull();
    expect(within(ligne).getByText(/réservée aux validateurs/)).toBeInTheDocument();
  });
});
