// Issue #217 — Parcours du français au niveau de l'anglais (Claude)
//
// Activité de l'élève sur un dossier de français : quiz corrigé (après chaque question ou à la fin, selon le réglage
// du professeur), auto-évaluation « Je sais » et réponses rédigées relues par le professeur. Le corrigé d'une question
// n'arrive qu'après la réponse, enregistrée par l'API (ARCH-4).
import { useState } from "react";
import { api } from "../api.js";
import { Erreur } from "../composants.jsx";

export const NIVEAUX_AUTO_EVALUATION = [
  ["non_observe", "Pas encore"],
  ["avec_aide", "Avec de l'aide"],
  ["en_cours", "Presque"],
  ["autonome", "Oui !"],
];

const LETTRES = "ABCDEF";

/** Quiz : en mode « après chaque question », chaque réponse est envoyée puis corrigée ; sinon, tout à la fin. */
export function QuizFrancais({ dossier, jeton, onExpire }) {
  const quiz = dossier.eleve.quiz ?? [];
  const parQuestion = dossier.mode_correction === "apres_chaque_question";
  const [reponses, setReponses] = useState(() => quiz.map(() => null));
  const [corrections, setCorrections] = useState(() => quiz.map(() => null));
  const [resultat, setResultat] = useState(null);
  const [erreur, setErreur] = useState(null);

  async function appel(chemin, corps) {
    setErreur(null);
    try {
      return await api(`/francais/eleve/dossiers/${encodeURIComponent(dossier.code)}/${chemin}`, {
        methode: "POST",
        corps,
        jeton,
      });
    } catch (err) {
      if (err.status === 401 && onExpire) onExpire();
      else setErreur(err.message);
      return null;
    }
  }

  async function choisir(i, j) {
    if (resultat || corrections[i]) return;
    setReponses(reponses.map((r, k) => (k === i ? j : r)));
    if (!parQuestion) return;
    const c = await appel(`quiz/${i}`, { reponse: j });
    if (c) {
      setCorrections((cs) => cs.map((x, k) => (k === i ? c : x)));
      setReponses((rs) => rs.map((r, k) => (k === i ? c.choix : r)));
    }
  }

  async function terminer(e) {
    e.preventDefault();
    const r = await appel("corriger", { reponses });
    if (r) {
      setResultat(r);
      setCorrections(r.details);
    }
  }

  function recommencer() {
    setResultat(null);
    setReponses(quiz.map(() => null));
    setCorrections(quiz.map(() => null));
  }

  if (quiz.length === 0) return null;
  return (
    <form className="carte" onSubmit={terminer} aria-labelledby="titre-quiz-francais">
      <h2 id="titre-quiz-francais">Quiz</h2>
      <p className="doux petit">
        {parQuestion
          ? "Chaque réponse est corrigée dès que tu la choisis : ta première réponse compte."
          : "Réponds à toutes les questions : la correction arrive à la fin."}
      </p>
      <ol className="quiz-anglais">
        {quiz.map((q, i) => {
          const c = corrections[i];
          return (
            <li key={i}>
              <fieldset className={c ? (c.juste ? "juste" : "faux") : undefined}>
                <legend>
                  {i + 1}. {q.question} {q.texte && <span className="doux petit">({q.texte})</span>}
                </legend>
                {q.choix.map((choix, j) => (
                  <label key={j}>
                    <input
                      type="radio"
                      name={`quiz-${i}`}
                      checked={reponses[i] === j}
                      disabled={Boolean(resultat || c)}
                      onChange={() => choisir(i, j)}
                    />
                    {LETTRES[j]}) {choix}
                  </label>
                ))}
                {c && (
                  <p className="petit">
                    {c.juste ? "✓ Juste." : `✗ Réponse attendue : ${LETTRES[c.reponse]}) ${q.choix[c.reponse]}.`} {c.explication}
                  </p>
                )}
              </fieldset>
            </li>
          );
        })}
      </ol>
      <Erreur message={erreur} />
      {resultat ? (
        <>
          <p className="succes" role="status">
            Score : {resultat.score}/{resultat.total} · meilleur score : {resultat.meilleur_score}/{resultat.total}
          </p>
          <div className="actions">
            <button type="button" className="secondaire" onClick={recommencer}>
              Recommencer
            </button>
          </div>
        </>
      ) : (
        <div className="actions">
          <button type="submit" disabled={reponses.some((r) => r === null)}>
            {parQuestion ? "Terminer le quiz" : "Voir la correction"}
          </button>
        </div>
      )}
    </form>
  );
}

/** « Je sais… » : un niveau par phrase, comme le « I can » de l'anglais. */
export function AutoEvaluation({ dossier, jeton, onExpire }) {
  const phrases = dossier.eleve.je_sais ?? [];
  const [niveaux, setNiveaux] = useState(() => phrases.map((_, i) => dossier.auto_evaluation?.[i] ?? "non_observe"));
  const [enregistre, setEnregistre] = useState(false);
  const [erreur, setErreur] = useState(null);

  async function enregistrer() {
    setErreur(null);
    try {
      await api(`/francais/eleve/dossiers/${encodeURIComponent(dossier.code)}/auto-evaluation`, {
        methode: "PUT",
        corps: { niveaux },
        jeton,
      });
      setEnregistre(true);
    } catch (err) {
      if (err.status === 401 && onExpire) onExpire();
      else setErreur(err.message);
    }
  }

  if (phrases.length === 0) return null;
  return (
    <div className="carte">
      <h2>Je fais le point</h2>
      {phrases.map((phrase, i) => (
        <div key={phrase}>
          <label htmlFor={`je-sais-${i}`}>{phrase}</label>
          <select
            id={`je-sais-${i}`}
            value={niveaux[i]}
            onChange={(e) => {
              setEnregistre(false);
              setNiveaux(niveaux.map((n, k) => (k === i ? e.target.value : n)));
            }}
          >
            {NIVEAUX_AUTO_EVALUATION.map(([valeur, libelle]) => (
              <option key={valeur} value={valeur}>
                {libelle}
              </option>
            ))}
          </select>
        </div>
      ))}
      <Erreur message={erreur} />
      <div className="actions">
        <button className="secondaire" onClick={enregistrer}>
          Enregistrer
        </button>
        {enregistre && (
          <span className="succes" role="status">
            Enregistré
          </span>
        )}
      </div>
    </div>
  );
}

const ETATS = { brouillon: "Brouillon", remise: "Remise : en attente du retour", corrigee: "Retour du professeur reçu" };

/** Réponses rédigées : brouillon, remise, retour du professeur, puis réécriture (règles RGPD-2). */
export function ReponsesRedigees({ dossier, jeton, onExpire }) {
  const [reponses, setReponses] = useState(() => Object.fromEntries((dossier.reponses ?? []).map((r) => [r.question, r])));
  const [textes, setTextes] = useState(() => Object.fromEntries((dossier.reponses ?? []).map((r) => [r.question, r.texte])));
  const [erreur, setErreur] = useState(null);

  async function envoyer(question, remise) {
    setErreur(null);
    const base = `/francais/eleve/dossiers/${encodeURIComponent(dossier.code)}/reponses/${question}`;
    try {
      let r = await api(base, { methode: "PUT", corps: { texte: textes[question] ?? "" }, jeton });
      if (remise) r = await api(`${base}/remise`, { methode: "POST", jeton });
      setReponses((rs) => ({ ...rs, [question]: r }));
    } catch (err) {
      if (err.status === 401 && onExpire) onExpire();
      else setErreur(err.message);
    }
  }

  if (!dossier.saisie_ouverte) {
    return <p className="doux petit">Réponds aux questions dans ton cahier : ton professeur te fera un retour.</p>;
  }
  return (
    <div className="carte">
      <h2>Mes réponses rédigées</h2>
      <p className="doux petit">Ton professeur lit tes réponses une fois remises. Tes brouillons ne sont visibles que de toi.</p>
      <Erreur message={erreur} />
      {dossier.eleve.questions.map((q) => {
        const r = reponses[q.code];
        const remise = r?.statut === "remise";
        return (
          <div key={q.code} className="reponse-redigee">
            <label htmlFor={`reponse-${q.code}`}>
              <strong>{q.code}.</strong> {q.consigne}
            </label>
            {r && <p className="doux petit">{ETATS[r.statut]}</p>}
            {r?.commentaire && (
              <p className="succes petit" role="status">
                Retour du professeur : {r.commentaire}
              </p>
            )}
            <textarea
              id={`reponse-${q.code}`}
              rows={4}
              maxLength={5000}
              disabled={remise}
              value={textes[q.code] ?? ""}
              onChange={(e) => setTextes((t) => ({ ...t, [q.code]: e.target.value }))}
            />
            {!remise && (
              <div className="actions">
                <button type="button" className="secondaire" onClick={() => envoyer(q.code, false)}>
                  Enregistrer le brouillon
                </button>
                <button type="button" disabled={!(textes[q.code] ?? "").trim()} onClick={() => envoyer(q.code, true)}>
                  Remettre
                </button>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
