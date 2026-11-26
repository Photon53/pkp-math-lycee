import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import EspaceAnglais from "../anglais/EspaceAnglais.jsx";
import EspaceEleveAnglais from "../anglais/EspaceEleveAnglais.jsx";
import { fausseApi } from "./setup.js";

const CAHIER = {
  hook: "AFTER SCHOOL!",
  visual: [{ label: "FOOTBALL", picto: "ballon", image: "data:image/svg+xml;base64,PHN2Zy8+" }],
  vocab: [["usually", "d'habitude", "I usually walk."]],
  grammar: { title: "Present simple", rule: "He plays.", examples: ["She reads."] },
  pronunciation: "plays [z]",
  did_you_know: "School ends at 3:30.",
  model: "Alex: I play.\nSam: I read.",
  listening: {
    title: "Free time", source: "British Council", level: "A2", media: "audio",
    url: "https://learnenglishteens.britishcouncil.org/x", verified_on: "2026-11-02",
    questions: ["What sport?"], fallback: "Tyrone: water polo.",
  },
  go_further: [],
  practice: ["She ___ (play) tennis."],
  starters: ["I usually..."],
  mission: "Interview a partner.",
  can_do: ["I can say how often I do an activity."],
  memory: "Five words.",
};

function connecte(compte) {
  sessionStorage.setItem(
    "pkp.enseignant",
    JSON.stringify({ jeton: "j", nom: "Mrs Smith", role: "enseignant", mdp_provisoire: false, enseigne_anglais: true, ...compte }),
  );
}

describe("Boussole Anglais : élèves, codes et validation", () => {
  it("un nouveau code s'affiche sur une carte à imprimer une seule fois", async () => {
    connecte({});
    const groupes = [{ id: 1, nom: "4e A", niveau: "4e", eleves: [{ id: 9, prenom: "Lina", identifiant: "lina-k7m4", a_un_code: true }] }];
    fausseApi({
      "GET /anglais/groupes": () => ({ json: groupes }),
      "POST /anglais/groupes/1/eleves/9/code": () => ({ json: { id: 9, prenom: "Lina", identifiant: "lina-k7m4", code: "ZZ45QQ" } }),
    });
    render(<EspaceAnglais chemin="/anglais/groupes" />);
    await userEvent.click(await screen.findByRole("button", { name: /4e A/ }));
    expect(screen.getByText("lina-k7m4")).toBeInTheDocument();

    vi.spyOn(window, "confirm").mockReturnValue(true);
    await userEvent.click(screen.getByRole("button", { name: "Nouveau code pour Lina" }));
    expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining("L'ancien code ne fonctionnera plus."));
    expect(await screen.findByText("ZZ45QQ")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Cartes de connexion — Anglais 4e · 4e A" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "J'ai imprimé les cartes" }));
    expect(screen.queryByText("ZZ45QQ")).not.toBeInTheDocument();
  });

  it("une séance non validée porte la mention NON VALIDÉ chez le professeur", async () => {
    connecte({});
    fausseApi({
      "GET /anglais/seances": { json: [{ code: "4E-01", niveau: "4e", titre: "My daily life", validee: false }] },
      "GET /anglais/seances/4E-01": {
        json: { code: "4E-01", niveau: "4e", titre: "My daily life", objectif: "Habitudes", version: 1, statut: "soumis", validee: false,
          etapes: [], fiches: [], cahier: { ...CAHIER, listening: { ...CAHIER.listening, answers: ["Polo"] }, practice_answers: ["plays"] } },
      },
    });
    render(<EspaceAnglais chemin="/anglais" />);
    expect(await screen.findByRole("note")).toHaveTextContent("NON VALIDÉ");
    expect(screen.getByRole("option", { name: /4E-01 · My daily life · NON VALIDÉ/ })).toBeInTheDocument();
  });

  it("le référent voit la page Validation, relit puis valide ; le refus exige un motif", async () => {
    connecte({ referent_anglais: true });
    let liste = [{ code: "4E-01", titre: "My daily life", version: 1, statut: "soumis", auteur: null, version_publiee: null, est_auteur: false }];
    const appels = fausseApi({
      "GET /anglais/validation": () => ({ json: liste }),
      "GET /anglais/validation/4E-01": {
        json: {
          code: "4E-01", titre: "My daily life", objectif: "Habitudes", version: 1, statut: "soumis",
          etapes: [{ titre: "Warm-up", duree_minutes: 90, consigne_eleve: "Write", consigne_animateur: "Collect" }],
          fiches: [{ parcours: "A", enonce: "Complete", corrige: "I like reading" }],
          cahier: { ...CAHIER, listening: { ...CAHIER.listening, answers: ["Polo"] }, practice_answers: ["plays"] },
          quiz: [{ question: "« usually » means…", choix: ["jamais", "d'habitude"], reponse: 1 }],
          historique: [{ numero: 1, statut: "soumis", auteur: "Import du dépôt" }],
        },
      },
      "POST /anglais/validation/4E-01/valider": () => {
        liste = [];
        return { json: {} };
      },
    });
    render(<EspaceAnglais chemin="/anglais/validation" />);
    expect(screen.getByRole("link", { name: /Validation/ })).toBeInTheDocument();
    await userEvent.selectOptions(await screen.findByLabelText(/Séance à relire/), "4E-01");
    expect(await screen.findByText(/✓ d'habitude/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Refuser" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Valider cette version" }));
    expect(await screen.findByRole("status")).toHaveTextContent("4E-01 validée");
    expect(appels.some((a) => a.cle === "POST /anglais/validation/4E-01/valider")).toBe(true);
    expect(screen.getByText("Aucune séance en attente de validation.")).toBeInTheDocument();
  });

  it("un validateur d'anglais qui n'enseigne pas l'anglais accède à la seule page Validation", async () => {
    connecte({ enseigne_anglais: false, referent_anglais: true });
    fausseApi({ "GET /anglais/validation": { json: [] } });
    render(<EspaceAnglais chemin="/anglais" />);
    expect(await screen.findByText("Aucune séance en attente de validation.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Validation/ })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Mes groupes/ })).not.toBeInTheDocument();
    expect(screen.queryByText("Espace réservé aux professeurs d'anglais")).not.toBeInTheDocument();
  });

  it("sans la case référent, pas de page Validation", async () => {
    connecte({});
    fausseApi({ "GET /anglais/seances": { json: [] } });
    render(<EspaceAnglais chemin="/anglais/validation" />);
    expect(screen.queryByRole("link", { name: /Validation/ })).not.toBeInTheDocument();
  });

  it("l'élève se connecte, ouvre une séance validée et fait le quiz corrigé", async () => {
    const appels = fausseApi({
      "POST /anglais/eleve/connexion": { json: { jeton: "e", eleve: { prenom: "Lina", niveau: "4e", groupe: "4e A" } } },
      "GET /anglais/eleve/seances": { json: [{ code: "4E-01", titre: "My daily life", objectif: "Habitudes", can_do: CAHIER.can_do, score: null, total: null, tentatives: 0, i_can: [] }] },
      "GET /anglais/eleve/seances/4E-01": {
        json: { code: "4E-01", niveau: "4e", titre: "My daily life", objectif: "Habitudes", etapes: [], i_can: [],
          fiches: [{ parcours: "A", enonce: "Complete" }], cahier: CAHIER,
          quiz: [{ question: "« usually » means…", choix: ["jamais", "d'habitude"] }] },
      },
      "POST /anglais/eleve/seances/4E-01/corriger": {
        json: { score: 1, total: 1, meilleur_score: 1, details: [{ juste: true, reponse: 1, explication: "usually = d'habitude" }],
          practice_answers: ["plays"], listening_answers: ["Water polo"] },
      },
      "PUT /anglais/eleve/seances/4E-01/i-can": { json: { i_can: ["autonome"] } },
    });
    render(<EspaceEleveAnglais />);
    await userEvent.type(screen.getByLabelText("Identifiant"), "lina-k7m4");
    await userEvent.type(screen.getByLabelText("Code personnel"), "ab23cd");
    await userEvent.click(screen.getByRole("button", { name: "Let's go!" }));
    expect(appels[0].corps).toEqual({ identifiant: "lina-k7m4", code_personnel: "AB23CD", rester_connecte: false });

    await userEvent.click(await screen.findByRole("button", { name: /4E-01 · My daily life/ }));
    expect(await screen.findByRole("heading", { name: "My daily life" })).toBeInTheDocument();
    // Aucun corrigé n'est affiché avant l'envoi.
    expect(screen.queryByText("Réponse")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Check my answers" })).toBeDisabled();
    await userEvent.click(screen.getByLabelText("d'habitude"));
    await userEvent.click(screen.getByRole("button", { name: "Check my answers" }));
    expect(await screen.findByText(/Score : 1\/1/)).toBeInTheDocument();
    expect(screen.getByText("→ Water polo")).toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText(CAHIER.can_do[0]), "autonome");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Saved!")).toBeInTheDocument();
    expect(appels.at(-1).corps).toEqual({ i_can: ["autonome"] });
  });
});
