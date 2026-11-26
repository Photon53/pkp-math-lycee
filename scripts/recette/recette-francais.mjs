#!/usr/bin/env node
// Issue #217 — Recette automatisée multi-rôles du Français dans un vrai navigateur (Claude)
//
// Rejoue, écran par écran, le parcours Français de chaque rôle et produit un rapport (Markdown + JSON) avec une
// capture par étape. Aucune dépendance du dépôt : Playwright est celui du poste (require('playwright')).
//
//   BASE_URL       adresse de l'application (défaut http://127.0.0.1:5173 ; en DEV : l'adresse du tunnel IAP)
//   ADMIN_EMAIL    compte administrateur ; ADMIN_MDP son mot de passe ; ADMIN_TOTP le code à 6 chiffres si exigé
//   MODE           « lecture » (défaut) : ne valide rien, n'ouvre rien, ne règle aucun domaine. Contrôle l'import,
//                  les écrans de chaque rôle et les refus ; les étapes élève lisent ce qui est déjà ouvert.
//                  « complet » : valide le dossier (administrateur, V2-D15) et l'ouvre à une classe pilote de
//                  recette. RÉSERVÉ à une base jetable : sur une instance partagée, la validation d'un contenu
//                  réel est une décision pédagogique humaine.
//   VERSION        SHA ou digest de la version testée, recopié dans le rapport (défaut : « non renseignée »)
//   SORTIE         dossier du rapport (défaut ./recette-francais-<horodatage>)
//   DOSSIER        code du dossier attendu (défaut FR3-DNB27-01)
//
// Les comptes créés sont fictifs, préfixés « recette-<horodatage> », sans aucune donnée personnelle réelle.

import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const BASE_URL = (process.env.BASE_URL ?? "http://127.0.0.1:5173").replace(/\/$/, "");
const MODE = process.env.MODE ?? "lecture";
const CODE = process.env.DOSSIER ?? "FR3-DNB27-01";
const DOMAINE = "francais-college";
const HORODATAGE = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
const PREFIXE = `recette-${HORODATAGE.toLowerCase()}`;
const SORTIE = process.env.SORTIE ?? `recette-francais-${HORODATAGE}`;
const MDP = `Recette-${HORODATAGE}-Fr!`;

if (!["lecture", "complet"].includes(MODE)) throw new Error(`MODE inconnu : ${MODE}`);
if (!process.env.ADMIN_EMAIL || !process.env.ADMIN_MDP) throw new Error("ADMIN_EMAIL et ADMIN_MDP sont requis.");
mkdirSync(SORTIE, { recursive: true });

// --- Rapport -------------------------------------------------------------------------------------------------
const etapes = [];
let numero = 0;

async function etape(role, nom, fn, { page, bloquante = false } = {}) {
  numero += 1;
  const ligne = { numero, role, nom, statut: "OK", detail: "", capture: null };
  try {
    ligne.detail = (await fn()) ?? "";
  } catch (err) {
    ligne.statut = err.nonApplicable ? "N/A" : "KO";
    ligne.detail = String(err.message ?? err).split("\n")[0].slice(0, 300);
  }
  if (page) {
    ligne.capture = `${String(numero).padStart(2, "0")}-${role}.png`.replace(/[^\w.-]/g, "_");
    await page.screenshot({ path: join(SORTIE, ligne.capture), fullPage: true }).catch(() => (ligne.capture = null));
  }
  etapes.push(ligne);
  console.log(`${ligne.statut.padEnd(3)} [${role}] ${nom}${ligne.detail ? ` — ${ligne.detail}` : ""}`);
  if (bloquante && ligne.statut === "KO") throw new Error(`Étape bloquante en échec : ${nom}`);
  return ligne.statut === "OK";
}

const nonApplicable = (message) => Object.assign(new Error(message), { nonApplicable: true });
const verifier = (condition, message) => {
  if (!condition) throw new Error(message);
};

// --- API -----------------------------------------------------------------------------------------------------
async function api(chemin, { methode = "GET", corps, jeton } = {}) {
  const reponse = await fetch(`${BASE_URL}/api${chemin}`, {
    method: methode,
    headers: { ...(corps ? { "Content-Type": "application/json" } : {}), ...(jeton ? { Authorization: `Bearer ${jeton}` } : {}) },
    body: corps ? JSON.stringify(corps) : undefined,
  });
  const texte = await reponse.text();
  let json = null;
  try {
    json = texte ? JSON.parse(texte) : null;
  } catch {
    json = texte;
  }
  return { status: reponse.status, json };
}

async function apiOk(chemin, options) {
  const r = await api(chemin, options);
  if (r.status >= 400) throw new Error(`${options?.methode ?? "GET"} ${chemin} → ${r.status} ${JSON.stringify(r.json?.detail ?? r.json)}`);
  return r.json;
}

async function creerProfesseur(jetonAdmin, suffixe, habilitations) {
  const email = `${PREFIXE}-${suffixe}@recette.test`;
  const cree = await apiOk("/admin/enseignants", {
    methode: "POST", jeton: jetonAdmin, corps: { nom: `Recette ${suffixe}`, email, role: "enseignant", habilitations },
  });
  const provisoire = cree.mot_de_passe_provisoire;
  const { jeton } = await apiOk("/enseignants/connexion", { methode: "POST", corps: { email, mot_de_passe: provisoire } });
  await apiOk("/enseignants/mot-de-passe", { methode: "POST", jeton, corps: { actuel: provisoire, nouveau: MDP } });
  return { id: cree.enseignant.id, email };
}

// --- Navigateur ----------------------------------------------------------------------------------------------
async function connecterProfesseur(navigateur, chemin, email) {
  const page = await (await navigateur.newContext()).newPage();
  await page.goto(`${BASE_URL}${chemin}`);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Mot de passe").fill(MDP);
  await page.getByRole("button", { name: "Se connecter" }).click();
  return page;
}

async function connecterEleve(navigateur, prenom, codeClasse, codePersonnel) {
  const page = await (await navigateur.newContext()).newPage();
  await page.goto(`${BASE_URL}/eleve`);
  // L'espace élève est chargé à la demande : attendre le formulaire, puis choisir la connexion par prénom.
  await page.getByRole("heading", { name: "Connexion élève" }).waitFor({ timeout: 15_000 });
  const lienClasse = page.getByRole("button", { name: /me connecter avec mon prénom/ });
  if (await lienClasse.isVisible()) await lienClasse.click();
  await page.getByLabel("Prénom").fill(prenom);
  await page.getByLabel("Code classe").fill(codeClasse);
  await page.getByLabel("Code personnel").fill(codePersonnel);
  await page.getByRole("button", { name: "Commencer" }).click();
  await page.getByRole("tab", { name: "Cours", exact: true }).waitFor({ timeout: 15_000 });
  return page;
}

const visible = (locator, ms = 10_000) => locator.first().waitFor({ state: "visible", timeout: ms }).then(() => true);

// --- Recette -------------------------------------------------------------------------------------------------
async function recette() {
  const ctx = {};

  // 0. Version et préparation (API, compte administrateur) ----------------------------------------------------
  await etape("système", "API joignable (/api/health)", async () => {
    const r = await apiOk("/health");
    verifier(r?.status === "ok", "réponse inattendue");
    return `version testée : ${process.env.VERSION ?? "non renseignée"}`;
  }, { bloquante: true });

  await etape("administrateur", "Connexion administrateur (API)", async () => {
    const r = await apiOk("/admin/connexion", {
      methode: "POST",
      corps: { email: process.env.ADMIN_EMAIL, mot_de_passe: process.env.ADMIN_MDP, code_totp: process.env.ADMIN_TOTP || null },
    });
    ctx.admin = r.jeton;
  }, { bloquante: true });

  await etape("système", "Dossier importé et domaine Français collège actif", async () => {
    let etat = await apiOk("/francais/etat", { jeton: ctx.admin });
    const domaine = etat.domaines.find((d) => d.code === DOMAINE);
    verifier(etat.dossiers > 0, "aucun dossier de français dans la base : import absent");
    if (!domaine.actif) {
      if (MODE !== "complet") throw new Error(`${domaine.libelle} n'est pas actif (Administration → Domaines)`);
      await apiOk(`/admin/domaines/${DOMAINE}`, { methode: "POST", jeton: ctx.admin, corps: { actif: true, public: false } });
      etat = await apiOk("/francais/etat", { jeton: ctx.admin });
    }
    return etat.domaines.map((d) => `${d.libelle} : ${d.actif ? "actif" : "inactif"}, ${d.dossiers} dossier(s)`).join(" ; ");
  }, { bloquante: true });

  await etape("administrateur", "Comptes de recette (professeur 3e, validateur, hors périmètre) et classes pilotes", async () => {
    ctx.prof = await creerProfesseur(ctx.admin, "prof3e", [{ role: "professeur", domaine: DOMAINE, niveau: "3e" }]);
    ctx.validateur = await creerProfesseur(ctx.admin, "validateur", [
      { role: "professeur", domaine: DOMAINE, niveau: "3e" }, { role: "validateur", domaine: DOMAINE, niveau: "3e" },
    ]);
    ctx.hors = await creerProfesseur(ctx.admin, "prof6e", [{ role: "professeur", domaine: DOMAINE, niveau: "6e" }]);
    const { jeton: jetonProf } = await apiOk("/enseignants/connexion", { methode: "POST", corps: { email: ctx.prof.email, mot_de_passe: MDP } });
    ctx.jetonProf = jetonProf;
    for (const cle of ["pilote", "horsPilote"]) {
      const c = await apiOk("/admin/classes-pilotes", {
        methode: "POST", jeton: ctx.admin,
        corps: { matiere: "francais", niveau: "3e", enseignant_id: ctx.prof.id, motif: `Recette automatisée #217 (${PREFIXE})` },
      });
      const e = await apiOk(`/enseignants/classes/${c.classe_id}/eleves`, { methode: "POST", jeton: jetonProf, corps: { prenoms: ["Recette"] } });
      ctx[cle] = { id: c.classe_id, code: c.code, codePersonnel: e.crees[0].code };
    }
    // Classe retirée de la liste pilote : ses élèves doivent perdre l'accès (SEC-D6).
    await apiOk(`/admin/classes-pilotes/${ctx.horsPilote.id}`, { methode: "DELETE", jeton: ctx.admin });
    return `préfixe ${PREFIXE} ; classe pilote ${ctx.pilote.code} ; classe retirée ${ctx.horsPilote.code}`;
  }, { bloquante: true });

  const navigateur = await chromium.launch();
  try {
    // 1. Professeur hors périmètre ---------------------------------------------------------------------------
    {
      const page = await connecterProfesseur(navigateur, "/francais", ctx.hors.email);
      await etape("prof hors périmètre", "Aucun dossier de 3e visible", async () => {
        await visible(page.getByText("Aucun dossier de français accessible avec vos habilitations."));
        const r = await api(`/francais/dossiers/${CODE}/professeur`, {
          jeton: (await apiOk("/enseignants/connexion", { methode: "POST", corps: { email: ctx.hors.email, mot_de_passe: MDP } })).jeton,
        });
        verifier(r.status === 404, `accès direct aux supports : ${r.status} au lieu de 404`);
      }, { page });
    }

    // 2. Validateur, depuis l'espace professeur habituel -------------------------------------------------------
    {
      const page = await connecterProfesseur(navigateur, "/enseignant", ctx.validateur.email);
      await etape("validateur", "Lien vers la validation du français depuis /enseignant", async () => {
        await page.getByRole("link", { name: /Boussole Français : dossiers et validation/ }).first().click();
        await visible(page.getByRole("heading", { name: "Dossiers de français" }));
      }, { page });
      await etape("validateur", "File de validation : dossier soumis et bouton « Valider »", async () => {
        await page.getByRole("tab", { name: "Validation" }).click();
        const liste = page.locator("#dossier-a-valider");
        // Attendre la fin du chargement de la file (liste ou message « aucun dossier ») avant de choisir.
        await liste.or(page.getByText("Aucun dossier en attente de validation.")).first().waitFor({ timeout: 10_000 });
        if (!(await liste.isVisible())) {
          await visible(page.getByText("Aucun dossier en attente de validation."));
          throw nonApplicable("aucune version soumise : le dossier est déjà validé ou refusé");
        }
        await liste.selectOption(CODE);
        // La file se recharge à l'ouverture de l'onglet : refaire le choix s'il a été perdu.
        if (!(await visible(page.getByRole("button", { name: "Valider cette version" }), 5_000).catch(() => false))) {
          await liste.selectOption(CODE);
          await visible(page.getByRole("button", { name: "Valider cette version" }));
        }
        await visible(page.getByRole("button", { name: "Refuser" }));
      }, { page });
    }

    // 3. Administrateur : connexion à l'écran, puis Français sans nouvelle connexion ; validation (mode complet)
    {
      const page = await (await navigateur.newContext()).newPage();
      await page.goto(`${BASE_URL}/admin`);
      await etape("administrateur", "Connexion à l'écran et accès au Français depuis l'administration", async () => {
        await page.getByLabel("Email").fill(process.env.ADMIN_EMAIL);
        await page.getByLabel("Mot de passe").fill(process.env.ADMIN_MDP);
        if (process.env.ADMIN_TOTP) await page.getByLabel("Code de l'application d'authentification").fill(process.env.ADMIN_TOTP);
        await page.getByRole("button", { name: /Se connecter/ }).click();
        await page.getByRole("link", { name: "Boussole Français (préparation)" }).first().click();
        await visible(page.getByRole("heading", { name: "Dossiers de français" }));
        await visible(page.getByText(CODE));
      }, { page });
      await etape("administrateur", "Supports professeur et export PDF", async () => {
        await page.getByRole("button", { name: "Ouvrir" }).first().click();
        await page.getByRole("tab", { name: /Supports professeur/ }).click();
        await visible(page.getByText("Corrigés expliqués"));
        const [telechargement] = await Promise.all([
          page.waitForEvent("download"),
          page.getByRole("button", { name: "PDF élève (sans corrigé)" }).click(),
        ]);
        return `PDF élève : ${telechargement.suggestedFilename()}`;
      }, { page });
      await etape("administrateur", "Validation du dossier (V2-D15)", async () => {
        if (MODE !== "complet") throw nonApplicable("mode lecture : aucune validation");
        const resume = (await apiOk("/francais/dossiers", { jeton: ctx.admin })).find((d) => d.code === CODE);
        if (resume.statut !== "soumis") throw nonApplicable(`aucune version soumise (statut ${resume.statut}, validée : v${resume.version_validee})`);
        await page.getByRole("button", { name: /Tous les dossiers/ }).click();
        await page.getByRole("tab", { name: "Validation" }).click();
        await page.locator("#dossier-a-valider").selectOption(CODE);
        await page.getByRole("button", { name: "Valider cette version" }).click();
        await visible(page.getByText(`${CODE} validé`));
      }, { page });
    }

    // 4. Professeur : consultation, PDF et ouverture à la classe pilote ---------------------------------------
    {
      const page = await connecterProfesseur(navigateur, "/francais", ctx.prof.email);
      await etape("professeur", "Dossier visible et PDF professeur", async () => {
        await page.getByRole("button", { name: "Ouvrir" }).first().click();
        const [telechargement] = await Promise.all([
          page.waitForEvent("download"),
          page.getByRole("button", { name: "PDF professeur (avec corrigés)" }).click(),
        ]);
        return `PDF : ${telechargement.suggestedFilename()}`;
      }, { page });
      await etape("professeur", "Ouverture du dossier à la classe pilote", async () => {
        await page.getByRole("tab", { name: "Mes classes" }).click();
        const ligne = page.locator("li").filter({ hasText: ctx.pilote.code });
        await visible(ligne);
        if (MODE !== "complet") throw nonApplicable("mode lecture : aucune ouverture");
        await ligne.getByRole("button", { name: "Ouvrir à cette classe" }).click();
        await visible(ligne.getByText("Ouvert"));
      }, { page });
    }

    // 5. Élèves -------------------------------------------------------------------------------------------------
    const ouvert = MODE === "complet";
    const corriges = (await apiOk(`/francais/dossiers/${CODE}/professeur`, { jeton: ctx.admin })).professeur.corriges
      .flatMap((c) => c.paragraphes).filter((p) => p.length >= 40);
    {
      const page = await connecterEleve(navigateur, "Recette", ctx.pilote.code, ctx.pilote.codePersonnel);
      await etape("élève pilote", "Dossier lisible dans « Cours », sans aucun corrigé", async () => {
        await page.getByRole("tab", { name: "Cours", exact: true }).click();
        if (!ouvert) throw nonApplicable("mode lecture : la classe de recette n'a aucun dossier ouvert");
        await visible(page.getByRole("heading", { name: "Mes dossiers" }));
        await page.locator("section").filter({ has: page.getByRole("heading", { name: "Mes dossiers" }) }).getByRole("button").first().click();
        await visible(page.getByText(/Rédige ta réponse/));
        const texte = await page.locator("body").innerText();
        const fuite = corriges.find((p) => texte.includes(p.slice(0, 60)));
        verifier(!fuite, `corrigé visible côté élève : « ${fuite?.slice(0, 60)}… »`);
      }, { page });
      // Issue #217 : quiz corrigé, comme l'anglais ; aucune explication visible avant la réponse (ARCH-4).
      await etape("élève pilote", "Quiz : réponse corrigée après chaque question, puis score", async () => {
        if (!ouvert) throw nonApplicable("mode lecture : aucun dossier ouvert");
        const quiz = (await apiOk(`/francais/dossiers/${CODE}/professeur`, { jeton: ctx.admin })).professeur.quiz ?? [];
        if (quiz.length === 0) throw nonApplicable("la version validée n'a pas de quiz");
        await visible(page.getByRole("heading", { name: "Quiz" }));
        const avant = await page.locator("body").innerText();
        const fuite = quiz.find((q) => avant.includes(q.explication.slice(0, 50)));
        verifier(!fuite, `explication du quiz visible avant la réponse : « ${fuite?.explication.slice(0, 50)}… »`);
        for (let i = 0; i < quiz.length; i += 1) {
          await page.locator(`input[name="quiz-${i}"]`).first().check();
          await visible(page.locator("fieldset").nth(i).locator("p.petit"));
        }
        await page.getByRole("button", { name: /Terminer le quiz|Voir la correction/ }).click();
        await visible(page.getByText(/Score : \d+\/\d+/));
        return `${quiz.length} questions`;
      }, { page });
    }
    // Issue #217 : suivi de la classe par le professeur.
    if (ouvert) {
      const page = await connecterProfesseur(navigateur, "/francais", ctx.prof.email);
      await etape("professeur", "Suivi des classes : score de l'élève pilote", async () => {
        await page.getByRole("tab", { name: "Suivi des classes" }).click();
        const option = page.locator("#classe-francais option", { hasText: ctx.pilote.code });
        await option.waitFor({ state: "attached" });
        await page.locator("#classe-francais").selectOption(await option.getAttribute("value"));
        await visible(page.getByRole("heading", { name: "Progression" }));
        await visible(page.getByText(/1er essai/));
      }, { page });
    }
    {
      const page = await connecterEleve(navigateur, "Recette", ctx.horsPilote.code, ctx.horsPilote.codePersonnel).catch(() => null);
      await etape("élève hors pilote", "Aucun dossier, et 403 par adresse directe", async () => {
        const { jeton } = await apiOk("/eleves/connexion", {
          methode: "POST", corps: { prenom: "Recette", code_classe: ctx.horsPilote.code, code_personnel: ctx.horsPilote.codePersonnel },
        });
        const r = await api(`/francais/eleve/dossiers/${CODE}`, { jeton });
        verifier(r.status === 403, `adresse directe : ${r.status} au lieu de 403`);
        if (page) {
          await page.getByRole("tab", { name: "Cours", exact: true }).click();
          verifier(!(await page.getByRole("heading", { name: "Mes dossiers" }).isVisible()), "« Mes dossiers » affiché");
        }
      }, { page: page ?? undefined });
    }

    // 6. Simulation par le professeur ---------------------------------------------------------------------------
    await etape("professeur", "Simulation d'un élève de la classe pilote", async () => {
      const { jeton } = await apiOk("/enseignants/simulation", { methode: "POST", jeton: ctx.jetonProf, corps: { classe_id: ctx.pilote.id } });
      const dossiers = await apiOk("/francais/eleve/dossiers", { jeton });
      if (ouvert) verifier(dossiers.some((d) => d.code === CODE), "l'élève fictif ne voit pas le dossier ouvert");
      const adulte = await api("/francais/dossiers", { jeton });
      verifier(adulte.status === 401, `jeton fictif sur une route adulte : ${adulte.status} au lieu de 401`);
      await apiOk("/eleves/moi/simulation/fermer", { methode: "POST", jeton });
      return `${dossiers.length} dossier(s) vu(s) par l'élève fictif`;
    });

    // 7. Non-régression rapide ----------------------------------------------------------------------------------
    await etape("administrateur", "Non-régression : listes Maths et Anglais de l'administration", async () => {
      await apiOk("/admin/contenu", { jeton: ctx.admin });
      await apiOk("/admin/anglais/seances", { jeton: ctx.admin });
    });
  } finally {
    await navigateur.close();
  }
}

// --- Exécution et rapport -------------------------------------------------------------------------------------
let erreurFatale = null;
try {
  await recette();
} catch (err) {
  erreurFatale = String(err.message ?? err);
}

const ko = etapes.filter((e) => e.statut === "KO").length;
const resume = {
  date: new Date().toISOString(), base_url: BASE_URL, mode: MODE, version: process.env.VERSION ?? "non renseignée",
  dossier: CODE, prefixe_comptes: PREFIXE, resultat: ko || erreurFatale ? "ÉCHEC" : "RÉUSSIE", erreur: erreurFatale, etapes,
};
writeFileSync(join(SORTIE, "rapport.json"), JSON.stringify(resume, null, 2));
writeFileSync(join(SORTIE, "rapport.md"), [
  `# Recette Français — ${resume.resultat}`,
  "",
  `- Adresse : ${BASE_URL}`,
  `- Version testée : ${resume.version}`,
  `- Mode : ${MODE}`,
  `- Date : ${resume.date}`,
  `- Comptes fictifs créés : préfixe \`${PREFIXE}\``,
  ...(erreurFatale ? [`- **Arrêt** : ${erreurFatale}`] : []),
  "",
  "| # | Rôle | Étape | Résultat | Détail | Capture |",
  "|---|---|---|---|---|---|",
  ...etapes.map((e) => `| ${e.numero} | ${e.role} | ${e.nom} | ${e.statut} | ${e.detail.replace(/\|/g, "/")} | ${e.capture ? `![](${e.capture})` : ""} |`),
  "",
].join("\n"));
console.log(`\nRecette ${resume.resultat} : rapport dans ${SORTIE}/rapport.md`);
process.exit(ko || erreurFatale ? 1 : 0);
