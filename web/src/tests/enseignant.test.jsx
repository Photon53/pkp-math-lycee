import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import Classes from "../enseignant/Classes.jsx";
import Questions from "../enseignant/Questions.jsx";
import { fausseApi } from "./setup.js";

const CLASSES = [{ id: 1, code: "2NDE-A-DEMO", niveau: "2nde", nb_eleves: 2 }];
const ELEVES = [
  { id: 1, prenom: "Lina", nb_reponses: 5, taux_reussite: 0.6, competences_maitrisees: 1, competences_total: 4 },
  { id: 2, prenom: "Yanis", nb_reponses: 0, taux_reussite: null, competences_maitrisees: 0, competences_total: 4 },
];

describe("classes et élèves", () => {
  it("affiche le tableau de bord d'une classe", async () => {
    fausseApi({
      "GET /enseignants/classes": { json: CLASSES },
      "GET /enseignants/classes/1/eleves": { json: ELEVES },
    });
    render(<Classes jeton="j" onExpire={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: /2NDE-A-DEMO/ }));
    const lina = (await screen.findByText("Lina")).closest("tr");
    expect(within(lina).getByText("60 %")).toBeInTheDocument();
    expect(within(lina).getByText("1 / 4")).toBeInTheDocument();
    expect(within(screen.getByText("Yanis").closest("tr")).getByText("—")).toBeInTheDocument();
  });

  it("demande confirmation avant l'effacement RGPD", async () => {
    const appels = fausseApi({
      "GET /enseignants/classes": { json: CLASSES },
      "GET /enseignants/classes/1/eleves": { json: ELEVES },
      "DELETE /enseignants/eleves/1": { status: 204 },
    });
    const confirmer = vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
    render(<Classes jeton="j" onExpire={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: /2NDE-A-DEMO/ }));
    const bouton = await screen.findByRole("button", { name: "Supprimer Lina" });

    await userEvent.click(bouton);
    expect(appels.some((a) => a.cle.startsWith("DELETE"))).toBe(false);

    await userEvent.click(bouton);
    expect(confirmer).toHaveBeenCalledTimes(2);
    expect(confirmer.mock.calls[0][0]).toContain("irréversible");
    expect(await screen.findByRole("status")).toHaveTextContent("Lina a été supprimé·e");
    expect(appels.some((a) => a.cle === "DELETE /enseignants/eleves/1")).toBe(true);
  });

  it("supprime une classe entière après confirmation", async () => {
    let classes = CLASSES;
    const appels = fausseApi({
      "GET /enseignants/classes": () => ({ json: classes }),
      "GET /enseignants/classes/1/eleves": { json: ELEVES },
      "DELETE /enseignants/classes/1": () => {
        classes = [];
        return { status: 204 };
      },
    });
    const confirmer = vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<Classes jeton="j" onExpire={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: /2NDE-A-DEMO/ }));
    await userEvent.click(await screen.findByRole("button", { name: /Supprimer la classe/ }));
    expect(confirmer.mock.calls[0][0]).toContain("2 élève(s)");
    expect(await screen.findByRole("status")).toHaveTextContent("La classe 2NDE-A-DEMO a été supprimée");
    expect(appels.some((a) => a.cle === "DELETE /enseignants/classes/1")).toBe(true);
    expect(screen.queryByText("Lina")).not.toBeInTheDocument();
  });

  it("exporte les données d'un élève en JSON", async () => {
    fausseApi({
      "GET /enseignants/classes": { json: CLASSES },
      "GET /enseignants/classes/1/eleves": { json: ELEVES },
      "GET /enseignants/eleves/1/export": { json: { eleve: { prenom: "Lina", classe: "2NDE-A-DEMO" }, seances: [] } },
    });
    URL.createObjectURL = vi.fn(() => "blob:x");
    URL.revokeObjectURL = vi.fn();
    const clic = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    render(<Classes jeton="j" onExpire={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: /2NDE-A-DEMO/ }));
    await userEvent.click(await screen.findByRole("button", { name: "Exporter les données de Lina" }));
    await vi.waitFor(() => expect(clic).toHaveBeenCalled());
    expect(clic.mock.contexts[0].download).toBe("pkp-2NDE-A-DEMO-Lina.json");
  });

  it("crée une classe et affiche son code", async () => {
    let classes = [];
    fausseApi({
      "GET /enseignants/classes": () => ({ json: classes }),
      "POST /enseignants/classes": (corps) => {
        classes = [{ id: 9, code: "1RE-7KQ4M", niveau: corps.niveau, nb_eleves: 0 }];
        return { status: 201, json: classes[0] };
      },
      "GET /enseignants/classes/9/eleves": { json: [] },
    });
    render(<Classes jeton="j" onExpire={vi.fn()} />);
    await userEvent.selectOptions(await screen.findByLabelText("Niveau de la nouvelle classe"), "1re");
    await userEvent.click(screen.getByRole("button", { name: "Créer une classe" }));
    expect(await screen.findByRole("status")).toHaveTextContent("1RE-7KQ4M");
    expect(await screen.findByText("Aucun élève connecté pour l'instant.")).toBeInTheDocument();
  });
});

describe("banque de questions", () => {
  it("affiche le refus du moteur pour une solution illisible", async () => {
    fausseApi({
      "GET /enseignants/competences": { json: [{ id: 3, code: "2NDE-DEV", libelle: "Développer", chapitre: "Calcul littéral", niveau: "2nde" }] },
      "GET /enseignants/questions?archivees=false": { json: [] },
      "POST /enseignants/questions": { status: 422, json: { detail: "Solution illisible par le moteur de correction." } },
    });
    render(<Questions jeton="j" onExpire={vi.fn()} />);
    await screen.findAllByRole("option", { name: /Développer/ });
    await userEvent.type(screen.getByLabelText("Énoncé"), "Développer (x+1)².");
    await userEvent.selectOptions(screen.getByLabelText("Type"), "expression");
    await userEvent.type(screen.getByLabelText("Solution"), "x +");
    await userEvent.click(screen.getByRole("button", { name: "Ajouter" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Solution illisible");
  });
});
