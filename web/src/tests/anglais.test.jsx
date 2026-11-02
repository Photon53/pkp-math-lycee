import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import Accueil from "../Accueil.jsx";
import Professeurs from "../admin/Professeurs.jsx";
import EspaceAnglais from "../anglais/EspaceAnglais.jsx";
import EspaceEnseignant from "../enseignant/EspaceEnseignant.jsx";
import { fausseApi } from "./setup.js";

const SEANCE = {
  code: "4E-01", niveau: "4e", titre: "My daily life", objectif: "Parler de ses habitudes",
  etapes: [{ titre: "Warm-up", duree_minutes: 90, consigne_eleve: "Write three activities", consigne_animateur: "Recueillir" }],
  fiches: [{ parcours: "A", enonce: "Complete", corrige: "I like reading" }],
  cahier: {
    hook: "AFTER SCHOOL: WHAT'S YOUR STYLE?",
    visual: [{ label: "FOOTBALL", picto: "ballon", image: "data:image/svg+xml;base64,PHN2Zy8+" }],
    vocab: [["usually", "d'habitude", "I usually walk to school."]],
    grammar: { title: "Present simple + how often?", rule: "He plays.", examples: ["How often do you read?"] },
    pronunciation: "plays sounds like [z]",
    did_you_know: "In the UK, the school day usually ends around half past three.",
    model: "Alex: I usually play football.\nSam: I often read.",
    listening: {
      title: "Free time", source: "British Council - LearnEnglish Teens", level: "A2", media: "audio",
      url: "https://learnenglishteens.britishcouncil.org/skills/listening/a2-listening/free-time", verified_on: "2026-11-02",
      questions: ["What sport does Tyrone want to try?"], answers: ["Water polo"], fallback: "Tyrone: I'd like to join the water polo club.",
    },
    go_further: [],
    practice: ["Complete: She ___ (play) tennis."], practice_answers: ["plays"],
    starters: ["After school, I usually..."],
    mission: "Interview a partner about three after-school activities.",
    can_do: ["I can say how often I do an activity."],
    memory: "Write five frequency words.",
  },
};

function connecte(disciplines) {
  sessionStorage.setItem("pkp.enseignant", JSON.stringify({ jeton: "j", nom: "Mme Smith", role: "enseignant", mdp_provisoire: false, ...disciplines }));
}

describe("PKP Anglais", () => {
  it("l'accueil mène à un espace dédié", () => {
    render(<Accueil />);
    expect(screen.getByRole("link", { name: /PKP Anglais/ })).toHaveAttribute("href", "/anglais");
  });

  it("l'espace professeur de maths n'a plus d'onglet anglais", () => {
    connecte({ enseigne_maths: true, enseigne_anglais: false });
    fausseApi({ "GET /enseignants/classes": { json: [] } });
    render(<EspaceEnseignant chemin="/enseignant" />);
    expect(screen.queryByText("PKP Anglais")).not.toBeInTheDocument();
  });

  it("un professeur de maths seul est refusé dans l'espace anglais", () => {
    connecte({ enseigne_maths: true, enseigne_anglais: false });
    const appels = fausseApi({});
    render(<EspaceAnglais chemin="/anglais" />);
    expect(screen.getByRole("heading", { name: "Espace réservé aux professeurs d'anglais" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Aller à l'espace professeur" })).toHaveAttribute("href", "/enseignant");
    expect(appels).toEqual([]);
  });

  it("un professeur d'anglais seul est refusé dans l'espace maths", () => {
    connecte({ enseigne_maths: false, enseigne_anglais: true });
    const appels = fausseApi({});
    render(<EspaceEnseignant chemin="/enseignant" />);
    expect(screen.getByRole("heading", { name: "Espace réservé aux professeurs de mathématiques" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Aller à l'espace PKP Anglais" })).toHaveAttribute("href", "/anglais");
    expect(appels).toEqual([]);
  });

  it("un professeur d'anglais voit ses séances", async () => {
    connecte({ enseigne_maths: false, enseigne_anglais: true });
    fausseApi({
      "GET /anglais/seances": { json: [{ code: "4E-01", niveau: "4e", titre: "My daily life", objectif: "x", duree_minutes: 90 }] },
      "GET /anglais/seances/4E-01": { json: SEANCE },
    });
    render(<EspaceAnglais chemin="/anglais" />);
    expect(await screen.findByRole("heading", { name: "My daily life" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "PDF élève" })).toBeInTheDocument();
    expect(screen.queryByText("Espace professeur de maths")).not.toBeInTheDocument();
    // Écoute : simple lien vers le site source, ouvert à part, sans lecteur intégré.
    const lien = screen.getByRole("link", { name: "Free time" });
    expect(lien).toHaveAttribute("href", SEANCE.cahier.listening.url);
    expect(lien).toHaveAttribute("target", "_blank");
    expect(lien).toHaveAttribute("rel", "noopener noreferrer");
    expect(document.querySelector("iframe")).toBeNull();
    expect(screen.getByText("Script de secours (sans réseau, à lire deux fois)")).toBeInTheDocument();
  });

  it("la page du professeur reprend le cours du cahier, rubrique par rubrique", async () => {
    connecte({ enseigne_maths: false, enseigne_anglais: true });
    fausseApi({
      "GET /anglais/seances": { json: [{ code: "4E-01", niveau: "4e", titre: "My daily life", objectif: "x", duree_minutes: 90 }] },
      "GET /anglais/seances/4E-01": { json: SEANCE },
    });
    render(<EspaceAnglais chemin="/anglais" />);
    await screen.findByRole("heading", { name: "Le cours" });
    const rubriques = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
    expect(rubriques).toEqual([
      "1. Get curious - Choose your idea", "2. Word power - Learn and remember",
      "3. Grammar focus - Present simple + how often?", "4. Listen and watch", "5. Read the model",
      "6. Practise - Try it yourself", "7. Choose your challenge - A / B / C", "8. Final mission",
      "9. Check yourself - I can...", "10. Remember for next time",
    ]);
    expect(screen.getByText("FOOTBALL").querySelector("img")).toHaveAttribute("src", SEANCE.cahier.visual[0].image);
    expect(screen.getByText("I usually walk to school.")).toBeInTheDocument();
    expect(screen.getByText("I can say how often I do an activity.")).toBeInTheDocument();
    expect(screen.getByText(/After school, I usually/)).toBeInTheDocument();
    // Dialogue en bulles, comme dans le cahier.
    expect(screen.getByText("I usually play football.").closest("p")).toHaveClass("bulle", "gauche");
    expect(screen.getByText("I often read.").closest("p")).toHaveClass("bulle", "droite");
    // Les réponses sont présentes mais repliées.
    expect(screen.getByText("Water polo").closest("details")).not.toHaveAttribute("open");
    expect(screen.getByText("plays").closest("details")).not.toHaveAttribute("open");
  });

  it("l'administrateur coche les disciplines d'un nouveau professeur", async () => {
    let liste = [];
    const appels = fausseApi({
      "GET /admin/enseignants": () => ({ json: liste }),
      "POST /admin/enseignants": (corps) => {
        const enseignant = { id: 9, ...corps, actif: true, mdp_provisoire: true, totp_configure: false, nb_classes: 0, nb_eleves: 0, derniere_connexion: null };
        liste = [enseignant];
        return { status: 201, json: { enseignant, mot_de_passe_provisoire: "Abc23defGhk45mnP" } };
      },
    });
    render(<Professeurs jeton="j" onExpire={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: /Nouveau professeur/ }));
    const fenetre = screen.getByRole("dialog");
    await userEvent.type(within(fenetre).getByLabelText("Nom affiché"), "Mrs Smith");
    await userEvent.type(within(fenetre).getByLabelText("E-mail"), "smith@college.fr");
    await userEvent.click(within(fenetre).getByLabelText(/Mathématiques/));
    await userEvent.click(within(fenetre).getByRole("button", { name: "Créer le compte" }));
    expect(within(fenetre).getByText("Cochez au moins une discipline.")).toBeInTheDocument();
    await userEvent.click(within(fenetre).getByLabelText(/Anglais/));
    await userEvent.click(within(fenetre).getByRole("button", { name: "Créer le compte" }));
    expect(await screen.findByText("Abc23defGhk45mnP")).toBeInTheDocument();
    const creation = appels.find((a) => a.cle === "POST /admin/enseignants");
    expect(creation.corps).toMatchObject({ enseigne_maths: false, enseigne_anglais: true });
  });
});
