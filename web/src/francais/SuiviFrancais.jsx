// Issue #217 — Parcours du français au niveau de l'anglais (Claude)
//
// Suivi d'une classe de français, comme la progression d'un groupe d'anglais : meilleur score au quiz, score du
// premier essai, essais et auto-évaluation par dossier ; réponses rédigées à relire avec le retour du professeur ;
// mode de correction de la classe et de chaque dossier (#110).
import { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";
import { Erreur } from "../composants.jsx";
import { NIVEAUX_AUTO_EVALUATION } from "../eleve/ActiviteFrancais.jsx";
import { Vide } from "../ui/Cadre.jsx";

const MODES = [
  ["apres_chaque_question", "Après chaque question"],
  ["fin_du_quiz", "À la fin du quiz"],
];
const LIBELLE_NIVEAU = Object.fromEntries(NIVEAUX_AUTO_EVALUATION);

export default function SuiviFrancais({ appeler, jeton }) {
  const [classes, setClasses] = useState(null);
  const [choisie, setChoisie] = useState(null);

  useEffect(() => {
    appeler("/francais/classes").then(
      (c) => {
        setClasses(c);
        if (c.length) setChoisie((x) => x ?? c[0].id);
      },
      () => {},
    );
  }, [appeler]);

  if (classes === null) return <p className="doux">Chargement…</p>;
  if (classes.length === 0) return <Vide>Aucune classe de français active.</Vide>;
  return (
    <section>
      <div className="carte">
        <label htmlFor="classe-francais">Classe</label>
        <select id="classe-francais" value={choisie ?? ""} onChange={(e) => setChoisie(Number(e.target.value))}>
          {classes.map((c) => (
            <option key={c.id} value={c.id}>
              {c.code} · {c.niveau}
              {c.acces_eleves ? "" : " (élèves sans accès)"}
            </option>
          ))}
        </select>
      </div>
      {choisie && <SuiviClasse key={choisie} classeId={choisie} appeler={appeler} jeton={jeton} />}
    </section>
  );
}

function SuiviClasse({ classeId, appeler, jeton }) {
  const [suivi, setSuivi] = useState(null);
  const [reglage, setReglage] = useState(null);
  const [reponses, setReponses] = useState(null);
  const [erreur, setErreur] = useState(null);

  const charger = useCallback(() => {
    appeler(`/francais/classes/${classeId}/progression`).then(setSuivi, () => {});
    appeler(`/francais/classes/${classeId}/correction`).then(setReglage, () => {});
    // Réponses rédigées : fermées tant que la rédaction en ligne n'est pas ouverte (403 attendu, sans erreur).
    api(`/francais/classes/${classeId}/reponses`, { jeton }).then(setReponses, () => setReponses(null));
  }, [appeler, classeId, jeton]);

  useEffect(() => {
    charger();
  }, [charger]);

  async function regler(chemin, mode) {
    setErreur(null);
    try {
      setReglage(await appeler(chemin, { methode: "PUT", corps: { mode } }));
    } catch (err) {
      setErreur(err.message);
    }
  }

  if (!suivi || !reglage) return <p className="doux">Chargement…</p>;
  return (
    <>
      <div className="carte">
        <h2>Correction des quiz</h2>
        <label htmlFor="mode-classe">Pour toute la classe</label>
        <select
          id="mode-classe"
          value={reglage.mode}
          onChange={(e) => regler(`/francais/classes/${classeId}/correction`, e.target.value)}
        >
          {MODES.map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
        {suivi.dossiers.map((d) => (
          <div key={d.code}>
            <label htmlFor={`mode-${d.code}`}>{d.titre}</label>
            <select
              id={`mode-${d.code}`}
              value={reglage.dossiers[d.code] ?? ""}
              onChange={(e) => regler(`/francais/classes/${classeId}/dossiers/${d.code}/correction`, e.target.value || null)}
            >
              <option value="">Comme la classe</option>
              {MODES.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </div>
        ))}
        <Erreur message={erreur} />
      </div>

      <div className="carte">
        <h2>Progression</h2>
        {suivi.dossiers.length === 0 ? (
          <p className="doux">Aucun dossier validé n'est ouvert à cette classe.</p>
        ) : suivi.eleves.length === 0 ? (
          <p className="doux">Aucun élève inscrit.</p>
        ) : (
          <div className="tableau-defilant">
            <table>
              <caption className="visuellement-cache">Progression de la classe par dossier</caption>
              <thead>
                <tr>
                  <th scope="col">Élève</th>
                  {suivi.dossiers.map((d) => (
                    <th key={d.code} scope="col">
                      {d.titre}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {suivi.eleves.map((e) => (
                  <tr key={e.id}>
                    <th scope="row">{e.prenom}</th>
                    {suivi.dossiers.map((d) => (
                      <td key={d.code}>
                        <Cellule p={e.dossiers[d.code]} dossier={d} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {reponses && <Reponses reponses={reponses} appeler={appeler} onRetour={charger} />}
    </>
  );
}

function Cellule({ p, dossier }) {
  if (!p) return <span className="doux">—</span>;
  return (
    <>
      {dossier.nb_quiz > 0 &&
        (p.tentatives ? (
          <span>
            {p.score}/{p.total}{" "}
            <span className="doux petit">
              (1er essai {p.premier_score ?? "?"}/{p.total}, {p.tentatives} essai{p.tentatives > 1 ? "s" : ""})
            </span>
          </span>
        ) : (
          <span className="doux">Quiz non fait</span>
        ))}
      {p.auto_evaluation.length > 0 && (
        <p className="petit">
          {p.auto_evaluation.map((n, i) => (
            <span key={i} title={dossier.je_sais[i]}>
              {LIBELLE_NIVEAU[n] ?? n}
              {i < p.auto_evaluation.length - 1 ? " · " : ""}
            </span>
          ))}
        </p>
      )}
      {p.a_relire > 0 && <p className="petit">{p.a_relire} réponse(s) à relire</p>}
    </>
  );
}

function Reponses({ reponses, appeler, onRetour }) {
  const [commentaires, setCommentaires] = useState({});
  const aRelire = reponses.filter((r) => r.statut === "remise");

  async function envoyer(r) {
    try {
      await appeler(`/francais/reponses/${r.id}/retour`, { methode: "PUT", corps: { commentaire: commentaires[r.id] } });
      onRetour();
    } catch {
      // erreur affichée par la page
    }
  }

  return (
    <div className="carte">
      <h2>Réponses rédigées à relire ({aRelire.length})</h2>
      {aRelire.length === 0 && <p className="doux">Aucune réponse en attente.</p>}
      {aRelire.map((r) => (
        <div key={r.id} className="reponse-redigee">
          <p>
            <strong>{r.prenom}</strong> · {r.dossier} · {r.question}
          </p>
          <p className="citation">{r.texte}</p>
          <label htmlFor={`retour-${r.id}`}>Votre retour</label>
          <textarea
            id={`retour-${r.id}`}
            rows={3}
            maxLength={5000}
            value={commentaires[r.id] ?? ""}
            onChange={(e) => setCommentaires((c) => ({ ...c, [r.id]: e.target.value }))}
          />
          <div className="actions">
            <button disabled={!(commentaires[r.id] ?? "").trim()} onClick={() => envoyer(r)}>
              Envoyer le retour
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
