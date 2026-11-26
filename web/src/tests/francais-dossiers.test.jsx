// Issue #98 — Intégration du premier dossier Français 3e en DEV (Claude)
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import MonCours from "../eleve/MonCours.jsx";
import EspaceFrancais, { causesAbsence } from "../francais/EspaceFrancais.jsx";
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
    const appels = fausseApi({
      "GET /francais/dossiers": { status: 403, json: { detail: "Réservé" } },
      "GET /francais/etat": { status: 403, json: { detail: "Réservé aux administrateurs." } },
    });
    render(<EspaceFrancais />);
    expect(await screen.findByText("Espace réservé aux adultes habilités en français")).toBeInTheDocument();
    await waitFor(() => expect(appels.some((a) => a.cle === "GET /francais/etat")).toBe(true));
    expect(screen.queryByText("Diagnostic administrateur")).not.toBeInTheDocument();
  });

  it("l'aperçu élève ne montre pas le corrigé ; l'onglet professeur le montre", async () => {
    connecte();
    fausseApi({
      "GET /francais/dossiers": { json: [RESUME] },
      "GET /francais/dossiers/FR3-DNB27-01/eleve": { json: { ...RESUME, eleve: ELEVE } },
      "GET /francais/dossiers/FR3-DNB27-01/professeur": { json: { ...RESUME, professeur: PROFESSEUR } },
    });
    render(<EspaceFrancais />);
    expect(await screen.findByText(/lue par les élèves/)).toBeInTheDocument();
    // La note est affichée avant le chargement de la liste : attendre la liste elle-même (sinon dépend du minutage).
    expect(await screen.findByText(/Non visible des élèves/)).toBeInTheDocument();
    expect(screen.getByText(/Rédaction : Codex/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Ouvrir" }));
    expect(await screen.findByText("La porte de la salle était déjà ouverte.")).toBeInTheDocument();
    expect(screen.getByText("Réponse rédigée : retour du professeur.")).toBeInTheDocument();
    expect(screen.queryByText("Un jardin avec des bancs.")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("tab", { name: "Supports professeur (corrigés)" }));
    expect(await screen.findByText("Un jardin avec des bancs.")).toBeInTheDocument();
  });
});

// Issue #212 : liste vide ou refus expliqués à l'administrateur, sans rien montrer de plus aux professeurs.
const domaines = (college, lycee) => [
  { code: "francais-college", libelle: "Français collège", actif: college[0], dossiers: college[1] },
  { code: "francais-lycee", libelle: "Français lycée", actif: lycee[0], dossiers: lycee[1] },
];

describe("Français : cause d'une liste vide (#212)", () => {
  it("dossier non importé sur l'instance", async () => {
    connecte();
    fausseApi({
      "GET /francais/dossiers": { json: [] },
      "GET /francais/etat": { json: { domaines: domaines([true, 0], [false, 0]), dossiers: 0 } },
    });
    render(<EspaceFrancais />);
    expect(await screen.findByText(/Aucun dossier de français n'est importé dans la base de cette instance/)).toBeInTheDocument();
    expect(screen.getByText("Aucun dossier de français accessible avec vos habilitations.")).toBeInTheDocument();
  });

  it("dossier rangé dans un domaine non activé", async () => {
    connecte();
    fausseApi({
      "GET /francais/dossiers": { json: [] },
      "GET /francais/etat": { json: { domaines: domaines([false, 1], [true, 0]), dossiers: 1 } },
    });
    render(<EspaceFrancais />);
    expect(await screen.findByText(/1 dossier\(s\) rangé\(s\) dans « Français collège »/)).toBeInTheDocument();
  });

  it("aucun domaine actif : le refus de l'administrateur est expliqué", async () => {
    connecte();
    fausseApi({
      "GET /francais/dossiers": { status: 403, json: { detail: "Réservé" } },
      "GET /francais/etat": { json: { domaines: domaines([false, 1], [false, 0]), dossiers: 1 } },
    });
    render(<EspaceFrancais />);
    expect(await screen.findByText("Diagnostic administrateur")).toBeInTheDocument();
    expect(screen.getByText(/rangé\(s\) dans « Français collège », qui n'est pas activé/)).toBeInTheDocument();
  });

  it("professeur : liste vide sans diagnostic ni message d'erreur", async () => {
    connecte();
    const appels = fausseApi({
      "GET /francais/dossiers": { json: [] },
      "GET /francais/etat": { status: 403, json: { detail: "Réservé aux administrateurs." } },
    });
    render(<EspaceFrancais />);
    expect(await screen.findByText("Aucun dossier de français accessible avec vos habilitations.")).toBeInTheDocument();
    await waitFor(() => expect(appels.some((a) => a.cle === "GET /francais/etat")).toBe(true));
    expect(screen.queryByText("Diagnostic administrateur")).not.toBeInTheDocument();
    expect(screen.queryByText(/Réservé aux administrateurs/)).not.toBeInTheDocument();
  });

  it("causesAbsence : rien à expliquer quand l'état est inconnu ou cohérent", () => {
    expect(causesAbsence(null)).toEqual([]);
    expect(causesAbsence({ domaines: domaines([true, 1], [false, 0]), dossiers: 1 })).toEqual([]);
    expect(causesAbsence({ domaines: domaines([false, 0], [false, 0]), dossiers: 0 })).toHaveLength(2);
  });
});

// Issue #212 : circuit aligné sur l'anglais — file de validation, version validée diffusée, ouverture aux classes.
describe("Français : validation et ouverture aux classes (#212)", () => {
  it("le validateur relit la version soumise et la valide depuis la file", async () => {
    connecte();
    const appels = fausseApi({
      "GET /francais/dossiers": { json: [RESUME] },
      "GET /francais/validation": { json: [{ ...RESUME, est_auteur: false, peut_valider: true }] },
      "GET /francais/validation/FR3-DNB27-01": {
        json: { ...RESUME, version_affichee: 1, validee: false, eleve: ELEVE, professeur: PROFESSEUR, historique: [] },
      },
      "POST /francais/validation/FR3-DNB27-01/valider": { json: { ...RESUME, statut: "valide", version_validee: 1 } },
    });
    render(<EspaceFrancais />);
    await userEvent.click(await screen.findByRole("tab", { name: "Validation" }));
    await userEvent.selectOptions(await screen.findByLabelText(/Dossier à relire/), "FR3-DNB27-01");
    expect(await screen.findByText("La porte de la salle était déjà ouverte.")).toBeInTheDocument();
    expect(screen.getByText("Un jardin avec des bancs.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Valider cette version" }));
    expect(await screen.findByText(/validé : les classes ouvertes lisent cette version/)).toBeInTheDocument();
    expect(appels.some((a) => a.cle === "POST /francais/validation/FR3-DNB27-01/valider")).toBe(true);
  });

  it("l'auteur ne peut pas valider sa propre version", async () => {
    connecte();
    fausseApi({
      "GET /francais/dossiers": { json: [RESUME] },
      "GET /francais/validation": { json: [{ ...RESUME, est_auteur: true, peut_valider: false }] },
      "GET /francais/validation/FR3-DNB27-01": {
        json: { ...RESUME, version_affichee: 1, validee: false, eleve: ELEVE, professeur: PROFESSEUR, historique: [] },
      },
    });
    render(<EspaceFrancais />);
    await userEvent.click(await screen.findByRole("tab", { name: "Validation" }));
    await userEvent.selectOptions(await screen.findByLabelText(/Dossier à relire/), "FR3-DNB27-01");
    expect(await screen.findByText(/un autre validateur doit la valider/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Valider cette version" })).not.toBeInTheDocument();
  });

  it("un professeur sans habilitation de validateur ne voit pas la file", async () => {
    connecte();
    fausseApi({
      "GET /francais/dossiers": { json: [RESUME] },
      "GET /francais/validation": { status: 403, json: { detail: "Réservé aux validateurs de français." } },
    });
    render(<EspaceFrancais />);
    expect(await screen.findByText(/Non visible des élèves/)).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Validation" })).not.toBeInTheDocument();
    expect(screen.queryByText(/Réservé aux validateurs/)).not.toBeInTheDocument();
  });

  it("version non validée : mention NON VALIDÉ et ouverture impossible", async () => {
    connecte();
    fausseApi({
      "GET /francais/dossiers": { json: [RESUME] },
      "GET /francais/dossiers/FR3-DNB27-01/eleve": { json: { ...RESUME, version_affichee: 1, validee: false, eleve: ELEVE } },
      "GET /francais/dossiers/FR3-DNB27-01/classes": {
        json: [{ id: 7, code: "3E-FR-A", niveau: "3e", ouvert: false, acces_eleves: true, motif_acces: null }],
      },
    });
    render(<EspaceFrancais />);
    await userEvent.click(await screen.findByRole("button", { name: "Ouvrir" }));
    expect(await screen.findByText(/NON VALIDÉ — version v1/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Mes classes" }));
    expect(await screen.findByRole("button", { name: "Ouvrir à cette classe" })).toBeDisabled();
  });

  it("version validée : la professeure l'ouvre à sa classe", async () => {
    connecte();
    const valide = { ...RESUME, statut: "valide", version_validee: 1 };
    const classe = { id: 7, code: "3E-FR-A", niveau: "3e", ouvert: false, acces_eleves: true, motif_acces: null };
    const appels = fausseApi({
      "GET /francais/dossiers": { json: [valide] },
      "GET /francais/dossiers/FR3-DNB27-01/eleve": { json: { ...valide, version_affichee: 1, validee: true, eleve: ELEVE } },
      "GET /francais/dossiers/FR3-DNB27-01/classes": { json: [classe] },
      "PUT /francais/dossiers/FR3-DNB27-01/classes/7": { json: [{ ...classe, ouvert: true }] },
    });
    render(<EspaceFrancais />);
    await userEvent.click(await screen.findByRole("button", { name: "Ouvrir" }));
    expect(await screen.findByText(/Version validée v1 : celle que lisent les élèves/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Mes classes" }));
    await userEvent.click(await screen.findByRole("button", { name: "Ouvrir à cette classe" }));
    expect(await screen.findByRole("button", { name: "Retirer à cette classe" })).toBeInTheDocument();
    expect(appels.some((a) => a.cle === "PUT /francais/dossiers/FR3-DNB27-01/classes/7")).toBe(true);
  });
});

describe("Français : lecture par l'élève (#212)", () => {
  it("l'élève lit la partie élève d'un dossier ouvert à sa classe, sans corrigé", async () => {
    fausseApi({
      "GET /cours/mon-cours": { json: [] },
      "GET /francais/eleve/dossiers": { json: [{ code: "FR3-DNB27-01", titre: RESUME.titre, niveau: "3e", version: 1 }] },
      "GET /francais/eleve/dossiers/FR3-DNB27-01": {
        json: { code: "FR3-DNB27-01", titre: RESUME.titre, niveau: "3e", version: 1, eleve: ELEVE },
      },
    });
    render(<MonCours jeton="j" onExpire={() => {}} />);
    await userEvent.click(await screen.findByRole("button", { name: RESUME.titre }));
    expect(await screen.findByText("La porte de la salle était déjà ouverte.")).toBeInTheDocument();
    expect(screen.getByText("Rédige ta réponse : ton professeur la relira.")).toBeInTheDocument();
    expect(screen.queryByText(/Aperçu réservé aux adultes/)).not.toBeInTheDocument();
    expect(screen.queryByText("Un jardin avec des bancs.")).not.toBeInTheDocument();
  });

  it("aucun dossier ouvert : rien n'apparaît", async () => {
    fausseApi({ "GET /cours/mon-cours": { json: [] }, "GET /francais/eleve/dossiers": { json: [] } });
    render(<MonCours jeton="j" onExpire={() => {}} />);
    expect(await screen.findByText("Ta professeure n'a pas encore ouvert de chapitre.")).toBeInTheDocument();
    expect(screen.queryByText("Mes dossiers")).not.toBeInTheDocument();
  });
});

describe("Français : statut « À corriger » et export PDF (#217)", () => {
  it("une version refusée s'affiche « À corriger » avec son motif", async () => {
    connecte();
    fausseApi({
      "GET /francais/dossiers": { json: [{ ...RESUME, statut: "refuse", motif_refus: "Q4 : consigne ambiguë." }] },
      "GET /francais/validation": { status: 403, json: { detail: "Réservé" } },
    });
    render(<EspaceFrancais />);
    expect(await screen.findByText("À corriger")).toBeInTheDocument();
    expect(screen.getByText("Motif : Q4 : consigne ambiguë.")).toBeInTheDocument();
    expect(screen.queryByText("Refusé")).not.toBeInTheDocument();
  });

  it("le professeur exporte le PDF élève et le PDF professeur du dossier", async () => {
    connecte();
    const appels = fausseApi({
      "GET /francais/dossiers": { json: [RESUME] },
      "GET /francais/validation": { status: 403, json: { detail: "Réservé" } },
      "GET /francais/dossiers/FR3-DNB27-01/eleve": { json: { ...RESUME, eleve: ELEVE } },
      "GET /francais/dossiers/FR3-DNB27-01/pdf/eleve": { json: {} },
      "GET /francais/dossiers/FR3-DNB27-01/pdf/professeur": { json: {} },
    });
    URL.createObjectURL = vi.fn(() => "blob:x");
    URL.revokeObjectURL = vi.fn();
    const clic = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    render(<EspaceFrancais />);
    await userEvent.click(await screen.findByRole("button", { name: "Ouvrir" }));
    await userEvent.click(await screen.findByRole("button", { name: "PDF élève (sans corrigé)" }));
    await userEvent.click(screen.getByRole("button", { name: "PDF professeur (avec corrigés)" }));
    await vi.waitFor(() => expect(clic).toHaveBeenCalledTimes(2));
    expect(clic.mock.contexts.map((a) => a.download)).toEqual(["FR3-DNB27-01-eleve.pdf", "FR3-DNB27-01-professeur.pdf"]);
    expect(appels.map((a) => a.cle)).toContain("GET /francais/dossiers/FR3-DNB27-01/pdf/professeur");
    clic.mockRestore();
  });
});
