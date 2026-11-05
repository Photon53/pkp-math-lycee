import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import Repertoire, { FicheEleve } from "../admin/Repertoire.jsx";
import { api } from "../api.js";
import { fausseApi } from "./setup.js";

const appeler = (chemin, options = {}) => api(chemin, { ...options, jeton: "j" });
const CLASSE = { id: 1, code: "2NDE-TC-AAAAA", niveau: "2nde", parcours: "tronc-commun", enseignant: "Enseignant Démo" };
const NOE = {
  id: 7, prenom: "Noé", nom: "Durand", niveau: "2nde", identifiant: "noe-p2q3", a_un_code: true, bloque: false,
  derniere_connexion: null, cree_le: "2026-11-01T10:00:00", maths: [], anglais: [], responsables: [], alertes: ["Aucun responsable"],
};
const page = (elements) => ({ json: { total: elements.length, elements } });

afterEach(() => vi.restoreAllMocks());

describe("administrateur : tous les élèves", () => {
  it("affiche un élève par ligne, ses points à vérifier, filtre et inscrit dans une classe de son niveau", async () => {
    let noe = NOE;
    const appels = fausseApi({
      "GET /admin/repertoire?page=1&tri=nom": () => page([noe]),
      "GET /admin/repertoire?page=1&tri=nom&sans_responsable=true": () => page([noe]),
      "GET /admin/repertoire?page=1&tri=nom&sans_responsable=true&a_verifier=true": () => page([]),
      "GET /admin/classes": { json: [CLASSE, { ...CLASSE, id: 2, code: "1RE-SPE-BBBBB", niveau: "1re", parcours: "specialite" }] },
      "POST /admin/classes/1/enfants": () => {
        noe = { ...noe, maths: [{ eleve_id: 30, code_classe: CLASSE.code, principal: true, libelle_parcours: "Tronc commun" }] };
        return { json: { ajoutes: ["Noé Durand"], refus: [] } };
      },
    });
    render(<Repertoire appeler={appeler} />);
    expect(await screen.findByText("Noé Durand")).toBeInTheDocument();
    expect(screen.getAllByText("Aucun responsable").length).toBeGreaterThan(0);
    const choix = screen.getByLabelText("Inscrire Noé Durand dans une classe");
    expect(within(choix).queryByText(/1RE-SPE/)).not.toBeInTheDocument(); // autre niveau
    await userEvent.selectOptions(choix, "1");
    expect(await screen.findByText("Inscription faite : Noé Durand.")).toBeInTheDocument();
    expect(appels.find((a) => a.cle === "POST /admin/classes/1/enfants").corps).toEqual({ enfant_ids: [7] });
    expect(await screen.findByText(CLASSE.code)).toBeInTheDocument();

    await userEvent.click(screen.getByLabelText(/Sans responsable/));
    await userEvent.click(screen.getByLabelText(/À vérifier/));
    expect(await screen.findByText("Aucun élève ne correspond.")).toBeInTheDocument();
  });

  it("change le niveau de la sélection après confirmation", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const appels = fausseApi({
      "GET /admin/repertoire?page=1&tri=nom": page([NOE]),
      "GET /admin/classes": { json: [] },
      "POST /admin/enfants/niveau": page([{ ...NOE, niveau: "1re" }]),
    });
    render(<Repertoire appeler={appeler} />);
    await userEvent.click(await screen.findByLabelText("Sélectionner Noé Durand"));
    await userEvent.selectOptions(screen.getByLabelText("Changer le niveau de la sélection"), "1re");
    expect(await screen.findByText(/Niveau changé/)).toBeInTheDocument();
    expect(appels.find((a) => a.cle === "POST /admin/enfants/niveau").corps).toEqual({ ids: [7], niveau: "1re" });
  });
});

describe("administrateur : fiche élève", () => {
  const fiche = (responsables) => ({
    json: {
      eleve: { ...NOE, responsables, alertes: responsables.length ? [] : ["Aucun responsable"] },
      maths: [{ eleve_id: 30, code_classe: CLASSE.code, niveau: "2nde", parcours: "tronc-commun", libelle_parcours: "Tronc commun",
        principal: true, enseignant: "Enseignant Démo", inscrit_le: null, seances: 3, reponses: 20, taux_reussite: 0.75, derniere_activite: null }],
      anglais: [],
      archives: [{ id: 5, matiere: "maths", domaine_code: "maths-lycee", niveau: "2nde", parcours: "excellence", cours: "2NDE-EXC-CCCCC",
        enseignant: "Enseignant Démo", inscrit_le: null, archivee_le: "2026-11-02T09:00:00", par: "Admin", motif: "classe supprimée",
        resume: { seances: 2, reponses: 8 } }],
      historique: [{ le: "2026-11-02T09:00:00", admin: "Admin", action: "bloquer", objet: "enfant", avant: null, apres: null }],
    },
  });

  it("montre progression, archives et historique, puis rattache un responsable créé avec un mot de passe provisoire", async () => {
    let responsables = [];
    const appels = fausseApi({
      "GET /admin/enfants/7/fiche": () => fiche(responsables),
      "POST /admin/enfants/7/responsables": (corps) => {
        responsables = [{ id: 3, email: corps.email, nom: corps.nom, prenom: corps.prenom, mdp_provisoire: true, bloque: false }];
        return { json: { responsable: responsables[0], cree: true, mot_de_passe_provisoire: "Provisoire-123" } };
      },
    });
    render(<FicheEleve id={7} appeler={appeler} onFermer={() => {}} />);
    expect(await screen.findByText("75 %")).toBeInTheDocument();
    expect(screen.getByText("principal")).toBeInTheDocument();
    expect(screen.getByText("2NDE-EXC-CCCCC")).toBeInTheDocument();
    expect(screen.getByText("Carte bloquée")).toBeInTheDocument();
    expect(screen.getByText(/Aucun responsable : rattachez/)).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText("E-mail du responsable"), "tuteur@x.test");
    await userEvent.type(screen.getByLabelText("Prénom", { selector: "#fe-r-prenom" }), "Paul");
    await userEvent.type(screen.getByLabelText("Nom", { selector: "#fe-r-nom" }), "Durand");
    await userEvent.click(screen.getByText("Rattacher ce responsable"));
    expect(await screen.findByText("Provisoire-123")).toBeInTheDocument();
    expect(screen.getByText("Paul Durand")).toBeInTheDocument();
    expect(appels.find((a) => a.cle === "POST /admin/enfants/7/responsables").corps).toEqual({
      email: "tuteur@x.test", prenom: "Paul", nom: "Durand",
    });
  });

  it("demande une confirmation au-delà de deux responsables", async () => {
    const confirmation = vi.spyOn(window, "confirm").mockReturnValue(true);
    const deux = [1, 2].map((id) => ({ id, email: `p${id}@x.test`, nom: "", prenom: "", mdp_provisoire: false, bloque: false }));
    const appels = fausseApi({
      "GET /admin/enfants/7/fiche": fiche(deux),
      "POST /admin/enfants/7/responsables": {
        status: 409, json: { detail: "Cet élève a déjà 2 responsables : confirmez l'ajout d'un responsable supplémentaire." },
      },
      "POST /admin/enfants/7/responsables?confirmer=true": {
        json: { responsable: { id: 9, email: "trois@x.test", nom: "", prenom: "", mdp_provisoire: false, bloque: false }, cree: false, mot_de_passe_provisoire: null },
      },
    });
    render(<FicheEleve id={7} appeler={appeler} onFermer={() => {}} />);
    await userEvent.type(await screen.findByLabelText("E-mail du responsable"), "trois@x.test");
    await userEvent.click(screen.getByText("Rattacher ce responsable"));
    expect(await screen.findByText(/compte existant, mot de passe inchangé/)).toBeInTheDocument();
    expect(confirmation).toHaveBeenCalled();
    expect(appels.some((a) => a.cle === "POST /admin/enfants/7/responsables?confirmer=true")).toBe(true);
  });
});
