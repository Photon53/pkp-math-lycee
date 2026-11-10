import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import Accueil from "../Accueil.jsx";
import AnglaisAdmin from "../admin/AnglaisAdmin.jsx";
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

const DOMAINES = [
  { code: "maths-lycee", matiere: "maths", cycle: "lycee", libelle: "Maths lycée", niveaux: ["2nde", "1re", "Tle"], actif: true, public: true },
  { code: "anglais-college", matiere: "anglais", cycle: "college", libelle: "Anglais collège", niveaux: ["6e", "5e", "4e", "3e"], actif: true, public: true },
  { code: "francais-lycee", matiere: "francais", cycle: "lycee", libelle: "Français lycée", niveaux: ["2nde", "1re"], actif: false, public: false },
];

describe("PKP Anglais", () => {
  it("l'accueil mène à un espace dédié", () => {
    render(<Accueil />);
    expect(screen.getByRole("link", { name: /^Professeur — Anglais/ })).toHaveAttribute("href", "/anglais");
    expect(screen.getByRole("link", { name: /^Élève — Anglais/ })).toHaveAttribute("href", "/anglais/eleve");
    expect(screen.getByRole("link", { name: /^Parent/ })).toHaveAttribute("href", "/parent");
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

  it("l'administrateur coche les qualifications d'un nouveau compte, matière par matière", async () => {
    let liste = [];
    const appels = fausseApi({
      "GET /admin/domaines": { json: DOMAINES },
      "GET /admin/enseignants": () => ({ json: liste }),
      "POST /admin/enseignants": (corps) => {
        const enseignant = { id: 9, ...corps, actif: true, mdp_provisoire: true, totp_configure: false, nb_classes: 0, nb_eleves: 0, derniere_connexion: null };
        liste = [enseignant];
        return { status: 201, json: { enseignant, mot_de_passe_provisoire: "Abc23defGhk45mnP" } };
      },
    });
    render(<Professeurs jeton="j" onExpire={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: /Nouveau compte/ }));
    const fenetre = screen.getByRole("dialog");
    await userEvent.type(within(fenetre).getByLabelText("Nom affiché"), "Mrs Smith");
    await userEvent.type(within(fenetre).getByLabelText("E-mail"), "smith@college.fr");
    // Domaine non activé : sa case est grisée.
    expect(within(fenetre).getByLabelText("Valide — Français lycée")).toBeDisabled();
    await userEvent.click(within(fenetre).getByLabelText("Enseigne — Maths lycée"));
    await userEvent.click(within(fenetre).getByRole("button", { name: "Créer le compte" }));
    expect(within(fenetre).getByText("Cochez au moins une qualification.")).toBeInTheDocument();
    await userEvent.click(within(fenetre).getByLabelText("Enseigne — Anglais collège"));
    await userEvent.click(within(fenetre).getByLabelText("Valide — Anglais collège"));
    // Validation restreinte à la 3e.
    await userEvent.click(within(within(fenetre).getByRole("group", { name: "Niveaux validés en Anglais collège" })).getByLabelText("3e"));
    await userEvent.click(within(fenetre).getByRole("button", { name: "Créer le compte" }));
    expect(await screen.findByText("Abc23defGhk45mnP")).toBeInTheDocument();
    const creation = appels.find((a) => a.cle === "POST /admin/enseignants");
    expect(creation.corps.habilitations).toEqual([
      { role: "professeur", domaine: "anglais-college", niveau: null },
      { role: "validateur", domaine: "anglais-college", niveau: "3e" },
    ]);
  });

  it("le professeur d'anglais crée un groupe de 4e et y inscrit ses élèves", async () => {
    connecte({ enseigne_maths: false, enseigne_anglais: true });
    let groupes = [{ id: 1, nom: "3e A", niveau: "3e", eleves: [] }];
    const appels = fausseApi({
      "GET /anglais/groupes": () => ({ json: groupes }),
      "POST /anglais/groupes": (corps) => {
        const g = { id: 2, ...corps, eleves: [] };
        groupes = [g, ...groupes];
        return { status: 201, json: g };
      },
      "GET /anglais/groupes/2/enfants?q=li": { json: [{ id: 21, nom: "Lina", niveau: "4e", identifiant: "lina-k7m4", deja_inscrit: false }] },
      "GET /anglais/groupes/2/enfants?q=ya": { json: [{ id: 22, nom: "Yanis", niveau: "4e", identifiant: "yanis-p2q3", deja_inscrit: false }] },
      "POST /anglais/groupes/2/enfants": ({ enfant_ids }) => {
        groupes = [{ ...groupes[0], eleves: enfant_ids.map((id) => ({ id: 10 + id, prenom: id === 21 ? "Lina" : "Yanis" })) }, ...groupes.slice(1)];
        return { json: { ajoutes: ["Lina", "Yanis"], refus: [] } };
      },
    });
    render(<EspaceAnglais chemin="/anglais/groupes" />);
    expect(await screen.findByRole("heading", { name: "Mes groupes", level: 1 })).toBeInTheDocument();
    expect(screen.getByText("Aucun groupe de 4e pour l'instant.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /3e A/ })).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText("Nom du nouveau groupe"), "4e B");
    await userEvent.selectOptions(screen.getByLabelText("Niveau du nouveau groupe"), "4e");
    await userEvent.click(screen.getByRole("button", { name: "Créer le groupe" }));
    expect(await screen.findByRole("heading", { name: "Groupe 4e B · 4e" })).toBeInTheDocument();

    const recherche = screen.getByLabelText("Ajouter des élèves");
    await userEvent.type(recherche, "li");
    await userEvent.click(await screen.findByRole("button", { name: "Choisir" }));
    await userEvent.clear(recherche);
    await userEvent.type(recherche, "ya");
    expect(await screen.findByText("yanis-p2q3", { exact: false })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Choisir" }));
    await userEvent.click(screen.getByRole("button", { name: "Ajouter les 2 élèves" }));
    expect(await screen.findByRole("button", { name: "Retirer Yanis" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /4e B/ })).toHaveTextContent("2 élèves");
    expect(appels.find((a) => a.cle === "POST /anglais/groupes").corps).toEqual({ nom: "4e B", niveau: "4e" });
    expect(appels.find((a) => a.cle === "POST /anglais/groupes/2/enfants").corps).toEqual({ enfant_ids: [21, 22] });
  });

  it("l'administrateur voit les groupes d'anglais et transfère un groupe à un professeur d'anglais", async () => {
    let groupes = [{ id: 3, nom: "4e A", niveau: "4e", enseignant_id: 5, enseignant: "Mrs Smith", eleves: [{ id: 7, prenom: "Lina" }] }];
    const profs = [
      { id: 5, nom: "Mrs Smith", email: "s@x.fr", actif: true, enseigne_maths: false, enseigne_anglais: true },
      { id: 6, nom: "M. Maths", email: "m@x.fr", actif: true, enseigne_maths: true, enseigne_anglais: false },
      { id: 8, nom: "Mr Brown", email: "b@x.fr", actif: true, enseigne_maths: false, enseigne_anglais: true },
    ];
    const appels = fausseApi({
      "GET /admin/anglais/groupes": () => ({ json: groupes }),
      "GET /admin/enseignants": { json: profs },
      "POST /admin/anglais/groupes/3/transfert": () => {
        groupes = [{ ...groupes[0], enseignant_id: 8, enseignant: "Mr Brown" }];
        return { json: groupes[0] };
      },
    });
    render(<AnglaisAdmin jeton="j" onExpire={vi.fn()} />);
    expect(await screen.findByRole("cell", { name: "Mrs Smith" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "1 élève" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Transférer" }));
    const fenetre = screen.getByRole("dialog");
    // Seuls les autres professeurs d'anglais sont proposés.
    expect(within(fenetre).getAllByRole("option").map((o) => o.textContent)).toEqual(["Mr Brown (b@x.fr)"]);
    await userEvent.click(within(fenetre).getByRole("button", { name: "Transférer" }));
    expect(await screen.findByRole("cell", { name: "Mr Brown" })).toBeInTheDocument();
    expect(appels.find((a) => a.cle === "POST /admin/anglais/groupes/3/transfert").corps).toEqual({ vers_enseignant_id: 8 });
  });

  it("l'administrateur crée un groupe d'anglais et le gère comme une classe", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    let groupes = [];
    const profs = [{ id: 5, nom: "Mrs Smith", email: "s@x.fr", actif: true, enseigne_maths: false, enseigne_anglais: true }];
    const appels = fausseApi({
      "GET /admin/anglais/groupes": () => ({ json: groupes }),
      "GET /admin/enseignants": { json: profs },
      "POST /admin/anglais/groupes": (corps) => {
        groupes = [{ id: 9, nom: corps.nom, niveau: corps.niveau, enseignant_id: 5, enseignant: "Mrs Smith", eleves: [] }];
        return { json: groupes[0] };
      },
      "GET /admin/anglais/groupes/9/enfants?q=": { json: [{ id: 4, nom: "Noé", niveau: "4e", identifiant: "noe-k7m4", deja_inscrit: false }] },
      "POST /admin/anglais/groupes/9/enfants": () => {
        groupes = [{ ...groupes[0], eleves: [{ id: 12, prenom: "Noé", identifiant: "noe-k7m4", a_un_code: true }] }];
        return { json: { ajoutes: ["Noé"], refus: [] } };
      },
      "POST /admin/anglais/eleves/12/code": { json: { id: 12, prenom: "Noé", identifiant: "noe-k7m4", code: "ABCD-2345" } },
    });
    render(<AnglaisAdmin jeton="j" onExpire={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: /Nouveau groupe/ }));
    await userEvent.type(screen.getByLabelText("Nom du groupe"), "4e Soleil");
    await userEvent.click(screen.getByRole("button", { name: "Créer le groupe" }));
    expect(appels.find((a) => a.cle === "POST /admin/anglais/groupes").corps).toEqual({ nom: "4e Soleil", niveau: "4e", enseignant_id: 5 });

    const fenetre = await screen.findByRole("dialog", { name: /Groupe 4e Soleil/ });
    await userEvent.click(await within(fenetre).findByRole("button", { name: "Choisir" }));
    await userEvent.click(within(fenetre).getByRole("button", { name: "Ajouter l'élève" }));
    expect(await within(fenetre).findByText("noe-k7m4", { selector: "code" })).toBeInTheDocument();
    await userEvent.click(within(fenetre).getByRole("button", { name: "Nouvelle carte pour Noé" }));
    expect(await within(fenetre).findByText("ABCD-2345")).toBeInTheDocument();
  });
});
