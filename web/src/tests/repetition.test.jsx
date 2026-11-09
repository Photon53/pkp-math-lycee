import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import Exercice from "../eleve/Exercice.jsx";
import { fausseApi } from "./setup.js";

// Ticket #26 : quand tout est réussi, l'élève le sait et choisit de réviser ou de terminer.
const QUESTION = { id: 7, competence_id: 1, enonce: "Calculer 2 + 2.", type: "numerique", difficulte: 1 };

describe("banque épuisée", () => {
  it("toutes les questions réussies : révision possible, à la demande", async () => {
    const appels = fausseApi({
      "POST /seances": { status: 201, json: { id: 3 } },
      "GET /seances/3/question": { status: 204 },
      "GET /seances/3/epuisement": { json: { motif: "toutes-reussies", nb_questions: 2, nb_au_repos: 2 } },
      "GET /seances/3/question?revision=true": { json: QUESTION },
    });
    render(<Exercice jeton="j" onExpire={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Démarrer une séance" }));
    expect(await screen.findByText(/Tu as réussi toutes les questions/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Réviser les questions réussies" }));
    expect(await screen.findByText("Calculer 2 + 2.")).toBeInTheDocument();
    expect(appels.at(-1).cle).toBe("GET /seances/3/question?revision=true");
  });

  it("aucune question : pas de bouton de révision", async () => {
    fausseApi({
      "POST /seances": { status: 201, json: { id: 3 } },
      "GET /seances/3/question": { status: 204 },
      "GET /seances/3/epuisement": { json: { motif: "aucune-question", nb_questions: 0, nb_au_repos: 0 } },
    });
    render(<Exercice jeton="j" onExpire={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Démarrer une séance" }));
    expect(await screen.findByText(/pas encore ajouté de questions/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Réviser les questions réussies" })).toBeNull();
  });
});
