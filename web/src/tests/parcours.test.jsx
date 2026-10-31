import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import EspaceEleve from "../eleve/EspaceEleve.jsx";
import { fausseApi } from "./setup.js";

const SPE = { id: 5, prenom: "Roiya", code_classe: "1RE-SPE-4KQ7M", niveau: "1re", parcours: "specialite" };
const MAN = { id: 8, prenom: "Roiya", code_classe: "1RE-MAN-9TRBX", niveau: "1re", parcours: "mise-a-niveau" };
const inscription = (e, actuelle) => ({ eleve_id: e.id, prenom: e.prenom, code_classe: e.code_classe, niveau: e.niveau, parcours: e.parcours, actuelle });

describe("même élève dans plusieurs parcours", () => {
  it("affiche le parcours à côté du prénom et bascule vers un parcours relié", async () => {
    sessionStorage.setItem("pkp.eleve", JSON.stringify({ jeton: "j-spe", eleve: SPE }));
    const appels = fausseApi({
      "GET /eleves/moi/parcours": { json: [inscription(SPE, true), inscription(MAN, false)] },
      "POST /eleves/moi/parcours/8": { json: { jeton: "j-man", eleve: MAN } },
    });
    render(<EspaceEleve />);
    expect(screen.getByText(/1RE-SPE-4KQ7M · Première — Spécialité maths \(voie générale\)/)).toBeInTheDocument();

    await userEvent.selectOptions(await screen.findByLabelText("Mon parcours"), "8");

    expect(appels.find((a) => a.cle === "POST /eleves/moi/parcours/8")).toBeTruthy();
    expect(await screen.findByText(/1RE-MAN-9TRBX · Première — Mise à niveau/)).toBeInTheDocument();
    expect(JSON.parse(sessionStorage.getItem("pkp.eleve")).jeton).toBe("j-man"); // les appels suivants visent la mise à niveau
  });

  it("n'affiche pas de choix quand l'élève n'a qu'un parcours", async () => {
    sessionStorage.setItem("pkp.eleve", JSON.stringify({ jeton: "j-spe", eleve: SPE }));
    const appels = fausseApi({ "GET /eleves/moi/parcours": { json: [inscription(SPE, true)] } });
    render(<EspaceEleve />);
    await screen.findByText(/Spécialité maths/);
    await new Promise((r) => setTimeout(r, 0));
    expect(appels.some((a) => a.cle === "GET /eleves/moi/parcours")).toBe(true);
    expect(screen.queryByLabelText("Mon parcours")).not.toBeInTheDocument();
  });
});
