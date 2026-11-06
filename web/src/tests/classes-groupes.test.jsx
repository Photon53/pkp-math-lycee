import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Eleves from "../admin/Eleves.jsx";
import { fausseApi } from "./setup.js";

const CLASSE = {
  id: 4, code: "2NDE-TC-AAAAA", niveau: "2nde", parcours: "tronc-commun", domaine_code: "maths-lycee",
  enseignant_id: 3, enseignant: "Enseignant Démo", nb_eleves: 12, nb_chapitres_ouverts: 5, archivee_le: null,
};
const GROUPE = {
  id: 7, nom: "4eA", niveau: "4e", enseignant_id: 5, enseignant: "Prof Anglais", eleves: [{ id: 1 }, { id: 2 }],
  domaine_code: "anglais-college", archivee_le: null,
};

beforeEach(() => window.history.pushState({}, "", "/admin/eleves?onglet=classes"));
afterEach(() => window.history.pushState({}, "", "/"));

describe("administrateur : classes et groupes", () => {
  it("réunit classes et groupes, archive la sélection en fin d'année puis la montre parmi les archivées", async () => {
    let archivees = false;
    const appels = fausseApi({
      "GET /admin/enseignants": { json: [] },
      "GET /admin/classes?etat=actives": () => ({ json: archivees ? [] : [CLASSE] }),
      "GET /admin/anglais/groupes?etat=actives": () => ({ json: archivees ? [] : [GROUPE] }),
      "GET /admin/classes?etat=archivees": { json: [{ ...CLASSE, archivee_le: "2026-07-05T10:00:00", motif_archivage: "Fin d'année scolaire" }] },
      "GET /admin/anglais/groupes?etat=archivees": { json: [] },
      "POST /admin/classes/archivage": () => {
        archivees = true;
        return { json: { traites: 1 } };
      },
      "POST /admin/anglais/groupes/archivage": { json: { traites: 1 } },
    });
    render(<Eleves jeton="j" onExpire={vi.fn()} />);
    expect(await screen.findByText(CLASSE.code)).toBeInTheDocument();
    expect(screen.getByText("4eA")).toBeInTheDocument();
    expect(screen.getByText("Anglais collège")).toBeInTheDocument();

    await userEvent.click(screen.getByLabelText("Sélectionner toutes les classes et tous les groupes"));
    // Un groupe sélectionné : la suppression (réservée aux classes) n'est pas proposée.
    expect(screen.getByRole("button", { name: "Supprimer" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Archiver (fin d'année)" }));
    await userEvent.click(screen.getByRole("button", { name: "Archiver" }));
    expect(await screen.findByText(/2 classe\(s\) ou groupe\(s\) archivé\(s\)/)).toBeInTheDocument();
    expect(appels.find((a) => a.cle === "POST /admin/classes/archivage").corps).toEqual({
      ids: [4], archiver: true, motif: "Fin d'année scolaire",
    });
    expect(appels.find((a) => a.cle === "POST /admin/anglais/groupes/archivage").corps.ids).toEqual([7]);

    await userEvent.selectOptions(screen.getByLabelText("Afficher"), "archivees");
    expect(await screen.findByText(/Archivée le/)).toBeInTheDocument();
  });
});
