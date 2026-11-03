import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import EspaceEleve from "../eleve/EspaceEleve.jsx";
import Exercice, { decouperQcm } from "../eleve/Exercice.jsx";
import { fausseApi } from "./setup.js";

const QUESTION = { id: 7, enonce: "Développer (x + 3)².", type: "expression", difficulte: 2 };

describe("decouperQcm", () => {
  it("sépare l'intitulé des options", () => {
    expect(decouperQcm("Quel est le signe de (−3)⁷ ? A) positif  B) négatif")).toEqual({
      intitule: "Quel est le signe de (−3)⁷ ?",
      options: [
        { lettre: "A", texte: "positif" },
        { lettre: "B", texte: "négatif" },
      ],
    });
  });

  it("laisse l'énoncé intact sans options", () => {
    expect(decouperQcm("Calculer f(2).").options).toBeNull();
  });
});

describe("connexion élève", () => {
  it("affiche un message clair si un des trois éléments est faux, et efface le code personnel", async () => {
    fausseApi({
      "POST /eleves/connexion": { status: 401, json: { detail: "Prénom, code classe ou code personnel incorrect." } },
    });
    render(<EspaceEleve />);
    await userEvent.click(screen.getByRole("button", { name: /Je n'ai pas de carte/ }));
    await userEvent.type(screen.getByLabelText("Prénom"), "Lina");
    await userEvent.type(screen.getByLabelText("Code classe"), "nope");
    await userEvent.type(screen.getByLabelText("Code personnel"), "faux12");
    await userEvent.click(screen.getByRole("button", { name: "Commencer" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Prénom, code classe ou code personnel incorrect");
    expect(screen.getByLabelText("Code personnel")).toHaveValue("");
  });

  it("exige le code personnel, masqué à la saisie", async () => {
    render(<EspaceEleve />);
    await userEvent.click(screen.getByRole("button", { name: /Je n'ai pas de carte/ }));
    await userEvent.type(screen.getByLabelText("Prénom"), "Lina");
    await userEvent.type(screen.getByLabelText("Code classe"), "2NDE-A-DEMO");
    expect(screen.getByRole("button", { name: "Commencer" })).toBeDisabled();
    expect(screen.getByLabelText("Code personnel")).toHaveAttribute("type", "password");
  });

  it("met les codes en majuscules et ouvre l'espace élève", async () => {
    const appels = fausseApi({
      "POST /eleves/connexion": {
        json: { jeton: "j", eleve: { id: 1, prenom: "Lina", code_classe: "2NDE-A-DEMO", niveau: "2nde" } },
      },
    });
    render(<EspaceEleve />);
    await userEvent.click(screen.getByRole("button", { name: /Je n'ai pas de carte/ }));
    await userEvent.type(screen.getByLabelText("Prénom"), "lina");
    await userEvent.type(screen.getByLabelText("Code classe"), "2nde-a-demo");
    await userEvent.type(screen.getByLabelText("Code personnel"), "pkp222");
    await userEvent.click(screen.getByRole("button", { name: "Commencer" }));
    expect(appels[0].corps).toEqual({ prenom: "lina", code_classe: "2NDE-A-DEMO", code_personnel: "PKP222" });
    expect(await screen.findByText("Lina")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "S'entraîner" })).toHaveAttribute("aria-selected", "true");
  });
});

describe("connexion par carte (identifiant + code)", () => {
  const REPONSE = { json: { jeton: "j", eleve: { id: 1, prenom: "Lina", code_classe: "2NDE-A-DEMO", niveau: "2nde" } } };

  it("se connecte avec l'identifiant et le code, sans prénom ni code classe", async () => {
    const appels = fausseApi({ "POST /eleves/connexion/identifiant": REPONSE });
    render(<EspaceEleve />);
    await userEvent.type(screen.getByLabelText("Identifiant"), "Lina-Demo");
    await userEvent.type(screen.getByLabelText("Code personnel"), "pkp222");
    await userEvent.click(screen.getByRole("button", { name: "Commencer" }));
    expect(appels[0].corps).toEqual({ identifiant: "lina-demo", code_personnel: "PKP222", rester_connecte: false });
    expect(await screen.findByText("Lina")).toBeInTheDocument();
    expect(sessionStorage.getItem("pkp.eleve")).not.toBeNull();
    expect(localStorage.getItem("pkp.eleve")).toBeNull();
  });

  it("« rester connecté » garde la session après fermeture du navigateur", async () => {
    const appels = fausseApi({ "POST /eleves/connexion/identifiant": REPONSE });
    render(<EspaceEleve />);
    await userEvent.type(screen.getByLabelText("Identifiant"), "lina-demo");
    await userEvent.type(screen.getByLabelText("Code personnel"), "PKP222");
    await userEvent.click(screen.getByRole("checkbox", { name: /Rester connecté/ }));
    await userEvent.click(screen.getByRole("button", { name: "Commencer" }));
    expect(appels[0].corps.rester_connecte).toBe(true);
    await screen.findByText("Lina");
    expect(localStorage.getItem("pkp.eleve")).not.toBeNull();
    localStorage.clear();
  });

  it("se connecte directement depuis le QR code et efface le code de l'adresse", async () => {
    window.history.replaceState(null, "", "/eleve#carte=lina-demo.PKP222");
    const appels = fausseApi({ "POST /eleves/connexion/identifiant": REPONSE });
    render(<EspaceEleve />);
    expect(await screen.findByText("Lina")).toBeInTheDocument();
    expect(appels[0].corps).toEqual({ identifiant: "lina-demo", code_personnel: "PKP222", rester_connecte: true });
    expect(window.location.hash).toBe("");
    localStorage.clear();
  });

  it("la carte scannée passe avant la session d'un autre élève sur le même appareil", async () => {
    sessionStorage.setItem("pkp.eleve", JSON.stringify({ jeton: "ancien", eleve: { ...REPONSE.json.eleve, prenom: "Yanis" } }));
    window.history.replaceState(null, "", "/eleve#carte=lina-demo.PKP222");
    const appels = fausseApi({ "POST /eleves/connexion/identifiant": REPONSE });
    render(<EspaceEleve />);
    expect(await screen.findByText("Lina")).toBeInTheDocument();
    expect(screen.queryByText("Yanis")).not.toBeInTheDocument();
    expect(appels[0].cle).toBe("POST /eleves/connexion/identifiant");
    localStorage.clear();
  });
});

describe("séance d'exercices", () => {
  it("déroule question → réponse fausse → solution → question suivante", async () => {
    let servie = 0;
    const appels = fausseApi({
      "POST /seances": { status: 201, json: { id: 3, debut: "", fin: null } },
      "GET /seances/3/question": () => ({ json: { ...QUESTION, id: QUESTION.id + servie++ } }),
      "POST /seances/3/reponses": { json: { correcte: false, solution: "x^2 + 6x + 9", maitrise: 0.31, maitrisee: false } },
    });
    render(<Exercice jeton="j" onExpire={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: "Démarrer une séance" }));
    expect(await screen.findByText("Développer (x + 3)².")).toBeInTheDocument();
    expect(screen.getByLabelText("Ta réponse")).toHaveFocus();

    await userEvent.type(screen.getByLabelText("Ta réponse"), "x²+9{Enter}");
    expect(appels.at(-1).corps).toEqual({ question_id: 7, reponse_donnee: "x²+9" });
    expect(await screen.findByText("Pas tout à fait.")).toBeInTheDocument();
    expect(screen.getByText("x^2 + 6x + 9")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "31");

    await userEvent.click(screen.getByRole("button", { name: "Question suivante" }));
    expect(await screen.findByLabelText("Ta réponse")).toHaveValue("");
    expect(screen.queryByText("Pas tout à fait.")).not.toBeInTheDocument();
  });

  it("après une erreur, propose le même exercice avec d'autres nombres", async () => {
    const variable = { id: 9, enonce: "Résoudre $3x + 1 = 7$.", type: "numerique", difficulte: 2, variable: true };
    const appels = fausseApi({
      "POST /seances": { status: 201, json: { id: 3 } },
      "GET /seances/3/question": { json: variable },
      "POST /seances/3/reponses": { json: { correcte: false, solution: "2", maitrise: 0.2, maitrisee: false } },
      "POST /seances/3/variante": { json: { ...variable, enonce: "Résoudre $5x - 2 = 8$." } },
    });
    render(<Exercice jeton="j" onExpire={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Démarrer une séance" }));
    await userEvent.type(await screen.findByLabelText("Ta réponse"), "3{Enter}");
    await userEvent.click(await screen.findByRole("button", { name: "Refaire avec d'autres nombres" }));
    expect(appels.at(-1).corps).toEqual({ question_id: 9 });
    expect(await screen.findByLabelText("Ta réponse")).toHaveValue("");
    expect(screen.queryByText("Pas tout à fait.")).not.toBeInTheDocument();
  });

  it("signale une question en relecture et une réponse juste mais pas sous la forme demandée", async () => {
    const remarque = "Ta réponse a la bonne valeur, mais elle n'est pas sous forme développée.";
    fausseApi({
      "POST /seances": { status: 201, json: { id: 3 } },
      "GET /seances/3/question": { json: { ...QUESTION, en_relecture: true } },
      "POST /seances/3/reponses": { json: { correcte: false, solution: "x^2 + 6x + 9", maitrise: 0.2, maitrisee: false, remarque } },
    });
    render(<Exercice jeton="j" onExpire={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Démarrer une séance" }));
    expect(await screen.findByText("En relecture")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Ta réponse"), "(x+3)^2{Enter}");
    expect(await screen.findByText(remarque)).toBeInTheDocument();
  });

  it("ne propose pas de variante pour un exercice à valeurs fixes", async () => {
    fausseApi({
      "POST /seances": { status: 201, json: { id: 3 } },
      "GET /seances/3/question": { json: QUESTION },
      "POST /seances/3/reponses": { json: { correcte: false, solution: "x^2 + 6x + 9", maitrise: 0.2, maitrisee: false } },
    });
    render(<Exercice jeton="j" onExpire={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Démarrer une séance" }));
    await userEvent.type(await screen.findByLabelText("Ta réponse"), "x{Enter}");
    await screen.findByText("Pas tout à fait.");
    expect(screen.queryByRole("button", { name: /autres nombres/ })).toBeNull();
  });

  it("répond à un QCM d'un clic", async () => {
    const appels = fausseApi({
      "POST /seances": { status: 201, json: { id: 3 } },
      "GET /seances/3/question": { json: { id: 5, enonce: "Signe ? A) positif  B) négatif", type: "qcm", difficulte: 2 } },
      "POST /seances/3/reponses": { json: { correcte: true, solution: "B", maitrise: 0.5, maitrisee: false } },
    });
    render(<Exercice jeton="j" onExpire={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Démarrer une séance" }));
    await userEvent.click(await screen.findByRole("button", { name: /négatif/ }));
    expect(appels.at(-1).corps).toEqual({ question_id: 5, reponse_donnee: "B" });
    expect(await screen.findByText("Bonne réponse !")).toBeInTheDocument();
  });

  it("reprend la séance et son compteur après un rechargement", async () => {
    sessionStorage.setItem("pkp.seance", "3");
    sessionStorage.setItem("pkp.bilan", JSON.stringify({ reponses: 4, reussies: 3 }));
    fausseApi({ "GET /seances/3/question": { json: QUESTION } });
    render(<Exercice jeton="j" onExpire={vi.fn()} />);
    expect(await screen.findByText("Développer (x + 3)².")).toBeInTheDocument();
    expect(screen.getByText("Réponses :")).toHaveTextContent("Réponses : 4");
    expect(screen.getByText("Réussies :")).toHaveTextContent("Réussies : 3");
  });

  it("déconnecte si le jeton a expiré", async () => {
    fausseApi({ "POST /seances": { status: 401, json: { detail: "Authentification requise." } } });
    const onExpire = vi.fn();
    render(<Exercice jeton="j" onExpire={onExpire} />);
    await userEvent.click(screen.getByRole("button", { name: "Démarrer une séance" }));
    expect(onExpire).toHaveBeenCalled();
  });

  it("affiche le bilan en fin de séance", async () => {
    fausseApi({
      "POST /seances": { status: 201, json: { id: 3 } },
      "GET /seances/3/question": { json: QUESTION },
      "POST /seances/3/reponses": { json: { correcte: true, solution: "x^2+6x+9", maitrise: 0.5, maitrisee: false } },
      "POST /seances/3/fin": { json: { id: 3 } },
    });
    render(<Exercice jeton="j" onExpire={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Démarrer une séance" }));
    await userEvent.type(await screen.findByLabelText("Ta réponse"), "x²+6x+9{Enter}");
    await userEvent.click(await screen.findByRole("button", { name: "Terminer la séance" }));
    expect(await screen.findByText("1 bonne réponse sur 1.")).toBeInTheDocument();
    expect(sessionStorage.getItem("pkp.seance")).toBeNull();
  });
});
