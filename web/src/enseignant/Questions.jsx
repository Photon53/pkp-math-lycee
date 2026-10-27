import { useCallback, useEffect, useState } from "react";
import { Difficulte, Erreur, LIBELLES_TYPE } from "../composants.jsx";
import { useApi } from "./useApi.js";

const ignorer = () => {};
const VIDE = { enonce: "", type: "numerique", solution: "", difficulte: 2 };

const EXEMPLES_SOLUTION = {
  numerique: "ex. 5/6, -4, 0.01",
  expression: "ex. x^2 + 6x + 9",
  qcm: "ex. B",
};

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
  const [nouvelle, setNouvelle] = useState({ ...VIDE, competence_id: "" });
  const [message, setMessage] = useState(null);

  useEffect(() => {
    appeler("/enseignants/competences").then((reponse) => {
      const rang = (c) => NIVEAUX.findIndex(([n]) => n === c.niveau);
      const liste = [...reponse].sort((a, b) => rang(a) - rang(b));
      setCompetences(liste);
      setNouvelle((n) => ({ ...n, competence_id: n.competence_id || String(liste[0]?.id ?? "") }));
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

  async function creer(e) {
    e.preventDefault();
    setMessage(null);
    try {
      await appeler("/enseignants/questions", {
        methode: "POST",
        corps: { ...nouvelle, competence_id: Number(nouvelle.competence_id), difficulte: Number(nouvelle.difficulte) },
      });
      setNouvelle((n) => ({ ...n, enonce: "", solution: "" }));
      setMessage("Question ajoutée. Elle peut être proposée dès maintenant aux élèves.");
      charger();
    } catch {
      // erreur déjà affichée (ex. solution illisible par le moteur)
    }
  }

  async function archiver(q) {
    if (!window.confirm("Archiver cette question ? Elle ne sera plus proposée aux élèves, mais leur historique est conservé.")) return;
    try {
      await appeler(`/enseignants/questions/${q.id}/archiver`, { methode: "POST" });
      charger();
    } catch {
      // erreur déjà affichée
    }
  }

  const libelleCompetence = (id) => competences.find((c) => c.id === id)?.libelle ?? "";
  const champ = (cle) => ({ value: nouvelle[cle], onChange: (e) => setNouvelle({ ...nouvelle, [cle]: e.target.value }) });

  return (
    <>
      <form className="carte" onSubmit={creer}>
        <h2>Ajouter une question</h2>
        <label htmlFor="q-competence">Compétence</label>
        <select id="q-competence" {...champ("competence_id")} required>
          <CompetencesOptions competences={competences} />
        </select>
        <label htmlFor="q-enonce">Énoncé</label>
        <textarea id="q-enonce" rows={2} maxLength={2000} required {...champ("enonce")} />
        <p className="aide">Pour un QCM, écrire les choix dans l'énoncé : « … ? A) 0  B) 1  C) 2 ».</p>
        <div className="ligne">
          <div>
            <label htmlFor="q-type">Type</label>
            <select id="q-type" {...champ("type")}>
              {Object.entries(LIBELLES_TYPE).map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="q-difficulte">Difficulté (1 à 5)</label>
            <input id="q-difficulte" type="number" min={1} max={5} required {...champ("difficulte")} />
          </div>
        </div>
        <label htmlFor="q-solution">Solution</label>
        <input id="q-solution" maxLength={200} required placeholder={EXEMPLES_SOLUTION[nouvelle.type]} {...champ("solution")} />
        <p className="aide">Vérifiée par le moteur de correction : toute écriture équivalente sera acceptée.</p>
        <div className="actions">
          <button type="submit">Ajouter</button>
        </div>
        {message && (
          <p className="succes" role="status">
            {message}
          </p>
        )}
        <Erreur message={erreur} />
      </form>

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
                  <th>
                    <span className="visuellement-cache">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {questions.map((q) => (
                  <tr key={q.id}>
                    <td>
                      {q.enonce}
                      <div className="aide">
                        {LIBELLES_TYPE[q.type]} · {libelleCompetence(q.competence_id)}
                        {q.archivee && <span className="pastille archivee">Archivée</span>}
                      </div>
                    </td>
                    <td>
                      <code>{q.solution}</code>
                    </td>
                    <td>
                      <Difficulte niveau={q.difficulte} />
                    </td>
                    <td className="nombre">
                      {!q.archivee && (
                        <button className="secondaire petit" onClick={() => archiver(q)}>
                          Archiver
                        </button>
                      )}
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
