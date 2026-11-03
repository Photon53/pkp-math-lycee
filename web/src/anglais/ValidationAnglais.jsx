import { useCallback, useEffect, useState } from "react";
import { Erreur } from "../composants.jsx";
import { useApi } from "../enseignant/useApi.js";
import { Cahier, telecharger } from "./SeancesAnglais.jsx";

export const STATUTS = {
  brouillon: "Brouillon",
  soumis: "Soumis à validation",
  valide: "Validé",
  refuse: "Refusé",
  archive: "Archivé",
};

export function StatutSeance({ statut }) {
  return <span className={`statut-anglais ${statut}`}>{STATUTS[statut] ?? statut}</span>;
}

const date = (iso) => (iso ? new Date(iso).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" }) : "");

/** Versions successives d'une séance : qui l'a écrite, qui l'a validée ou refusée, et pourquoi. */
export function Historique({ versions }) {
  return (
    <div className="tableau-defilant">
      <table>
        <caption className="visuellement-cache">Historique des versions</caption>
        <thead>
          <tr>
            <th>Version</th>
            <th>Statut</th>
            <th>Auteur</th>
            <th>Décision</th>
          </tr>
        </thead>
        <tbody>
          {versions.map((v) => (
            <tr key={v.numero}>
              <td>v{v.numero}</td>
              <td>
                <StatutSeance statut={v.statut} />
              </td>
              <td>
                {v.auteur} <span className="doux petit">{date(v.cree_le)}</span>
              </td>
              <td>
                {v.validateur && (
                  <>
                    {v.validateur} <span className="doux petit">{date(v.decide_le)}</span>
                  </>
                )}
                {v.motif_refus && <p className="petit">Motif : {v.motif_refus}</p>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Valider ou refuser (motif obligatoire) ; `interdit` explique pourquoi la décision n'est pas possible. */
export function Decision({ interdit, onValider, onRefuser }) {
  const [motif, setMotif] = useState("");
  if (interdit) return <p className="doux">{interdit}</p>;
  return (
    <div>
      <div className="actions">
        <button onClick={onValider}>Valider cette version</button>
      </div>
      <label htmlFor="motif-refus">Motif du refus (obligatoire pour refuser)</label>
      <textarea id="motif-refus" rows={3} value={motif} maxLength={2000} onChange={(e) => setMotif(e.target.value)} />
      <div className="actions">
        <button className="danger" disabled={!motif.trim()} onClick={() => onRefuser(motif.trim())}>
          Refuser
        </button>
      </div>
    </div>
  );
}

/** Tout ce que la version contient : le cahier avec ses réponses, le quiz corrigé et le déroulé animateur. */
export function ApercuVersion({ seance }) {
  return (
    <>
      <Cahier cahier={seance.cahier} fiches={seance.fiches} />
      <article className="carte anglais-rubrique">
        <h3>Quiz de l'élève (corrigé immédiatement)</h3>
        <ol>
          {seance.quiz.map((q, i) => (
            <li key={i}>
              {q.question}{" "}
              <span className="doux">
                ({q.choix.map((c, j) => (j === q.reponse ? `✓ ${c}` : c)).join(" / ")})
              </span>
            </li>
          ))}
        </ol>
      </article>
      <h3>Déroulé des 90 minutes</h3>
      {seance.etapes.map((etape, i) => (
        <article className="carte" key={i}>
          <h4>
            {i + 1}. {etape.titre} ({etape.duree_minutes} min)
          </h4>
          <p>
            <strong>Élève :</strong> {etape.consigne_eleve}
          </p>
          <p>
            <strong>Animateur :</strong> {etape.consigne_animateur}
          </p>
        </article>
      ))}
    </>
  );
}

/** Page du professeur référent : séances soumises, à valider ou refuser (jamais les siennes). */
export default function ValidationAnglais({ jeton, onExpire }) {
  const { appeler, erreur, setErreur } = useApi(jeton, onExpire);
  const [liste, setListe] = useState(null);
  const [code, setCode] = useState(null);
  const [seance, setSeance] = useState(null);
  const [message, setMessage] = useState(null);

  const charger = useCallback(() => appeler("/anglais/validation").then(setListe, () => {}), [appeler]);

  useEffect(() => {
    charger();
  }, [charger]);

  useEffect(() => {
    setSeance(null);
    if (code) appeler(`/anglais/validation/${encodeURIComponent(code)}`).then(setSeance, () => {});
  }, [appeler, code]);

  async function decider(chemin, corps, texte) {
    setMessage(null);
    try {
      await appeler(`/anglais/validation/${code}/${chemin}`, { methode: "POST", corps });
      setMessage(texte);
      setCode(null);
      await charger();
    } catch {
      // erreur déjà affichée
    }
  }

  async function pdf(publicCible) {
    setErreur(null);
    try {
      await telecharger(code, publicCible, jeton, "/anglais/validation");
    } catch (err) {
      setErreur(err.message);
    }
  }

  const choisie = liste?.find((s) => s.code === code);

  return (
    <section>
      <div className="carte">
        <p className="doux">
          Séances soumises par un administrateur ou importées du dépôt. Une fois validée, une séance est ouverte aux élèves de son
          niveau et ses PDF perdent la mention NON VALIDÉ. Vous ne pouvez pas valider un contenu dont vous êtes l'auteur.
        </p>
        {message && (
          <p className="succes" role="status">
            {message}
          </p>
        )}
        <Erreur message={erreur} />
        {liste === null && <p className="doux">Chargement…</p>}
        {liste?.length === 0 && <p className="doux">Aucune séance en attente de validation.</p>}
        {liste?.length > 0 && (
          <>
            <label htmlFor="seance-a-valider">Séance à relire ({liste.length} en attente)</label>
            <select id="seance-a-valider" value={code ?? ""} onChange={(e) => setCode(e.target.value || null)}>
              <option value="">Choisir…</option>
              {liste.map((s) => (
                <option key={s.code} value={s.code}>
                  {s.code} · {s.titre} · v{s.version}
                  {s.est_auteur ? " (vous en êtes l'auteur)" : ""}
                </option>
              ))}
            </select>
          </>
        )}
      </div>
      {seance && choisie && (
        <>
          <div className="carte">
            <h2>
              {choisie.code} · {seance.titre} <StatutSeance statut={seance.statut} />
            </h2>
            <p>
              <strong>Objectif :</strong> {seance.objectif}
            </p>
            <p className="doux">
              Version {seance.version} · auteur : {choisie.auteur ?? "import du dépôt"}
              {choisie.version_publiee ? ` · version publiée actuellement : v${choisie.version_publiee}` : " · jamais publiée"}
            </p>
            <div className="actions">
              <button className="secondaire" onClick={() => pdf("eleve")}>
                PDF élève
              </button>
              <button className="secondaire" onClick={() => pdf("animateur")}>
                PDF animateur
              </button>
            </div>
            <Decision
              interdit={choisie.est_auteur && "Vous êtes l'auteur de cette version : un autre référent doit la valider."}
              onValider={() => decider("valider", undefined, `${choisie.code} validée : elle est ouverte aux élèves.`)}
              onRefuser={(motif) => decider("refuser", { motif }, `${choisie.code} refusée, motif transmis à l'auteur.`)}
            />
          </div>
          <ApercuVersion seance={seance} />
          <div className="carte">
            <h3>Historique</h3>
            <Historique versions={seance.historique} />
          </div>
        </>
      )}
    </section>
  );
}
