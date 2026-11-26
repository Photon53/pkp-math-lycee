// Issue #176 — Accès au français réservé aux classes pilotes (Claude)
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import ClassesPilotes from "../admin/ClassesPilotes.jsx";
import { fausseApi } from "./setup.js";

const DOMAINES = [
  { code: "maths-lycee", matiere: "maths", libelle: "Maths lycée", niveaux: ["2nde"], actif: true, public: true },
  { code: "francais-college", matiere: "francais", libelle: "Français collège", niveaux: ["6e", "5e"], actif: true, public: false },
];
const PILOTE = {
  classe_id: 7, code: "5E-FR-ABCDE", niveau: "5e", domaine_code: "francais-college", domaine: "Français collège",
  enseignant: "Mme Lettres", nb_eleves: 24, motif: "Pilote de janvier", accordee_le: "2026-11-19T08:00:00Z", accordee_par: "Équipe",
};

describe("classes pilotes (#176)", () => {
  it("crée une classe pilote dans un domaine activé mais fermé, pour un professeur habilité", async () => {
    const appels = fausseApi({
      "GET /admin/classes-pilotes": { json: [] },
      "GET /admin/enseignants?domaine=francais-college": { json: [{ id: 3, nom: "Mme Lettres", actif: true }, { id: 4, nom: "M. Parti", actif: false }] },
      "POST /admin/classes-pilotes": { status: 201, json: PILOTE },
    });
    render(<ClassesPilotes jeton="j" onExpire={vi.fn()} domaines={DOMAINES} />);
    expect(await screen.findByText("Aucune classe pilote.")).toBeInTheDocument();
    const domaine = screen.getByLabelText("Domaine");
    // Seuls les domaines activés mais fermés sont proposés.
    expect(within(domaine).queryByText("Maths lycée")).not.toBeInTheDocument();
    await userEvent.selectOptions(domaine, "francais-college");
    await userEvent.selectOptions(screen.getByLabelText("Niveau"), "5e");
    const professeur = screen.getByLabelText("Professeur");
    expect(await within(professeur).findByText("Mme Lettres")).toBeInTheDocument();
    expect(within(professeur).queryByText("M. Parti")).not.toBeInTheDocument(); // compte inactif écarté
    await userEvent.selectOptions(professeur, "3");
    await userEvent.type(screen.getByLabelText("Motif"), "Pilote de janvier");
    await userEvent.click(screen.getByRole("button", { name: "Créer la classe pilote" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Classe pilote 5E-FR-ABCDE créée pour Mme Lettres.");
    expect(appels.find((a) => a.cle === "POST /admin/classes-pilotes").corps).toEqual({
      matiere: "francais", niveau: "5e", enseignant_id: 3, motif: "Pilote de janvier",
    });
  });

  it("retire une classe pilote après confirmation", async () => {
    const appels = fausseApi({
      "GET /admin/classes-pilotes": { json: [PILOTE] },
      "DELETE /admin/classes-pilotes/7": { status: 204 },
    });
    const confirmer = vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
    render(<ClassesPilotes jeton="j" onExpire={vi.fn()} domaines={DOMAINES} />);
    const ligne = (await screen.findByText("5E-FR-ABCDE")).closest("tr");
    expect(ligne).toHaveTextContent("Mme Lettres");
    await userEvent.click(within(ligne).getByRole("button", { name: "Retirer" }));
    expect(appels.some((a) => a.cle.startsWith("DELETE"))).toBe(false); // refus de la confirmation : rien n'est envoyé
    await userEvent.click(within(ligne).getByRole("button", { name: "Retirer" }));
    expect(await screen.findByRole("status")).toHaveTextContent("5E-FR-ABCDE n'est plus une classe pilote.");
    expect(confirmer).toHaveBeenCalledTimes(2);
  });

  it("sans domaine fermé et activé, explique comment faire", async () => {
    fausseApi({ "GET /admin/classes-pilotes": { json: [] } });
    render(<ClassesPilotes jeton="j" onExpire={vi.fn()} domaines={[DOMAINES[0]]} />);
    expect(await screen.findByText(/activez d'abord un domaine sans l'ouvrir aux élèves/)).toBeInTheDocument();
  });
});

describe("historique vu par le parent après révocation (#176, option b)", () => {
  it("n'affiche ni énoncé ni réponse attendue quand le contenu est masqué", async () => {
    const { default: Historique } = await import("../eleve/Historique.jsx");
    const element = {
      id: 1, repondu_le: "2026-11-19T08:00:00Z", seance_id: 1, question_id: 1, competence_id: 1, competence: "Conjuguer au présent",
      chapitre: "Le présent", enonce: "", type: "texte", difficulte: 1, reponse_donnee: "finissons", correcte: false, solution: "",
      correction: null, duree_s: 12, contenu_masque: true,
    };
    fausseApi({ "GET /parents/enfants/5/historique?page=1&erreurs=false": { json: { total: 1, erreurs: 1, elements: [element] } } });
    render(<Historique jeton="j" onExpire={vi.fn()} chemin="/parents/enfants/5/historique" eleve={false} />);
    expect(await screen.findByText("Énoncé et correction réservés aux élèves de la classe pilote.")).toBeInTheDocument();
    expect(screen.getByText("finissons")).toBeInTheDocument();
    expect(screen.queryByText(/Réponse attendue/)).not.toBeInTheDocument();
  });
});
