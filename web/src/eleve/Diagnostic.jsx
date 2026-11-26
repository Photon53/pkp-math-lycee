// Issue #162 — Diagnostic des acquis antérieurs, lot 3 : passation (Claude)
import { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";
import { Erreur } from "../composants.jsx";
import { Maths } from "../maths.jsx";
import { decouperQcm } from "./Exercice.jsx";

const AIDE = {
  numerique: "Écris 1/2, 0,5 ou -3.",
  expression: "Écris x^2 ou x², 2x pour 2×x.",
  texte: "Écris ta réponse en toutes lettres.",
  redaction: "Explique ta démarche en quelques phrases : ton professeur lira ta réponse.",
};

/** Le diagnostic, côté élève : une question à la fois, sans correction ni note (#162).
 * « Je ne sais pas » est une vraie réponse, distincte d'une erreur. */
export default function Diagnostic({ jeton, onExpire }) {
  const [etat, setEtat] = useState(null); // { statut, nb_reponses }
  const [question, setQuestion] = useState(null);
  const [saisie, setSaisie] = useState("");
  const [cochees, setCochees] = useState(new Set());
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState(null);

  const appeler = useCallback(
    async (chemin, options = {}) => {
      try {
        return await api(chemin, { ...options, jeton });
      } catch (err) {
        if (err.status === 401) onExpire();
        throw err;
      }
    },
    // onExpire change à chaque rendu du parent : ne pas recréer la fonction pour autant.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [jeton],
  );

  const chargerQuestion = useCallback(async () => {
    setSaisie("");
    setCochees(new Set());
    const q = await appeler("/eleves/moi/diagnostic/question");
    if (q === null) {
      setQuestion(null);
      setEtat(await appeler("/eleves/moi/diagnostic"));
    } else {
      setQuestion(q);
    }
  }, [appeler]);

  useEffect(() => {
    appeler("/eleves/moi/diagnostic").then(setEtat, (err) => setErreur(err.message));
  }, [appeler]);

  async function commencer() {
    setErreur(null);
    try {
      setEtat(await appeler("/eleves/moi/diagnostic", { methode: "POST" }));
      await chargerQuestion();
    } catch (err) {
      setErreur(err.message);
    }
  }

  async function envoyer(reponse, neSaitPas = false) {
    setEnvoi(true);
    setErreur(null);
    try {
      await appeler("/eleves/moi/diagnostic/reponses", {
        methode: "POST",
        corps: { question_id: question.id, reponse_donnee: neSaitPas ? null : reponse, ne_sait_pas: neSaitPas },
      });
      await chargerQuestion();
    } catch (err) {
      setErreur(err.message);
    } finally {
      setEnvoi(false);
    }
  }

  if (etat === null) return erreur ? <Erreur message={erreur} /> : <p className="doux">Chargement…</p>;

  if (etat.statut === "termine") {
    return (
      <section className="carte">
        <h2>Diagnostic terminé</h2>
        <p>Merci ! Tes réponses sont enregistrées. Ton professeur s'en servira pour savoir quelles bases revoir avec toi.</p>
        <p className="doux">Ce diagnostic n'est pas noté et ne change pas ta progression.</p>
      </section>
    );
  }

  if (etat.statut === "ferme" || etat.statut === "indisponible") {
    return (
      <section className="carte">
        <h2>Diagnostic</h2>
        <p className="doux">Le diagnostic n'est pas encore ouvert pour ta classe.</p>
      </section>
    );
  }

  if (!question) {
    return (
      <section className="carte">
        <h2>Diagnostic de rentrée</h2>
        <p>
          Quelques questions sur ce que tu as appris les années précédentes, pour savoir quelles bases revoir. Ce n'est
          pas une note et cela ne change pas ta progression.
        </p>
        <ul>
          <li>Une question à la fois ; tu ne vois pas la correction.</li>
          <li>Tu peux utiliser un brouillon. Compte environ 25 à 35 minutes, sans te presser.</li>
          <li>Si tu ne sais pas, dis-le avec « Je ne sais pas » : c'est utile à ton professeur.</li>
        </ul>
        <Erreur message={erreur} />
        <div className="actions">
          <button onClick={commencer}>{etat.statut === "en-cours" ? "Reprendre le diagnostic" : "Commencer le diagnostic"}</button>
        </div>
      </section>
    );
  }

  const multiple = question.type === "choix_multiples";
  const { intitule, options } =
    question.type === "qcm" || multiple ? decouperQcm(question.enonce) : { intitule: question.enonce, options: null };

  function basculer(lettre) {
    setCochees((avant) => {
      const apres = new Set(avant);
      apres.has(lettre) ? apres.delete(lettre) : apres.add(lettre);
      return apres;
    });
  }

  return (
    <article className="carte">
      <p className="doux">Question {question.numero}</p>
      <p className="enonce">
        <Maths enLigne texte={intitule} />
      </p>
      {options && !multiple && (
        <div className="options">
          {options.map((o) => (
            <button key={o.lettre} onClick={() => envoyer(o.lettre)} disabled={envoi}>
              <span className="lettre">{o.lettre}</span>
              <Maths enLigne texte={o.texte} />
            </button>
          ))}
        </div>
      )}
      {options && multiple && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            envoyer([...cochees].sort().join(""));
          }}
        >
          <fieldset className="choix-chapitres">
            <legend>Coche toutes les bonnes réponses</legend>
            {options.map((o) => (
              <label key={o.lettre} className="case">
                <input type="checkbox" checked={cochees.has(o.lettre)} onChange={() => basculer(o.lettre)} />
                <span className="lettre">{o.lettre}</span> <Maths enLigne texte={o.texte} />
              </label>
            ))}
          </fieldset>
          <div className="actions">
            <button type="submit" disabled={envoi || cochees.size === 0}>
              Valider
            </button>
          </div>
        </form>
      )}
      {!options && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (saisie.trim()) envoyer(saisie);
          }}
        >
          <label htmlFor="saisie-diagnostic">Ta réponse</label>
          {question.type === "redaction" ? (
            <textarea id="saisie-diagnostic" rows={6} maxLength={4000} value={saisie} onChange={(e) => setSaisie(e.target.value)} />
          ) : (
            <input
              id="saisie-diagnostic"
              value={saisie}
              onChange={(e) => setSaisie(e.target.value)}
              autoComplete="off"
              spellCheck={false}
              maxLength={200}
            />
          )}
          {AIDE[question.type] && <p className="aide">{AIDE[question.type]}</p>}
          <div className="actions">
            <button type="submit" disabled={envoi || !saisie.trim()}>
              Valider
            </button>
          </div>
        </form>
      )}
      <div className="actions">
        <button className="secondaire" onClick={() => envoyer(null, true)} disabled={envoi}>
          Je ne sais pas
        </button>
      </div>
      <Erreur message={erreur} />
    </article>
  );
}
