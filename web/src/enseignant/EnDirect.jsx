import { useCallback, useEffect, useRef, useState } from "react";
import { telechargerFichier } from "../api.js";
import { Erreur } from "../composants.jsx";
import { Correction } from "../ui/Pedagogie.jsx";
import { Maths } from "../maths.jsx";
import { useApi } from "./useApi.js";

// Actualisation automatique pendant la séance (ticket #28) : assez vite pour réagir, sans surcharger le serveur.
export const INTERVALLE_MS = 8000;

const PERIODES = [
  ["1h", "Dernière heure", 1],
  ["2h", "2 dernières heures", 2],
  ["jour", "Aujourd'hui", null],
  ["7j", "7 derniers jours", 24 * 7],
];

function debutDePeriode(periode, maintenant = new Date()) {
  const [, , heures] = PERIODES.find(([v]) => v === periode);
  if (heures === null) {
    const d = new Date(maintenant);
    d.setHours(0, 0, 0, 0);
    return d;
  }
  return new Date(maintenant.getTime() - heures * 3600 * 1000);
}

const heure = (iso) => new Date(iso).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
const pourcent = (x) => (x === null || x === undefined ? "—" : `${Math.round(x * 100)} %`);
const OBJETS = { cours: "Cours", exercice: "Exercice", corrige: "Correction" };

/**
 * Tableau de bord de la séance : réussites, erreurs, non-réponses, notions à retravailler et demandes
 * « Je n'ai pas compris » des élèves de mes classes, actualisés automatiquement.
 */
export default function EnDirect({ jeton, onExpire }) {
  const { appeler, erreur } = useApi(jeton, onExpire);
  const [classes, setClasses] = useState([]);
  const [chapitres, setChapitres] = useState([]);
  const [filtres, setFiltres] = useState({ classe: "", periode: "2h", chapitre: "", competence: "", erreurs: false });
  const [tableau, setTableau] = useState(null);
  const [ouverte, setOuverte] = useState(null); // question dont on affiche l'énoncé et la correction
  const enCours = useRef(false);

  useEffect(() => {
    appeler("/enseignants/classes").then(setClasses, () => {});
  }, [appeler]);

  useEffect(() => {
    setChapitres([]);
    if (filtres.classe) appeler(`/enseignants/classes/${filtres.classe}/chapitres`).then((l) => setChapitres(l.filter((c) => c.propose)), () => {});
  }, [appeler, filtres.classe]);

  const parametres = useCallback(
    (avecErreurs = true) => {
      const p = new URLSearchParams({ depuis: debutDePeriode(filtres.periode).toISOString() });
      if (filtres.classe) p.set("classe_id", filtres.classe);
      if (filtres.chapitre) p.set("chapitre_id", filtres.chapitre);
      if (filtres.competence) p.set("competence_id", filtres.competence);
      if (avecErreurs && filtres.erreurs) p.set("erreurs_uniquement", "true");
      return p.toString();
    },
    [filtres],
  );

  const actualiser = useCallback(async () => {
    if (enCours.current) return;
    enCours.current = true;
    try {
      setTableau(await appeler(`/enseignants/seance-en-direct?${parametres()}`));
    } catch {
      // Erreur affichée par useApi ; on réessaie à la prochaine actualisation.
    } finally {
      enCours.current = false;
    }
  }, [appeler, parametres]);

  useEffect(() => {
    actualiser();
    const minuteur = setInterval(() => {
      if (document.visibilityState !== "hidden") actualiser();
    }, INTERVALLE_MS);
    return () => clearInterval(minuteur);
  }, [actualiser]);

  async function traiter(demande, statut) {
    try {
      await appeler(`/enseignants/demandes/${demande.id}`, { methode: "POST", corps: { statut } });
      actualiser();
    } catch {
      // Message affiché par useApi.
    }
  }

  const changer = (cle) => (e) =>
    setFiltres((f) => ({
      ...f,
      [cle]: e.target.type === "checkbox" ? e.target.checked : e.target.value,
      ...(cle === "classe" ? { chapitre: "", competence: "" } : {}),
      ...(cle === "chapitre" ? { competence: "" } : {}),
    }));

  const competences = tableau ? tableau.notions : [];

  return (
    <>
      <section className="carte">
        <div className="filtres" style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "end" }}>
          <label>
            Classe
            <select value={filtres.classe} onChange={changer("classe")}>
              <option value="">Toutes mes classes</option>
              {classes.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.code}
                </option>
              ))}
            </select>
          </label>
          <label>
            Période
            <select value={filtres.periode} onChange={changer("periode")}>
              {PERIODES.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </label>
          <label>
            Chapitre
            <select value={filtres.chapitre} onChange={changer("chapitre")} disabled={!filtres.classe}>
              <option value="">Tous</option>
              {chapitres.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.titre}
                </option>
              ))}
            </select>
          </label>
          <label>
            Compétence
            <select value={filtres.competence} onChange={changer("competence")}>
              <option value="">Toutes</option>
              {competences.map((n) => (
                <option key={n.competence_id} value={n.competence_id}>
                  {n.competence}
                </option>
              ))}
            </select>
          </label>
          <label className="case">
            <input type="checkbox" checked={filtres.erreurs} onChange={changer("erreurs")} /> Erreurs uniquement
          </label>
          <button
            className="secondaire"
            onClick={() => telechargerFichier(`/enseignants/seance-en-direct/export.csv?${parametres(false)}`, jeton, "seance-agregee.csv")}
          >
            Exporter (sans nom d'élève)
          </button>
        </div>
        <p className="doux petit" role="status">
          {tableau ? `Actualisé à ${heure(tableau.genere_le)} · toutes les ${INTERVALLE_MS / 1000} s` : "Chargement…"}
        </p>
        <Erreur message={erreur} />
        {tableau && (
          <div className="compteurs" style={{ display: "flex", flexWrap: "wrap", gap: 16 }}>
            <span>
              Élèves actifs : <strong>{tableau.compteurs.eleves_actifs}</strong>
            </span>
            <span>
              « Pas compris » cours : <strong>{tableau.compteurs.demandes_cours}</strong>
            </span>
            <span>
              Exercices : <strong>{tableau.compteurs.demandes_exercices}</strong>
            </span>
            <span>
              Corrections : <strong>{tableau.compteurs.demandes_corriges}</strong>
            </span>
            <span>
              Résolues : <strong>{tableau.compteurs.resolues}</strong>
            </span>
          </div>
        )}
      </section>

      {tableau && (
        <>
          <section className="carte" aria-labelledby="titre-notions">
            <h2 id="titre-notions">Notions à retravailler</h2>
            {tableau.notions.length === 0 ? (
              <p className="doux">Aucune difficulté repérée sur la période.</p>
            ) : (
              <ol>
                {tableau.notions.map((n) => (
                  <li key={n.competence_id}>
                    <strong>{n.competence}</strong> <span className="doux">({n.chapitre})</span> : {n.nb_eleves_en_difficulte} élève(s) en
                    difficulté, erreurs {pourcent(n.taux_erreur)}, {n.nb_demandes} demande(s) d'aide
                  </li>
                ))}
              </ol>
            )}
          </section>

          <Demandes
            titre="« Je n'ai pas compris » sur les cours"
            vide="Aucun élève n'a signalé de cours incompris."
            demandes={tableau.demandes_cours}
            onTraiter={traiter}
          />
          <Demandes
            titre="Demandes d'aide sur les exercices et les corrections"
            vide="Aucune demande d'aide sur les exercices."
            demandes={tableau.demandes_exercices}
            onTraiter={traiter}
          />

          <section className="carte" aria-labelledby="titre-questions">
            <h2 id="titre-questions">Questions de la séance</h2>
            {tableau.questions.length === 0 ? (
              <p className="doux">{filtres.erreurs ? "Aucune erreur sur la période." : "Aucune réponse sur la période."}</p>
            ) : (
              <div className="tableau-defilant">
                <table>
                  <thead>
                    <tr>
                      <th>Question</th>
                      <th>Compétence</th>
                      <th>Tentatives</th>
                      <th>Élèves</th>
                      <th>Réussites</th>
                      <th>Erreurs</th>
                      <th>Réussies après erreur</th>
                      <th>En échec</th>
                      <th>Sans réponse</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tableau.questions.map((q) => (
                      <LigneQuestion key={q.question_id} q={q} ouverte={ouverte === q.question_id} onBasculer={() => setOuverte(ouverte === q.question_id ? null : q.question_id)} />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </>
  );
}

function LigneQuestion({ q, ouverte, onBasculer }) {
  return (
    <>
      <tr>
        <td>
          <button className="lien" onClick={onBasculer} aria-expanded={ouverte}>
            {q.code ?? `#${q.question_id}`}
          </button>
        </td>
        <td>{q.competence}</td>
        <td>{q.nb_tentatives}</td>
        <td>{q.nb_eleves}</td>
        <td>{q.nb_reussites}</td>
        <td>
          {q.nb_erreurs} <span className="doux petit">({pourcent(q.taux_erreur)})</span>
        </td>
        <td>{q.nb_reussies_apres_erreur}</td>
        <td>{q.eleves_en_echec.join(", ") || "—"}</td>
        <td>{q.eleves_sans_reponse.join(", ") || "—"}</td>
      </tr>
      {ouverte && (
        <tr>
          <td colSpan={9}>
            <p>
              <Maths texte={q.enonce} enLigne />
            </p>
            <p>
              <strong>Réponse attendue :</strong> <Maths texte={q.solution} enLigne />
            </p>
            <Correction correction={q.correction} />
          </td>
        </tr>
      )}
    </>
  );
}

function Demandes({ titre, vide, demandes, onTraiter }) {
  return (
    <section className="carte">
      <h2>
        {titre} <span className="doux">({demandes.length})</span>
      </h2>
      {demandes.length === 0 ? (
        <p className="doux">{vide}</p>
      ) : (
        <ul className="liste-demandes">
          {demandes.map((d) => (
            <li key={d.id} style={{ marginBottom: 8 }}>
              <strong>{d.eleve}</strong> <span className="doux">({d.classe})</span> · {OBJETS[d.objet]} · {d.chapitre} — {d.competence}
              {d.question_code && <> · {d.question_code}</>} · {heure(d.cree_le)}
              {d.statut === "prise-en-charge" && <span className="doux"> · pris en charge{d.traitee_par ? ` par ${d.traitee_par}` : ""}</span>}{" "}
              {d.statut === "ouverte" && (
                <button className="secondaire petit" onClick={() => onTraiter(d, "prise-en-charge")}>
                  Je m'en occupe
                </button>
              )}{" "}
              <button className="secondaire petit" onClick={() => onTraiter(d, "resolue")}>
                Résolue
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
