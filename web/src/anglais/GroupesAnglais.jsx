import { useCallback, useEffect, useState } from "react";
import { Erreur } from "../composants.jsx";
import { useApi } from "../enseignant/useApi.js";

const NIVEAUX = ["4e", "3e"];
const ignorer = () => {};
const pluriel = (n) => `${n} élève${n > 1 ? "s" : ""}`;

/** Groupes PKP Anglais par niveau (4e, 3e) et leurs élèves : séparés des classes de maths. */
export default function GroupesAnglais({ jeton, onExpire }) {
  const { appeler, erreur } = useApi(jeton, onExpire);
  const [groupes, setGroupes] = useState(null);
  const [groupeId, setGroupeId] = useState(null);
  const [nom, setNom] = useState("");
  const [niveau, setNiveau] = useState("4e");
  const [prenomsSaisis, setPrenomsSaisis] = useState("");
  const [message, setMessage] = useState(null);

  const charger = useCallback(() => appeler("/anglais/groupes").then(setGroupes, ignorer), [appeler]);

  useEffect(() => {
    charger();
  }, [charger]);

  const groupe = groupes?.find((g) => g.id === groupeId);

  function choisir(id) {
    setGroupeId(id);
    setPrenomsSaisis("");
    setMessage(null);
  }

  async function creer(e) {
    e.preventDefault();
    try {
      const cree = await appeler("/anglais/groupes", { methode: "POST", corps: { nom, niveau } });
      setNom("");
      await charger();
      choisir(cree.id);
    } catch {
      // erreur déjà affichée (nom en double, par exemple)
    }
  }

  async function inscrire(e) {
    e.preventDefault();
    const prenoms = prenomsSaisis.split(/\r?\n/).map((p) => p.trim()).filter(Boolean);
    try {
      const r = await appeler(`/anglais/groupes/${groupeId}/eleves`, { methode: "POST", corps: { prenoms } });
      setPrenomsSaisis("");
      setMessage(r.deja_presents.length ? `Déjà inscrit(s), ignoré(s) : ${r.deja_presents.join(", ")}.` : null);
      await charger();
    } catch {
      // erreur déjà affichée (prénom invalide, groupe complet)
    }
  }

  async function retirer(eleve) {
    if (!window.confirm(`Retirer ${eleve.prenom} du groupe ?\n\nSon prénom est supprimé définitivement.`)) return;
    try {
      await appeler(`/anglais/groupes/${groupeId}/eleves/${eleve.id}`, { methode: "DELETE" });
      await charger();
    } catch {
      // erreur déjà affichée
    }
  }

  async function supprimer() {
    const ok = window.confirm(
      `Supprimer le groupe « ${groupe.nom} » ?\n\nSes ${pluriel(groupe.eleves.length)} seront supprimés définitivement.`,
    );
    if (!ok) return;
    try {
      await appeler(`/anglais/groupes/${groupeId}`, { methode: "DELETE" });
      setGroupeId(null);
      await charger();
    } catch {
      // erreur déjà affichée
    }
  }

  return (
    <>
      <section className="carte">
        <h2>Groupes de 4e et de 3e</h2>
        <p className="doux">Un groupe par niveau, de préférence 8 à 10 élèves. Les élèves sont inscrits par leur seul prénom.</p>
        {groupes === null ? (
          <p className="doux">Chargement…</p>
        ) : (
          NIVEAUX.map((n) => {
            const duNiveau = groupes.filter((g) => g.niveau === n);
            return (
              <div key={n}>
                <h3>Niveau {n}</h3>
                {duNiveau.length === 0 ? (
                  <p className="doux">Aucun groupe de {n} pour l'instant.</p>
                ) : (
                  <div className="grille-classes">
                    {duNiveau.map((g) => (
                      <button
                        key={g.id}
                        className={g.id === groupeId ? "classe choisie" : "classe"}
                        aria-pressed={g.id === groupeId}
                        onClick={() => choisir(g.id)}
                      >
                        <span className="code">{g.nom}</span>
                        <span className="doux">
                          {g.niveau} · {pluriel(g.eleves.length)}
                        </span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            );
          })
        )}
        <form className="actions" onSubmit={creer}>
          <label htmlFor="nom-groupe" className="visuellement-cache">
            Nom du nouveau groupe
          </label>
          <input
            id="nom-groupe"
            value={nom}
            maxLength={60}
            onChange={(e) => setNom(e.target.value)}
            placeholder="Ex. : 4e B - mardi"
            style={{ width: "auto", flex: 1 }}
          />
          <label htmlFor="niveau-groupe" className="visuellement-cache">
            Niveau du nouveau groupe
          </label>
          <select id="niveau-groupe" value={niveau} onChange={(e) => setNiveau(e.target.value)} style={{ width: "auto" }}>
            {NIVEAUX.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
          <button type="submit" className="secondaire" disabled={!nom.trim()}>
            Créer le groupe
          </button>
        </form>
        <Erreur message={!groupe ? erreur : null} />
      </section>

      {groupe && (
        <section className="carte">
          <h2>
            Groupe {groupe.nom} · {groupe.niveau}
          </h2>
          <p className="doux">
            {pluriel(groupe.eleves.length)}. Séances de ce niveau : <a href="/anglais">Séances 4e et 3e</a> ({groupe.niveau.toUpperCase()}-01,{" "}
            {groupe.niveau.toUpperCase()}-02).
          </p>
          {groupe.eleves.length > 0 && (
            <ul className="liste-eleves-anglais">
              {groupe.eleves.map((e) => (
                <li key={e.id}>
                  <span>{e.prenom}</span>
                  <button className="lien" onClick={() => retirer(e)} aria-label={`Retirer ${e.prenom}`}>
                    Retirer
                  </button>
                </li>
              ))}
            </ul>
          )}
          <form onSubmit={inscrire}>
            <label htmlFor="prenoms-anglais">Inscrire des élèves (un prénom par ligne)</label>
            <textarea
              id="prenoms-anglais"
              rows={4}
              value={prenomsSaisis}
              onChange={(e) => setPrenomsSaisis(e.target.value)}
              placeholder={"Lina\nYanis\nInès"}
            />
            <p className="aide">Prénom seulement, sans nom de famille.</p>
            <div className="actions">
              <button type="submit" className="secondaire" disabled={!prenomsSaisis.trim()}>
                Inscrire
              </button>
            </div>
          </form>
          {message && (
            <p className="succes" role="status">
              {message}
            </p>
          )}
          <Erreur message={erreur} />
          <div className="actions">
            <button className="danger" onClick={supprimer}>
              Supprimer le groupe
            </button>
          </div>
        </section>
      )}
    </>
  );
}
