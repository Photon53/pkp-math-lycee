// Issue #102 — Accès à la préparation Français depuis la navigation adulte (Codex)
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import App from "../App.jsx";
import { PageSimple } from "../enseignant/EspaceEnseignant.jsx";
import { fausseApi } from "./setup.js";

const PROFESSEUR = {
  jeton: "session-professeur", nom: "Compte Français", role: "enseignant",
  mdp_provisoire: false, enseigne_maths: false, enseigne_anglais: false,
};

// État public des domaines : Français collège actif (en préparation par l'équipe), ou aucun domaine Français actif.
const FRANCAIS_ACTIF = { "GET /domaines/publics": { json: [{ code: "francais-college", matiere: "francais", etat: "en_preparation" }] } };
const FRANCAIS_INACTIF = { "GET /domaines/publics": { json: [{ code: "francais-college", matiere: "francais", etat: "en_chantier" }] } };

describe("navigation vers le Français en préparation", () => {
  it("propose le Français à la connexion maths sans l'ajouter au cadre partagé avec les parents", async () => {
    window.history.replaceState(null, "", "/enseignant");
    fausseApi(FRANCAIS_ACTIF);
    const vue = render(<App />);
    expect(await screen.findByRole("heading", { name: "Connexion professeur" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Français (préparation)" })).toHaveAttribute("href", "/francais");
    vue.unmount();
    render(<PageSimple><p>Connexion parent</p></PageSimple>);
    expect(screen.queryByRole("link", { name: /Français/ })).not.toBeInTheDocument();
  });

  it("n'annonce pas le Français à la connexion tant qu'aucun domaine Français n'est actif", async () => {
    window.history.replaceState(null, "", "/enseignant");
    const appels = fausseApi(FRANCAIS_INACTIF);
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Connexion professeur" })).toBeInTheDocument();
    await waitFor(() => expect(appels.some((a) => a.cle === "GET /domaines/publics")).toBe(true));
    expect(screen.queryByRole("link", { name: /Français/ })).not.toBeInTheDocument();
  });

  it("propose une sortie vers le Français quand le compte est refusé en maths", async () => {
    window.history.replaceState(null, "", "/enseignant");
    sessionStorage.setItem("pkp.enseignant", JSON.stringify(PROFESSEUR));
    const appels = fausseApi(FRANCAIS_ACTIF);
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Espace réservé aux professeurs de mathématiques" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Aller à l'espace Français (préparation)" })).toHaveAttribute("href", "/francais");
    // Seule la lecture publique de l'état des domaines : rien n'est demandé avec la session refusée.
    expect(appels.map((a) => a.cle)).toEqual(["GET /domaines/publics"]);
  });

  it("ouvre le Français depuis le menu admin avec la session professeur existante", async () => {
    window.history.replaceState(null, "", "/admin");
    sessionStorage.setItem("pkp.admin", JSON.stringify({ jeton: "session-admin", nom: "Admin", expire_le: Date.now() + 600_000 }));
    sessionStorage.setItem("pkp.enseignant", JSON.stringify(PROFESSEUR));
    const appels = fausseApi({
      "GET /admin/moi": { json: { permissions: ["pilotage.global", "contenu.lire"] } },
      "GET /admin/domaines": { json: [] },
      "GET /admin/statistiques?periode=30": { json: null },
      "GET /francais/dossiers": { json: [] },
    });
    render(<App />);
    // Premier chargement différé de l'espace admin : jusqu'à ~15 s à froid sur un poste Windows lent.
    const navigation = await screen.findByRole("navigation", { name: "Navigation Administration" }, { timeout: 30_000 });
    await userEvent.click(within(navigation).getByRole("link", { name: "PKP Français (préparation)" }));
    expect(await screen.findByRole("heading", { name: "Dossiers de français" }, { timeout: 30_000 })).toBeInTheDocument();
    expect(window.location.pathname).toBe("/francais");
    expect(screen.getByText(/non publiés aux élèves/)).toBeInTheDocument();
    expect(appels.some((a) => a.cle === "GET /francais/dossiers")).toBe(true);
    expect(appels.some((a) => a.cle.startsWith("GET /enseignants/"))).toBe(false);
  }, 70_000);

  it("demande une connexion professeur si seule la session admin existe", async () => {
    window.history.replaceState(null, "", "/francais");
    sessionStorage.setItem("pkp.admin", JSON.stringify({ jeton: "session-admin", nom: "Admin", expire_le: Date.now() + 600_000 }));
    const appels = fausseApi({});
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Connexion — Français (préparation)" })).toBeInTheDocument();
    expect(appels).toHaveLength(0);
  });
});
