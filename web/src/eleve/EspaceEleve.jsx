import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Erreur, Onglets } from "../composants.jsx";
import { libelleNiveauParcours } from "../parcours.js";
import { ecrire, lire } from "../stockage.js";
import { AutresEspaces, RepereEleve } from "../ui/Cadre.jsx";
import Cours from "./Cours.jsx";
import Exercice, { CLE_BILAN, CLE_CIBLE, CLE_SEANCE } from "./Exercice.jsx";
import Historique from "./Historique.jsx";
import Progression from "./Progression.jsx";
import EspaceEnfant, { CLE_ENFANT } from "./EspaceEnfant.jsx";
import PkpMath from "../pkpmath/PkpMath.jsx";
import Remarques from "../ui/Remarques.jsx";

const CLE_COMPTE = "pkp.eleve";

export default function EspaceEleve() {
  // Carte scannée (ou saisie sur la mauvaise page) : c'est peut-être un autre élève sur le même appareil,
  // elle passe avant la session déjà ouverte.
  const [compte, setCompte] = useState(() => (lireCarte() ? null : lire(CLE_COMPTE)));
  // Enfant d'une famille : une seule carte, puis le choix de la matière (PKP Math, Anglais, Français).
  const [enfant, setEnfant] = useState(() => (lireCarte() ? null : lire(CLE_ENFANT)));
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

  function quitterInscription() {
    ecrire(CLE_COMPTE, null);
    ecrire(CLE_SEANCE, null);
    ecrire(CLE_BILAN, null);
    ecrire(CLE_CIBLE, null);
    setCompte(null);
  }

  function deconnecter() {
    quitterInscription();
    ecrire(CLE_ENFANT, null);
    setEnfant(null);
  }

  function connexionCarte(reponse, durable) {
    if (reponse.type === "enfant") {
      const session = { jeton: reponse.jeton, enfant: reponse.enfant, durable };
      ecrire(CLE_ENFANT, session, { durable });
      setEnfant(session);
    } else {
      connecter(reponse.type === "eleve" ? { jeton: reponse.jeton, eleve: reponse.eleve } : reponse, durable);
    }
  }

  if (!compte && enfant)
    return (
      <EspaceEnfant
        session={enfant}
        onOuvrirMaths={(inscription) => connecter(inscription, enfant.durable)}
        onDeconnexion={deconnecter}
      />
    );
  if (!compte) return <ConnexionEleve onConnexion={connexionCarte} />;

  return (
    <>
      <div className="barre-session">
        <p>
          Bonjour <strong>{compte.eleve.prenom}</strong>{" "}
          <span className="doux">
            · {compte.eleve.code_classe}
            {compte.eleve.matiere === "francais"
              ? ` · Français · ${compte.eleve.niveau}`
              : compte.eleve.parcours && ` · ${libelleNiveauParcours(compte.eleve.niveau, compte.eleve.parcours)}`}
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
        {enfant ? (
          <button className="lien" onClick={quitterInscription}>
            ← Mes matières
          </button>
        ) : (
          <button className="lien" onClick={deconnecter}>
            Ce n'est pas moi
          </button>
        )}
      </div>
      <Erreur message={erreurParcours} />
      <Onglets
        valeur={onglet}
        onChange={changerOnglet}
        options={[
          ["exercice", "S'entraîner"],
          ["cours", "Cours"],
          ["pkp", "Fiches et PDF"],
          ["historique", "Mon historique"],
          ["progression", "Ma progression"],
          ["remarques", "Remarques"],
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
      {onglet === "pkp" && (
        <PkpMath
          key={compte.eleve.id}
          jeton={compte.jeton}
          onExpire={deconnecter}
          niveauParDefaut={compte.eleve.niveau}
          intro="Les chapitres ouverts par ton professeur : résumé de cours, cours complet, fiche d'exercices et corrigé, à lire ici ou à exporter en PDF."
        />
      )}
      {onglet === "progression" && <Progression key={compte.eleve.id} jeton={compte.jeton} onExpire={deconnecter} />}
      {onglet === "remarques" && <Remarques jeton={compte.jeton} onExpire={deconnecter} tutoiement />}
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
      if (err.status === 409 && corps.identifiant) {
        // Carte PKP Anglais saisie ici : même connexion directe que son QR code, sur la page élève d'anglais.
        const id = corps.identifiant.trim().toLowerCase();
        const codeCarte = corps.code_personnel.toUpperCase().replace(/[\s-]/g, "");
        window.location.assign(`/anglais/eleve#carte=${id}.${codeCarte}`);
        return;
      }
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
      "/enfants/connexion",
      { identifiant: carte.identifiant, code_personnel: carte.code, rester_connecte: true },
      true,
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function soumettre(e) {
    e.preventDefault();
    if (mode === "identifiant") {
      envoyer(
        "/enfants/connexion",
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
      <RepereEleve matiere="Maths · Anglais · Français" />
      <h1>Connexion élève</h1>
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
      <AutresEspaces />
    </form>
  );
}
