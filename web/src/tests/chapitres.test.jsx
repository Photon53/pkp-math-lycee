import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import Exercice from "../eleve/Exercice.jsx";
import Classes from "../enseignant/Classes.jsx";
import { fausseApi } from "./setup.js";

const OUVERTS = [
  { id: 1, code: "1RE-SECOND-DEGRE", titre: "Second degré", nb_questions: 2 },
  { id: 2, code: "1RE-SUITES", titre: "Suites numériques", nb_questions: 11 },
  { id: 3, code: "1RE-DERIV", titre: "Dérivation", nb_questions: 0 },
];

describe("élève : choix des chapitres", () => {
  it("coche par défaut les chapitres qui ont des questions et envoie le choix", async () => {
    const appels = fausseApi({
      "GET /eleves/moi/chapitres": { json: OUVERTS },
      "POST /seances": { status: 201, json: { id: 7, chapitres: [{ id: 2, titre: "Suites numériques" }] } },
      "GET /seances/7/question": { json: { id: 30, competence_id: 4, enonce: "Calculer $u_5$.", type: "numerique", difficulte: 1 } },
    });
    render(<Exercice jeton="j" onExpire={vi.fn()} />);
    const second = await screen.findByRole("checkbox", { name: /Second degré/ });
    expect(second).toBeChecked();
    expect(screen.getByRole("checkbox", { name: /Dérivation/ })).toBeDisabled();
    expect(screen.getByText(/bientôt disponible/)).toBeInTheDocument();

    await userEvent.click(second); // l'élève ne garde que les suites
    await userEvent.click(screen.getByRole("button", { name: "Démarrer une séance" }));
    expect(appels.find((a) => a.cle === "POST /seances").corps).toEqual({ chapitre_ids: [2] });
  });

  it("ne peut pas démarrer sans chapitre coché", async () => {
    fausseApi({ "GET /eleves/moi/chapitres": { json: OUVERTS } });
    render(<Exercice jeton="j" onExpire={vi.fn()} />);
    await userEvent.click(await screen.findByRole("checkbox", { name: /Second degré/ }));
    await userEvent.click(screen.getByRole("checkbox", { name: /Suites numériques/ }));
    expect(screen.getByRole("button", { name: "Démarrer une séance" })).toBeDisabled();
  });

  it("indique quand le professeur n'a ouvert aucun chapitre", async () => {
    fausseApi({ "GET /eleves/moi/chapitres": { json: [] } });
    render(<Exercice jeton="j" onExpire={vi.fn()} />);
    expect(await screen.findByText("Ton professeur n'a pas encore ouvert de chapitre.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Démarrer une séance" })).toBeDisabled();
  });
});

describe("enseignant : chapitres proposés", () => {
  it("affiche le programme, permet d'ouvrir ou fermer des chapitres et enregistre", async () => {
    const PROGRAMME = [
      { id: 1, code: "1RE-SECOND-DEGRE", titre: "Second degré", ordre: 1, propose: true, nb_competences: 1, nb_questions: 2 },
      { id: 2, code: "1RE-SUITES", titre: "Suites numériques", ordre: 2, propose: false, nb_competences: 3, nb_questions: 11 },
    ];
    const appels = fausseApi({
      "GET /enseignants/classes": { json: [{ id: 4, code: "1RE-B-DEMO", niveau: "1re", parcours: "specialite", nb_eleves: 1 }] },
      "GET /enseignants/classes/4/eleves": { json: [] },
      "GET /enseignants/classes/4/chapitres": { json: PROGRAMME },
      "PUT /enseignants/classes/4/chapitres": (corps) => ({ json: PROGRAMME.map((c) => ({ ...c, propose: corps.chapitre_ids.includes(c.id) })) }),
    });
    render(<Classes jeton="j" onExpire={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: /1RE-B-DEMO/ }));
    const suites = await screen.findByRole("checkbox", { name: /Suites numériques/ });
    expect(suites).not.toBeChecked();
    expect(screen.getByRole("button", { name: "Enregistrer" })).toBeDisabled(); // rien de modifié

    await userEvent.click(suites);
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
    expect(appels.find((a) => a.cle === "PUT /enseignants/classes/4/chapitres").corps.chapitre_ids.sort()).toEqual([1, 2]);
    expect(await screen.findByText("2 chapitre(s) ouvert(s) aux élèves de 1RE-B-DEMO.")).toBeInTheDocument();
  });
});
