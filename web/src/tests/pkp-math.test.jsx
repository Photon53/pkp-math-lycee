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

describe("PKP Maths", () => {
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

  it("élève : le corrigé d'un exercice sans réponse en séance reste masqué (ARCH-4)", async () => {
    const masquee = { ...QUESTION(2, 1), solution: "", correction: null, corrige_visible: false };
    const doc = { ...DOC, competences: [{ ...DOC.competences[0], questions: [{ ...QUESTION(1, 1), corrige_visible: true }, masquee] }] };
    fausseApi({ "GET /pkp-math/catalogue": { json: CATALOGUE }, "GET /pkp-math/chapitres/1": { json: doc } });
    render(<PkpMath jeton="j" niveauParDefaut="2nde" />);
    await userEvent.click(await screen.findByRole("button", { name: /Fractions/ }));
    await userEvent.click(await screen.findByRole("tab", { name: "Corrigé" }));
    expect(screen.getAllByText("Additionner.").length).toBe(1);
    expect(screen.getByText(/Le corrigé s'affichera ici après ta réponse/)).toBeInTheDocument();
  });
});

// Issue #178 : PDF élève (sans aucun corrigé, redemandé à l'API) et PDF professeur (avec corrigés).
const CORRIGE_PROF = {
  rappel: "Rappel de la règle.", methode: "Additionner.", etapes: ["Étape détaillée du corrigé."], resultat: "2",
  autre_methode: "Passer par un schéma.", erreurs_frequentes: ["Oublier la retenue."],
};
const DOC_COMPLET = {
  ...DOC, matiere: "maths", version: "complete",
  competences: [{ ...DOC.competences[0], questions: [{ ...QUESTION(1, 1), correction: CORRIGE_PROF }] }],
};
const DOC_ELEVE = {
  ...DOC_COMPLET, version: "eleve",
  competences: [{
    ...DOC_COMPLET.competences[0],
    // Énoncé propre à la version élève : prouve que l'impression part du document redemandé à l'API.
    questions: [{ ...QUESTION(1, 1), enonce: "Énoncé servi en version élève.", solution: "", correction: null, corrige_visible: false }],
  }],
};

async function ouvrirExport(routes, props = {}) {
  const appels = fausseApi({ "GET /pkp-math/catalogue": { json: CATALOGUE }, "GET /pkp-math/chapitres/1": { json: DOC_COMPLET }, ...routes });
  const imprimer = vi.spyOn(window, "print").mockImplementation(() => {});
  render(<PkpMath jeton="j" niveauParDefaut="2nde" adulte {...props} />);
  await userEvent.click(await screen.findByRole("button", { name: /Fractions/ }));
  await screen.findByRole("heading", { name: "Fractions" });
  await userEvent.click(screen.getByRole("button", { name: "Exporter en PDF" }));
  return { appels, imprimer, fenetre: screen.getByRole("dialog", { name: "Exporter en PDF" }) };
}

describe("export PDF élève et professeur (#178)", () => {
  it("PDF élève par défaut : document redemandé sans corrigé, aucun corrigé imprimé", async () => {
    const { appels, imprimer, fenetre } = await ouvrirExport({ "GET /pkp-math/chapitres/1?version=eleve": { json: DOC_ELEVE } });
    expect(within(fenetre).getByLabelText(/PDF élève/)).toBeChecked();
    expect(within(fenetre).queryByLabelText("Corrigé")).not.toBeInTheDocument();
    await userEvent.click(within(fenetre).getByLabelText("Fiche d'exercices"));
    await userEvent.click(within(fenetre).getByRole("button", { name: "Exporter" }));
    await vi.waitFor(() => expect(imprimer).toHaveBeenCalled());
    expect(appels.map((a) => a.cle)).toContain("GET /pkp-math/chapitres/1?version=eleve");
    const impression = document.getElementById("pkp-impression");
    expect(impression).toHaveTextContent("Version élève");
    expect(impression).toHaveTextContent("Énoncé servi en version élève.");
    expect(document.title).toBe("PKP Maths - Fractions - élève");
    for (const texte of ["Étape détaillée du corrigé.", "Oublier la retenue.", "Passer par un schéma.", "Rappel de la règle.", "Réponse :"])
      expect(impression).not.toHaveTextContent(texte);
    window.dispatchEvent(new Event("afterprint"));
  });

  it("PDF professeur : corrigés complets avec rappel, autre méthode et erreurs fréquentes", async () => {
    const { appels, imprimer, fenetre } = await ouvrirExport({});
    await userEvent.click(within(fenetre).getByLabelText(/PDF professeur/));
    await userEvent.click(within(fenetre).getByLabelText("Corrigé"));
    await userEvent.click(within(fenetre).getByRole("button", { name: "Exporter" }));
    await vi.waitFor(() => expect(imprimer).toHaveBeenCalled());
    expect(appels.map((a) => a.cle)).not.toContain("GET /pkp-math/chapitres/1?version=eleve");
    const impression = document.getElementById("pkp-impression");
    expect(impression).toHaveTextContent("Version professeur");
    expect(document.title).toBe("PKP Maths - Fractions - professeur (corrigé)");
    for (const texte of ["Rappel de la règle.", "Étape détaillée du corrigé.", "Passer par un schéma.", "Oublier la retenue."])
      expect(impression).toHaveTextContent(texte);
    window.dispatchEvent(new Event("afterprint"));
  });

  it("passer de la version professeur à la version élève retire le corrigé ; erreur réseau affichée", async () => {
    const { imprimer, fenetre } = await ouvrirExport({ "GET /pkp-math/chapitres/1?version=eleve": { status: 500, json: { detail: "Panne." } } });
    await userEvent.click(within(fenetre).getByLabelText(/PDF professeur/));
    await userEvent.click(within(fenetre).getByLabelText("Corrigé"));
    expect(within(fenetre).getByLabelText("Corrigé")).toBeChecked();
    await userEvent.click(within(fenetre).getByLabelText(/PDF élève/));
    expect(within(fenetre).queryByLabelText("Corrigé")).not.toBeInTheDocument();
    await userEvent.click(within(fenetre).getByRole("button", { name: "Exporter" }));
    expect(await screen.findByRole("button", { name: "Exporter en PDF" })).toBeEnabled();
    expect(imprimer).not.toHaveBeenCalled();
    expect(document.getElementById("pkp-impression")).toBeNull();
  });

  it("PDF élève refusé si l'API renvoie encore un corrigé", async () => {
    const fuite = { ...DOC_COMPLET, version: "eleve" };
    const { imprimer, fenetre } = await ouvrirExport({ "GET /pkp-math/chapitres/1?version=eleve": { json: fuite } });
    await userEvent.click(within(fenetre).getByRole("button", { name: "Exporter" }));
    expect(await screen.findByText(/export annulé/)).toBeInTheDocument();
    expect(imprimer).not.toHaveBeenCalled();
    expect(document.getElementById("pkp-impression")).toBeNull();
  });

  it("élève : pas de choix de version, et un chapitre de français porte la marque PKP Français", async () => {
    const francais = { ...DOC_COMPLET, matiere: "francais" };
    const { imprimer, fenetre } = await ouvrirExport({ "GET /pkp-math/chapitres/1": { json: francais } }, { adulte: false });
    expect(within(fenetre).queryByText("Version")).not.toBeInTheDocument();
    await userEvent.click(within(fenetre).getByRole("button", { name: "Exporter" }));
    await vi.waitFor(() => expect(imprimer).toHaveBeenCalled());
    const impression = document.getElementById("pkp-impression");
    expect(impression).toHaveTextContent("PKP Français");
    expect(impression).not.toHaveTextContent("PKP Maths");
    window.dispatchEvent(new Event("afterprint"));
  });
});

describe("espace parent : enfants de la famille", () => {
  const SUIVI = {
    enfant: {
      id: 7, prenom: "Inès", niveau: "2nde", identifiant: "ines-k7m4", a_un_code: true, derniere_connexion: null,
      maths: [{ eleve_id: 11, code_classe: "2NDE-TC-AAAAA", niveau: "2nde", parcours: "tronc-commun", libelle_parcours: "Tronc commun", enseignant: "M. Prof" }],
      anglais: [],
    },
    matieres: [
      { code: "maths", libelle: "PKP Maths", disponible: true },
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
