// Issue #171 — Candidatures de professeurs et demandes de partenariat (Claude)
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import Accueil from "../Accueil.jsx";
import AccueilDemandes from "../admin/AccueilDemandes.jsx";
import Collaborer from "../Collaborer.jsx";
import { fausseApi } from "./setup.js";

const OUVERT = { ouvert: true, formats_cv: ["pdf"], cv_taille_max_mo: 5, conservation_jours: { candidature: 180, partenariat: 365 } };

async function coordonnees() {
  await userEvent.type(screen.getByLabelText("Prénom (obligatoire)"), "Camille");
  await userEvent.type(screen.getByLabelText("Nom (obligatoire)"), "Fictif");
  await userEvent.type(screen.getByLabelText(/^E-mail/), "camille@exemple.test");
}

describe("Enseigner ou collaborer avec nous", () => {
  it.each([[true], [false]])("accueil : l'entrée n'apparaît que si la collecte est ouverte (%s)", async (ouvert) => {
    fausseApi({ "GET /collaboration/etat": { json: { ...OUVERT, ouvert } } });
    render(<Accueil />);
    await screen.findByRole("heading", { level: 1 });
    await new Promise((r) => setTimeout(r, 0));
    const lien = screen.queryByRole("link", { name: "Enseigner ou collaborer avec nous" });
    if (ouvert) expect(lien).toHaveAttribute("href", "/collaborer");
    else expect(lien).not.toBeInTheDocument();
  });

  it("fermé : aucun formulaire", async () => {
    fausseApi({ "GET /collaboration/etat": { json: { ...OUVERT, ouvert: false } } });
    render(<Collaborer />);
    expect(await screen.findByText(/ne sont pas encore ouvertes/)).toBeInTheDocument();
    expect(screen.queryByRole("radio")).not.toBeInTheDocument();
  });

  it("professeur : information, champs minimisés, envoi unique et référence", async () => {
    // Réponse différée : le bouton reste désactivé pendant l'envoi (pas de double demande).
    let resoudre;
    const appels = [];
    vi.stubGlobal("fetch", vi.fn(async (url, { method = "GET", body } = {}) => {
      const cle = `${method} ${url.replace(/^\/api/, "")}`;
      appels.push({ cle, corps: body ? JSON.parse(body) : undefined });
      if (cle === "GET /collaboration/etat") return { ok: true, status: 200, json: async () => OUVERT };
      return new Promise((r) => {
        resoudre = () => r({ ok: true, status: 201, json: async () => ({ reference: "C-ABCD2345", type: "candidature" }) });
      });
    }));
    render(<Collaborer />);
    await userEvent.click(await screen.findByLabelText(/Professeur ou/));
    expect(screen.getByText(/supprimés 180 jours après/)).toBeInTheDocument();
    await coordonnees();
    await userEvent.click(screen.getByLabelText("Mathématiques"));
    await userEvent.click(screen.getByLabelText("2nde"));
    const envoyer = screen.getByRole("button", { name: "Envoyer ma demande" });
    expect(envoyer).toBeDisabled(); // information pas encore lue
    await userEvent.click(screen.getByLabelText(/J'ai lu comment/));
    await userEvent.click(envoyer);
    expect(screen.getByRole("button", { name: "Envoi en cours…" })).toBeDisabled();
    const envoi = appels.filter((a) => a.cle === "POST /collaboration/candidatures");
    expect(envoi).toHaveLength(1);
    expect(envoi[0].corps).toMatchObject({
      prenom: "Camille", nom: "Fictif", email: "camille@exemple.test", telephone: null, matieres: ["maths"], niveaux: ["2nde"],
      information_lue: true, site_web: "", cv_base64: null,
    });
    resoudre();
    expect(await screen.findByText("C-ABCD2345")).toBeInTheDocument();
    expect(screen.getByText(/n'est pas automatique/)).toBeInTheDocument();
  });

  it("CV : un fichier trop gros ou d'un autre type est refusé avant l'envoi", async () => {
    fausseApi({ "GET /collaboration/etat": { json: { ...OUVERT, cv_taille_max_mo: 1 } } });
    render(<Collaborer />);
    await userEvent.click(await screen.findByLabelText(/Professeur ou/));
    const champ = screen.getByLabelText(/^CV \(facultatif\)/);
    await userEvent.upload(champ, new File([new Uint8Array(2 * 1024 * 1024)], "cv.pdf", { type: "application/pdf" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Le CV dépasse 1 Mo.");
    await userEvent.upload(champ, new File(["x"], "cv.docx", { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" }), {
      applyAccept: false,
    });
    expect(screen.getByRole("alert")).toHaveTextContent("Le CV doit être un fichier PDF.");
  });

  it("structure : formulaire adapté et erreur du serveur affichée", async () => {
    const appels = fausseApi({
      "GET /collaboration/etat": { json: OUVERT },
      "POST /collaboration/partenariats": { status: 429, json: { detail: "Trop de tentatives. Réessayez dans 60 minutes." } },
    });
    render(<Collaborer />);
    await userEvent.click(await screen.findByLabelText(/Une école, un/));
    expect(screen.queryByLabelText(/^CV/)).not.toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Nom de la structure (obligatoire)"), "Association Fictive");
    await userEvent.selectOptions(screen.getByLabelText("Type de structure (obligatoire)"), "association");
    await coordonnees();
    await userEvent.type(screen.getByLabelText("Partenariat envisagé (obligatoire)"), "Soutien scolaire de nos adhérents.");
    await userEvent.click(screen.getByLabelText(/J'ai lu comment/));
    await userEvent.click(screen.getByRole("button", { name: "Envoyer ma demande" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Trop de tentatives");
    expect(appels.find((a) => a.cle === "POST /collaboration/partenariats").corps).toMatchObject({
      structure_nom: "Association Fictive", structure_type: "association", partenariat: "Soutien scolaire de nos adhérents.",
    });
    expect(screen.getByRole("button", { name: "Envoyer ma demande" })).toBeEnabled(); // on peut réessayer
  });
});

describe("Accueil et demandes", () => {
  const FILES_API = [
    { categorie: "famille", nouvelles: 1, conservation_jours: 30 },
    { categorie: "information", nouvelles: 0, conservation_jours: null },
    { categorie: "candidature", nouvelles: 2, conservation_jours: 180 },
    { categorie: "partenariat", nouvelles: 0, conservation_jours: 365 },
  ];
  const vide = { demandes: [], total: 0, page: 1, taille_page: 50 };
  const resume = { id: 1, reference: "F-ABCD2345", categorie: "famille", origine: "saisie-admin", contact_id: 7, contact: "Sacha Fictif", organisation: null, statut: "nouveau", issue: null, a_un_cv: false, responsable: null, cree_le: "2026-11-19T08:00:00Z" };
  const autre = { ...resume, id: 2, reference: "I-WXYZ2345", categorie: "information" };
  const detail = {
    ...resume, prenom: "Sacha", nom: "Fictif", email: "sacha@exemple.test", telephone: null, message: "Bilan en 4e", details: {},
    cv_taille_octets: null, notes_internes: null, responsable_id: null, maj_le: "2026-11-19T08:00:00Z",
    contact_fiche: { id: 7, prenom: "Sacha", nom: "Fictif", email: "sacha@exemple.test", telephone: null, cree_le: "2026-11-19T08:00:00Z" },
    autres_demandes: [autre],
  };

  function routes(supplement = {}) {
    return fausseApi({
      "GET /admin/accueil/files": { json: FILES_API },
      "GET /admin/accueil/demandes?categorie=famille&page=1": { json: { demandes: [resume], total: 1, page: 1, taille_page: 50 } },
      "GET /admin/accueil/demandes?categorie=information&page=1": { json: vide },
      "GET /admin/accueil/demandes?categorie=candidature&page=1": { json: vide },
      "GET /admin/accueil/demandes/1": { json: detail },
      "GET /admin/moi": { json: { id: 2, nom: "Admin" } },
      "POST /admin/accueil/demandes/1": (corps) => ({ json: { ...detail, ...corps } }),
      ...supplement,
    });
  }

  it("quatre files avec leurs nouvelles demandes ; une file sans durée ne collecte rien", async () => {
    routes();
    render(<AccueilDemandes jeton="j" onExpire={vi.fn()} />);
    expect(await screen.findByRole("tab", { name: "Familles et préinscriptions (1)" })).toBeInTheDocument();
    expect(await screen.findByRole("tab", { name: "Candidatures de professeurs (2)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Saisir une demande" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Informations et questions" }));
    expect(await screen.findByText(/Durée de conservation non fixée/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Saisir une demande" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Candidatures de professeurs (2)" }));
    expect(screen.queryByRole("button", { name: "Saisir une demande" })).not.toBeInTheDocument(); // formulaire public seulement
    expect(screen.getByRole("link", { name: "Remarques" })).toHaveAttribute("href", "/admin/remarques");
  });

  it("fiche : historique du contact, issues propres à la file, traitement", async () => {
    const appels = routes();
    render(<AccueilDemandes jeton="j" onExpire={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: "F-ABCD2345" }));
    const fiche = await screen.findByRole("article", { name: "Demande F-ABCD2345" });
    expect(within(fiche).getByRole("button", { name: "I-WXYZ2345" })).toBeInTheDocument();
    expect(within(fiche).getByRole("button", { name: /détacher cette demande/ })).toBeInTheDocument();
    const issue = within(fiche).getByLabelText("Issue");
    expect(within(issue).getByRole("option", { name: "Inscription effective" })).toBeInTheDocument();
    const marquer = within(fiche).getByRole("button", { name: "Marquer traitée" });
    expect(marquer).toBeDisabled();
    await userEvent.selectOptions(issue, "inscription-effective");
    await userEvent.click(marquer);
    expect(appels.find((a) => a.cle === "POST /admin/accueil/demandes/1").corps).toEqual({ statut: "traite", issue: "inscription-effective" });
  });

  it("saisie d'une demande de famille par l'équipe", async () => {
    const appels = routes({ "POST /admin/accueil/demandes": { status: 201, json: { ...detail, id: 1 } } });
    render(<AccueilDemandes jeton="j" onExpire={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: "Saisir une demande" }));
    const form = screen.getByRole("form", { name: "Saisir une demande" });
    await userEvent.type(within(form).getByLabelText("Prénom"), "Sacha");
    await userEvent.type(within(form).getByLabelText("Nom"), "Fictif");
    await userEvent.type(within(form).getByLabelText("E-mail"), "sacha@exemple.test");
    await userEvent.type(within(form).getByLabelText("Besoin ou question"), "Bilan en 4e");
    await userEvent.click(within(form).getByRole("button", { name: "Enregistrer la demande" }));
    expect(appels.find((a) => a.cle === "POST /admin/accueil/demandes").corps).toEqual({
      prenom: "Sacha", nom: "Fictif", email: "sacha@exemple.test", telephone: null, message: "Bilan en 4e", categorie: "famille",
    });
    expect(await screen.findByRole("article", { name: "Demande F-ABCD2345" })).toBeInTheDocument();
  });
});
