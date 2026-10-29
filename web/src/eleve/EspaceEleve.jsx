import { useState } from "react";
import { api } from "../api.js";
import { Erreur, Onglets } from "../composants.jsx";
import { ecrire, lire } from "../stockage.js";
import Cours from "./Cours.jsx";
import Exercice, { CLE_BILAN, CLE_SEANCE } from "./Exercice.jsx";
import Progression from "./Progression.jsx";

const CLE_COMPTE = "pkp.eleve";

export default function EspaceEleve() {
  const [compte, setCompte] = useState(() => lire(CLE_COMPTE));
  const [onglet, setOnglet] = useState("exercice");
  const [leconOuverte, setLeconOuverte] = useState(null);

  function voirCours(competenceId) {
    setLeconOuverte(competenceId);
    setOnglet("cours");
  }

  function connecter(nouveau) {
    ecrire(CLE_COMPTE, nouveau);
    setCompte(nouveau);
  }

  function deconnecter() {
    ecrire(CLE_COMPTE, null);
    ecrire(CLE_SEANCE, null);
    ecrire(CLE_BILAN, null);
    setCompte(null);
  }

  if (!compte) return <ConnexionEleve onConnexion={connecter} />;

  return (
    <>
      <div className="barre-session">
        <p>
          Bonjour <strong>{compte.eleve.prenom}</strong> <span className="doux">· {compte.eleve.code_classe}</span>
        </p>
        <button className="lien" onClick={deconnecter}>
          Ce n'est pas moi
        </button>
      </div>
      <Onglets
        valeur={onglet}
        onChange={setOnglet}
        options={[
          ["exercice", "S'entraîner"],
          ["cours", "Cours"],
          ["progression", "Ma progression"],
        ]}
      />
      {onglet === "exercice" && <Exercice jeton={compte.jeton} onExpire={deconnecter} onVoirCours={voirCours} />}
      {onglet === "cours" && (
        <Cours jeton={compte.jeton} onExpire={deconnecter} competenceId={leconOuverte} onChoisir={setLeconOuverte} />
      )}
      {onglet === "progression" && <Progression jeton={compte.jeton} onExpire={deconnecter} />}
    </>
  );
}

export function ConnexionEleve({ onConnexion }) {
  const [prenom, setPrenom] = useState("");
  const [code, setCode] = useState("");
  const [codePersonnel, setCodePersonnel] = useState("");
  const [erreur, setErreur] = useState(null);
  const [envoi, setEnvoi] = useState(false);

  async function soumettre(e) {
    e.preventDefault();
    setErreur(null);
    setEnvoi(true);
    try {
      onConnexion(
        await api("/eleves/connexion", {
          methode: "POST",
          corps: { prenom, code_classe: code, code_personnel: codePersonnel },
        }),
      );
    } catch (err) {
      setErreur(
        err.status === 401 ? "Prénom, code classe ou code personnel incorrect. Vérifie-les avec ton professeur." : err.message,
      );
      setCodePersonnel("");
    } finally {
      setEnvoi(false);
    }
  }

  return (
    <form className="carte carte-etroite" onSubmit={soumettre}>
      <h1>Bienvenue</h1>
      <p className="doux">Entre ton prénom, le code de ta classe et ton code personnel, donnés par ton professeur.</p>
      <label htmlFor="prenom">Prénom</label>
      <input id="prenom" value={prenom} onChange={(e) => setPrenom(e.target.value)} autoComplete="given-name" maxLength={50} required />
      <label htmlFor="code">Code classe</label>
      <input
        id="code"
        value={code}
        onChange={(e) => setCode(e.target.value.toUpperCase())}
        placeholder="ex. 2NDE-7KQ4M"
        autoComplete="off"
        spellCheck={false}
        maxLength={20}
        required
      />
      <label htmlFor="code-personnel">Code personnel</label>
      <input
        id="code-personnel"
        type="password"
        value={codePersonnel}
        onChange={(e) => setCodePersonnel(e.target.value.toUpperCase())}
        placeholder="6 caractères"
        autoComplete="off"
        spellCheck={false}
        maxLength={20}
        required
      />
      <p className="aide">Ne le donne à personne : il protège ton compte.</p>
      <Erreur message={erreur} />
      <div className="actions">
        <button type="submit" disabled={envoi || !prenom.trim() || !code.trim() || !codePersonnel.trim()}>
          {envoi ? "Connexion…" : "Commencer"}
        </button>
      </div>
      <p className="aide">Seuls ton prénom et ta classe sont enregistrés.</p>
    </form>
  );
}
