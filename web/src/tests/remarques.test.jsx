import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import RemarquesAdmin from "../admin/RemarquesAdmin.jsx";
import Remarques from "../ui/Remarques.jsx";
import { fausseApi } from "./setup.js";

// Ticket #30 : choisir « Avec mon nom » ou « Anonyme » avant l'envoi ; l'administration n'affiche pas l'auteur anonyme.
describe("remarques et suggestions", () => {
  it("le mode est choisi avant l'envoi, puis référence et code de suivi s'affichent", async () => {
    const appels = fausseApi({
      "GET /remarques/miennes": { json: [] },
      "POST /remarques": { status: 201, json: { reference: "R-ABCD2345", code_suivi: "AAAA-BBBB-CCCC", anonyme: true, statut: "recue" } },
    });
    render(<Remarques jeton="j" onExpire={vi.fn()} tutoiement />);
    await userEvent.selectOptions(screen.getByLabelText("Catégorie"), "bug");
    await userEvent.type(screen.getByLabelText("Description"), "Le bouton ne répond pas.");
    expect(screen.getByRole("button", { name: "Envoyer" })).toBeDisabled();
    expect(screen.getByText(/Ce n'est pas un anonymat absolu/)).toBeInTheDocument();
    await userEvent.click(screen.getByLabelText("Anonyme"));
    await userEvent.click(screen.getByRole("button", { name: "Envoyer" }));
    expect(appels.find((a) => a.cle === "POST /remarques").corps).toEqual({
      categorie: "bug", description: "Le bouton ne répond pas.", page: null, anonyme: true,
    });
    expect(await screen.findByText("R-ABCD2345")).toBeInTheDocument();
    expect(screen.getByText("AAAA-BBBB-CCCC")).toBeInTheDocument();
  });

  it("suivi par référence et code", async () => {
    fausseApi({
      "GET /remarques/miennes": { json: [] },
      "POST /remarques/suivi": { json: { reference: "R-ABCD2345", categorie: "bug", statut: "resolue", reponse: "Corrigé.", cree_le: "2026-11-09T08:00:00Z", maj_le: "2026-11-09T09:00:00Z" } },
    });
    render(<Remarques jeton="j" onExpire={vi.fn()} />);
    await userEvent.click(screen.getByText("Suivre une remarque avec son code"));
    await userEvent.type(screen.getByLabelText("Référence"), "R-ABCD2345");
    await userEvent.type(screen.getByLabelText("Code de suivi"), "AAAA-BBBB-CCCC");
    await userEvent.click(screen.getByRole("button", { name: "Voir où en est la remarque" }));
    expect(await screen.findByText("Corrigé.")).toBeInTheDocument();
    expect(screen.getByText("Résolue")).toBeInTheDocument();
  });

  it("administration : « Anonyme » à la place de l'auteur, traitement du statut", async () => {
    const base = { categorie: "bug", description: "…", page: null, statut: "recue", priorite: "normale", assignee: null, reponse: null, cree_le: "2026-11-09T08:00:00Z", maj_le: "2026-11-09T08:00:00Z" };
    const appels = fausseApi({
      "GET /admin/moi": { json: { id: 2, nom: "Admin" } },
      "GET /admin/remarques?": { json: [
        { ...base, id: 1, reference: "R-ANON0001", anonyme: true, auteur: null },
        { ...base, id: 2, reference: "R-NOMM0002", anonyme: false, auteur: { role: "eleve", nom: "Lina (2NDE-A)" } },
      ] },
      "POST /admin/remarques/1": { json: { ...base, id: 1, reference: "R-ANON0001", anonyme: true, auteur: null, statut: "en-cours" } },
    });
    render(<RemarquesAdmin jeton="j" onExpire={vi.fn()} />);
    const anonyme = (await screen.findByText("R-ANON0001")).closest("tr");
    expect(within(anonyme).getByText("Anonyme")).toBeInTheDocument();
    expect(screen.getByText("Lina (2NDE-A) (élève)")).toBeInTheDocument();
    await userEvent.selectOptions(within(anonyme).getByLabelText("Statut de R-ANON0001"), "en-cours");
    expect(appels.find((a) => a.cle === "POST /admin/remarques/1").corps).toEqual({ statut: "en-cours" });
  });
});
