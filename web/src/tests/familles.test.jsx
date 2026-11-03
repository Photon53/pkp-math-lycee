import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import Configuration from "../admin/Configuration.jsx";
import Familles from "../admin/Familles.jsx";
import { fausseApi } from "./setup.js";

const LINA = { id: 1, prenom: "Lina", classe: "2NDE-A", niveau: "2nde", enseignant: "M. Demo" };
const YANIS = { id: 2, prenom: "Yanis", classe: "2NDE-A", niveau: "2nde", enseignant: "M. Demo" };
const famille = (enfants, historique = []) => ({
  id: 7, email: "parent@exemple.fr", mdp_provisoire: false, cree_le: "2026-11-01T10:00:00Z",
  derniere_connexion: null, enfants, historique,
});

describe("familles", () => {
  it("cherche par e-mail, puis détache un enfant avec effet immédiat", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const appels = fausseApi({
      "GET /admin/classes": { json: [] },
      "GET /admin/parents?page=1&q=parent": { json: { total: 1, elements: [famille([LINA, YANIS])] } },
      "GET /admin/parents/7": { json: famille([LINA, YANIS], [{ le: "2026-11-01T10:00:00Z", action: "ajout", par: "Professeur : M. Demo", enfant: "Lina (2NDE-A)" }]) },
      "DELETE /admin/parents/7/enfants/2": { json: famille([LINA]) },
    });
    render(<Familles jeton="j" onExpire={vi.fn()} />);
    await userEvent.type(screen.getByLabelText(/E-mail du parent/), "parent");
    await userEvent.click(await screen.findByRole("button", { name: "Gérer" }));
    const fenetre = screen.getByRole("dialog");
    expect(await within(fenetre).findByText("Professeur : M. Demo")).toBeInTheDocument();
    await userEvent.click(within(fenetre).getByRole("button", { name: "Détacher Yanis (2NDE-A)" }));
    expect(within(fenetre).queryByRole("button", { name: "Détacher Yanis (2NDE-A)" })).not.toBeInTheDocument();
    expect(appels.some((a) => a.cle === "DELETE /admin/parents/7/enfants/2")).toBe(true);
  });

  it("ne demande rien au serveur sans filtre : pas de liste complète des familles", async () => {
    const appels = fausseApi({ "GET /admin/classes": { json: [] } });
    render(<Familles jeton="j" onExpire={vi.fn()} />);
    await userEvent.type(screen.getByLabelText(/E-mail du parent/), "pa");
    await new Promise((r) => setTimeout(r, 300));
    expect(appels.some((a) => a.cle.startsWith("GET /admin/parents"))).toBe(false);
  });
});

describe("configuration", () => {
  it("ouvre un domaine aux élèves seulement s'il est activé", async () => {
    const domaine = { code: "anglais-lycee", libelle: "Anglais lycée", niveaux: ["2nde"], actif: false, public: false, nb_professeurs: 0, nb_validateurs: 0 };
    const appels = fausseApi({
      "GET /admin/domaines": { json: [domaine] },
      "POST /admin/domaines/anglais-lycee": (corps) => ({ json: [{ ...domaine, ...corps }] }),
    });
    render(<Configuration jeton="j" onExpire={vi.fn()} />);
    expect(await screen.findByLabelText("Anglais lycée ouvert aux élèves")).toBeDisabled();
    await userEvent.click(screen.getByLabelText("Anglais lycée activé pour l'équipe"));
    expect(appels.at(-1).corps).toEqual({ actif: true, public: false });
    expect(await screen.findByText("Aucun validateur")).toBeInTheDocument();
    expect(screen.getByLabelText("Anglais lycée ouvert aux élèves")).not.toBeDisabled();
  });
});
