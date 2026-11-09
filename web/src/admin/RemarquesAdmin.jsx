import { useCallback, useEffect, useState } from "react";
import { telechargerFichier } from "../api.js";
import { Erreur } from "../composants.jsx";
import { useApi } from "../enseignant/useApi.js";
import { GROUPES_CATEGORIES, LIBELLES_CATEGORIES, LIBELLES_STATUTS } from "../ui/Remarques.jsx";

const PRIORITES = { basse: "Basse", normale: "Normale", haute: "Haute" };
const ROLES = { eleve: "élève", parent: "parent", professeur: "professeur" };

/**
 * Remarques et suggestions (ticket #30) : filtrer, assigner, répondre, traiter. Une remarque anonyme n'a aucune
 * identité enregistrée : l'écran affiche « Anonyme », l'export aussi.
 */
export default function RemarquesAdmin({ jeton, onExpire }) {
  const { appeler, erreur } = useApi(jeton, onExpire);
  const [moi, setMoi] = useState(null);
  const [filtres, setFiltres] = useState({ categorie: "", statut: "", priorite: "", depuis: "" });
  const [liste, setListe] = useState(null);
  const [ouverte, setOuverte] = useState(null);

  const requete = useCallback(() => {
    const p = new URLSearchParams();
    for (const [k, v] of Object.entries(filtres)) if (v) p.set(k, k === "depuis" ? new Date(v).toISOString() : v);
    return p.toString();
  }, [filtres]);

  const charger = useCallback(() => {
    appeler(`/admin/remarques?${requete()}`).then(setListe, () => {});
  }, [appeler, requete]);

  useEffect(() => {
    charger();
  }, [charger]);

  useEffect(() => {
    appeler("/admin/moi").then(setMoi, () => {});
  }, [appeler]);

  async function traiter(r, changements) {
    try {
      const maj = await appeler(`/admin/remarques/${r.id}`, { methode: "POST", corps: changements });
      setListe((l) => l.map((x) => (x.id === maj.id ? maj : x)));
    } catch {
      // Message affiché par useApi.
    }
  }

  const changer = (cle) => (e) => setFiltres({ ...filtres, [cle]: e.target.value });

  return (
    <section className="carte">
      <div style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "end" }}>
        <label>
          Catégorie
          <select value={filtres.categorie} onChange={changer("categorie")}>
            <option value="">Toutes</option>
            {GROUPES_CATEGORIES.map(([g, options]) => (
              <optgroup key={g} label={g}>
                {options.map(([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </label>
        <label>
          Statut
          <select value={filtres.statut} onChange={changer("statut")}>
            <option value="">Tous</option>
            {Object.entries(LIBELLES_STATUTS).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </label>
        <label>
          Priorité
          <select value={filtres.priorite} onChange={changer("priorite")}>
            <option value="">Toutes</option>
            {Object.entries(PRIORITES).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </label>
        <label>
          Depuis le
          <input type="date" value={filtres.depuis} onChange={changer("depuis")} />
        </label>
        <button className="secondaire" onClick={() => telechargerFichier(`/admin/remarques/export.csv?${requete()}`, jeton, "remarques.csv")}>
          Exporter
        </button>
      </div>
      <Erreur message={erreur} />
      {liste === null && !erreur && <p className="doux">Chargement…</p>}
      {liste?.length === 0 && <p className="doux">Aucune remarque.</p>}
      {liste?.length > 0 && (
        <div className="tableau-defilant">
          <table>
            <thead>
              <tr>
                <th>Référence</th>
                <th>Date</th>
                <th>Catégorie</th>
                <th>Auteur</th>
                <th>Statut</th>
                <th>Priorité</th>
                <th>Assignée à</th>
              </tr>
            </thead>
            <tbody>
              {liste.map((r) => (
                <Ligne key={r.id} r={r} ouverte={ouverte === r.id} onBasculer={() => setOuverte(ouverte === r.id ? null : r.id)} onTraiter={traiter} moi={moi} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function Ligne({ r, ouverte, onBasculer, onTraiter, moi }) {
  const [reponse, setReponse] = useState(r.reponse ?? "");
  return (
    <>
      <tr>
        <td>
          <button className="lien" onClick={onBasculer} aria-expanded={ouverte}>
            {r.reference}
          </button>
        </td>
        <td>{new Date(r.cree_le).toLocaleDateString("fr-FR")}</td>
        <td>{LIBELLES_CATEGORIES[r.categorie]}</td>
        <td>{r.anonyme ? <em>Anonyme</em> : r.auteur ? `${r.auteur.nom} (${ROLES[r.auteur.role] ?? r.auteur.role})` : "—"}</td>
        <td>
          <select aria-label={`Statut de ${r.reference}`} value={r.statut} onChange={(e) => onTraiter(r, { statut: e.target.value })}>
            {Object.entries(LIBELLES_STATUTS).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </td>
        <td>
          <select aria-label={`Priorité de ${r.reference}`} value={r.priorite} onChange={(e) => onTraiter(r, { priorite: e.target.value })}>
            {Object.entries(PRIORITES).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </td>
        <td>
          {r.assignee ??
            (moi?.id ? (
              <button className="lien" onClick={() => onTraiter(r, { assignee_id: moi.id })}>
                Me l'assigner
              </button>
            ) : (
              "—"
            ))}
        </td>
      </tr>
      {ouverte && (
        <tr>
          <td colSpan={7}>
            <p style={{ whiteSpace: "pre-wrap" }}>{r.description}</p>
            {r.page && <p className="doux">Concerne : {r.page}</p>}
            <label>
              Réponse (visible par l'auteur avec sa référence et son code de suivi)
              <textarea value={reponse} onChange={(e) => setReponse(e.target.value)} rows={3} maxLength={3000} />
            </label>
            <div className="actions">
              <button onClick={() => onTraiter(r, { reponse, ...(r.statut === "recue" ? { statut: "en-cours" } : {}) })}>Enregistrer la réponse</button>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
