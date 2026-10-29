import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import Classes from "../enseignant/Classes.jsx";
import Questions from "../enseignant/Questions.jsx";
import { fausseApi } from "./setup.js";

const CLASSES = [{ id: 1, code: "2NDE-A-DEMO", niveau: "2nde", parcours: "tronc-commun", nb_eleves: 2 }];
const ELEVES = [
  { id: 1, prenom: "Lina", a_un_code: true, nb_reponses: 5, taux_reussite: 0.6, competences_maitrisees: 1, competences_total: 4 },
  { id: 2, prenom: "Yanis", a_un_code: true, nb_reponses: 0, taux_reussite: null, competences_maitrisees: 0, competences_total: 4 },
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
    expect(await screen.findByText("Aucun élève inscrit pour l'instant.")).toBeInTheDocument();
  });
});

describe("spécialité des classes", () => {
  it("propose la spécialité en Terminale seulement, et l'envoie à la création", async () => {
    const appels = fausseApi({
      "GET /enseignants/classes": { json: CLASSES },
      "POST /enseignants/classes": (corps) => ({ status: 201, json: { id: 9, code: "TLE-ABCDE", ...corps, nb_eleves: 0 } }),
      "GET /enseignants/classes/9/eleves": { json: [] },
    });
    render(<Classes jeton="j" onExpire={vi.fn()} />);
    expect(await screen.findByText(/Seconde · Tronc commun · 2 élèves/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Spécialité de la nouvelle classe")).not.toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Niveau de la nouvelle classe"), "Tle");
    await userEvent.selectOptions(screen.getByLabelText("Spécialité de la nouvelle classe"), "expertes");
    await userEvent.click(screen.getByRole("button", { name: "Créer une classe" }));
    expect(appels.find((a) => a.cle === "POST /enseignants/classes").corps).toEqual({ niveau: "Tle", parcours: "expertes" });
  });
});

describe("codes personnels des élèves", () => {
  it("inscrit des élèves et affiche leurs codes une seule fois, imprimables", async () => {
    let eleves = ELEVES;
    const appels = fausseApi({
      "GET /enseignants/classes": { json: CLASSES },
      "GET /enseignants/classes/1/eleves": () => ({ json: eleves }),
      "POST /enseignants/classes/1/eleves": (corps) => {
        eleves = [...ELEVES, { ...ELEVES[1], id: 3, prenom: "Noé" }];
        return { status: 201, json: { crees: [{ id: 3, prenom: "Noé", code: "K7M4QP" }], deja_presents: ["Lina"] } };
      },
    });
    const imprimer = vi.spyOn(window, "print").mockImplementation(() => {});
    render(<Classes jeton="j" onExpire={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: /2NDE-A-DEMO/ }));
    await userEvent.type(await screen.findByLabelText(/Inscrire des élèves/), "Noé{Enter}  {Enter}Lina");
    await userEvent.click(screen.getByRole("button", { name: "Inscrire et générer les codes" }));
    expect(appels.find((a) => a.cle === "POST /enseignants/classes/1/eleves").corps).toEqual({ prenoms: ["Noé", "Lina"] });
    const fiche = await screen.findByRole("region", { name: "Codes personnels à distribuer" });
    expect(within(fiche).getByText("K7M4QP")).toBeInTheDocument();
    expect(screen.getByText("Déjà inscrit(s), ignoré(s) : Lina.")).toBeInTheDocument();
    await userEvent.click(within(fiche).getByRole("button", { name: "Imprimer" }));
    expect(imprimer).toHaveBeenCalled();
    await userEvent.click(within(fiche).getByRole("button", { name: "J'ai noté les codes" }));
    expect(screen.queryByText("K7M4QP")).not.toBeInTheDocument();
  });

  it("nouveau code après confirmation, et codes manquants pour les élèves d'avant", async () => {
    let eleves = [ELEVES[0], { ...ELEVES[1], a_un_code: false }];
    const appels = fausseApi({
      "GET /enseignants/classes": { json: CLASSES },
      "GET /enseignants/classes/1/eleves": () => ({ json: eleves }),
      "POST /enseignants/eleves/1/code": { json: { id: 1, prenom: "Lina", code: "NEW234" } },
      "POST /enseignants/classes/1/codes-manquants": () => {
        eleves = ELEVES;
        return { json: [{ id: 2, prenom: "Yanis", code: "YAN234" }] };
      },
    });
    const confirmer = vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
    render(<Classes jeton="j" onExpire={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: /2NDE-A-DEMO/ }));
    expect(await screen.findByText("sans code")).toBeInTheDocument();

    const bouton = screen.getByRole("button", { name: "Nouveau code pour Lina" });
    await userEvent.click(bouton);
    expect(appels.some((a) => a.cle === "POST /enseignants/eleves/1/code")).toBe(false);
    await userEvent.click(bouton);
    expect(confirmer.mock.calls[1][0]).toContain("L'ancien code ne fonctionnera plus");
    expect(await screen.findByText("NEW234")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Générer les codes manquants" }));
    expect(await screen.findByText("YAN234")).toBeInTheDocument();
    expect(screen.queryByText("sans code")).not.toBeInTheDocument();
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
