import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import Cours from "../eleve/Cours.jsx";
import EspaceEleve from "../eleve/EspaceEleve.jsx";
import { versHtml } from "../maths.jsx";
import { fausseApi } from "./setup.js";

const SOMMAIRE = [
  {
    id: 4,
    code: "TLE-LN",
    titre: "Fonction logarithme népérien",
    competences: [
      { id: 10, code: "TLE-LN-DEF", libelle: "Définir la fonction logarithme népérien", a_une_lecon: true },
      { id: 11, code: "TLE-LN-XXX", libelle: "Compétence sans cours", a_une_lecon: false },
    ],
  },
];
const LECON = {
  competence_id: 10,
  code: "TLE-LN-DEF",
  libelle: "Définir la fonction logarithme népérien",
  chapitre: "Fonction logarithme népérien",
  resume: "- $\\ln(1) = 0$\n- $\\ln(e) = 1$",
  cours: "## Définition\nPour $x > 0$ :\n$$y = \\ln(x) \\iff e^y = x$$",
};

describe("rendu Markdown + formules", () => {
  it("rend les formules en ligne et centrées avec KaTeX", () => {
    const html = versHtml("Si $x_1 = 2$ alors :\n\n$$x_1^2 = 4$$");
    const div = document.createElement("div");
    div.innerHTML = html;
    expect(div.querySelectorAll(".katex")).toHaveLength(2);
    expect(div.querySelectorAll(".katex-display")).toHaveLength(1);
    // « _ » des formules non interprété comme de l'italique Markdown
    expect(div.querySelector("em")).toBeNull();
  });

  it("garde le Markdown autour des formules", () => {
    const div = document.createElement("div");
    div.innerHTML = versHtml("## Titre\n\n**Gras** et $a^2$\n\n| a | b |\n|---|---|\n| $1$ | 2 |");
    expect(div.querySelector("h2")).toHaveTextContent("Titre");
    expect(div.querySelector("strong")).toHaveTextContent("Gras");
    expect(div.querySelector("table .katex")).not.toBeNull();
  });

  it("le dollar échappé reste un dollar", () => {
    expect(versHtml("Prix : 5 \\$", { enLigne: true })).not.toContain("katex");
  });

  it("neutralise le HTML dangereux", () => {
    const html = versHtml('<img src=x onerror="alert(1)"><script>alert(2)</script> $x$');
    expect(html).not.toMatch(/onerror|<script/);
  });

  it("une formule erronée ne casse pas la page", () => {
    expect(() => versHtml("$\\frac{1}{$")).not.toThrow();
  });
});

describe("cours", () => {
  it("affiche le sommaire puis une leçon avec son résumé", async () => {
    fausseApi({ "GET /cours": { json: SOMMAIRE }, "GET /cours/10": { json: LECON } });
    const onChoisir = vi.fn();
    const { rerender } = render(<Cours jeton="j" onExpire={vi.fn()} competenceId={null} onChoisir={onChoisir} />);
    expect(await screen.findByText("Compétence sans cours (cours à venir)")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Définir la fonction logarithme népérien" }));
    expect(onChoisir).toHaveBeenCalledWith(10);

    rerender(<Cours jeton="j" onExpire={vi.fn()} competenceId={10} onChoisir={onChoisir} />);
    const resume = await screen.findByRole("region", { name: "L'essentiel" });
    expect(resume.querySelectorAll(".katex")).toHaveLength(2);
    expect(screen.getByRole("heading", { name: "Définition" })).toBeInTheDocument();
  });

  it("message clair si une compétence n'a pas encore de cours", async () => {
    fausseApi({ "GET /cours": { json: SOMMAIRE }, "GET /cours/11": { status: 404, json: { detail: "Cours introuvable." } } });
    render(<Cours jeton="j" onExpire={vi.fn()} competenceId={11} onChoisir={vi.fn()} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Pas encore de cours pour cette compétence.");
  });

  it("« Revoir le cours » depuis un exercice ouvre la leçon de la compétence", async () => {
    sessionStorage.setItem(
      "pkp.eleve",
      JSON.stringify({ jeton: "j", eleve: { id: 5, prenom: "Emma", code_classe: "TLE-C-DEMO", niveau: "Tle" } }),
    );
    fausseApi({
      "POST /seances": { status: 201, json: { id: 3 } },
      "GET /seances/3/question": {
        json: { id: 30, competence_id: 10, enonce: "Calculer $\\ln(1)$.", type: "numerique", difficulte: 1 },
      },
      "POST /seances/3/reponses": { json: { correcte: false, solution: "0", maitrise: 0, maitrisee: false } },
      "GET /cours": { json: SOMMAIRE },
      "GET /cours/10": { json: LECON },
    });
    render(<EspaceEleve />);
    await userEvent.click(screen.getByRole("button", { name: "Démarrer une séance" }));
    const enonce = await screen.findByText((_, el) => el?.classList?.contains("enonce") ?? false);
    expect(enonce.querySelector(".katex")).not.toBeNull();
    await userEvent.type(screen.getByLabelText("Ta réponse"), "1{Enter}");
    await userEvent.click(await screen.findByRole("button", { name: "Revoir le cours" }));
    expect(screen.getByRole("tab", { name: "Cours" })).toHaveAttribute("aria-selected", "true");
    expect(await screen.findByRole("heading", { name: "Définir la fonction logarithme népérien" })).toBeInTheDocument();
  });
});
