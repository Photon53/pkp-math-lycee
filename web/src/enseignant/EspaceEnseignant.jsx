import { useState } from "react";
import { api } from "../api.js";
import { Erreur } from "../composants.jsx";
import { naviguer } from "../navigation.js";
import { ecrire, lire } from "../stockage.js";
import { CadreApplication, EntetePage } from "../ui/Cadre.jsx";
import Icone, { Logo } from "../ui/Icone.jsx";
import Classes from "./Classes.jsx";
import CoursEnseignant from "./CoursEnseignant.jsx";
import Questions from "./Questions.jsx";
import RessourcesEnseignant from "./RessourcesEnseignant.jsx";

const CLE_COMPTE = "pkp.enseignant";

const PAGES = [
  { vers: "/enseignant", libelle: "Classes et élèves", icone: "classes" },
  { vers: "/enseignant/cours", libelle: "Cours", icone: "cours" },
  { vers: "/enseignant/ressources", libelle: "Mes ressources", icone: "ressources" },
  { vers: "/enseignant/banque", libelle: "Banque de questions", icone: "exercices" },
];

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

  const page = PAGES.filter((p) => chemin === p.vers || chemin.startsWith(`${p.vers}/`)).sort(
    (a, b) => b.vers.length - a.vers.length,
  )[0] ?? PAGES[0];
  const props = { jeton: compte.jeton, onExpire: deconnecter };

  return (
    <CadreApplication
      espace="Espace professeur"
      liens={PAGES}
      cheminActif={chemin}
      pied={
        <>
          <div className="compte">{compte.nom}</div>
          {compte.role === "admin" && (
            <a href="/admin">
              <Icone nom="bouclier" /> Administration
            </a>
          )}
          <button className="nav" onClick={deconnecter}>
            <Icone nom="sortie" /> Se déconnecter
          </button>
        </>
      }
    >
      <EntetePage titre={page.libelle} fil="Espace professeur" />
      {page.vers === "/enseignant" && <Classes {...props} />}
      {page.vers === "/enseignant/cours" && <CoursEnseignant {...props} chemin={chemin} />}
      {page.vers === "/enseignant/ressources" && <RessourcesEnseignant {...props} />}
      {page.vers === "/enseignant/banque" && <Questions {...props} />}
    </CadreApplication>
  );
}

function PageSimple({ children }) {
  return (
    <div className="page">
      <header className="entete">
        <Logo />
        <nav aria-label="Espaces">
          <a href="/eleve">Espace élève</a>
        </nav>
      </header>
      <main>{children}</main>
    </div>
  );
}

function ConnexionEnseignant({ onConnexion }) {
  const [email, setEmail] = useState("");
  const [motDePasse, setMotDePasse] = useState("");
  const [erreur, setErreur] = useState(null);
  const [envoi, setEnvoi] = useState(false);

  async function soumettre(e) {
    e.preventDefault();
    setErreur(null);
    setEnvoi(true);
    try {
      onConnexion(await api("/enseignants/connexion", { methode: "POST", corps: { email, mot_de_passe: motDePasse } }));
    } catch (err) {
      setErreur(err.message);
      setMotDePasse("");
    } finally {
      setEnvoi(false);
    }
  }

  return (
    <form className="carte carte-etroite" onSubmit={soumettre}>
      <h1>Connexion professeur</h1>
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
function NouveauMotDePasse({ compte, onChange, onAnnuler }) {
  const [actuel, setActuel] = useState("");
  const [nouveau, setNouveau] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [erreur, setErreur] = useState(null);

  async function soumettre(e) {
    e.preventDefault();
    if (nouveau !== confirmation) return setErreur("Les deux saisies diffèrent.");
    setErreur(null);
    try {
      onChange(await api("/enseignants/mot-de-passe", { methode: "POST", jeton: compte.jeton, corps: { actuel, nouveau } }));
      naviguer("/enseignant");
    } catch (err) {
      if (err.status === 401 && err.message.startsWith("Authentification")) onAnnuler();
      else setErreur(err.message);
    }
  }

  return (
    <form className="carte carte-etroite" onSubmit={soumettre}>
      <h1>Choisissez votre mot de passe</h1>
      <p className="doux">Bienvenue {compte.nom}. Votre mot de passe actuel est provisoire : remplacez-le pour continuer.</p>
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
