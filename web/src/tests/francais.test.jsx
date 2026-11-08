import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { solutionLisible } from "../composants.jsx";
import EspaceEnfant from "../eleve/EspaceEnfant.jsx";
import Classes from "../enseignant/Classes.jsx";
import { fausseApi } from "./setup.js";

const CLASSE_FR = { id: 5, code: "5E-FR-ABCDE", niveau: "5e", parcours: "tronc-commun", matiere: "francais", nb_eleves: 0 };

describe("PKP Français (F1)", () => {
  it("le professeur habilité choisit la matière : pas de parcours ni de Terminale en français", async () => {
    const appels = fausseApi({
      "GET /enseignants/classes": { json: [] },
      "POST /enseignants/classes": { status: 201, json: CLASSE_FR },
      "GET /enseignants/classes/5/eleves": { json: [] },
    });
    render(<Classes jeton="j" onExpire={vi.fn()} maths francais />);
    await userEvent.selectOptions(await screen.findByLabelText("Matière de la nouvelle classe"), "francais");
    expect(screen.queryByLabelText("Parcours de la nouvelle classe")).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Terminale" })).not.toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Niveau de la nouvelle classe"), "5e");
    await userEvent.click(screen.getByRole("button", { name: "Créer une classe" }));
    expect(appels.find((a) => a.cle === "POST /enseignants/classes").corps).toEqual({ matiere: "francais", niveau: "5e" });
    expect(await screen.findByText(/5E-FR-ABCDE/, { selector: ".succes" })).toBeInTheDocument();
  });

  it("sans habilitation en français, pas de choix de matière", async () => {
    fausseApi({ "GET /enseignants/classes": { json: [] } });
    render(<Classes jeton="j" onExpire={vi.fn()} />);
    await screen.findByText(/Aucune classe/);
    expect(screen.queryByLabelText("Matière de la nouvelle classe")).not.toBeInTheDocument();
  });

  it("l'enfant ouvre sa classe de français dans l'espace d'entraînement", async () => {
    const espace = {
      id: 1, prenom: "Inès", nom: "Martin", niveau: "5e", identifiant: "ines.m",
      matieres: [
        { code: "maths", libelle: "Boussole Maths", disponible: true },
        { code: "anglais", libelle: "Boussole Anglais", disponible: true },
        { code: "francais", libelle: "Boussole Français", disponible: true },
      ],
      maths: [], anglais: [],
      francais: [{ eleve_id: 9, code_classe: "5E-FR-ABCDE", niveau: "5e", parcours: "tronc-commun", libelle_parcours: "Français", enseignant: "Mme Lettres" }],
    };
    const jeton = { jeton: "e", eleve: { id: 9, matiere: "francais" } };
    fausseApi({ "GET /enfants/moi": { json: espace }, "POST /enfants/moi/maths/9": { json: jeton } });
    const onOuvrir = vi.fn();
    render(<EspaceEnfant session={{ jeton: "j", enfant: espace }} onOuvrirMaths={onOuvrir} onDeconnexion={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /Boussole Français/ }));
    expect(screen.getByText("Mme Lettres", { exact: false })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "S'entraîner" }));
    expect(onOuvrir).toHaveBeenCalledWith(jeton);
  });

  it("une réponse courte s'affiche avec ses autres réponses acceptées", () => {
    expect(solutionLisible("texte", "finissent | ils finissent")).toBe("finissent (aussi accepté : ils finissent)");
    expect(solutionLisible("texte", "à")).toBe("à");
    expect(solutionLisible("numerique", "1/2")).toBe("1/2");
  });
});
