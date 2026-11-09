import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { Correction } from "../ui/Pedagogie.jsx";

// Ticket #27 : les rubriques du gabarit s'affichent quand le corrigé les contient, et seulement alors.
describe("corrigé détaillé", () => {
  it("affiche rappel, formule, conditions, étapes, vérification et autre méthode", async () => {
    render(
      <Correction
        correction={{
          rappel: "f est affine.",
          formule: "m = (f(x2) - f(x1)) / (x2 - x1)",
          conditions: "x1 et x2 distincts",
          methode: "Taux d'accroissement.",
          etapes: ["m = 6 / 3 = 2", "p = 1"],
          resultat: "21",
          verification: "f(4) = 9",
          autre_methode: "Proportionnalité des accroissements.",
        }}
      />,
    );
    expect(screen.getByText(/f est affine/)).toBeInTheDocument();
    await userEvent.click(screen.getByText("Voir le détail de la correction"));
    for (const texte of [/m = \(f\(x2\)/, /x1 et x2 distincts/, /p = 1/, /f\(4\) = 9/, /Proportionnalité/]) {
      expect(screen.getByText(texte)).toBeInTheDocument();
    }
    expect(screen.getByText("Vérification :")).toBeInTheDocument();
  });

  it("un corrigé court n'affiche pas de rubrique vide", () => {
    render(<Correction correction={{ etapes: ["x = 2"], resultat: "2" }} />);
    expect(screen.queryByText("Rappel :")).toBeNull();
    expect(screen.queryByText("Formule :")).toBeNull();
    expect(screen.queryByText("Vérification :")).toBeNull();
  });
});
