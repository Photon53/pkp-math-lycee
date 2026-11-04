import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { GererClasse, ListeEnfants } from "../admin/GestionClasses.jsx";
import { api } from "../api.js";
import { fausseApi } from "./setup.js";

const CLASSE = {
  id: 4, code: "2NDE-EXC-42JJJ", niveau: "2nde", parcours: "excellence", domaine_code: "maths-lycee",
  enseignant_id: 3, enseignant: "Enseignant Démo", nb_eleves: 1, nb_chapitres_ouverts: 2,
};
const appeler = (chemin, options = {}) => api(chemin, { ...options, jeton: "j" });

describe("administrateur : gérer une classe", () => {
  it("retire un élève, ferme un chapitre, change de professeur et supprime avec le code", async () => {
    let eleves = [{ id: 9, prenom: "Inès", identifiant: "ines-k7m4", a_un_code: true, nb_reponses: 4, taux_reussite: 0.75, competences_maitrisees: 0, competences_total: 3 }];
    const appels = fausseApi({
      "GET /admin/classes/4": { json: CLASSE },
      "GET /admin/classes/4/eleves": () => ({ json: eleves }),
      "DELETE /admin/eleves/9": () => {
        eleves = [];
        return { status: 204 };
      },
      "GET /admin/classes/4/chapitres": {
        json: [
          { id: 1, code: "A", titre: "Arithmétique", ordre: 1, propose: true, nb_competences: 2, nb_questions: 10 },
          { id: 2, code: "B", titre: "Inégalités", ordre: 2, propose: true, nb_competences: 1, nb_questions: 0 },
        ],
      },
      "PUT /admin/classes/4/chapitres": {
        json: [
          { id: 1, code: "A", titre: "Arithmétique", ordre: 1, propose: true, nb_competences: 2, nb_questions: 10 },
          { id: 2, code: "B", titre: "Inégalités", ordre: 2, propose: false, nb_competences: 1, nb_questions: 0 },
        ],
      },
      "GET /admin/enseignants": { json: [{ id: 3, nom: "Enseignant Démo", actif: true }, { id: 5, nom: "Mme Remplaçante", actif: true }] },
      "PATCH /admin/classes/4": { json: { ...CLASSE, enseignant_id: 5, enseignant: "Mme Remplaçante" } },
      "DELETE /admin/classes/4?confirmation=2nde-exc-42jjj": { status: 204 },
    });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const onChange = vi.fn();
    const onFermer = vi.fn();
    render(<GererClasse classe={CLASSE} appeler={appeler} onFermer={onFermer} onChange={onChange} />);
    const fenetre = screen.getByRole("dialog", { name: "Classe 2NDE-EXC-42JJJ" });
    expect(within(fenetre).getByText(/Seconde — Excellence et olympiades/)).toBeInTheDocument();

    expect(await screen.findByText("ines-k7m4")).toBeInTheDocument();
    expect(screen.getByText("75 %")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retirer Inès" }));
    expect(await screen.findByText("Inès a été retiré·e de la classe.")).toBeInTheDocument();
    expect(screen.getByText("Aucun élève inscrit pour l'instant.")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("tab", { name: "Chapitres ouverts" }));
    await userEvent.click(await screen.findByLabelText(/Inégalités/));
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer les chapitres" }));
    expect(appels.find((a) => a.cle === "PUT /admin/classes/4/chapitres").corps).toEqual({ chapitre_ids: [1] });

    await userEvent.click(screen.getByRole("tab", { name: "Professeur" }));
    await userEvent.selectOptions(await screen.findByLabelText("Professeur de mathématiques"), "5");
    await userEvent.click(screen.getByRole("button", { name: "Changer de professeur" }));
    expect(await screen.findByText("2NDE-EXC-42JJJ est maintenant suivie par Mme Remplaçante.")).toBeInTheDocument();
    expect(appels.find((a) => a.cle === "PATCH /admin/classes/4").corps).toEqual({ enseignant_id: 5 });

    await userEvent.click(screen.getByRole("tab", { name: "Supprimer" }));
    const bouton = screen.getByRole("button", { name: "Supprimer la classe" });
    expect(bouton).toBeDisabled();
    await userEvent.type(screen.getByLabelText(/Pour confirmer/), "2nde-exc-42jjj");
    await userEvent.click(bouton);
    await vi.waitFor(() => expect(onFermer).toHaveBeenCalled());
    expect(onChange).toHaveBeenCalledWith("Classe 2NDE-EXC-42JJJ supprimée.");
  });
});

describe("administrateur : enfants des familles", () => {
  it("montre les enfants inscrits nulle part et les inscrit dans une classe de leur niveau", async () => {
    let enfants = [
      { id: 7, prenom: "Noé", nom: "Durand", niveau: "2nde", identifiant: "noe-p2q3", a_un_code: true, derniere_connexion: null, maths: [], anglais: [] },
    ];
    const appels = fausseApi({
      "GET /admin/enfants?": () => ({ json: enfants }),
      "GET /admin/enfants?sans_classe=true": () => ({ json: enfants.filter((e) => !e.maths.length) }),
      "GET /admin/classes": {
        json: [
          { ...CLASSE, id: 1, code: "2NDE-TC-AAAAA", parcours: "tronc-commun" },
          { ...CLASSE, id: 2, code: "1RE-SPE-BBBBB", niveau: "1re", parcours: "specialite" },
        ],
      },
      "POST /admin/classes/1/enfants": () => {
        enfants = [{ ...enfants[0], maths: [{ eleve_id: 30, code_classe: "2NDE-TC-AAAAA" }] }];
        return { json: { ajoutes: ["Noé Durand"], refus: [] } };
      },
    });
    render(<ListeEnfants appeler={appeler} />);
    expect(await screen.findByText("Noé Durand")).toBeInTheDocument();
    expect(screen.getByText("Sans classe")).toBeInTheDocument();
    const choix = screen.getByLabelText("Inscrire Noé Durand dans une classe");
    expect(within(choix).queryByText(/1RE-SPE/)).not.toBeInTheDocument(); // autre niveau
    await userEvent.selectOptions(choix, "1");
    expect(await screen.findByText("Inscription faite : Noé Durand.")).toBeInTheDocument();
    expect(appels.find((a) => a.cle === "POST /admin/classes/1/enfants").corps).toEqual({ enfant_ids: [7] });

    await userEvent.click(screen.getByLabelText(/Seulement les enfants inscrits nulle part/));
    expect(await screen.findByText("Aucun enfant ne correspond.")).toBeInTheDocument();
  });
});
