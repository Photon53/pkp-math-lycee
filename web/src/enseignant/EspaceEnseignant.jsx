import { useState } from "react";
import { api } from "../api.js";
import { Erreur } from "../composants.jsx";
import { naviguer } from "../navigation.js";
import { ecrire, lire } from "../stockage.js";
import { CadreApplication, EntetePage } from "../ui/Cadre.jsx";
import Icone, { Logo } from "../ui/Icone.jsx";
import Classes from "./Classes.jsx";
import CoursEnseignant from "./CoursEnseignant.jsx";
import EnDirect from "./EnDirect.jsx";
import PkpMath from "../pkpmath/PkpMath.jsx";
import Questions from "./Questions.jsx";
import RessourcesEnseignant from "./RessourcesEnseignant.jsx";
import Remarques from "../ui/Remarques.jsx";
import Validation from "./Validation.jsx";

// Session partagée avec l'espace PKP Anglais : un professeur des deux disciplines ne se connecte qu'une fois.
export const CLE_COMPTE = "pkp.enseignant";

const PAGES = [
  { vers: "/enseignant", libelle: "Classes et élèves", icone: "classes" },
  { vers: "/enseignant/seance", libelle: "Séance en direct", icone: "tableau" },
  { vers: "/enseignant/cours", libelle: "Cours", icone: "cours" },
  { vers: "/enseignant/pkp-math", libelle: "Boussole Maths (fiches PDF)", icone: "pdf" },
  { vers: "/enseignant/ressources", libelle: "Mes ressources", icone: "ressources" },
  { vers: "/enseignant/banque", libelle: "Banque de questions", icone: "exercices" },
  { vers: "/enseignant/remarques", libelle: "Remarques et suggestions", icone: "crayon" },
];
// Validateurs en maths (ticket #29) : consulter, modifier et valider les cours et exercices de leur périmètre.
const VALIDATION = { vers: "/enseignant/validation", libelle: "Validation", icone: "bouclier" };

export default function EspaceEnseignant({ chemin = "/enseignant" }) {
  const [compte, setCompte] = useState(() => lire(CLE_COMPTE));

  function connecter(nouveau) {
    ecrire(CLE_COMPTE, nouveau);
    setCompte(nouveau);
  }

  function deconnecter() {
    ecrire(CLE_COMPTE, null);
    setCompte(null);
  }

  if (!compte) return <PageSimple><ConnexionEnseignant onConnexion={connecter} /></PageSimple>;
  if (compte.mdp_provisoire) {
    return (
      <PageSimple>
        <NouveauMotDePasse compte={compte} onChange={connecter} onAnnuler={deconnecter} />
      </PageSimple>
    );
  }
  // Session ouverte avant l'ajout des disciplines : le champ manque, le compte reste un compte de maths.
  const enseigne = compte.enseigne_maths !== false || Boolean(compte.enseigne_francais);
  if (!enseigne && !compte.validateur_maths) {
    return (
      <PageSimple>
        <AccesReserve
          titre="Espace réservé aux professeurs de mathématiques"
          compte={compte}
          autreEspace={{ vers: "/anglais", libelle: "Aller à l'espace Boussole Anglais" }}
          onDeconnexion={deconnecter}
        />
      </PageSimple>
    );
  }

  // Un validateur qui n'enseigne pas les maths n'a que la page Validation (l'API refuse le reste).
  const pages = !enseigne ? [VALIDATION] : compte.validateur_maths ? [...PAGES, VALIDATION] : PAGES;
  const page = pages.filter((p) => chemin === p.vers || chemin.startsWith(`${p.vers}/`)).sort(
    (a, b) => b.vers.length - a.vers.length,
  )[0] ?? pages[0];
  const props = { jeton: compte.jeton, onExpire: deconnecter };

  return (
    <CadreApplication
      espace="Espace professeur"
      marque="Maths"
      liens={pages}
      cheminActif={chemin}
      pied={
        <>
          <div className="compte">{compte.nom}</div>
          {compte.role === "admin" && (
            <a href="/admin">
              <Icone nom="bouclier" /> Administration
            </a>
          )}
          {compte.enseigne_anglais && (
            <a href="/anglais">
              <Icone nom="cours" /> Boussole Anglais
            </a>
          )}
          <button className="nav" onClick={deconnecter}>
            <Icone nom="sortie" /> Se déconnecter
          </button>
        </>
      }
    >
      <EntetePage titre={page.libelle} fil="Espace professeur" />
      {page.vers === "/enseignant" && (
        <Classes {...props} maths={compte.enseigne_maths !== false} francais={Boolean(compte.enseigne_francais)} />
      )}
      {page.vers === "/enseignant/seance" && <EnDirect {...props} />}
      {page.vers === "/enseignant/cours" && <CoursEnseignant {...props} chemin={chemin} />}
      {page.vers === "/enseignant/ressources" && <RessourcesEnseignant {...props} />}
      {page.vers === "/enseignant/banque" && <Questions {...props} />}
      {page.vers === "/enseignant/remarques" && <Remarques {...props} />}
      {page.vers === "/enseignant/validation" && <Validation {...props} chemin={chemin} />}
      {page.vers === "/enseignant/pkp-math" && <section className="carte"><PkpMath {...props} /></section>}
    </CadreApplication>
  );
}

export function PageSimple({ marque, children }) {
  return (
    <div className="page">
      <header className="entete">
        <Logo marque={marque} />
        <nav aria-label="Espaces">
          <a href="/eleve">Espace élève</a>
          <a href="/parent">Espace parent</a>
        </nav>
      </header>
      <main>{children}</main>
    </div>
  );
}

/** Compte connecté sans la discipline de cet espace : l'API refuserait aussi chaque requête (403). */
export function AccesReserve({ titre, compte, autreEspace, onDeconnexion }) {
  return (
    <div className="carte carte-etroite">
      <h1>{titre}</h1>
      <p className="doux">
        Le compte de {compte.nom} n'y a pas accès. Si c'est une erreur, demandez à un administrateur de cocher la discipline sur
        votre compte.
      </p>
      <div className="actions">
        {autreEspace && (
          <a className="bouton" href={autreEspace.vers}>
            {autreEspace.libelle}
          </a>
        )}
        <button type="button" className="lien" onClick={onDeconnexion}>
          Se déconnecter
        </button>
      </div>
    </div>
  );
}

export function ConnexionEnseignant({ titre = "Connexion professeur", onConnexion, chemin = "/enseignants/connexion", children }) {
  const [email, setEmail] = useState("");
  const [motDePasse, setMotDePasse] = useState("");
  const [erreur, setErreur] = useState(null);
  const [envoi, setEnvoi] = useState(false);

  async function soumettre(e) {
    e.preventDefault();
    setErreur(null);
    setEnvoi(true);
    try {
      onConnexion(await api(chemin, { methode: "POST", corps: { email, mot_de_passe: motDePasse } }));
    } catch (err) {
      setErreur(err.message);
      setMotDePasse("");
    } finally {
      setEnvoi(false);
    }
  }

  return (
    <form className="carte carte-etroite" onSubmit={soumettre}>
      <h1>{titre}</h1>
      {children}
      <label htmlFor="email">Email</label>
      <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" required />
      <label htmlFor="mdp">Mot de passe</label>
      <input
        id="mdp"
        type="password"
        value={motDePasse}
        onChange={(e) => setMotDePasse(e.target.value)}
        autoComplete="current-password"
        required
      />
      <Erreur message={erreur} />
      <div className="actions">
        <button type="submit" disabled={envoi}>
          {envoi ? "Connexion…" : "Se connecter"}
        </button>
      </div>
    </form>
  );
}

/** Mot de passe provisoire donné par un administrateur : à remplacer avant tout le reste (EA3.2). */
export function NouveauMotDePasse({ compte, onChange, onAnnuler, retour = "/enseignant", chemin = "/enseignants/mot-de-passe" }) {
  const [actuel, setActuel] = useState("");
  const [nouveau, setNouveau] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [erreur, setErreur] = useState(null);

  async function soumettre(e) {
    e.preventDefault();
    if (nouveau !== confirmation) return setErreur("Les deux saisies diffèrent.");
    setErreur(null);
    try {
      onChange(await api(chemin, { methode: "POST", jeton: compte.jeton, corps: { actuel, nouveau } }));
      naviguer(retour);
    } catch (err) {
      if (err.status === 401 && err.message.startsWith("Authentification")) onAnnuler();
      else setErreur(err.message);
    }
  }

  return (
    <form className="carte carte-etroite" onSubmit={soumettre}>
      <h1>Choisissez votre mot de passe</h1>
      <p className="doux">Bienvenue {compte.nom ?? compte.email}. Votre mot de passe actuel est provisoire : remplacez-le pour continuer.</p>
      <label htmlFor="actuel">Mot de passe provisoire</label>
      <input id="actuel" type="password" value={actuel} onChange={(e) => setActuel(e.target.value)} autoComplete="current-password" required />
      <label htmlFor="nouveau">Nouveau mot de passe</label>
      <input
        id="nouveau"
        type="password"
        minLength={12}
        value={nouveau}
        onChange={(e) => setNouveau(e.target.value)}
        autoComplete="new-password"
        required
      />
      <p className="aide">12 caractères au moins.</p>
      <label htmlFor="confirmation">Confirmation</label>
      <input
        id="confirmation"
        type="password"
        value={confirmation}
        onChange={(e) => setConfirmation(e.target.value)}
        autoComplete="new-password"
        required
      />
      <Erreur message={erreur} />
      <div className="actions">
        <button type="submit">Enregistrer</button>
        <button type="button" className="lien" onClick={onAnnuler}>
          Se déconnecter
        </button>
      </div>
    </form>
  );
}
