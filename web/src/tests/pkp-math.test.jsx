import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import EspaceParent from "../parent/EspaceParent.jsx";
import PkpMath from "../pkpmath/PkpMath.jsx";
import { fausseApi } from "./setup.js";

const CATALOGUE = [
  { id: 1, code: "2NDE-FRAC", titre: "Fractions", niveau: "2nde", parcours: "tronc-commun", libelle_parcours: "Tronc commun", ordre: 1, nb_competences: 2, nb_questions: 3, valide: false },
  { id: 2, code: "1RE-SUITES", titre: "Suites", niveau: "1re", parcours: "specialite", libelle_parcours: "Spécialité", ordre: 1, nb_competences: 1, nb_questions: 1, valide: true },
];
const QUESTION = (id, difficulte) => ({
  id, code: `Q${id}`, difficulte, type: "numerique", enonce: `Calculer $${id}+1$.`, solution: String(id + 1),
  correction: { methode: "Additionner.", etapes: [`$${id}+1=${id + 1}$`], resultat: String(id + 1) }, validee: false,
});
const DOC = {
  id: 1, code: "2NDE-FRAC", titre: "Fractions", niveau: "2nde", parcours: "tronc-commun", libelle_parcours: "Tronc commun", valide: false,
  competences: [
    { id: 10, code: "C1", libelle: "Additionner des fractions", objectifs: ["Additionner"], resume: "Même dénominateur.", cours: "## Cours\nTexte du cours.",
      methodes: [{ titre: "Réduire au même dénominateur", etapes: ["Trouver le dénominateur commun."], exemple: { enonce: "$\\dfrac12+\\dfrac13$", resolution: ["$\\dfrac56$"], resultat: "$\\dfrac56$" } }],
      erreurs_frequentes: [{ erreur: "Additionner les dénominateurs.", explication: "Non." }], questions: [QUESTION(1, 1), QUESTION(2, 4)] },
    { id: 11, code: "C2", libelle: "Simplifier", objectifs: [], resume: "Diviser par le PGCD.", cours: "", methodes: [], erreurs_frequentes: [], questions: [QUESTION(3, 2)] },
  ],
};

describe("PKP Math", () => {
  it("catalogue par niveau, document du chapitre et export PDF avec la mention NON VALIDÉ", async () => {
    fausseApi({ "GET /pkp-math/catalogue": { json: CATALOGUE }, "GET /pkp-math/chapitres/1": { json: DOC } });
    const imprimer = vi.spyOn(window, "print").mockImplementation(() => {});
    render(<PkpMath jeton="j" niveauParDefaut="2nde" />);
    expect(await screen.findByRole("button", { name: /Fractions/ })).toHaveTextContent("Non validé");
    expect(screen.queryByRole("button", { name: /Suites/ })).not.toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Niveau"), "");
    expect(screen.getByRole("button", { name: /Suites/ })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Fractions/ }));
    expect(await screen.findByRole("heading", { name: "Fractions" })).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent("Non validé");
    expect(screen.getByText("Même dénominateur.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Fiche d'exercices" }));
    expect(screen.getByText("Exercice 3")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Corrigé" }));
    expect(screen.getAllByText("Additionner.").length).toBe(3);

    // Export : fiche d'exercices et corrigé, une seule compétence, difficultés 1 à 2.
    await userEvent.click(screen.getByRole("button", { name: "Exporter en PDF" }));
    const fenetre = screen.getByRole("dialog", { name: "Exporter en PDF" });
    await userEvent.click(within(fenetre).getByLabelText("Fiche d'exercices"));
    await userEvent.click(within(fenetre).getByLabelText("Simplifier"));
    await userEvent.selectOptions(within(fenetre).getByLabelText("à"), "2");
    await userEvent.click(within(fenetre).getByRole("button", { name: "Exporter" }));
    await vi.waitFor(() => expect(imprimer).toHaveBeenCalled());
    const impression = document.getElementById("pkp-impression");
    expect(impression).toHaveTextContent("NON VALIDÉ");
    expect(impression).toHaveTextContent("Fiche d'exercices");
    expect(impression).toHaveTextContent("Exercice 1");
    expect(impression).not.toHaveTextContent("Exercice 2"); // difficulté 4 exclue
    expect(impression).not.toHaveTextContent("Simplifier");
    expect(document.body).toHaveClass("pkp-imprime");
    window.dispatchEvent(new Event("afterprint"));
    await vi.waitFor(() => expect(document.getElementById("pkp-impression")).toBeNull());
  });
});

describe("espace parent : enfants de la famille", () => {
  const SUIVI = {
    enfant: {
      id: 7, prenom: "Inès", nom: "Martin", niveau: "2nde", identifiant: "ines-k7m4", a_un_code: true, derniere_connexion: null,
      maths: [{ eleve_id: 11, code_classe: "2NDE-TC-AAAAA", niveau: "2nde", parcours: "tronc-commun", libelle_parcours: "Tronc commun", enseignant: "M. Prof" }],
      anglais: [],
    },
    matieres: [
      { code: "maths", libelle: "PKP Math", disponible: true },
      { code: "anglais", libelle: "PKP Anglais", disponible: true },
      { code: "francais", libelle: "PKP Français", disponible: false },
    ],
    maths: [],
    anglais: [{ groupe: "4e A", niveau: "2nde", seances_faites: 3, score_moyen: 0.8, i_can: 5 }],
  };

  it("suit l'anglais, annonce le français et renouvelle l'accès de l'enfant", async () => {
    sessionStorage.setItem("pkp.parent", JSON.stringify({ jeton: "j", email: "p@x.fr", mdp_provisoire: false }));
    const appels = fausseApi({
      "GET /parents/famille": { json: [SUIVI] },
      "GET /parents/enfants": { json: [] },
      "POST /parents/famille/7/acces": { json: { identifiant: "ines-k7m4", code: "NEW234" } },
    });
    render(<EspaceParent />);
    expect(await screen.findByText(/identifiant ines-k7m4/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "PKP Anglais" }));
    expect(screen.getByText("3 séances")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "PKP Français" }));
    expect(screen.getByText(/Le français arrive bientôt/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Accès de l'enfant" }));
    await userEvent.click(screen.getByRole("button", { name: "Générer un nouveau code" }));
    expect(await screen.findByText("NEW234")).toBeInTheDocument();
    expect(appels.find((a) => a.cle === "POST /parents/famille/7/acces").corps).toEqual({});
  });
});
