import { useState } from "react";
import { api } from "../api.js";
import { Erreur, Onglets } from "../composants.jsx";
import { ecrire, lire } from "../stockage.js";
import Cours from "./Cours.jsx";
import Exercice, { CLE_BILAN, CLE_CIBLE, CLE_SEANCE } from "./Exercice.jsx";
import Historique from "./Historique.jsx";
import Progression from "./Progression.jsx";

const CLE_COMPTE = "pkp.eleve";

export default function EspaceEleve() {
  const [compte, setCompte] = useState(() => lire(CLE_COMPTE));
  const [onglet, setOnglet] = useState("exercice");
  const [leconOuverte, setLeconOuverte] = useState(null);
  // Leçon ouverte depuis un exercice : la leçon propose d'y revenir, l'exercice n'est pas perdu.
  const [depuisExercice, setDepuisExercice] = useState(false);
  // Demande d'entrainement ciblé, depuis une leçon ou l'historique : { id, libelle, n }.
  const [cible, setCible] = useState(null);

  function voirCours(competenceId, { depuisLExercice = true } = {}) {
    setLeconOuverte(competenceId);
    setDepuisExercice(depuisLExercice);
    setOnglet("cours");
  }

  // Historique filtré sur une compétence (étape « Je vérifie » d'une leçon) ; null = tout.
  const [historiqueDe, setHistoriqueDe] = useState(null);

  function entrainer(competenceId, libelle, niveaux = null) {
    setCible({ id: competenceId, libelle, niveaux, n: Date.now() });
    setDepuisExercice(false);
    setOnglet("exercice");
  }

  function changerOnglet(nouvel) {
    if (nouvel !== "cours") setDepuisExercice(false);
    if (nouvel !== "historique") setHistoriqueDe(null);
    setOnglet(nouvel);
  }

  function voirHistorique(competenceId) {
    setDepuisExercice(false);
    setHistoriqueDe(competenceId);
    setOnglet("historique");
  }

  function connecter(nouveau) {
    ecrire(CLE_COMPTE, nouveau);
    setCompte(nouveau);
  }

  function deconnecter() {
    ecrire(CLE_COMPTE, null);
    ecrire(CLE_SEANCE, null);
    ecrire(CLE_BILAN, null);
    ecrire(CLE_CIBLE, null);
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
        onChange={changerOnglet}
        options={[
          ["exercice", "S'entraîner"],
          ["cours", "Cours"],
          ["historique", "Mon historique"],
          ["progression", "Ma progression"],
        ]}
      />
      {/* Toujours monté, seulement masqué : aller au cours ne fait pas perdre la question ni sa correction. */}
      <div hidden={onglet !== "exercice"}>
        <Exercice jeton={compte.jeton} onExpire={deconnecter} onVoirCours={voirCours} cible={cible} />
      </div>
      {onglet === "cours" && (
        <Cours
          jeton={compte.jeton}
          onExpire={deconnecter}
          competenceId={leconOuverte}
          onChoisir={(id) => {
            setLeconOuverte(id);
            if (id === null) setDepuisExercice(false);
          }}
          onRetourExercice={depuisExercice ? () => changerOnglet("exercice") : null}
          onEntrainer={entrainer}
          onVoirHistorique={voirHistorique}
        />
      )}
      {onglet === "historique" && (
        <Historique
          jeton={compte.jeton}
          onExpire={deconnecter}
          chemin="/eleves/moi/historique"
          competenceId={historiqueDe}
          onToutVoir={() => setHistoriqueDe(null)}
          onVoirCours={(id) => voirCours(id, { depuisLExercice: false })}
          onEntrainer={entrainer}
        />
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
