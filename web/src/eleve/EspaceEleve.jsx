import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Erreur, Onglets } from "../composants.jsx";
import { libelleNiveauParcours } from "../parcours.js";
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
  const [ancreLecon, setAncreLecon] = useState(null); // section à montrer : « lecon-cours », « methode-2 »…
  // Leçon ouverte depuis un exercice : la leçon propose d'y revenir, l'exercice n'est pas perdu.
  const [depuisExercice, setDepuisExercice] = useState(false);
  // Demande d'entrainement ciblé, depuis une leçon ou l'historique : { id, libelle, n }.
  const [cible, setCible] = useState(null);

  function voirCours(competenceId, { depuisLExercice = true, ancre = null } = {}) {
    setLeconOuverte(competenceId);
    setAncreLecon(ancre);
    setDepuisExercice(depuisLExercice);
    setOnglet("cours");
  }

  // Inscriptions reliées par le professeur (spécialité, mise à niveau, excellence…) : l'élève change de parcours ici.
  const [mesParcours, setMesParcours] = useState([]);
  const [erreurParcours, setErreurParcours] = useState(null);
  useEffect(() => {
    if (!compte) return setMesParcours([]);
    api("/eleves/moi/parcours", { jeton: compte.jeton }).then(setMesParcours, () => setMesParcours([]));
  }, [compte]);

  async function changerParcours(eleveId) {
    try {
      const nouveau = await api(`/eleves/moi/parcours/${eleveId}`, { methode: "POST", jeton: compte.jeton });
      // La séance en cours appartient à l'autre parcours : on repart de l'accueil du nouveau.
      ecrire(CLE_SEANCE, null);
      ecrire(CLE_BILAN, null);
      ecrire(CLE_CIBLE, null);
      setCible(null);
      setLeconOuverte(null);
      setHistoriqueDe(null);
      setOnglet("exercice");
      setErreurParcours(null);
      connecter(nouveau);
    } catch (err) {
      setErreurParcours(err.message);
    }
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

  function connecter(nouveau, durable = compte?.durable ?? false) {
    const avecDuree = { ...nouveau, durable };
    ecrire(CLE_COMPTE, avecDuree, { durable });
    setCompte(avecDuree);
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
          Bonjour <strong>{compte.eleve.prenom}</strong>{" "}
          <span className="doux">
            · {compte.eleve.code_classe}
            {compte.eleve.parcours && ` · ${libelleNiveauParcours(compte.eleve.niveau, compte.eleve.parcours)}`}
          </span>
        </p>
        {mesParcours.length > 1 && (
          <div className="choix-parcours">
            <label htmlFor="mon-parcours">Mon parcours</label>
            <select id="mon-parcours" value={compte.eleve.id} onChange={(e) => changerParcours(Number(e.target.value))}>
              {mesParcours.map((p) => (
                <option key={p.eleve_id} value={p.eleve_id}>
                  {libelleNiveauParcours(p.niveau, p.parcours)} ({p.code_classe})
                </option>
              ))}
            </select>
          </div>
        )}
        <button className="lien" onClick={deconnecter}>
          Ce n'est pas moi
        </button>
      </div>
      <Erreur message={erreurParcours} />
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
        <Exercice key={compte.eleve.id} jeton={compte.jeton} onExpire={deconnecter} onVoirCours={voirCours} cible={cible} />
      </div>
      {onglet === "cours" && (
        <Cours
          key={compte.eleve.id}
          jeton={compte.jeton}
          onExpire={deconnecter}
          competenceId={leconOuverte}
          ancre={ancreLecon}
          onChoisir={(id) => {
            setLeconOuverte(id);
            setAncreLecon(null);
            if (id === null) setDepuisExercice(false);
          }}
          onRetourExercice={depuisExercice ? () => changerOnglet("exercice") : null}
          onEntrainer={entrainer}
          onVoirHistorique={voirHistorique}
        />
      )}
      {onglet === "historique" && (
        <Historique
          key={compte.eleve.id}
          jeton={compte.jeton}
          onExpire={deconnecter}
          chemin="/eleves/moi/historique"
          competenceId={historiqueDe}
          onToutVoir={() => setHistoriqueDe(null)}
          onVoirCours={(id) => voirCours(id, { depuisLExercice: false })}
          onEntrainer={entrainer}
        />
      )}
      {onglet === "progression" && <Progression key={compte.eleve.id} jeton={compte.jeton} onExpire={deconnecter} />}
    </>
  );
}

/** Contenu du QR code de la carte élève : « /eleve#carte=identifiant.code ».
 * Le fragment (#…) n'est jamais envoyé au serveur ni conservé dans ses journaux. */
export function lireCarte(fragment = window.location.hash) {
  const m = /^#carte=([a-z0-9-]+)\.([A-Za-z0-9]+)$/.exec(fragment || "");
  return m ? { identifiant: m[1], code: m[2] } : null;
}

export function ConnexionEleve({ onConnexion }) {
  const carte = lireCarte();
  const [mode, setMode] = useState("identifiant");
  const [identifiant, setIdentifiant] = useState(carte?.identifiant ?? "");
  const [prenom, setPrenom] = useState("");
  const [code, setCode] = useState("");
  const [codePersonnel, setCodePersonnel] = useState(carte?.code ?? "");
  // QR code scanné : c'est le téléphone ou la tablette de l'élève, on garde la session.
  const [resterConnecte, setResterConnecte] = useState(Boolean(carte));
  const [erreur, setErreur] = useState(null);
  const [envoi, setEnvoi] = useState(false);

  async function envoyer(chemin, corps, durable) {
    setErreur(null);
    setEnvoi(true);
    try {
      onConnexion(await api(chemin, { methode: "POST", corps }), durable);
    } catch (err) {
      setErreur(
        err.status === 401
          ? `${err.message} Vérifie ${mode === "identifiant" ? "ta carte" : "avec ton professeur"}.`
          : err.message,
      );
      setCodePersonnel("");
    } finally {
      setEnvoi(false);
    }
  }

  // Arrivée par le QR code : on efface le code de la barre d'adresse et on se connecte directement.
  useEffect(() => {
    if (!carte) return;
    window.history.replaceState(null, "", window.location.pathname);
    envoyer(
      "/eleves/connexion/identifiant",
      { identifiant: carte.identifiant, code_personnel: carte.code, rester_connecte: true },
      true,
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function soumettre(e) {
    e.preventDefault();
    if (mode === "identifiant") {
      envoyer(
        "/eleves/connexion/identifiant",
        { identifiant, code_personnel: codePersonnel, rester_connecte: resterConnecte },
        resterConnecte,
      );
    } else {
      envoyer("/eleves/connexion", { prenom, code_classe: code, code_personnel: codePersonnel }, false);
    }
  }

  const complet =
    codePersonnel.trim() && (mode === "identifiant" ? identifiant.trim() : prenom.trim() && code.trim());

  return (
    <form className="carte carte-etroite" onSubmit={soumettre}>
      <h1>Bienvenue</h1>
      {mode === "identifiant" ? (
        <>
          <p className="doux">Entre l'identifiant et le code personnel inscrits sur ta carte, ou scanne son QR code.</p>
          <label htmlFor="identifiant">Identifiant</label>
          <input
            id="identifiant"
            value={identifiant}
            onChange={(e) => setIdentifiant(e.target.value.toLowerCase())}
            placeholder="ex. lina-k7m4"
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            maxLength={40}
            required
          />
        </>
      ) : (
        <>
          <p className="doux">Entre ton prénom, le code de ta classe et ton code personnel, donnés par ton professeur.</p>
          <label htmlFor="prenom">Prénom</label>
          <input id="prenom" value={prenom} onChange={(e) => setPrenom(e.target.value)} autoComplete="given-name" maxLength={50} required />
          <label htmlFor="code">Code classe</label>
          <input
            id="code"
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
            placeholder="ex. 1RE-SPE-7KQ4M"
            autoComplete="off"
            spellCheck={false}
            maxLength={20}
            required
          />
        </>
      )}
      <label htmlFor="code-personnel">Code personnel</label>
      <input
        id="code-personnel"
        type="password"
        value={codePersonnel}
        onChange={(e) => setCodePersonnel(e.target.value.toUpperCase())}
        placeholder="6 caractères"
        autoComplete="current-password"
        spellCheck={false}
        maxLength={20}
        required
      />
      <p className="aide">Ne le donne à personne : il protège ton compte.</p>
      {mode === "identifiant" && (
        <label className="case">
          <input type="checkbox" checked={resterConnecte} onChange={(e) => setResterConnecte(e.target.checked)} />
          Rester connecté sur cet appareil (30 jours). À ne pas cocher sur un ordinateur du lycée.
        </label>
      )}
      <Erreur message={erreur} />
      <div className="actions">
        <button type="submit" disabled={envoi || !complet}>
          {envoi ? "Connexion…" : "Commencer"}
        </button>
      </div>
      <p className="aide">
        {mode === "identifiant" ? (
          <button type="button" className="lien" onClick={() => setMode("classe")}>
            Je n'ai pas de carte : me connecter avec mon prénom et le code de ma classe
          </button>
        ) : (
          <button type="button" className="lien" onClick={() => setMode("identifiant")}>
            Me connecter avec l'identifiant de ma carte
          </button>
        )}
      </p>
      <p className="aide">Seuls ton prénom et ta classe sont enregistrés.</p>
    </form>
  );
}
