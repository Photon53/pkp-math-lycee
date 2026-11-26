// Issue #179 — Rédaction en ligne et correction par le professeur (Claude)
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import Redactions from "../enseignant/Redactions.jsx";
import Redaction, { RAPPEL } from "../eleve/Redaction.jsx";
import { fausseApi } from "./setup.js";

const SUJET = { question_id: 7, chapitre: "Raconter", competence: "Écrire un récit", enonce: "Raconte une aventure.", statut: null, version: null };
const version = (statut, extra = {}) => ({
  id: 1, version: 1, texte: "Il était une fois.", statut, commentaire: null, maj_le: "2026-11-19T08:00:00Z",
  remise_le: null, corrigee_le: null, ...extra,
});
const detail = (versions) => ({ question_id: 7, enonce: "Raconte une aventure.", versions, conserver_jusqu_au: "2027-08-31" });

describe("rédaction : élève (#179)", () => {
  it("écrit, enregistre puis remet ; le rappel sur les informations personnelles est affiché", async () => {
    const appels = fausseApi({
      "GET /eleves/moi/redactions": { json: [SUJET] },
      "GET /eleves/moi/redactions/7": { json: detail([]) },
      "PUT /eleves/moi/redactions/7": { json: detail([version("brouillon")]) },
      "POST /eleves/moi/redactions/7/remise": { json: detail([version("remise")]) },
    });
    render(<Redaction jeton="j" onExpire={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: /Raconter/ }));
    expect(await screen.findByRole("note")).toHaveTextContent(RAPPEL);
    await userEvent.type(screen.getByLabelText("Ta rédaction"), "Il était une fois.");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer le brouillon" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Brouillon enregistré.");
    await userEvent.click(screen.getByRole("button", { name: "Remettre à ma professeure" }));
    expect(await screen.findByText("Ta rédaction est remise : ta professeure va la corriger.")).toBeInTheDocument();
    expect(appels.filter((a) => a.cle === "PUT /eleves/moi/redactions/7").map((a) => a.corps)).toEqual([
      { texte: "Il était une fois." }, { texte: "Il était une fois." },
    ]);
    expect(screen.getByText(/conservées jusqu'au 31\/08\/2027/)).toBeInTheDocument();
  });

  it("lit le commentaire et propose la réécriture", async () => {
    fausseApi({
      "GET /eleves/moi/redactions": { json: [{ ...SUJET, statut: "corrigee", version: 1 }] },
      "GET /eleves/moi/redactions/7": { json: detail([version("corrigee", { commentaire: "Travaille la ponctuation." })]) },
    });
    render(<Redaction jeton="j" onExpire={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: /Raconter/ }));
    expect(await screen.findByText("Travaille la ponctuation.")).toBeInTheDocument();
    expect(screen.getByLabelText("Réécriture (version 2)")).toHaveValue("");
  });

  it("affiche que la rédaction n'est pas encore ouverte", async () => {
    fausseApi({ "GET /eleves/moi/redactions": { status: 403, json: { detail: "La rédaction en ligne n'est pas encore ouverte." } } });
    render(<Redaction jeton="j" onExpire={vi.fn()} />);
    expect(await screen.findByText("La rédaction en ligne n'est pas encore ouverte.")).toBeInTheDocument();
  });
});

describe("rédaction : professeur (#179)", () => {
  it("choisit une classe de français, lit une rédaction et envoie son commentaire", async () => {
    const appels = fausseApi({
      "GET /enseignants/classes": { json: [{ id: 3, code: "5E-FR-AAAAA", matiere: "francais" }, { id: 4, code: "2NDE-A", matiere: "maths" }] },
      "GET /enseignants/classes/3/redactions": { json: [{ id: 11, eleve: "Lina", sujet: "Raconte.", version: 1, statut: "remise", remise_le: null, corrigee_le: null }] },
      "GET /enseignants/redactions/11": { json: { id: 11, eleve: "Lina", sujet: "Raconte.", guide: "Récit au passé.", correction: { etapes: ["Vérifier les temps."] }, version: 1, texte: "Il était une fois.", statut: "remise", commentaire: null, remise_le: null } },
      "POST /enseignants/redactions/11/correction": (corps) => ({ json: { id: 11, eleve: "Lina", sujet: "Raconte.", guide: "", correction: null, version: 1, texte: "Il était une fois.", statut: "corrigee", commentaire: corps.commentaire, remise_le: null } }),
    });
    render(<Redactions jeton="j" onExpire={vi.fn()} />);
    const classe = await screen.findByLabelText("Classe");
    expect([...classe.options].map((o) => o.textContent)).toEqual(["Choisir…", "5E-FR-AAAAA"]); // classes de français seulement
    await userEvent.selectOptions(classe, "3");
    await userEvent.click(await screen.findByRole("button", { name: /Lina — version 1/ }));
    expect(await screen.findByText("Il était une fois.")).toBeInTheDocument();
    expect(screen.getByText("Vérifier les temps.")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Commentaire pour l'élève"), "Bon début.");
    await userEvent.click(screen.getByRole("button", { name: "Envoyer la correction" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Correction envoyée à l'élève.");
    expect(appels.find((a) => a.cle === "POST /enseignants/redactions/11/correction").corps).toEqual({ commentaire: "Bon début." });
  });
});
