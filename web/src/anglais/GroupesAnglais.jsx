import { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";
import { Erreur } from "../composants.jsx";
import AjoutEnfants from "../ui/AjoutEnfants.jsx";
import { FicheCodes } from "../enseignant/Classes.jsx";
import { useApi } from "../enseignant/useApi.js";

const NIVEAUX = ["6e", "5e", "4e", "3e", "2nde", "1re", "Tle"];
const ignorer = () => {};
const pluriel = (n) => `${n} élève${n > 1 ? "s" : ""}`;
const I_CAN = { non_observe: "—", avec_aide: "avec aide", en_cours: "en cours", autonome: "autonome" };

/** Groupes Boussole Anglais par niveau (6e à Tle) et leurs élèves : séparés des classes de maths. */
export default function GroupesAnglais({ jeton, onExpire }) {
  const { appeler, erreur } = useApi(jeton, onExpire);
  const [groupes, setGroupes] = useState(null);
  const [groupeId, setGroupeId] = useState(null);
  const [nom, setNom] = useState("");
  const [niveau, setNiveau] = useState("4e");
  const [message, setMessage] = useState(null);
  // Codes montrés une seule fois, juste après leur création : le serveur n'en garde que l'empreinte.
  const [codes, setCodes] = useState(null);
  const [progression, setProgression] = useState(null);

  const charger = useCallback(() => appeler("/anglais/groupes").then(setGroupes, ignorer), [appeler]);

  useEffect(() => {
    charger();
  }, [charger]);

  const groupe = groupes?.find((g) => g.id === groupeId);

  function choisir(id) {
    setGroupeId(id);
    setMessage(null);
    setCodes(null);
    setProgression(null);
  }

  async function genererCodes(chemin, confirmation) {
    if (confirmation && !window.confirm(confirmation)) return;
    try {
      const r = await appeler(chemin, { methode: "POST" });
      setCodes(Array.isArray(r) ? r : [r]);
      await charger();
    } catch {
      // erreur déjà affichée
    }
  }

  async function voirProgression() {
    try {
      setProgression(await appeler(`/anglais/groupes/${groupeId}/progression`));
    } catch {
      // erreur déjà affichée
    }
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

  // Les élèves sont créés par l'administrateur dans leur famille : le professeur les ajoute à son groupe.
  const chercherEnfants = useCallback(
    (q) => api(`/anglais/groupes/${groupeId}/enfants?q=${encodeURIComponent(q)}`, { jeton }),
    [groupeId, jeton],
  );

  async function retirer(eleve) {
    if (!window.confirm(`Retirer ${eleve.prenom} du groupe ?\n\nSon prénom est supprimé définitivement.`)) return;
    try {
      await appeler(`/anglais/groupes/${groupeId}/eleves/${eleve.id}`, { methode: "DELETE" });
      await charger();
    } catch {
      // erreur déjà affichée
    }
  }

  async function renommerGroupe() {
    const nouveau = window.prompt("Nouveau nom du groupe :", groupe.nom);
    if (!nouveau?.trim() || nouveau.trim() === groupe.nom) return;
    try {
      await appeler(`/anglais/groupes/${groupeId}`, { methode: "PATCH", corps: { nom: nouveau.trim() } });
      setMessage(`Groupe renommé : ${nouveau.trim()}.`);
      await charger();
    } catch {
      // erreur déjà affichée (nom en double, par exemple)
    }
  }

  async function renommerEleve(eleve) {
    const prenom = window.prompt(`Corriger le prénom de ${eleve.prenom} :`, eleve.prenom);
    if (!prenom?.trim() || prenom.trim() === eleve.prenom) return;
    try {
      await appeler(`/anglais/groupes/${groupeId}/eleves/${eleve.id}`, { methode: "PATCH", corps: { prenom: prenom.trim() } });
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
        <h2>Mes groupes</h2>
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
          <div className="barre-session">
            <h2>
              Groupe {groupe.nom} · {groupe.niveau}
            </h2>
            <button className="lien petit" onClick={renommerGroupe}>
              Renommer le groupe
            </button>
          </div>
          <p className="doux">
            {pluriel(groupe.eleves.length)}. Séances de ce niveau : <a href="/anglais">Séances</a> (codes {groupe.niveau.toUpperCase()}-01, -02…).
          </p>
          {codes && (
            <FicheCodes
              classe={groupe.nom}
              intitule={`Anglais ${groupe.niveau} · ${groupe.nom}`}
              chemin="/anglais/eleve"
              codes={codes}
              onFermer={() => setCodes(null)}
            />
          )}
          {groupe.eleves.length > 0 && (
            <ul className="liste-eleves-anglais">
              {groupe.eleves.map((e) => (
                <li key={e.id}>
                  <span>{e.prenom}</span>
                  <span className="doux petit">
                    {e.identifiant ? <code className="identifiant-eleve">{e.identifiant}</code> : "sans code"}
                  </span>
                  <span className="actions-ligne">
                    <button
                      className="lien"
                      onClick={() =>
                        genererCodes(
                          `/anglais/groupes/${groupeId}/eleves/${e.id}/code`,
                          e.a_un_code && `Nouveau code pour ${e.prenom} ?\n\nL'ancien code ne fonctionnera plus.`,
                        )
                      }
                      aria-label={`Nouveau code pour ${e.prenom}`}
                    >
                      Nouveau code
                    </button>
                    <button className="lien" onClick={() => renommerEleve(e)} aria-label={`Corriger le prénom de ${e.prenom}`}>
                      Renommer
                    </button>
                    <button className="lien" onClick={() => retirer(e)} aria-label={`Retirer ${e.prenom}`}>
                      Retirer
                    </button>
                  </span>
                </li>
              ))}
            </ul>
          )}
          {groupe.eleves.length > 0 && (
            <div className="actions">
              {groupe.eleves.some((e) => !e.a_un_code) && (
                <button className="secondaire" onClick={() => genererCodes(`/anglais/groupes/${groupeId}/codes`)}>
                  Créer les codes manquants
                </button>
              )}
              <button
                className="secondaire"
                onClick={() =>
                  genererCodes(
                    `/anglais/groupes/${groupeId}/codes?tous=true`,
                    "Réimprimer les cartes de tout le groupe ?\n\nChaque élève reçoit un nouveau code ; les anciens ne fonctionnent plus.",
                  )
                }
              >
                Réimprimer toutes les cartes
              </button>
              <button className="secondaire" onClick={voirProgression}>
                Voir la progression
              </button>
            </div>
          )}
          <p className="aide">
            Chaque élève se connecte sur <strong>{window.location.origin}/anglais/eleve</strong> avec son identifiant et son
            code personnel (ou en scannant le QR code de sa carte). Il n'y voit que les séances validées de son niveau.
          </p>
          {progression && <TableProgression lignes={progression} />}
          <AjoutEnfants
            key={groupe.id}
            chercher={chercherEnfants}
            ajouter={(ids) => appeler(`/anglais/groupes/${groupeId}/enfants`, { methode: "POST", corps: { enfant_ids: ids } })}
            onAjoutes={charger}
          />
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

/** Meilleur score au quiz et auto-évaluation « I can », séance par séance. */
function TableProgression({ lignes }) {
  const codes = [...new Set(lignes.flatMap((l) => Object.keys(l.seances)))].sort();
  if (codes.length === 0) return <p className="doux">Aucun élève n'a encore fait de quiz.</p>;
  return (
    <div className="tableau-defilant">
      <table>
        <caption className="visuellement-cache">Progression du groupe</caption>
        <thead>
          <tr>
            <th>Élève</th>
            {codes.map((c) => (
              <th key={c}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {lignes.map((l) => (
            <tr key={l.id}>
              <td>{l.prenom}</td>
              {codes.map((c) => {
                const p = l.seances[c];
                return (
                  <td key={c}>
                    {p ? (
                      <>
                        {p.score}/{p.total}
                        {p.i_can.length > 0 && (
                          <span className="doux petit"> · I can : {p.i_can.map((n) => I_CAN[n]).join(", ")}</span>
                        )}
                      </>
                    ) : (
                      "—"
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
