// Issue #184 — Vue élève simulée (Claude)
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import EspaceEleve from "../eleve/EspaceEleve.jsx";
import VueEleve from "../ui/VueEleve.jsx";
import { fausseApi } from "./setup.js";

const CLASSE = {
  classe_id: 4, code_classe: "2NDE-A-DEMO", niveau: "2nde", parcours: "tronc-commun", matiere: "maths",
  domaine: "Maths lycée", professeur: "Enseignant Démo", ouverte_aux_eleves: true, motif_fermeture: null, en_cours: false,
};
const FERMEE = {
  ...CLASSE, classe_id: 9, code_classe: "5E-FR-ABCDE", niveau: "5e", matiere: "francais", domaine: "Français collège",
  professeur: "Mme Lettres", ouverte_aux_eleves: false, motif_fermeture: "Français collège est fermé pour le moment.", en_cours: true,
};
const SIMULATION = {
  role: "enseignant", classe_id: 4, code_classe: "2NDE-A-DEMO", niveau: "2nde", matiere: "maths", domaine: "Maths lycée",
  expire_le: "2026-11-19T12:00:00Z",
};
const ELEVE = {
  id: 42, prenom: "Élève fictif P1", identifiant: null, code_classe: "2NDE-A-DEMO", niveau: "2nde", parcours: "tronc-commun", matiere: "maths",
};
const OUVERTURE = { json: { jeton: "jeton-fictif", eleve: ELEVE, simulation: SIMULATION } };

/** Routes appelées au montage de l'espace élève. */
const ESPACE_ELEVE = {
  "GET /eleves/moi/parcours": { json: [] },
  "GET /eleves/moi/diagnostic": { json: { statut: "ferme" } },
};

describe("vue élève simulée : choix de la classe (#184)", () => {
  it("le professeur ouvre l'espace élève d'une de ses classes avec un élève fictif", async () => {
    window.history.replaceState(null, "", "/enseignant/vue-eleve");
    sessionStorage.setItem("pkp.seance", "3"); // séance d'un autre élève sur ce poste : jamais reprise
    const appels = fausseApi({
      "GET /enseignants/simulation/classes": { json: [CLASSE] },
      "POST /enseignants/simulation": OUVERTURE,
    });
    render(<VueEleve jeton="j" onExpire={vi.fn()} role="enseignant" />);
    const bouton = await screen.findByRole("button", { name: "Voir comme un élève de 2NDE-A-DEMO" });
    expect(screen.queryByText("Professeur")).not.toBeInTheDocument();
    await userEvent.click(bouton);
    expect(appels.find((a) => a.cle === "POST /enseignants/simulation").corps).toEqual({ classe_id: 4 });
    expect(JSON.parse(sessionStorage.getItem("pkp.eleve"))).toEqual({
      jeton: "jeton-fictif", eleve: ELEVE, simulation: SIMULATION, durable: false,
    });
    expect(localStorage.getItem("pkp.eleve")).toBeNull();
    expect(sessionStorage.getItem("pkp.seance")).toBeNull();
    expect(window.location.pathname).toBe("/eleve");
  });

  it("l'administrateur voit toutes les classes, leur professeur et l'état d'ouverture aux élèves", async () => {
    const appels = fausseApi({
      "GET /admin/simulation/classes": { json: [CLASSE, FERMEE] },
      "POST /admin/simulation": { status: 404, json: { detail: "Classe introuvable." } },
    });
    render(<VueEleve jeton="j" onExpire={vi.fn()} role="admin" />);
    const ligne = (await screen.findByText("5E-FR-ABCDE")).closest("tr");
    expect(ligne).toHaveTextContent("Mme Lettres");
    expect(ligne).toHaveTextContent("Fermé : Français collège est fermé pour le moment.");
    await userEvent.click(within(ligne).getByRole("button", { name: "Voir comme un élève de 5E-FR-ABCDE" }));
    expect(within(ligne).getByRole("button")).toHaveTextContent("Reprendre la simulation");
    expect(await screen.findByText("Classe introuvable.")).toBeInTheDocument();
    expect(appels.at(-1).cle).toBe("POST /admin/simulation");
    expect(sessionStorage.getItem("pkp.eleve")).toBeNull();
  });

  it("session professeur expirée : retour à la connexion", async () => {
    fausseApi({ "GET /enseignants/simulation/classes": { status: 401, json: { detail: "Authentification requise." } } });
    const onExpire = vi.fn();
    render(<VueEleve jeton="j" onExpire={onExpire} role="enseignant" />);
    await vi.waitFor(() => expect(onExpire).toHaveBeenCalled());
  });
});

describe("vue élève simulée : bandeau de l'espace élève (#184)", () => {
  function ouvrirEspace(simulation = SIMULATION) {
    window.history.replaceState(null, "", "/eleve");
    sessionStorage.setItem("pkp.eleve", JSON.stringify({ jeton: "jeton-fictif", eleve: ELEVE, simulation }));
  }

  it("affiche le contexte en permanence, sans « Ce n'est pas moi »", async () => {
    ouvrirEspace();
    fausseApi(ESPACE_ELEVE);
    render(<EspaceEleve />);
    const bandeau = await screen.findByRole("region", { name: "Simulation élève" });
    expect(bandeau).toHaveTextContent("Maths lycée · 2nde · classe 2NDE-A-DEMO");
    expect(within(bandeau).getByRole("button", { name: "Revenir à mon espace professeur" })).toBeInTheDocument();
    expect(screen.queryByText("Ce n'est pas moi")).not.toBeInTheDocument();
  });

  it("le retour ferme la simulation côté serveur et rouvre l'espace d'origine", async () => {
    ouvrirEspace({ ...SIMULATION, role: "admin" });
    sessionStorage.setItem("pkp.seance", "12");
    const appels = fausseApi({ ...ESPACE_ELEVE, "POST /eleves/moi/simulation/fermer": { status: 204 } });
    render(<EspaceEleve />);
    await userEvent.click(await screen.findByRole("button", { name: "Revenir à mon espace administrateur" }));
    expect(appels.some((a) => a.cle === "POST /eleves/moi/simulation/fermer")).toBe(true);
    expect(sessionStorage.getItem("pkp.eleve")).toBeNull();
    expect(sessionStorage.getItem("pkp.seance")).toBeNull();
    expect(window.location.pathname).toBe("/admin");
  });

  it("la réinitialisation demande confirmation puis repart d'un nouvel élève fictif", async () => {
    ouvrirEspace();
    sessionStorage.setItem("pkp.seance", "12");
    const nouveau = { ...ELEVE, id: 43 };
    const appels = fausseApi({
      ...ESPACE_ELEVE,
      "POST /eleves/moi/simulation/reinitialiser": { json: { jeton: "jeton-neuf", eleve: nouveau, simulation: SIMULATION } },
    });
    vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
    render(<EspaceEleve />);
    const bouton = await screen.findByRole("button", { name: "Réinitialiser la simulation" });
    await userEvent.click(bouton);
    expect(appels.some((a) => a.cle.endsWith("/reinitialiser"))).toBe(false);
    await userEvent.click(bouton);
    await vi.waitFor(() => expect(JSON.parse(sessionStorage.getItem("pkp.eleve")).jeton).toBe("jeton-neuf"));
    expect(JSON.parse(sessionStorage.getItem("pkp.eleve")).simulation).toEqual(SIMULATION);
    expect(sessionStorage.getItem("pkp.seance")).toBeNull();
  });
});
