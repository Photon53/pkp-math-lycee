import { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";
import { Erreur } from "../composants.jsx";
import { lireCarte } from "../eleve/EspaceEleve.jsx";
import { ecrire, lire } from "../stockage.js";
import { Cahier } from "./SeancesAnglais.jsx";

const CLE_COMPTE = "pkp.eleve.anglais";
const NIVEAUX_I_CAN = [
  ["non_observe", "Not yet"],
  ["avec_aide", "With help"],
  ["en_cours", "Almost"],
  ["autonome", "Yes!"],
];

/** Espace élève PKP Anglais : séances validées de son niveau, quiz corrigé tout de suite, « I can ». */
export default function EspaceEleveAnglais() {
  const [compte, setCompte] = useState(() => lire(CLE_COMPTE));

  function connecter(nouveau, durable) {
    ecrire(CLE_COMPTE, nouveau, { durable });
    setCompte(nouveau);
  }

  const deconnecter = useCallback(() => {
    ecrire(CLE_COMPTE, null);
    setCompte(null);
  }, []);

  if (!compte) return <ConnexionEleveAnglais onConnexion={connecter} />;
  return <MesSeances compte={compte} onDeconnexion={deconnecter} />;
}

function ConnexionEleveAnglais({ onConnexion }) {
  const carte = lireCarte();
  const [identifiant, setIdentifiant] = useState(carte?.identifiant ?? "");
  const [code, setCode] = useState(carte?.code ?? "");
  const [resterConnecte, setResterConnecte] = useState(Boolean(carte));
  const [erreur, setErreur] = useState(null);
  const [envoi, setEnvoi] = useState(false);

  async function envoyer(corps, durable) {
    setErreur(null);
    setEnvoi(true);
    try {
      onConnexion(await api("/anglais/eleve/connexion", { methode: "POST", corps }), durable);
    } catch (err) {
      setErreur(err.status === 401 ? `${err.message} Vérifie ta carte.` : err.message);
      setCode("");
    } finally {
      setEnvoi(false);
    }
  }

  // Arrivée par le QR code : le code quitte la barre d'adresse et l'élève est connecté directement.
  useEffect(() => {
    if (!carte) return;
    window.history.replaceState(null, "", window.location.pathname);
    envoyer({ identifiant: carte.identifiant, code_personnel: carte.code, rester_connecte: true }, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function soumettre(e) {
    e.preventDefault();
    envoyer({ identifiant, code_personnel: code, rester_connecte: resterConnecte }, resterConnecte);
  }

  return (
    <form className="carte carte-etroite" onSubmit={soumettre}>
      <h1>PKP Anglais</h1>
      <p className="doux">Entre l'identifiant et le code personnel de ta carte d'anglais, ou scanne son QR code.</p>
      <label htmlFor="identifiant-anglais">Identifiant</label>
      <input
        id="identifiant-anglais"
        value={identifiant}
        onChange={(e) => setIdentifiant(e.target.value.toLowerCase())}
        placeholder="ex. lina-k7m4"
        autoComplete="username"
        autoCapitalize="none"
        spellCheck={false}
        maxLength={40}
        required
      />
      <label htmlFor="code-anglais">Code personnel</label>
      <input
        id="code-anglais"
        type="password"
        value={code}
        onChange={(e) => setCode(e.target.value.toUpperCase())}
        placeholder="6 caractères"
        autoComplete="current-password"
        spellCheck={false}
        maxLength={20}
        required
      />
      <label className="case">
        <input type="checkbox" checked={resterConnecte} onChange={(e) => setResterConnecte(e.target.checked)} />
        Rester connecté sur cet appareil (30 jours). À ne pas cocher sur un ordinateur du collège.
      </label>
      <Erreur message={erreur} />
      <div className="actions">
        <button type="submit" disabled={envoi || !identifiant.trim() || !code.trim()}>
          {envoi ? "Connexion…" : "Let's go!"}
        </button>
      </div>
    </form>
  );
}

function MesSeances({ compte, onDeconnexion }) {
  const [seances, setSeances] = useState(null);
  const [code, setCode] = useState(null);
  const [erreur, setErreur] = useState(null);

  const appeler = useCallback(
    async (chemin, options = {}) => {
      try {
        return await api(chemin, { ...options, jeton: compte.jeton });
      } catch (err) {
        if (err.status === 401) onDeconnexion();
        setErreur(err.message);
        throw err;
      }
    },
    [compte.jeton, onDeconnexion],
  );

  const charger = useCallback(() => appeler("/anglais/eleve/seances").then(setSeances, () => {}), [appeler]);

  useEffect(() => {
    charger();
  }, [charger]);

  if (code) {
    return (
      <SeanceEleve
        code={code}
        appeler={appeler}
        onRetour={() => {
          setCode(null);
          charger();
        }}
      />
    );
  }

  return (
    <section>
      <div className="carte">
        <h1>Hello {compte.eleve.prenom}!</h1>
        <p className="doux">
          Anglais {compte.eleve.niveau} · groupe {compte.eleve.groupe}
        </p>
        <button className="lien" onClick={onDeconnexion}>
          Se déconnecter
        </button>
      </div>
      <Erreur message={erreur} />
      {seances === null ? (
        <p className="doux">Chargement…</p>
      ) : seances.length === 0 ? (
        <p className="carte doux">Aucune séance ouverte pour l'instant : ton professeur les ouvre au fil de l'année.</p>
      ) : (
        <ul className="grille-classes" aria-label="Mes séances">
          {seances.map((s) => (
            <li key={s.code}>
              <button className="classe" onClick={() => setCode(s.code)}>
                <span className="code">
                  {s.code} · {s.titre}
                </span>
                <span className="doux">
                  {s.score === null ? "Quiz à faire" : `Meilleur score : ${s.score}/${s.total}`}
                  {s.i_can.length > 0 && ` · I can : ${s.i_can.filter((n) => n === "autonome").length}/${s.can_do.length}`}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function SeanceEleve({ code, appeler, onRetour }) {
  const [seance, setSeance] = useState(null);
  const [reponses, setReponses] = useState([]);
  const [resultat, setResultat] = useState(null);
  const [iCan, setICan] = useState([]);
  const [enregistre, setEnregistre] = useState(false);

  useEffect(() => {
    appeler(`/anglais/eleve/seances/${encodeURIComponent(code)}`).then((s) => {
      setSeance(s);
      setReponses(s.quiz.map(() => null));
      setICan(s.cahier.can_do.map((_, i) => s.i_can[i] ?? "non_observe"));
    }, () => {});
  }, [appeler, code]);

  if (!seance) return <p className="doux">Chargement…</p>;

  async function corriger(e) {
    e.preventDefault();
    try {
      setResultat(await appeler(`/anglais/eleve/seances/${code}/corriger`, { methode: "POST", corps: { reponses } }));
    } catch {
      // erreur affichée par la liste
    }
  }

  async function enregistrerICan() {
    try {
      await appeler(`/anglais/eleve/seances/${code}/i-can`, { methode: "PUT", corps: { i_can: iCan } });
      setEnregistre(true);
    } catch {
      // erreur affichée par la liste
    }
  }

  function recommencer() {
    setResultat(null);
    setReponses(seance.quiz.map(() => null));
  }

  return (
    <section>
      <div className="actions">
        <button className="secondaire" onClick={onRetour}>
          ← Mes séances
        </button>
      </div>
      <div className="carte">
        <h1>{seance.titre}</h1>
        <p className="anglais-accroche">{seance.cahier.hook}</p>
        <p>
          <strong>Goal:</strong> {seance.objectif}
        </p>
      </div>

      <Cahier cahier={seance.cahier} fiches={seance.fiches} />

      <form className="carte" onSubmit={corriger}>
        <h2>Quiz</h2>
        <ol className="quiz-anglais">
          {seance.quiz.map((q, i) => {
            const detail = resultat?.details[i];
            return (
              <li key={i}>
                <fieldset className={detail ? (detail.juste ? "juste" : "faux") : undefined}>
                  <legend>
                    {i + 1}. {q.question}
                  </legend>
                  {q.choix.map((c, j) => (
                    <label key={j}>
                      <input
                        type="radio"
                        name={`q${i}`}
                        checked={reponses[i] === j}
                        disabled={Boolean(resultat)}
                        onChange={() => setReponses(reponses.map((r, k) => (k === i ? j : r)))}
                      />
                      {c}
                    </label>
                  ))}
                  {detail && (
                    <p className="petit">
                      {detail.juste ? "✓ Right!" : `✗ Answer: ${q.choix[detail.reponse]}.`} {detail.explication}
                    </p>
                  )}
                </fieldset>
              </li>
            );
          })}
        </ol>
        {resultat ? (
          <>
            <p className="succes" role="status">
              Score : {resultat.score}/{resultat.total} · meilleur score : {resultat.meilleur_score}/{resultat.total}
            </p>
            <h3>Correction des exercices ouverts</h3>
            <p className="doux">Compare avec ce que tu as écrit dans ton cahier.</p>
            <ol>
              {seance.cahier.practice.map((p, i) => (
                <li key={i}>
                  {p} <strong>→ {resultat.practice_answers[i]}</strong>
                </li>
              ))}
            </ol>
            <h4>Listen and watch</h4>
            <ol>
              {seance.cahier.listening.questions.map((q, i) => (
                <li key={i}>
                  {q} <strong>→ {resultat.listening_answers[i]}</strong>
                </li>
              ))}
            </ol>
            <div className="actions">
              <button type="button" className="secondaire" onClick={recommencer}>
                Try again
              </button>
            </div>
          </>
        ) : (
          <div className="actions">
            <button type="submit" disabled={reponses.some((r) => r === null)}>
              Check my answers
            </button>
          </div>
        )}
      </form>

      <div className="carte">
        <h2>Check yourself - I can...</h2>
        {seance.cahier.can_do.map((phrase, i) => (
          <div key={phrase}>
            <label htmlFor={`ican-${i}`}>{phrase}</label>
            <select
              id={`ican-${i}`}
              value={iCan[i]}
              onChange={(e) => {
                setEnregistre(false);
                setICan(iCan.map((n, k) => (k === i ? e.target.value : n)));
              }}
            >
              {NIVEAUX_I_CAN.map(([valeur, libelle]) => (
                <option key={valeur} value={valeur}>
                  {libelle}
                </option>
              ))}
            </select>
          </div>
        ))}
        <div className="actions">
          <button className="secondaire" onClick={enregistrerICan}>
            Save
          </button>
          {enregistre && (
            <span className="succes" role="status">
              Saved!
            </span>
          )}
        </div>
      </div>
    </section>
  );
}
