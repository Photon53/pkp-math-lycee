import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import ParentsEleve from "../enseignant/ParentsEleve.jsx";
import EspaceParent from "../parent/EspaceParent.jsx";
import { fausseApi } from "./setup.js";

const ENFANT = {
  id: 1, prenom: "Lina", identifiant: "lina-demo", code_classe: "2NDE-A-DEMO", niveau: "2nde", parcours: "tronc-commun",
  a_un_code: true, nb_reponses: 12, taux_reussite: 0.75, competences_maitrisees: 2, competences_total: 8,
  derniere_activite: "2026-11-02T17:00:00Z", minutes_7_jours: 95,
};
const TABLEAU = {
  enfant: ENFANT,
  activite: Array.from({ length: 14 }, (_, i) => ({ jour: `2026-11-${String(i + 1).padStart(2, "0")}`, nb_reponses: i % 2, minutes: i % 2 ? 12 : 0 })),
  minutes_30_jours: 240,
  seances_30_jours: 6,
  chapitres: [{ titre: "Fonctions", competences_total: 4, competences_maitrisees: 2 }],
  progression: [{ competence_id: 3, code: "F1", libelle: "Lire une image", chapitre: "Fonctions", nb_reponses: 4, maitrise: 0.9, maitrisee: true }],
};

function connecterParent() {
  sessionStorage.setItem("pkp.parent", JSON.stringify({ jeton: "j", email: "parent@exemple.fr", mdp_provisoire: false }));
}

describe("espace parent", () => {
  it("demande de changer le mot de passe provisoire", async () => {
    const appels = fausseApi({
      "POST /parents/connexion": { json: { jeton: "j", email: "parent@exemple.fr", mdp_provisoire: true } },
    });
    render(<EspaceParent />);
    await userEvent.type(screen.getByLabelText("Email"), "parent@exemple.fr");
    await userEvent.type(screen.getByLabelText("Mot de passe"), "provisoire");
    await userEvent.click(screen.getByRole("button", { name: "Se connecter" }));
    expect(await screen.findByText("Choisissez votre mot de passe")).toBeInTheDocument();
    expect(appels[0].corps).toEqual({ email: "parent@exemple.fr", mot_de_passe: "provisoire" });
  });

  it("affiche le tableau de bord de l'enfant", async () => {
    connecterParent();
    fausseApi({
      "GET /parents/enfants": { json: [ENFANT] },
      "GET /parents/enfants/1": { json: TABLEAU },
    });
    render(<EspaceParent />);
    expect(await screen.findByText("2 / 8")).toBeInTheDocument();
    expect(screen.getByText("75 %")).toBeInTheDocument();
    expect(screen.getByText("1 h 35")).toBeInTheDocument();
    expect(screen.getByText("Fonctions", { selector: ".nom" })).toBeInTheDocument();
    expect(screen.getByText("Lire une image")).toBeInTheDocument();
  });

  it("choisit le code de connexion de l'enfant", async () => {
    connecterParent();
    const appels = fausseApi({
      "GET /parents/enfants": { json: [ENFANT] },
      "GET /parents/enfants/1": { json: TABLEAU },
      "PUT /parents/enfants/1/code": { json: { identifiant: "lina-demo" } },
    });
    render(<EspaceParent />);
    await userEvent.click(await screen.findByRole("tab", { name: "Code de connexion" }));
    await userEvent.type(screen.getByLabelText("Nouveau code"), "court1");
    await userEvent.type(screen.getByLabelText("Confirmation"), "court1");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer le code" }));
    expect(screen.getByRole("alert")).toHaveTextContent("de 8 à 16 caractères");

    await userEvent.clear(screen.getByLabelText("Nouveau code"));
    await userEvent.clear(screen.getByLabelText("Confirmation"));
    await userEvent.type(screen.getByLabelText("Nouveau code"), "maths2026k");
    await userEvent.type(screen.getByLabelText("Confirmation"), "maths2026k");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer le code" }));
    expect(await screen.findByText(/Code enregistré/)).toBeInTheDocument();
    expect(appels.find((a) => a.cle === "PUT /parents/enfants/1/code").corps).toEqual({ code: "maths2026k" });
  });
});

describe("comptes parents côté professeur", () => {
  it("crée un compte et affiche le mot de passe provisoire une fois", async () => {
    let parents = [];
    const appeler = vi.fn(async (chemin, { methode = "GET" } = {}) => {
      if (methode === "POST") {
        parents = [{ id: 7, email: "parent@exemple.fr", mdp_provisoire: true, derniere_connexion: null, enfants: ["Lina (2NDE-A-DEMO)"] }];
        return { parent: parents[0], mot_de_passe_provisoire: "Abc23defGhj45kmn" };
      }
      return parents;
    });
    render(<ParentsEleve eleve={{ id: 1, prenom: "Lina" }} appeler={appeler} />);
    expect(await screen.findByText("Aucun compte parent pour l'instant.")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("E-mail du parent"), "parent@exemple.fr");
    await userEvent.click(screen.getByRole("button", { name: "Créer le compte parent" }));
    expect(await screen.findByText("Abc23defGhj45kmn")).toBeInTheDocument();
    expect(screen.getByText(/pas encore changé/)).toBeInTheDocument();
  });
});
