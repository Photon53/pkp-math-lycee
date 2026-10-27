import { useState } from "react";
import { api } from "../api.js";
import { Erreur, Onglets } from "../composants.jsx";
import { ecrire, lire } from "../stockage.js";
import Classes from "./Classes.jsx";
import Questions from "./Questions.jsx";

const CLE_COMPTE = "pkp.enseignant";

export default function EspaceEnseignant() {
  const [compte, setCompte] = useState(() => lire(CLE_COMPTE));
  const [onglet, setOnglet] = useState("classes");

  function connecter(nouveau) {
    ecrire(CLE_COMPTE, nouveau);
    setCompte(nouveau);
  }

  function deconnecter() {
    ecrire(CLE_COMPTE, null);
    setCompte(null);
  }

  if (!compte) return <ConnexionEnseignant onConnexion={connecter} />;

  return (
    <>
      <div className="barre-session">
        <h1>Espace enseignant</h1>
        <p>
          {compte.nom}{" "}
          <button className="lien" onClick={deconnecter}>
            Se déconnecter
          </button>
        </p>
      </div>
      <Onglets
        valeur={onglet}
        onChange={setOnglet}
        options={[
          ["classes", "Classes et élèves"],
          ["questions", "Banque de questions"],
        ]}
      />
      {onglet === "classes" ? (
        <Classes jeton={compte.jeton} onExpire={deconnecter} />
      ) : (
        <Questions jeton={compte.jeton} onExpire={deconnecter} />
      )}
    </>
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
      <h1>Connexion enseignant</h1>
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
