import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import EspaceEleve from "../eleve/EspaceEleve.jsx";
import { fausseApi } from "./setup.js";

const LECON = {
  competence_id: 10, code: "TLE-LN-DEF", libelle: "Définir la fonction logarithme népérien",
  chapitre: "Fonction logarithme népérien", resume: "Résumé.", cours: "Cours.",
};
const QUESTION = { id: 30, competence_id: 10, enonce: "Calculer $\\ln(1)$.", type: "numerique", difficulte: 1 };
const HISTORIQUE = {
  total: 2,
  erreurs: 1,
  elements: [
    {
      id: 2, repondu_le: "2026-10-31T10:05:00Z", seance_id: 3, question_id: 30, competence_id: 10,
      competence: "Définir la fonction logarithme népérien", chapitre: "Fonction logarithme népérien",
      enonce: "Calculer $\\ln(1)$.", type: "numerique", difficulte: 1, reponse_donnee: "1", correcte: false,
      solution: "0", correction: { etapes: ["$\\ln(1) = 0$ car $e^0 = 1$."], resultat: "0" }, duree_s: 12.5,
    },
    {
      id: 1, repondu_le: "2026-10-31T10:00:00Z", seance_id: 3, question_id: 31, competence_id: 10,
      competence: "Définir la fonction logarithme népérien", chapitre: "Fonction logarithme népérien",
      enonce: "Calculer $\\ln(e)$.", type: "numerique", difficulte: 1, reponse_donnee: "1", correcte: true,
      solution: "1", correction: null, duree_s: 8,
    },
  ],
};

function connecterEmma() {
  sessionStorage.setItem(
    "pkp.eleve",
    JSON.stringify({ jeton: "j", eleve: { id: 5, prenom: "Emma", code_classe: "TLE-C-DEMO", niveau: "Tle" } }),
  );
}

describe("lien entre exercices, cours et historique", () => {
  it("garde l'exercice et sa correction quand on va voir le cours, puis y revient", async () => {
    connecterEmma();
    const appels = fausseApi({
      "POST /seances": { status: 201, json: { id: 3 } },
      "GET /seances/3/question": { json: QUESTION },
      "POST /seances/3/reponses": {
        json: { correcte: false, solution: "0", maitrise: 0, maitrisee: false, correction: { etapes: ["$e^0 = 1$."] } },
      },
      "GET /cours": { json: [] },
      "GET /cours/10": { json: LECON },
    });
    render(<EspaceEleve />);
    await userEvent.click(screen.getByRole("button", { name: "Démarrer une séance" }));
    await userEvent.type(await screen.findByLabelText("Ta réponse"), "1{Enter}");
    expect(await screen.findByText("Pas tout à fait.")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Revoir le cours" }));
    expect(await screen.findByRole("heading", { name: LECON.libelle })).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole("button", { name: /Revenir à l'exercice/ })[0]);

    expect(screen.getByRole("tab", { name: "S'entraîner" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("Pas tout à fait.")).toBeVisible(); // le résultat et la correction sont toujours là
    expect(screen.getByText("Voir la correction détaillée")).toBeInTheDocument();
    expect(appels.filter((a) => a.cle === "GET /seances/3/question")).toHaveLength(1); // pas de nouvelle question
  });

  it("lance un entrainement ciblé sur la compétence depuis la leçon", async () => {
    connecterEmma();
    const appels = fausseApi({
      "GET /cours": {
        json: [{ id: 4, code: "TLE-LN", titre: "Logarithme", competences: [{ id: 10, code: "TLE-LN-DEF", libelle: LECON.libelle, a_une_lecon: true }] }],
      },
      "GET /cours/10": { json: LECON },
      "POST /seances": { status: 201, json: { id: 7, competences: [{ id: 10, libelle: LECON.libelle }] } },
      "GET /seances/7/question": { json: QUESTION },
    });
    render(<EspaceEleve />);
    await userEvent.click(screen.getByRole("tab", { name: "Cours" }));
    await userEvent.click(await screen.findByRole("button", { name: LECON.libelle }));
    await userEvent.click(await screen.findByRole("button", { name: "S'entraîner sur cette compétence" }));

    expect(appels.find((a) => a.cle === "POST /seances").corps).toEqual({ competence_ids: [10] });
    expect(await screen.findByText(/Entrainement ciblé/)).toHaveTextContent(LECON.libelle);
    expect(screen.getByRole("tab", { name: "S'entraîner" })).toHaveAttribute("aria-selected", "true");
  });

  it("montre l'historique avec la réponse attendue, la correction et le filtre des erreurs", async () => {
    connecterEmma();
    const appels = fausseApi({
      "GET /eleves/moi/historique?page=1&erreurs=false": { json: HISTORIQUE },
      "GET /eleves/moi/historique?page=1&erreurs=true": { json: { ...HISTORIQUE, total: 1, elements: [HISTORIQUE.elements[0]] } },
    });
    render(<EspaceEleve />);
    await userEvent.click(screen.getByRole("tab", { name: "Mon historique" }));
    expect(await screen.findByText("2 réponses · 1 erreur")).toBeInTheDocument();
    const [faute] = screen.getAllByRole("listitem");
    expect(within(faute).getByText("À revoir")).toBeInTheDocument();
    expect(within(faute).getByText(/Réponse attendue/)).toBeInTheDocument();
    expect(within(faute).getByText("Voir la correction détaillée")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("checkbox", { name: "Seulement mes erreurs" }));
    expect(await screen.findAllByText("À revoir")).toHaveLength(1);
    expect(screen.queryByText("Réussie")).not.toBeInTheDocument();
    expect(appels.some((a) => a.cle.endsWith("erreurs=true"))).toBe(true);
  });
});

describe("partie du cours à utiliser", () => {
  it("montre le résumé de la compétence quand la correction détaillée manque", async () => {
    connecterEmma();
    fausseApi({
      "POST /seances": { status: 201, json: { id: 3 } },
      "GET /seances/3/question": { json: QUESTION },
      "POST /seances/3/reponses": {
        json: { correcte: false, solution: "0", maitrise: 0, maitrisee: false, correction: null,
                competence: LECON.libelle, rappel: "- $\ln(1) = 0$" },
      },
    });
    render(<EspaceEleve />);
    await userEvent.click(screen.getByRole("button", { name: "Démarrer une séance" }));
    await userEvent.type(await screen.findByLabelText("Ta réponse"), "1{Enter}");
    expect(await screen.findByText(`Partie du cours à utiliser : ${LECON.libelle}`)).toBeVisible();
    expect(screen.getByText(/pas encore rédigée/)).toBeVisible(); // ouvert d'office après une erreur
  });
});

describe("méthode PKP", () => {
  it("présente les cinq étapes et les dix gestes", async () => {
    const { default: Methode } = await import("../Methode.jsx");
    render(<Methode />);
    expect(screen.getAllByRole("listitem").slice(0, 5).map((li) => li.querySelector("strong").textContent)).toEqual([
      "Je comprends", "Je mémorise", "Je m'entraîne", "Je me dépasse", "Je vérifie",
    ]);
    expect(screen.getByText("10. Persévérer intelligemment")).toBeInTheDocument();
  });

  it("propose dans la leçon l'étape suivante et lance un entrainement de niveaux 1 à 3", async () => {
    connecterEmma();
    const appels = fausseApi({
      "GET /cours": {
        json: [{ id: 4, code: "TLE-LN", titre: "Logarithme", competences: [{ id: 10, code: "TLE-LN-DEF", libelle: LECON.libelle, a_une_lecon: true }] }],
      },
      "GET /cours/10": { json: LECON },
      "GET /eleves/moi/competences/10/avancement": {
        json: { competence_id: 10, libelle: LECON.libelle, reponses: 2, reussies_bases: 1, objectif_bases: 3,
                reussies_avancees: 0, objectif_avancees: 2, maitrise: 0.2, maitrisee: false },
      },
      "POST /seances": { status: 201, json: { id: 8 } },
      "GET /seances/8/question": { json: QUESTION },
    });
    render(<EspaceEleve />);
    await userEvent.click(screen.getByRole("tab", { name: "Cours" }));
    await userEvent.click(await screen.findByRole("button", { name: LECON.libelle }));
    const etapes = await screen.findByRole("navigation", { name: "Méthode PKP pour cette compétence" });
    expect(await within(etapes).findByText("1 / 3 réussies (niveaux 1 à 3)")).toBeInTheDocument();
    const suivante = etapes.querySelector('[aria-current="step"]');
    expect(suivante).toHaveTextContent("Je m'entraîne");
    await userEvent.click(within(suivante).getByRole("button", { name: "S'entraîner" }));
    expect(appels.find((a) => a.cle === "POST /seances").corps).toEqual({ competence_ids: [10], difficulte_min: 1, difficulte_max: 3 });
    expect(await screen.findByText(/niveaux 1 à 3/)).toBeInTheDocument();
  });
});
