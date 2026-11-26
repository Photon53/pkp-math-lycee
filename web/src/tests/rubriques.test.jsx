// Issue #177 — Rubriques de l'espace Français (Claude)
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import PkpMath from "../pkpmath/PkpMath.jsx";
import { fausseApi } from "./setup.js";

const chapitre = (id, titre, niveau, rubrique) => ({
  id, code: `C${id}`, titre, niveau, parcours: "tronc-commun", libelle_parcours: "Tronc commun", ordre: id,
  nb_competences: 1, nb_questions: 9, valide: true, rubrique,
});
const CATALOGUE = [
  chapitre(1, "Le présent", "6e", "conjugaison"),
  chapitre(2, "Nature des mots", "6e", "grammaire"),
  chapitre(3, "Réécriture", "3e", "conjugaison"),
];

describe("rubriques du français (#177)", () => {
  it("filtre par rubrique sur tous les niveaux à la fois", async () => {
    fausseApi({ "GET /pkp-math/catalogue": { json: CATALOGUE } });
    render(<PkpMath jeton="j" />);
    expect(await screen.findByRole("button", { name: /Nature des mots/ })).toBeInTheDocument();
    const rubrique = screen.getByLabelText("Rubrique");
    // Seules les rubriques présentes sont proposées.
    expect([...rubrique.options].map((o) => o.textContent)).toEqual(["Toutes les rubriques", "Conjugaison", "Grammaire"]);
    await userEvent.selectOptions(rubrique, "conjugaison");
    expect(screen.getByRole("button", { name: /Le présent/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Réécriture/ })).toBeInTheDocument(); // 3e, même filtre
    expect(screen.queryByRole("button", { name: /Nature des mots/ })).not.toBeInTheDocument();
  });

  it("aucun filtre de rubrique pour un catalogue de maths", async () => {
    fausseApi({ "GET /pkp-math/catalogue": { json: [chapitre(4, "Fractions", "2nde", null)] } });
    render(<PkpMath jeton="j" />);
    expect(await screen.findByRole("button", { name: /Fractions/ })).toBeInTheDocument();
    expect(screen.queryByLabelText("Rubrique")).not.toBeInTheDocument();
  });
});
