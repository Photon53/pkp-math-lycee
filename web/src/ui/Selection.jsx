import { useCallback, useMemo, useState } from "react";
import { Erreur } from "../composants.jsx";
import { Modale } from "./Cadre.jsx";

export const MOT_DE_CONFIRMATION = "SUPPRIMER";

/** Cases cochées d'une liste (par identifiant). */
export function useSelection() {
  const [choisis, setChoisis] = useState(() => new Set());
  const basculer = useCallback(
    (id) =>
      setChoisis((avant) => {
        const apres = new Set(avant);
        if (apres.has(id)) apres.delete(id);
        else apres.add(id);
        return apres;
      }),
    [],
  );
  const regler = useCallback(
    (ids, coche) =>
      setChoisis((avant) => {
        const apres = new Set(avant);
        ids.forEach((id) => (coche ? apres.add(id) : apres.delete(id)));
        return apres;
      }),
    [],
  );
  const vider = useCallback(() => setChoisis(new Set()), []);
  return useMemo(() => ({ choisis, ids: [...choisis], nombre: choisis.size, basculer, regler, vider }), [choisis, basculer, regler, vider]);
}

/** Case d'en-tête : coche ou décoche toutes les lignes affichées. */
export function CaseTout({ selection, ids, libelle = "Tout sélectionner" }) {
  const toutes = ids.length > 0 && ids.every((id) => selection.choisis.has(id));
  const certaines = !toutes && ids.some((id) => selection.choisis.has(id));
  return (
    <th className="col-case">
      <input
        type="checkbox"
        aria-label={libelle}
        checked={toutes}
        ref={(el) => el && (el.indeterminate = certaines)}
        onChange={(e) => selection.regler(ids, e.target.checked)}
      />
    </th>
  );
}

export function CaseLigne({ selection, id, libelle }) {
  return (
    <td className="col-case">
      <input type="checkbox" aria-label={libelle} checked={selection.choisis.has(id)} onChange={() => selection.basculer(id)} />
    </td>
  );
}

/** Barre d'actions affichée dès qu'une ligne est cochée. */
export function BarreSelection({ selection, noms = ["élément", "éléments"], children }) {
  if (!selection.nombre) return null;
  const n = selection.nombre;
  return (
    <div className="barre-selection" role="region" aria-label="Actions sur la sélection">
      <strong>
        Sélection : {n} {n > 1 ? noms[1] : noms[0]}
      </strong>
      <div className="actions">
        {children}
        <button className="lien petit" onClick={selection.vider}>
          Tout désélectionner
        </button>
      </div>
    </div>
  );
}

/** Suppression de plusieurs éléments : l'administrateur saisit SUPPRIMER pour confirmer. */
export function ConfirmationSuppression({ titre, children, onConfirmer, onFermer }) {
  const [saisie, setSaisie] = useState("");
  const [erreur, setErreur] = useState(null);
  const [envoi, setEnvoi] = useState(false);

  async function confirmer(e) {
    e.preventDefault();
    setErreur(null);
    setEnvoi(true);
    try {
      await onConfirmer(saisie);
    } catch (err) {
      setErreur(err.message);
      setEnvoi(false);
    }
  }

  return (
    <Modale titre={titre} onFermer={onFermer}>
      <form onSubmit={confirmer}>
        {children}
        <p className="alerte-texte">Cette action est définitive.</p>
        <label htmlFor="confirmation-masse">Pour confirmer, saisissez {MOT_DE_CONFIRMATION}</label>
        <input id="confirmation-masse" value={saisie} onChange={(e) => setSaisie(e.target.value)} autoComplete="off" />
        <Erreur message={erreur} />
        <div className="actions">
          <button type="button" className="secondaire" onClick={onFermer}>
            Annuler
          </button>
          <button type="submit" className="danger" disabled={envoi || saisie.trim().toUpperCase() !== MOT_DE_CONFIRMATION}>
            Supprimer définitivement
          </button>
        </div>
      </form>
    </Modale>
  );
}
