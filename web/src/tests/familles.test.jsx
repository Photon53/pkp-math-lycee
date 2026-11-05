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
    await userEvent.type(screen.getByLabelText(/Nom ou e-mail du responsable/), "parent");
    await userEvent.click(await screen.findByRole("button", { name: "Gérer" }));
    const fenetre = screen.getByRole("dialog");
    expect(await within(fenetre).findByText("Professeur : M. Demo")).toBeInTheDocument();
    await userEvent.click(within(fenetre).getByRole("button", { name: "Détacher Yanis (2NDE-A)" }));
    expect(within(fenetre).queryByRole("button", { name: "Détacher Yanis (2NDE-A)" })).not.toBeInTheDocument();
    expect(appels.some((a) => a.cle === "DELETE /admin/parents/7/enfants/2")).toBe(true);
  });

  it("affiche les familles sans recherche et corrige l'e-mail du parent", async () => {
    const appels = fausseApi({
      "GET /admin/classes": { json: [] },
      "GET /admin/parents?page=1": { json: { total: 1, elements: [famille([])] } },
      "GET /admin/parents/7": { json: famille([]) },
      "GET /admin/parents/7/famille": { json: [] },
      "GET /admin/anglais/groupes": { json: [] },
      "PATCH /admin/parents/7": (corps) => ({ json: { id: 7, email: corps.email, nom: corps.nom, prenom: corps.prenom, mdp_provisoire: false, derniere_connexion: null, enfants: [] } }),
    });
    render(<Familles jeton="j" onExpire={vi.fn()} />);
    expect(await screen.findByText("parent@exemple.fr")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Gérer" }));
    const fenetre = screen.getByRole("dialog");
    await userEvent.click(await within(fenetre).findByRole("button", { name: "Modifier" }));
    await userEvent.type(within(fenetre).getByLabelText("Prénom du responsable"), "Claire");
    await userEvent.type(within(fenetre).getByLabelText("Nom du responsable"), "Martin");
    const champ = within(fenetre).getByLabelText("Adresse e-mail");
    await userEvent.clear(champ);
    await userEvent.type(champ, "nouveau@exemple.fr");
    await userEvent.click(within(fenetre).getByRole("button", { name: "Enregistrer" }));
    expect((await within(fenetre).findAllByText("nouveau@exemple.fr")).length).toBeGreaterThan(0);
    expect(within(fenetre).getAllByText("Claire Martin").length).toBeGreaterThan(0);
    expect(appels.find((a) => a.cle === "PATCH /admin/parents/7").corps).toEqual({ email: "nouveau@exemple.fr", prenom: "Claire", nom: "Martin" });
  });
});

describe("familles : actions en masse", () => {
  const ligne = (n, enfant, erreurs = []) => ({ ligne: n, enfant, niveau: "2nde", parents: ["a@x.fr"], inscriptions: [], erreurs, deja_present: false });
  const rapport = (lignes, autres = {}) => ({
    simulation: true, lignes, nb_enfants: lignes.filter((l) => !l.erreurs.length).length, nb_deja_presents: 0,
    nb_comptes_nouveaux: 1, nb_erreurs: lignes.filter((l) => l.erreurs.length).length, cartes: [], comptes: [], ...autres,
  });

  it("vérifie le fichier Excel, signale les lignes à corriger, puis importe et donne cartes et mots de passe", async () => {
    let essai = 0;
    const appels = fausseApi({
      "GET /admin/classes": { json: [] },
      "GET /admin/parents?page=1": { json: { total: 0, elements: [] } },
      "POST /admin/import?simulation=true": () =>
        ++essai === 1
          ? { json: rapport([ligne(2, "Inès Durand"), ligne(3, "Léa", ["Niveau « CM2 » inconnu (6e, 5e, 4e, 3e, 2nde, 1re ou Tle)."])]) }
          : { json: rapport([ligne(2, "Inès Durand")]) },
      "POST /admin/import?simulation=false": {
        json: rapport([ligne(2, "Inès Durand")], {
          simulation: false,
          cartes: [{ id: 5, prenom: "Inès", nom: "Durand", niveau: "2nde", identifiant: "ines-ab12", code: "CODE-1234", famille: "a@x.fr" }],
          comptes: [{ email: "a@x.fr", mot_de_passe_provisoire: "mdp-provisoire-1" }],
        }),
      },
    });
    render(<Familles jeton="j" onExpire={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: /Importer \(Excel\)/ }));
    const fenetre = screen.getByRole("dialog");
    const fichier = new File(["xlsx"], "eleves.xlsx", { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
    await userEvent.upload(within(fenetre).getByLabelText("Fichier rempli (.xlsx)"), fichier);
    await userEvent.click(within(fenetre).getByRole("button", { name: "Vérifier le fichier" }));
    expect(await within(fenetre).findByText(/1 ligne\(s\) à corriger/)).toBeInTheDocument();
    expect(within(fenetre).getByText(/Niveau « CM2 » inconnu/)).toBeInTheDocument();
    expect(within(fenetre).getByRole("button", { name: /Importer 1 élève/ })).toBeDisabled();
    expect(appels.find((a) => a.cle === "POST /admin/import?simulation=true").corps).toBe(fichier);

    await userEvent.click(within(fenetre).getByRole("button", { name: "Vérifier le fichier" }));
    await userEvent.click(await within(fenetre).findByRole("button", { name: /Importer 1 élève/ }));
    const fin = await screen.findByRole("dialog", { name: "Import terminé" });
    expect(within(fin).getByText("mdp-provisoire-1")).toBeInTheDocument();
    expect(within(fin).getByText("CODE-1234")).toBeInTheDocument();
  });

  it("bloque et supprime plusieurs familles cochées", async () => {
    const appels = fausseApi({
      "GET /admin/classes": { json: [] },
      "GET /admin/parents?page=1": {
        json: { total: 2, elements: [{ ...famille([]), famille: ["Inès (2nde)"] }, { ...famille([]), id: 8, email: "autre@exemple.fr", bloque: true }] },
      },
      "POST /admin/parents/blocage": { json: { traites: 2 } },
      "POST /admin/parents/suppression": { json: { traites: 2 } },
    });
    render(<Familles jeton="j" onExpire={vi.fn()} />);
    expect(await screen.findByText("Bloqué")).toBeInTheDocument();
    await userEvent.click(screen.getByLabelText("Sélectionner toutes les familles de la page"));
    expect(screen.getByText("Sélection : 2 familles")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Bloquer" }));
    expect(appels.find((a) => a.cle === "POST /admin/parents/blocage").corps).toEqual({ ids: [7, 8], bloque: true });
    expect(await screen.findByText(/2 compte\(s\) parent bloqué\(s\)/)).toBeInTheDocument();

    await userEvent.click(screen.getByLabelText("Sélectionner parent@exemple.fr"));
    await userEvent.click(screen.getByLabelText("Sélectionner autre@exemple.fr"));
    await userEvent.click(screen.getByRole("button", { name: "Supprimer" }));
    const fenetre = screen.getByRole("dialog");
    const confirmer = within(fenetre).getByRole("button", { name: "Supprimer définitivement" });
    expect(confirmer).toBeDisabled();
    await userEvent.click(within(fenetre).getByLabelText(/Supprimer aussi leurs enfants/));
    await userEvent.type(within(fenetre).getByLabelText(/saisissez SUPPRIMER/), "supprimer");
    await userEvent.click(confirmer);
    expect(appels.find((a) => a.cle === "POST /admin/parents/suppression").corps).toEqual({ ids: [7, 8], confirmation: "supprimer", avec_enfants: true });
    expect(await screen.findByText(/2 famille\(s\) supprimée\(s\), avec leurs enfants/)).toBeInTheDocument();
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
