// Issue #217 — Parcours du français au niveau de l'anglais (Claude)
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { AutoEvaluation, QuizFrancais, ReponsesRedigees } from "../eleve/ActiviteFrancais.jsx";
import EditionDossier from "../francais/EditionDossier.jsx";
import SuiviFrancais from "../francais/SuiviFrancais.jsx";
import { api } from "../api.js";
import { fausseApi } from "./setup.js";

const CODE = "FR3-DNB27-01";
const QUIZ = [
  { question: "Qui raconte ?", texte: "TEXTE-1", choix: ["Le narrateur", "L'auteur"] },
  { question: "Une information implicite est…", texte: null, choix: ["écrite", "à déduire"] },
];
const dossier = (extra = {}) => ({
  code: CODE,
  titre: "Comprendre un texte",
  mode_correction: "apres_chaque_question",
  auto_evaluation: [],
  saisie_ouverte: false,
  reponses: [],
  eleve: {
    quiz: QUIZ,
    je_sais: ["Je sais citer une ligne."],
    questions: [{ code: "Q1", consigne: "Quel est le projet ?" }],
  },
  ...extra,
});
const appeler = (chemin, options = {}) => api(chemin, { ...options, jeton: "j" });

describe("Élève : quiz de français (#217)", () => {
  it("après chaque question : la réponse est envoyée puis corrigée, et le score enregistré à la fin", async () => {
    const appels = fausseApi({
      [`POST /francais/eleve/dossiers/${CODE}/quiz/0`]: {
        json: { juste: false, reponse: 0, choix: 1, explication: "Le narrateur raconte." },
      },
      [`POST /francais/eleve/dossiers/${CODE}/quiz/1`]: { json: { juste: true, reponse: 1, choix: 1, explication: "" } },
      [`POST /francais/eleve/dossiers/${CODE}/corriger`]: {
        json: {
          score: 1,
          total: 2,
          meilleur_score: 1,
          premier_score: 1,
          tentatives: 1,
          details: [
            { juste: false, reponse: 0, choix: 1, explication: "Le narrateur raconte." },
            { juste: true, reponse: 1, choix: 1, explication: "" },
          ],
        },
      },
    });
    render(<QuizFrancais dossier={dossier()} jeton="j" />);
    await userEvent.click(screen.getByLabelText("B) L'auteur"));
    expect(await screen.findByText(/Réponse attendue : A\) Le narrateur/)).toBeInTheDocument();
    expect(screen.getByLabelText("A) Le narrateur")).toBeDisabled();
    await userEvent.click(screen.getByLabelText("B) à déduire"));
    await userEvent.click(await screen.findByRole("button", { name: "Terminer le quiz" }));
    expect(await screen.findByText(/Score : 1\/2/)).toBeInTheDocument();
    expect(appels.find((a) => a.cle.endsWith("/corriger")).corps).toEqual({ reponses: [1, 1] });
  });

  it("à la fin du quiz : aucune correction avant d'avoir répondu à tout", async () => {
    const appels = fausseApi({
      [`POST /francais/eleve/dossiers/${CODE}/corriger`]: {
        json: {
          score: 2,
          total: 2,
          meilleur_score: 2,
          details: [
            { juste: true, reponse: 0, choix: 0, explication: "" },
            { juste: true, reponse: 1, choix: 1, explication: "" },
          ],
        },
      },
    });
    render(<QuizFrancais dossier={dossier({ mode_correction: "fin_du_quiz" })} jeton="j" />);
    await userEvent.click(screen.getByLabelText("A) Le narrateur"));
    expect(appels).toHaveLength(0);
    expect(screen.getByRole("button", { name: "Voir la correction" })).toBeDisabled();
    await userEvent.click(screen.getByLabelText("B) à déduire"));
    await userEvent.click(screen.getByRole("button", { name: "Voir la correction" }));
    expect(await screen.findByText(/Score : 2\/2/)).toBeInTheDocument();
  });
});

describe("Élève : auto-évaluation et réponses rédigées (#217)", () => {
  it("enregistre l'auto-évaluation", async () => {
    const appels = fausseApi({
      [`PUT /francais/eleve/dossiers/${CODE}/auto-evaluation`]: { json: { auto_evaluation: ["autonome"] } },
    });
    render(<AutoEvaluation dossier={dossier()} jeton="j" />);
    await userEvent.selectOptions(screen.getByLabelText("Je sais citer une ligne."), "autonome");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
    expect(await screen.findByText("Enregistré")).toBeInTheDocument();
    expect(appels[0].corps).toEqual({ niveaux: ["autonome"] });
  });

  it("saisie fermée : réponses au cahier", () => {
    fausseApi({});
    render(<ReponsesRedigees dossier={dossier()} jeton="j" />);
    expect(screen.getByText(/Réponds aux questions dans ton cahier/)).toBeInTheDocument();
  });

  it("saisie ouverte : remise, puis retour du professeur affiché", async () => {
    const appels = fausseApi({
      [`PUT /francais/eleve/dossiers/${CODE}/reponses/Q1`]: {
        json: { question: "Q1", texte: "Un jardin.", statut: "brouillon" },
      },
      [`POST /francais/eleve/dossiers/${CODE}/reponses/Q1/remise`]: {
        json: { question: "Q1", texte: "Un jardin.", statut: "remise" },
      },
    });
    render(<ReponsesRedigees dossier={dossier({ saisie_ouverte: true })} jeton="j" />);
    await userEvent.type(screen.getByLabelText(/Quel est le projet/), "Un jardin.");
    await userEvent.click(screen.getByRole("button", { name: "Remettre" }));
    expect(await screen.findByText(/en attente du retour/)).toBeInTheDocument();
    expect(appels.map((a) => a.cle)).toEqual([
      `PUT /francais/eleve/dossiers/${CODE}/reponses/Q1`,
      `POST /francais/eleve/dossiers/${CODE}/reponses/Q1/remise`,
    ]);
    expect(screen.getByLabelText(/Quel est le projet/)).toBeDisabled();
  });

  it("affiche le retour du professeur", () => {
    fausseApi({});
    const reponses = [{ question: "Q1", texte: "Un jardin.", statut: "corrigee", commentaire: "Cite la ligne 4." }];
    render(<ReponsesRedigees dossier={dossier({ saisie_ouverte: true, reponses })} jeton="j" />);
    expect(screen.getByText("Retour du professeur : Cite la ligne 4.")).toBeInTheDocument();
  });
});

describe("Professeur : suivi des classes (#217)", () => {
  const routes = {
    "GET /francais/classes": { json: [{ id: 7, code: "3E-FR-A", niveau: "3e", acces_eleves: true, dossiers: [] }] },
    "GET /francais/classes/7/progression": {
      json: {
        classe: { id: 7, code: "3E-FR-A", niveau: "3e" },
        dossiers: [{ code: CODE, titre: "Comprendre un texte", nb_quiz: 2, je_sais: ["Je sais citer une ligne."] }],
        eleves: [
          {
            id: 1,
            prenom: "Lina",
            dossiers: {
              [CODE]: {
                score: 1,
                premier_score: 0,
                total: 2,
                tentatives: 2,
                auto_evaluation: ["autonome"],
                a_relire: 1,
                relues: 0,
              },
            },
          },
        ],
      },
    },
    "GET /francais/classes/7/correction": { json: { mode: "apres_chaque_question", dossiers: {} } },
    "PUT /francais/classes/7/correction": { json: { mode: "fin_du_quiz", dossiers: {} } },
    "GET /francais/classes/7/reponses": {
      json: [{ id: 3, prenom: "Lina", dossier: CODE, question: "Q1", texte: "Un jardin.", statut: "remise" }],
    },
    "PUT /francais/reponses/3/retour": { json: { statut: "corrigee" } },
  };

  it("progression, mode de correction et retour sur une réponse", async () => {
    const appels = fausseApi(routes);
    render(<SuiviFrancais appeler={appeler} jeton="j" />);
    expect(await screen.findByText(/1er essai 0\/2, 2 essais/)).toBeInTheDocument();
    expect(screen.getByText("Oui !")).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Pour toute la classe"), "fin_du_quiz");
    await waitFor(() => expect(appels.some((a) => a.cle === "PUT /francais/classes/7/correction")).toBe(true));
    expect(await screen.findByText("Un jardin.")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Votre retour"), "Cite la ligne.");
    await userEvent.click(screen.getByRole("button", { name: "Envoyer le retour" }));
    await waitFor(() =>
      expect(appels.find((a) => a.cle === "PUT /francais/reponses/3/retour")?.corps).toEqual({ commentaire: "Cite la ligne." }),
    );
  });

  it("rédaction fermée : pas de liste de réponses, sans message d'erreur", async () => {
    fausseApi({ ...routes, "GET /francais/classes/7/reponses": { status: 403, json: { detail: "Fermée" } } });
    render(<SuiviFrancais appeler={appeler} jeton="j" />);
    expect(await screen.findByText("Progression")).toBeInTheDocument();
    expect(screen.queryByText(/Réponses rédigées à relire/)).not.toBeInTheDocument();
    expect(screen.queryByText("Fermée")).not.toBeInTheDocument();
  });
});

describe("Administrateur : édition d'un dossier (#217)", () => {
  it("enregistre un brouillon puis le soumet", async () => {
    const appels = fausseApi({
      [`GET /francais/dossiers/${CODE}/source`]: {
        json: { version_affichee: 2, validee: true, statut: "valide", source: { code: CODE, titre: "Comprendre" } },
      },
      [`PUT /francais/dossiers/${CODE}/brouillon`]: { json: { version: 3, statut: "brouillon" } },
      [`POST /francais/dossiers/${CODE}/soumettre`]: { json: { version: 3, statut: "soumis" } },
    });
    render(<EditionDossier code={CODE} appeler={appeler} />);
    const zone = await screen.findByLabelText("Contenu du dossier (JSON)");
    expect(screen.getByRole("button", { name: "Soumettre à la validation" })).toBeDisabled();
    await userEvent.clear(zone);
    await userEvent.type(zone, "{{ pas du json");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer un brouillon" }));
    expect(await screen.findByText(/JSON invalide/)).toBeInTheDocument();
    await userEvent.clear(zone);
    await userEvent.type(zone, `{{"code": "${CODE}"}`);
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer un brouillon" }));
    expect(await screen.findByText(/Brouillon v3 enregistré/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Soumettre à la validation" }));
    expect(await screen.findByText(/soumise à la validation/)).toBeInTheDocument();
    expect(appels.find((a) => a.cle.endsWith("/brouillon")).corps).toEqual({ code: CODE });
  });
});
