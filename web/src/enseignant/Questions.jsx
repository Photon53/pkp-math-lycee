import { useCallback, useEffect, useState } from "react";
import { Difficulte, Erreur, LIBELLES_TYPE } from "../composants.jsx";
import { Maths } from "../maths.jsx";
import { useApi } from "./useApi.js";

const ignorer = () => {};

// Ordre scolaire, et non alphabétique (« 1re » < « 2nde »).
const NIVEAUX = [
  ["2nde", "Seconde"],
  ["1re", "Première"],
  ["Tle", "Terminale"],
];

function CompetencesOptions({ competences }) {
  const presents = new Set(competences.map((c) => c.niveau));
  return NIVEAUX.filter(([n]) => presents.has(n)).map(([n, libelle]) => (
    <optgroup key={n} label={libelle}>
      {competences
        .filter((c) => c.niveau === n)
        .map((c) => (
          <option key={c.id} value={c.id}>
            {c.chapitre} — {c.libelle}
          </option>
        ))}
    </optgroup>
  ));
}

export default function Questions({ jeton, onExpire }) {
  const { appeler, erreur } = useApi(jeton, onExpire);
  const [competences, setCompetences] = useState([]);
  const [filtre, setFiltre] = useState("");
  const [archivees, setArchivees] = useState(false);
  const [questions, setQuestions] = useState(null);

  useEffect(() => {
    appeler("/enseignants/competences").then((reponse) => {
      const rang = (c) => NIVEAUX.findIndex(([n]) => n === c.niveau);
      const liste = [...reponse].sort((a, b) => rang(a) - rang(b));
      setCompetences(liste);
    }, ignorer);
  }, [appeler]);

  const charger = useCallback(() => {
    const params = new URLSearchParams({ archivees: String(archivees) });
    if (filtre) params.set("competence_id", filtre);
    return appeler(`/enseignants/questions?${params}`).then(setQuestions, ignorer);
  }, [appeler, filtre, archivees]);

  useEffect(() => {
    charger();
  }, [charger]);

  const libelleCompetence = (id) => competences.find((c) => c.id === id)?.libelle ?? "";

  return (
    <>
      <p className="info">
        La banque est commune à tous les professeurs : elle est relue et enrichie par l'équipe PKP. Signalez une
        erreur ou proposez une question à votre administrateur.
      </p>
      <Erreur message={erreur} />

      <section className="carte">
        <h2>Banque de questions</h2>
        <div className="ligne">
          <div>
            <label htmlFor="filtre">Compétence</label>
            <select id="filtre" value={filtre} onChange={(e) => setFiltre(e.target.value)}>
              <option value="">Toutes</option>
              <CompetencesOptions competences={competences} />
            </select>
          </div>
          <label className="case">
            <input type="checkbox" checked={archivees} onChange={(e) => setArchivees(e.target.checked)} /> Afficher les questions archivées
          </label>
        </div>
        {questions === null ? (
          <p className="doux">Chargement…</p>
        ) : questions.length === 0 ? (
          <p className="doux">Aucune question.</p>
        ) : (
          <div className="tableau-defilant">
            <table>
              <thead>
                <tr>
                  <th>Énoncé</th>
                  <th>Solution</th>
                  <th>Difficulté</th>
                </tr>
              </thead>
              <tbody>
                {questions.map((q) => (
                  <tr key={q.id}>
                    <td>
                      <Maths enLigne texte={q.enonce} />
                      <div className="aide">
                        {LIBELLES_TYPE[q.type]} · {libelleCompetence(q.competence_id)}
                        {q.archivee && <span className="pastille archivee">Archivée</span>}
                        {q.statut_validation !== "validee" && (
                          <span className="pastille archivee">{q.statut_validation === "a-corriger" ? "À corriger" : "À valider"}</span>
                        )}
                        {q.adaptation !== "originale" && (
                          <span className="pastille archivee" title={q.licence_source ?? ""}>
                            {q.adaptation === "inspiree" ? "Inspirée de" : "Source :"} {q.source}
                          </span>
                        )}
                      </div>
                    </td>
                    <td>
                      <code>{q.solution}</code>
                    </td>
                    <td>
                      <Difficulte niveau={q.difficulte} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
