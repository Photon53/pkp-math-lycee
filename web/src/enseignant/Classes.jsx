import { Fragment, useCallback, useEffect, useState } from "react";
import { Erreur } from "../composants.jsx";
import { ListeProgression } from "../eleve/Progression.jsx";
import { useApi } from "./useApi.js";

const NIVEAUX = [
  ["2nde", "Seconde"],
  ["1re", "Première"],
  ["Tle", "Terminale"],
];

const pourcent = (x) => (x == null ? "—" : `${Math.round(x * 100)} %`);
const ignorer = () => {};

export default function Classes({ jeton, onExpire }) {
  const { appeler, erreur } = useApi(jeton, onExpire);
  const [classes, setClasses] = useState(null);
  const [classeId, setClasseId] = useState(null);
  const [eleves, setEleves] = useState(null);
  const [detail, setDetail] = useState(null); // { eleveId, competences }
  const [niveau, setNiveau] = useState("2nde");
  const [message, setMessage] = useState(null);

  const chargerClasses = useCallback(() => appeler("/enseignants/classes").then(setClasses, ignorer), [appeler]);
  const chargerEleves = useCallback(
    (id) => appeler(`/enseignants/classes/${id}/eleves`).then(setEleves, ignorer),
    [appeler],
  );

  useEffect(() => {
    chargerClasses();
  }, [chargerClasses]);

  function choisir(id) {
    setClasseId(id);
    setEleves(null);
    setDetail(null);
    setMessage(null);
    chargerEleves(id);
  }

  async function creer(e) {
    e.preventDefault();
    try {
      const classe = await appeler("/enseignants/classes", { methode: "POST", corps: { niveau } });
      await chargerClasses();
      choisir(classe.id);
      setMessage(`Classe créée. Code à donner aux élèves : ${classe.code}`);
    } catch {
      // erreur déjà affichée
    }
  }

  async function basculerDetail(eleveId) {
    if (detail?.eleveId === eleveId) return setDetail(null);
    try {
      setDetail({ eleveId, competences: await appeler(`/enseignants/eleves/${eleveId}/progression`) });
    } catch {
      // erreur déjà affichée
    }
  }

  async function supprimer(eleve) {
    const ok = window.confirm(
      `Supprimer définitivement ${eleve.prenom} et tout son historique (séances, réponses) ?\n\nCette action est irréversible.`,
    );
    if (!ok) return;
    try {
      await appeler(`/enseignants/eleves/${eleve.id}`, { methode: "DELETE" });
      setDetail(null);
      setMessage(`${eleve.prenom} a été supprimé·e avec tout son historique.`);
      await Promise.all([chargerEleves(classeId), chargerClasses()]);
    } catch {
      // erreur déjà affichée
    }
  }

  async function exporter(eleve) {
    try {
      const donnees = await appeler(`/enseignants/eleves/${eleve.id}/export`);
      const lien = document.createElement("a");
      lien.href = URL.createObjectURL(new Blob([JSON.stringify(donnees, null, 2)], { type: "application/json" }));
      lien.download = `pkp-${donnees.eleve.classe}-${eleve.prenom}.json`;
      lien.click();
      URL.revokeObjectURL(lien.href);
    } catch {
      // erreur déjà affichée
    }
  }

  async function supprimerClasse(c) {
    const ok = window.confirm(
      `Supprimer définitivement la classe ${c.code}, ses ${c.nb_eleves} élève(s) et tout leur historique ?\n\nCette action est irréversible.`,
    );
    if (!ok) return;
    try {
      await appeler(`/enseignants/classes/${c.id}`, { methode: "DELETE" });
      setClasseId(null);
      setEleves(null);
      setMessage(`La classe ${c.code} a été supprimée avec tous ses élèves.`);
      await chargerClasses();
    } catch {
      // erreur déjà affichée
    }
  }

  const classe = classes?.find((c) => c.id === classeId);

  return (
    <>
      <section className="carte">
        <h2>Mes classes</h2>
        {classes === null ? (
          <p className="doux">Chargement…</p>
        ) : classes.length === 0 ? (
          <p className="doux">Aucune classe pour l'instant : créez-en une ci-dessous.</p>
        ) : (
          <div className="grille-classes">
            {classes.map((c) => (
              <button
                key={c.id}
                className={c.id === classeId ? "classe choisie" : "classe"}
                aria-pressed={c.id === classeId}
                onClick={() => choisir(c.id)}
              >
                <span className="code">{c.code}</span>
                <span className="doux">
                  {NIVEAUX.find(([v]) => v === c.niveau)?.[1]} · {c.nb_eleves} élève{c.nb_eleves > 1 ? "s" : ""}
                </span>
              </button>
            ))}
          </div>
        )}
        <form className="actions" onSubmit={creer}>
          <label htmlFor="niveau" className="visuellement-cache">
            Niveau de la nouvelle classe
          </label>
          <select id="niveau" value={niveau} onChange={(e) => setNiveau(e.target.value)} style={{ width: "auto" }}>
            {NIVEAUX.map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
          <button type="submit" className="secondaire">
            Créer une classe
          </button>
        </form>
        {message && (
          <p className="succes" role="status">
            {message}
          </p>
        )}
        <Erreur message={erreur} />
      </section>

      {classe && (
        <section className="carte">
          <h2>
            Classe <code>{classe.code}</code>
          </h2>
          <p className="doux">Les élèves se connectent avec leur prénom et ce code. Leur compte est créé à la première connexion.</p>
          {eleves === null ? (
            <p className="doux">Chargement…</p>
          ) : eleves.length === 0 ? (
            <p className="doux">Aucun élève connecté pour l'instant.</p>
          ) : (
            <div className="tableau-defilant">
              <table>
                <thead>
                  <tr>
                    <th>Élève</th>
                    <th className="nombre">Réponses</th>
                    <th className="nombre">Réussite</th>
                    <th className="nombre">Compétences maîtrisées</th>
                    <th>
                      <span className="visuellement-cache">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {eleves.map((e) => (
                    <Fragment key={e.id}>
                      <tr>
                        <td>{e.prenom}</td>
                        <td className="nombre">{e.nb_reponses}</td>
                        <td className="nombre">{pourcent(e.taux_reussite)}</td>
                        <td className="nombre">
                          {e.competences_maitrisees} / {e.competences_total}
                        </td>
                        <td className="nombre">
                          <button className="lien petit" aria-expanded={detail?.eleveId === e.id} onClick={() => basculerDetail(e.id)}>
                            {detail?.eleveId === e.id ? "Masquer" : "Détail"}
                          </button>
                          <button className="lien petit" onClick={() => exporter(e)} aria-label={`Exporter les données de ${e.prenom}`}>
                            Exporter
                          </button>
                          <button className="danger petit" onClick={() => supprimer(e)} aria-label={`Supprimer ${e.prenom}`}>
                            Supprimer
                          </button>
                        </td>
                      </tr>
                      {detail?.eleveId === e.id && (
                        <tr className="detail">
                          <td colSpan={5}>
                            <ListeProgression competences={detail.competences} />
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="actions">
            <button className="danger" onClick={() => supprimerClasse(classe)}>
              Supprimer la classe (fin d'année)
            </button>
          </div>
        </section>
      )}
    </>
  );
}
