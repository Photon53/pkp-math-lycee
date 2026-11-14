import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { pagesPermises } from "../admin/EspaceAdmin.jsx";
import PrevalidationIA from "../admin/PrevalidationIA.jsx";
import { fausseApi } from "./setup.js";

const RESUME = {
  id: 7, lot: "L-20261110-ABC123", question_id: 42, question_code: "2NDE-AFF-Q1", niveau: "2nde", chapitre: "Fonctions affines",
  competence: "Lire un coefficient directeur", statut: "terminee", resultat: "erreur-detectee", version: "a1b2c3d4e5f6",
  obsolete: true, demandee_par: "Admin Démo", demandee_le: "2026-11-10T08:00:00Z", rendue_le: "2026-11-10T08:05:00Z",
  modele: "claude-opus-5-5", version_modele: "2026-06", nb_anomalies: 1, verite_humaine: null,
};
const DETAIL = {
  ...RESUME, version_complete: "a".repeat(64), version_actuelle: "b".repeat(64), tirage: null,
  enonce_lu_le: "2026-11-10T08:01:00Z", corrige_lu_le: "2026-11-10T08:03:00Z", compte_service: "Vérificateur IA",
  verite_commentaire: null, verite_par: null, verite_le: null,
  exercice: { enonce: "Résoudre 2x - 1 = 5.", solution: "4", type: "numerique", statut_validation: "a_valider", valide_par: null, auteur: "Brouillon IA (Claude)" },
  rapport: {
    synthese: "La réponse attendue est fausse.", reponse_independante: "x = 3", remarques_enonce: "", remarques_reponse: "",
    controle_programme: "", etapes: [{ numero: 1, avis: "erronee", remarque: "Erreur de signe." }],
    anomalies: [{ element: "reponse", etape: null, gravite: "erreur", description: "Réponse fausse.", justification: "2x = 6.", suggestion: "Remplacer 4 par 3." }],
    verifications: [{ nature: "symbolique", description: "Résolution", outil: "sympy", issue: "ecart" }], points_incertains: [],
  },
};

// Ticket #48 : page réservée aux administrateurs (permission « prevalidation.ia »), rapports détaillés et jeton montré une fois.
describe("prévalidation IA", () => {
  it("la page n'apparaît qu'avec la permission prevalidation.ia", () => {
    expect(pagesPermises(["contenu.lire", "contenu.valider"]).some((p) => p.vers === "/admin/prevalidation-ia")).toBe(false);
    expect(pagesPermises(["prevalidation.ia"]).some((p) => p.vers === "/admin/prevalidation-ia")).toBe(true);
  });

  it("liste, rapport détaillé, obsolescence et vérité humaine", async () => {
    const appels = fausseApi({
      "GET /admin/prevalidation-ia": { json: [RESUME] },
      "GET /admin/prevalidation-ia/7": { json: DETAIL },
      "POST /admin/prevalidation-ia/7/verite": { json: { ...DETAIL, verite_humaine: "erronee" } },
    });
    render(<PrevalidationIA jeton="j" onExpire={vi.fn()} />);
    expect(screen.getByText(/ne valide ni ne publie/)).toBeInTheDocument();
    const ligne = (await screen.findByText("2NDE-AFF-Q1")).closest("tr");
    expect(within(ligne).getByText("Obsolète")).toBeInTheDocument();
    expect(within(ligne).getByText("Erreur détectée")).toBeInTheDocument();
    await userEvent.click(within(ligne).getByRole("button", { name: "7" }));
    expect(await screen.findByText("Remplacer 4 par 3.", { exact: false })).toBeInTheDocument();
    expect(screen.getByText(/claude-opus-5-5/)).toBeInTheDocument();
    expect(screen.getByText(/x = 3/)).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("L'exercice était"), "erronee");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
    expect(appels.find((a) => a.cle === "POST /admin/prevalidation-ia/7/verite").corps).toEqual({ verite: "erronee", commentaire: "" });
  });

  it("lancer un contrôle sur un échantillon", async () => {
    const appels = fausseApi({
      "GET /admin/prevalidation-ia": { json: [] },
      "POST /admin/prevalidation-ia/demandes": { status: 201, json: { lot: "L-20261110-XYZ999", creees: [RESUME], deja_en_attente: [] } },
    });
    render(<PrevalidationIA jeton="j" onExpire={vi.fn()} />);
    await userEvent.click(screen.getByRole("tab", { name: "Lancer un contrôle" }));
    await userEvent.selectOptions(screen.getByLabelText("Niveau"), "2nde");
    await userEvent.click(screen.getByRole("button", { name: "Lancer la prévalidation" }));
    expect(appels.find((a) => a.cle === "POST /admin/prevalidation-ia/demandes").corps).toEqual({
      echantillon: { taille: 10, auteur_ia: true, niveau: "2nde" },
    });
    expect(await screen.findByText("L-20261110-XYZ999")).toBeInTheDocument();
  });

  it("le jeton du compte de service n'est affiché qu'à sa création", async () => {
    const compte = { id: 1, nom: "Vérificateur IA", prefixe: "pkpia_1_AbCdEfGhIj", etat: "actif", cree_le: "2026-11-10T08:00:00Z", expire_le: "2026-12-10T08:00:00Z", revoque_le: null, dernier_usage_le: null };
    fausseApi({
      "GET /admin/prevalidation-ia": { json: [] },
      "GET /admin/prevalidation-ia/comptes": { json: [compte] },
      "POST /admin/prevalidation-ia/comptes": { status: 201, json: { compte, jeton: "pkpia_1_AbCdEfGhIjSECRET" } },
    });
    render(<PrevalidationIA jeton="j" onExpire={vi.fn()} />);
    await userEvent.click(screen.getByRole("tab", { name: "Compte de service" }));
    expect(await screen.findByText("pkpia_1_AbCdEfGhIj…")).toBeInTheDocument();
    expect(screen.queryByText(/SECRET/)).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Créer un jeton" }));
    expect(await screen.findByText("pkpia_1_AbCdEfGhIjSECRET")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "C'est copié" }));
    expect(screen.queryByText(/SECRET/)).toBeNull();
  });
});
