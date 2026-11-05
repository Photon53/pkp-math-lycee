// Administrateur : gérer une classe de maths (élèves, chapitres ouverts, professeur, suppression).
import { useCallback, useEffect, useState } from "react";
import { Erreur, Onglets } from "../composants.jsx";
import { LIBELLES_PARCOURS, libelleNiveauParcours } from "../parcours.js";
import AjoutEnfants from "../ui/AjoutEnfants.jsx";
import { Modale } from "../ui/Cadre.jsx";

/** Libellé court du parcours, pour un tableau : « Excellence et olympiades », sans la précision entre parenthèses. */
export const parcoursCourt = (p) => (LIBELLES_PARCOURS[p] ?? p).split(" (")[0];

// --- Gérer une classe ----------------------------------------------------------------------------------

export function GererClasse({ classe, appeler, onFermer, onChange }) {
  const [vue, setVue] = useState("eleves");
  const [info, setInfo] = useState(classe);

  const recharger = useCallback(async () => {
    try {
      setInfo(await appeler(`/admin/classes/${classe.id}`));
    } catch {
      // erreur affichée par la vue
    }
    onChange();
  }, [appeler, classe.id, onChange]);

  return (
    <Modale titre={`Classe ${info.code}`} onFermer={onFermer} large>
      <p className="doux">
        {libelleNiveauParcours(info.niveau, info.parcours)} · {info.enseignant} · {info.nb_eleves} élève(s) ·{" "}
        {info.nb_chapitres_ouverts} chapitre(s) ouvert(s)
      </p>
      <Onglets
        valeur={vue}
        onChange={setVue}
        options={[
          ["eleves", "Élèves"],
          ["chapitres", "Chapitres ouverts"],
          ["professeur", "Professeur"],
          ["suppression", "Supprimer"],
        ]}
      />
      {vue === "eleves" && <ElevesDeLaClasse classe={info} appeler={appeler} onChange={recharger} />}
      {vue === "chapitres" && <ChapitresDeLaClasse classe={info} appeler={appeler} onChange={recharger} />}
      {vue === "professeur" && <ProfesseurDeLaClasse classe={info} appeler={appeler} onChange={recharger} />}
      {vue === "suppression" && (
        <SuppressionClasse
          classe={info}
          appeler={appeler}
          onSupprimee={() => {
            onChange(`Classe ${info.code} supprimée.`);
            onFermer();
          }}
        />
      )}
    </Modale>
  );
}

function ElevesDeLaClasse({ classe, appeler, onChange }) {
  const [eleves, setEleves] = useState(null);
  const [erreur, setErreur] = useState(null);
  const [message, setMessage] = useState(null);

  const charger = useCallback(
    () => appeler(`/admin/classes/${classe.id}/eleves`).then(setEleves, (err) => setErreur(err.message)),
    [appeler, classe.id],
  );
  useEffect(() => {
    charger();
  }, [charger]);

  const chercher = useCallback((q) => appeler(`/admin/classes/${classe.id}/enfants?q=${encodeURIComponent(q)}`), [appeler, classe.id]);
  const ajouter = (ids) => appeler(`/admin/classes/${classe.id}/enfants`, { methode: "POST", corps: { enfant_ids: ids } });

  async function retirer(e) {
    if (!window.confirm(`Retirer ${e.prenom} de ${classe.code} ? Son travail dans cette classe est effacé ; sa carte et ses autres matières restent.`)) return;
    setErreur(null);
    try {
      await appeler(`/admin/eleves/${e.id}`, { methode: "DELETE" });
      setMessage(`${e.prenom} a été retiré·e de la classe.`);
      await charger();
      onChange();
    } catch (err) {
      setErreur(err.message);
    }
  }

  return (
    <>
      <Erreur message={erreur} />
      {message && <p className="succes" role="status">{message}</p>}
      {eleves === null ? (
        <p className="doux">Chargement…</p>
      ) : eleves.length === 0 ? (
        <p className="doux">Aucun élève inscrit pour l'instant.</p>
      ) : (
        <div className="tableau-defilant">
          <table>
            <thead>
              <tr>
                <th>Élève</th>
                <th>Identifiant</th>
                <th className="nombre">Réponses</th>
                <th className="nombre">Réussite</th>
                <th>
                  <span className="visuellement-cache">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {eleves.map((e) => (
                <tr key={e.id}>
                  <td><strong>{e.prenom}</strong></td>
                  <td>{e.identifiant ? <code>{e.identifiant}</code> : <span className="doux">—</span>}</td>
                  <td className="nombre">{e.nb_reponses}</td>
                  <td className="nombre">{e.taux_reussite == null ? "—" : `${Math.round(e.taux_reussite * 100)} %`}</td>
                  <td className="nombre">
                    <button className="secondaire petit" onClick={() => retirer(e)} aria-label={`Retirer ${e.prenom}`}>
                      Retirer
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <AjoutEnfants
        chercher={chercher}
        ajouter={ajouter}
        onAjoutes={() => {
          charger();
          onChange();
        }}
      />
    </>
  );
}

function ChapitresDeLaClasse({ classe, appeler, onChange }) {
  const [chapitres, setChapitres] = useState(null);
  const [coches, setCoches] = useState(new Set());
  const [message, setMessage] = useState(null);
  const [erreur, setErreur] = useState(null);

  const appliquer = useCallback((liste) => {
    setChapitres(liste);
    setCoches(new Set(liste.filter((c) => c.propose).map((c) => c.id)));
  }, []);
  useEffect(() => {
    appeler(`/admin/classes/${classe.id}/chapitres`).then(appliquer, (err) => setErreur(err.message));
  }, [appeler, appliquer, classe.id]);

  function basculer(id) {
    setMessage(null);
    setCoches((avant) => {
      const apres = new Set(avant);
      apres.has(id) ? apres.delete(id) : apres.add(id);
      return apres;
    });
  }

  async function enregistrer() {
    setErreur(null);
    try {
      appliquer(await appeler(`/admin/classes/${classe.id}/chapitres`, { methode: "PUT", corps: { chapitre_ids: [...coches] } }));
      setMessage(`${coches.size} chapitre(s) ouvert(s) aux élèves de ${classe.code}.`);
      onChange();
    } catch (err) {
      setErreur(err.message);
    }
  }

  const modifie = chapitres !== null && chapitres.some((c) => c.propose !== coches.has(c.id));
  return (
    <>
      <Erreur message={erreur} />
      {chapitres === null ? (
        <p className="doux">Chargement…</p>
      ) : chapitres.length === 0 ? (
        <p className="doux">Aucun chapitre n'existe encore pour ce niveau et ce parcours.</p>
      ) : (
        <fieldset className="choix-chapitres">
          <legend>Programme de la classe</legend>
          {chapitres.map((c) => (
            <label key={c.id} className="case">
              <input type="checkbox" checked={coches.has(c.id)} onChange={() => basculer(c.id)} />
              {c.ordre}. {c.titre}
              <span className="doux">{c.nb_questions === 0 ? " — pas encore de questions" : ` — ${c.nb_questions} question(s)`}</span>
            </label>
          ))}
        </fieldset>
      )}
      <div className="actions">
        <button onClick={enregistrer} disabled={!modifie}>Enregistrer les chapitres</button>
      </div>
      {message && <p className="succes" role="status">{message}</p>}
    </>
  );
}

function ProfesseurDeLaClasse({ classe, appeler, onChange }) {
  const [professeurs, setProfesseurs] = useState([]);
  const [choix, setChoix] = useState(String(classe.enseignant_id));
  const [message, setMessage] = useState(null);
  const [erreur, setErreur] = useState(null);

  useEffect(() => {
    appeler("/admin/enseignants").then((liste) => setProfesseurs(liste.filter((p) => p.actif && p.enseigne_maths !== false)), () => {});
  }, [appeler]);

  async function enregistrer(e) {
    e.preventDefault();
    setErreur(null);
    try {
      const c = await appeler(`/admin/classes/${classe.id}`, { methode: "PATCH", corps: { enseignant_id: Number(choix) } });
      setMessage(`${c.code} est maintenant suivie par ${c.enseignant}.`);
      onChange();
    } catch (err) {
      setErreur(err.message);
    }
  }

  return (
    <form onSubmit={enregistrer}>
      <label htmlFor="gc-prof">Professeur de mathématiques</label>
      <select id="gc-prof" value={choix} onChange={(e) => setChoix(e.target.value)}>
        {professeurs.map((p) => (
          <option key={p.id} value={p.id}>{p.nom}</option>
        ))}
      </select>
      <p className="aide">Les élèves, leur travail et les chapitres ouverts restent dans la classe.</p>
      <Erreur message={erreur} />
      {message && <p className="succes" role="status">{message}</p>}
      <div className="actions">
        <button type="submit" disabled={choix === String(classe.enseignant_id)}>Changer de professeur</button>
      </div>
    </form>
  );
}

function SuppressionClasse({ classe, appeler, onSupprimee }) {
  const [saisie, setSaisie] = useState("");
  const [erreur, setErreur] = useState(null);

  async function supprimer(e) {
    e.preventDefault();
    setErreur(null);
    try {
      await appeler(`/admin/classes/${classe.id}?${new URLSearchParams({ confirmation: saisie })}`, { methode: "DELETE" });
      onSupprimee();
    } catch (err) {
      setErreur(err.message);
    }
  }

  return (
    <form onSubmit={supprimer}>
      <p>
        La classe, ses {classe.nb_eleves} inscription(s) et tout le travail fait dans cette classe (séances, réponses) seront
        effacés. Les enfants gardent leur carte, leur famille et leurs autres classes.
      </p>
      <label htmlFor="gc-confirmation">Pour confirmer, saisissez le code de la classe : {classe.code}</label>
      <input id="gc-confirmation" value={saisie} onChange={(e) => setSaisie(e.target.value)} autoComplete="off" />
      <Erreur message={erreur} />
      <div className="actions">
        <button type="submit" className="danger" disabled={saisie.trim().toUpperCase() !== classe.code}>
          Supprimer la classe
        </button>
      </div>
    </form>
  );
}
