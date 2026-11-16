// Issue #98 — Intégration du premier dossier Français 3e en DEV (Claude)
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import EspaceFrancais from "../francais/EspaceFrancais.jsx";
import { fausseApi } from "./setup.js";

const RESUME = {
  code: "FR3-DNB27-01", titre: "Comprendre un texte et justifier sa réponse", domaine: "francais-college", niveau: "3e",
  libelle_domaine: "Français collège", version: 1, statut: "soumis", motif_refus: null, version_validee: null,
  nb_questions: 11, cible: "DNB général, session 2027", competences_locales: ["FR3-L01"],
  attribution: { redaction: "Codex", redaction_issue: 55, integration: "Claude", integration_issue: 98 },
  registre: {}, auteur: null, validateur: null, decide_le: null, visible_eleves: false, peut_valider: false,
};
const ELEVE = {
  presentation: ["Français — 3e"], objectifs: ["Repérer une information."],
  lecon: [{ titre: "1. Je comprends", markdown: "Une information **explicite** est donnée directement." }],
  textes: [{ code: "TEXTE-1", titre: "La place près de la fenêtre", lignes: ["La porte de la salle était déjà ouverte."], mention: null }],
  consignes_questions: [],
  questions: [{ code: "Q1", partie: "entrainement", texte: "TEXTE-1", difficulte_proposee: 1, consigne: "Quel projet ?", coup_de_pouce: null, retour: "humain" }],
  je_verifie: null,
};
const PROFESSEUR = {
  presentation: [], deroulement: null, principes_correction: "Accepter une autre réponse cohérente.",
  questions: [{ code: "Q1", partie: "entrainement", consigne: "Quel projet ?", corrige: { question: "Q1", paragraphes: ["Un jardin avec des bancs."] } }],
  grille: null, controle_avant_utilisation: ["Relire le texte."], remarques: [], retour_seance: null,
};

function connecte() {
  sessionStorage.setItem("pkp.enseignant", JSON.stringify({ jeton: "j", nom: "Mme Martin", role: "enseignant", mdp_provisoire: false }));
}

describe("Français : préparation réservée aux adultes", () => {
  it("un compte sans habilitation française voit un accès réservé", async () => {
    connecte();
    fausseApi({ "GET /francais/dossiers": { status: 403, json: { detail: "Réservé" } } });
    render(<EspaceFrancais />);
    expect(await screen.findByText("Espace réservé aux adultes habilités en français")).toBeInTheDocument();
  });

  it("l'aperçu élève ne montre pas le corrigé ; l'onglet professeur le montre", async () => {
    connecte();
    fausseApi({
      "GET /francais/dossiers": { json: [RESUME] },
      "GET /francais/dossiers/FR3-DNB27-01/eleve": { json: { ...RESUME, eleve: ELEVE } },
      "GET /francais/dossiers/FR3-DNB27-01/professeur": { json: { ...RESUME, professeur: PROFESSEUR } },
    });
    render(<EspaceFrancais />);
    expect(await screen.findByText(/non publiés aux élèves/)).toBeInTheDocument();
    expect(screen.getByText(/Non visible des élèves/)).toBeInTheDocument();
    expect(screen.getByText(/Rédaction : Codex/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Ouvrir" }));
    expect(await screen.findByText("La porte de la salle était déjà ouverte.")).toBeInTheDocument();
    expect(screen.getByText("Réponse rédigée : retour du professeur.")).toBeInTheDocument();
    expect(screen.queryByText("Un jardin avec des bancs.")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("tab", { name: "Supports professeur (corrigés)" }));
    expect(await screen.findByText("Un jardin avec des bancs.")).toBeInTheDocument();
  });
});
