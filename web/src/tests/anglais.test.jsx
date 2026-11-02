import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import Accueil from "../Accueil.jsx";
import Professeurs from "../admin/Professeurs.jsx";
import EspaceAnglais from "../anglais/EspaceAnglais.jsx";
import EspaceEnseignant from "../enseignant/EspaceEnseignant.jsx";
import { fausseApi } from "./setup.js";

const SEANCE = {
  code: "4E-01", niveau: "4e", titre: "My daily life", objectif: "Parler de ses habitudes",
  etapes: [{ titre: "Warm-up", duree_minutes: 90, consigne_eleve: "Write three activities", consigne_animateur: "Recueillir" }],
  fiches: [{ parcours: "A", enonce: "Complete", corrige: "I like reading" }],
};

function connecte(disciplines) {
  sessionStorage.setItem("pkp.enseignant", JSON.stringify({ jeton: "j", nom: "Mme Smith", role: "enseignant", mdp_provisoire: false, ...disciplines }));
}

describe("PKP Anglais", () => {
  it("l'accueil mène à un espace dédié", () => {
    render(<Accueil />);
    expect(screen.getByRole("link", { name: /PKP Anglais/ })).toHaveAttribute("href", "/anglais");
  });

  it("l'espace professeur de maths n'a plus d'onglet anglais", () => {
    connecte({ enseigne_maths: true, enseigne_anglais: false });
    fausseApi({ "GET /enseignants/classes": { json: [] } });
    render(<EspaceEnseignant chemin="/enseignant" />);
    expect(screen.queryByText("PKP Anglais")).not.toBeInTheDocument();
  });

  it("un professeur de maths seul est refusé dans l'espace anglais", () => {
    connecte({ enseigne_maths: true, enseigne_anglais: false });
    const appels = fausseApi({});
    render(<EspaceAnglais chemin="/anglais" />);
    expect(screen.getByRole("heading", { name: "Espace réservé aux professeurs d'anglais" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Aller à l'espace professeur" })).toHaveAttribute("href", "/enseignant");
    expect(appels).toEqual([]);
  });

  it("un professeur d'anglais seul est refusé dans l'espace maths", () => {
    connecte({ enseigne_maths: false, enseigne_anglais: true });
    const appels = fausseApi({});
    render(<EspaceEnseignant chemin="/enseignant" />);
    expect(screen.getByRole("heading", { name: "Espace réservé aux professeurs de mathématiques" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Aller à l'espace PKP Anglais" })).toHaveAttribute("href", "/anglais");
    expect(appels).toEqual([]);
  });

  it("un professeur d'anglais voit ses séances", async () => {
    connecte({ enseigne_maths: false, enseigne_anglais: true });
    fausseApi({
      "GET /anglais/seances": { json: [{ code: "4E-01", niveau: "4e", titre: "My daily life", objectif: "x", duree_minutes: 90 }] },
      "GET /anglais/seances/4E-01": { json: SEANCE },
    });
    render(<EspaceAnglais chemin="/anglais" />);
    expect(await screen.findByRole("heading", { name: "My daily life" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "PDF élève" })).toBeInTheDocument();
    expect(screen.queryByText("Espace professeur de maths")).not.toBeInTheDocument();
  });

  it("l'administrateur coche les disciplines d'un nouveau professeur", async () => {
    let liste = [];
    const appels = fausseApi({
      "GET /admin/enseignants": () => ({ json: liste }),
      "POST /admin/enseignants": (corps) => {
        const enseignant = { id: 9, ...corps, actif: true, mdp_provisoire: true, totp_configure: false, nb_classes: 0, nb_eleves: 0, derniere_connexion: null };
        liste = [enseignant];
        return { status: 201, json: { enseignant, mot_de_passe_provisoire: "Abc23defGhk45mnP" } };
      },
    });
    render(<Professeurs jeton="j" onExpire={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: /Nouveau professeur/ }));
    const fenetre = screen.getByRole("dialog");
    await userEvent.type(within(fenetre).getByLabelText("Nom affiché"), "Mrs Smith");
    await userEvent.type(within(fenetre).getByLabelText("E-mail"), "smith@college.fr");
    await userEvent.click(within(fenetre).getByLabelText(/Mathématiques/));
    await userEvent.click(within(fenetre).getByRole("button", { name: "Créer le compte" }));
    expect(within(fenetre).getByText("Cochez au moins une discipline.")).toBeInTheDocument();
    await userEvent.click(within(fenetre).getByLabelText(/Anglais/));
    await userEvent.click(within(fenetre).getByRole("button", { name: "Créer le compte" }));
    expect(await screen.findByText("Abc23defGhk45mnP")).toBeInTheDocument();
    const creation = appels.find((a) => a.cle === "POST /admin/enseignants");
    expect(creation.corps).toMatchObject({ enseigne_maths: false, enseigne_anglais: true });
  });
});
