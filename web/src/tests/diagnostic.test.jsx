// Issue #162 — Diagnostic des acquis antérieurs, lot 3 : écrans (Claude)
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import Diagnostic from "../eleve/Diagnostic.jsx";
import Classes from "../enseignant/Classes.jsx";
import { fausseApi } from "./setup.js";

function passation(questions) {
  // Sert les questions dans l'ordre, puis 204 (terminé).
  let rang = 0;
  return {
    "GET /eleves/moi/diagnostic": () => ({ json: { statut: rang >= questions.length && rang > 0 ? "termine" : "a-commencer", nb_reponses: rang } }),
    "POST /eleves/moi/diagnostic": { json: { statut: "en-cours", nb_reponses: 0 } },
    "GET /eleves/moi/diagnostic/question": () => (rang < questions.length ? { json: questions[rang] } : { status: 204 }),
    "POST /eleves/moi/diagnostic/reponses": () => {
      rang += 1;
      return { json: { enregistree: true } };
    },
  };
}

describe("élève : passation du diagnostic", () => {
  it("une question à la fois, sans correction, choix multiples et « Je ne sais pas »", async () => {
    const appels = fausseApi(
      passation([
        { id: 1, numero: 1, enonce: "Vrai ? A) un  B) deux  C) trois", type: "choix_multiples" },
        { id: 2, numero: 2, enonce: "Calcule 2 + 2.", type: "numerique" },
        { id: 3, numero: 3, enonce: "Justifie.", type: "redaction" },
      ]),
    );
    render(<Diagnostic jeton="j" onExpire={vi.fn()} />);
    expect(await screen.findByText(/Ce n'est\s+pas une note/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Commencer le diagnostic" }));

    // Choix multiples : on coche C puis A ; la réponse part triée.
    await userEvent.click(await screen.findByRole("checkbox", { name: /trois/ }));
    await userEvent.click(screen.getByRole("checkbox", { name: /un/ }));
    await userEvent.click(screen.getByRole("button", { name: "Valider" }));
    const premiere = appels.filter((a) => a.cle === "POST /eleves/moi/diagnostic/reponses")[0];
    expect(premiere.corps).toEqual({ question_id: 1, reponse_donnee: "AC", ne_sait_pas: false });

    // Aucune correction affichée : on passe directement à la question suivante.
    expect(await screen.findByText("Question 2")).toBeInTheDocument();
    expect(screen.queryByText(/bonne réponse|Correction|Bravo/i)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Je ne sais pas" }));
    const deuxieme = appels.filter((a) => a.cle === "POST /eleves/moi/diagnostic/reponses")[1];
    expect(deuxieme.corps).toEqual({ question_id: 2, reponse_donnee: null, ne_sait_pas: true });

    // Rédaction : zone de texte longue.
    const zone = await screen.findByRole("textbox", { name: "Ta réponse" });
    expect(zone.tagName).toBe("TEXTAREA");
    await userEvent.type(zone, "Parce que 5² + 6² ≠ 8².");
    await userEvent.click(screen.getByRole("button", { name: "Valider" }));
    expect(await screen.findByText("Diagnostic terminé")).toBeInTheDocument();
  });

  it("diagnostic fermé : rien à passer", async () => {
    fausseApi({ "GET /eleves/moi/diagnostic": { json: { statut: "ferme", nb_reponses: 0 } } });
    render(<Diagnostic jeton="j" onExpire={vi.fn()} />);
    expect(await screen.findByText(/pas encore ouvert/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Commencer/ })).not.toBeInTheDocument();
  });
});

describe("enseignant : ouverture du diagnostic", () => {
  it("ouvre le diagnostic d'une classe de maths et affiche l'avancement", async () => {
    const vue = (ouvert) => ({
      ouvert,
      nb_questions_disponibles: 12,
      eleves: [{ eleve_id: 1, prenom: "Lina", statut: "en-cours", nb_reponses: 3, nb_en_attente: 1 }],
    });
    const appels = fausseApi({
      "GET /enseignants/classes": { json: [{ id: 4, code: "3E-A", niveau: "3e", parcours: "tronc-commun", matiere: "maths", nb_eleves: 1 }] },
      "GET /enseignants/classes/4/eleves": { json: [] },
      "GET /enseignants/classes/4/chapitres": { json: [] },
      "GET /enseignants/classes/4/diagnostic": { json: vue(false) },
      "PUT /enseignants/classes/4/diagnostic": (corps) => ({ json: vue(corps.ouvert) }),
    });
    render(<Classes jeton="j" onExpire={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: /3E-A/ }));
    await userEvent.click(await screen.findByRole("button", { name: "Ouvrir le diagnostic aux élèves" }));
    expect(appels.find((a) => a.cle === "PUT /enseignants/classes/4/diagnostic").corps).toEqual({ ouvert: true });
    expect(await screen.findByText(/Lina : en cours · 3 réponse\(s\) · 1 à corriger/)).toBeInTheDocument();
  });
});
