import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import EspaceAdmin from "../admin/EspaceAdmin.jsx";
import Exercices from "../admin/Exercices.jsx";
import Professeurs from "../admin/Professeurs.jsx";
import TableauDeBord from "../admin/TableauDeBord.jsx";
import Cours from "../eleve/Cours.jsx";
import EspaceEnseignant from "../enseignant/EspaceEnseignant.jsx";
import { formulesInvalides } from "../maths.jsx";
import { fausseApi } from "./setup.js";

const STATS = {
  periode_jours: 30, calcule_le: "2026-10-30T10:00:00Z", professeurs_actifs: 3, professeurs_total: 4,
  eleves_actifs: 40, eleves_total: 52, seances: 120, reponses: 1840, taux_reussite: 0.62,
  seances_par_jour: [{ jour: "2026-10-28", valeur: 30 }, { jour: "2026-10-29", valeur: 45 }],
  reponses_par_jour: [{ jour: "2026-10-28", reponses: 400, correctes: 250 }, { jour: "2026-10-29", reponses: 600, correctes: 380 }],
  reussite_par_chapitre: [
    { chapitre_id: 1, titre: "Fractions", niveau: "2nde", reponses: 300, taux_reussite: 0.35 },
    { chapitre_id: 2, titre: "Suites", niveau: "1re", reponses: 12, taux_reussite: null },
  ],
  questions_difficiles: [], couverture: [{ niveau: "2nde", a_valider: 80, validees: 40, a_corriger: 3 }],
  competences_sans_cours: 2, chapitres_sans_question_validee: ["Suites"],
  repartition: [{ niveau: "2nde", parcours: "tronc-commun", classes: 2, eleves: 52 }],
  ressources_liens: 3, ressources_pdf: 1, ressources_consultees: [],
};

describe("administration", () => {
  it("demande le code du second facteur et affiche le refus du serveur", async () => {
    const appels = fausseApi({
      "POST /admin/connexion": { status: 401, json: { detail: "Code de l'application d'authentification incorrect." } },
    });
    render(<EspaceAdmin chemin="/admin" />);
    await userEvent.type(screen.getByLabelText("Email"), "admin@pkp.fr");
    await userEvent.type(screen.getByLabelText("Mot de passe"), "secret-long-123");
    await userEvent.type(screen.getByLabelText(/Code de l'application/), "123456");
    await userEvent.click(screen.getByRole("button", { name: "Se connecter" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("incorrect");
    expect(appels[0].corps).toEqual({ email: "admin@pkp.fr", mot_de_passe: "secret-long-123", code_totp: "123456" });
  });

  it("tableau de bord : chiffres clés et agrégats masqués sous le seuil", async () => {
    fausseApi({ "GET /admin/statistiques?periode=30": { json: STATS } });
    render(<TableauDeBord jeton="j" onExpire={vi.fn()} />);
    expect(await screen.findByText("1 840")).toBeInTheDocument();
    expect(screen.getByText("62 %")).toBeInTheDocument();
    expect(screen.getByText("35 %")).toBeInTheDocument();
    expect(screen.getByText(/1 chapitre\(s\) masqué\(s\)/)).toBeInTheDocument();
  });

  it("affiche une seule fois le mot de passe provisoire d'un nouveau professeur", async () => {
    let liste = [];
    fausseApi({
      "GET /admin/enseignants": () => ({ json: liste }),
      "POST /admin/enseignants": (corps) => {
        const enseignant = { id: 9, ...corps, actif: true, mdp_provisoire: true, totp_configure: false, nb_classes: 0, nb_eleves: 0, derniere_connexion: null };
        liste = [enseignant];
        return { status: 201, json: { enseignant, mot_de_passe_provisoire: "Abc23defGhk45mnP" } };
      },
    });
    render(<Professeurs jeton="j" onExpire={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: /Nouveau professeur/ }));
    const fenetre = screen.getByRole("dialog");
    await userEvent.type(within(fenetre).getByLabelText("Nom affiché"), "Mme Martin");
    await userEvent.type(within(fenetre).getByLabelText("E-mail"), "martin@lycee.fr");
    await userEvent.click(within(fenetre).getByRole("button", { name: "Créer le compte" }));
    expect(await screen.findByText("Abc23defGhk45mnP")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "J'ai noté le mot de passe" }));
    expect(screen.queryByText("Abc23defGhk45mnP")).not.toBeInTheDocument();
    expect(await screen.findByText("Mot de passe provisoire")).toBeInTheDocument();
  });

  it("exercices : fige le fond d'une question déjà répondue", async () => {
    const question = {
      id: 5, code: "2NDE-FRAC-01", competence_id: 1, competence: "Fractions", chapitre: "Nombres", niveau: "2nde",
      enonce: "Calculer $1/2 + 1/3$.", type: "numerique", solution: "5/6", difficulte: 1, archivee: false, source: "PKP Math",
      source_url: null, licence_source: null, adaptation: "originale", statut_validation: "a-valider", valide_par: null,
      valide_le: null, auteur: null, nb_reponses: 12, taux_reussite: 0.5,
    };
    fausseApi({
      "GET /admin/questions?page=1&archivees=false": { json: { total: 1, elements: [question] } },
      "GET /admin/contenu": { json: [{ id: 1, titre: "Nombres", niveau: "2nde", competences: [{ id: 1, libelle: "Fractions" }] }] },
    });
    render(<Exercices jeton="j" onExpire={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: "Modifier la question 2NDE-FRAC-01" }));
    expect(screen.getByText(/Déjà 12 réponse\(s\)/)).toBeInTheDocument();
    expect(screen.getByLabelText("Solution")).toBeDisabled();
    expect(screen.getByLabelText("Difficulté (1 à 5)")).not.toBeDisabled();
  });

  it("refuse une formule que KaTeX ne sait pas afficher", () => {
    expect(formulesInvalides("Soit $x^2$ et $\\frac{1}{2}$.")).toEqual([]);
    expect(formulesInvalides("Soit $\\frac{1}{$ ici.")).toHaveLength(1);
  });
});

describe("professeur", () => {
  it("doit remplacer un mot de passe provisoire avant tout le reste", async () => {
    sessionStorage.setItem("pkp.enseignant", JSON.stringify({ jeton: "j", nom: "Mme Neuve", role: "enseignant", mdp_provisoire: true }));
    const appels = fausseApi({
      "POST /enseignants/mot-de-passe": { json: { jeton: "j2", nom: "Mme Neuve", role: "enseignant", mdp_provisoire: false } },
      "GET /enseignants/classes": { json: [] },
    });
    render(<EspaceEnseignant chemin="/enseignant" />);
    expect(screen.getByRole("heading", { name: "Choisissez votre mot de passe" })).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Mot de passe provisoire"), "Abc23defGhk45mnP");
    await userEvent.type(screen.getByLabelText("Nouveau mot de passe"), "mon-mot-de-passe-solide");
    await userEvent.type(screen.getByLabelText("Confirmation"), "mon-mot-de-passe-solide");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
    expect(await screen.findByRole("heading", { name: "Classes et élèves" })).toBeInTheDocument();
    expect(appels[0].corps).toEqual({ actuel: "Abc23defGhk45mnP", nouveau: "mon-mot-de-passe-solide" });
  });

  it("lit une leçon avec ses ressources, et peut la projeter", async () => {
    fausseApi({
      "GET /enseignants/cours/10": {
        json: {
          competence_id: 10, code: "TLE-LN", libelle: "Logarithme", chapitre: "Fonction ln", cours: "Cours", resume: "Résumé",
          ressources: [
            { id: 1, type: "lien", titre: "Vidéo", description: "", url: "https://example.org/v", domaine: "example.org", taille_octets: null, portee: "commune" },
            { id: 2, type: "pdf", titre: "Fiche", description: "", url: null, domaine: null, taille_octets: 2048, portee: "classe" },
          ],
        },
      },
    });
    render(<Cours jeton="j" onExpire={vi.fn()} competenceId={10} onChoisir={vi.fn()} base="/enseignants/cours" enseignant sommaireFourni={[]} />);
    const lien = await screen.findByRole("link", { name: "Vidéo" });
    expect(lien).toHaveAttribute("rel", "noopener noreferrer");
    expect(lien).toHaveAttribute("target", "_blank");
    expect(screen.getByText(/PDF · 2 Ko/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Projeter/ }));
    expect(screen.getByRole("article")).toHaveClass("projection");
    await userEvent.keyboard("{Escape}");
    expect(screen.getByRole("article")).not.toHaveClass("projection");
  });
});
