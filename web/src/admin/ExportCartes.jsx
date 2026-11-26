import { useState } from "react";
import { ApiError, telechargerPost } from "../api.js";
import { Erreur } from "../composants.jsx";
import { NIVEAUX } from "../parcours.js";
import { Modale } from "../ui/Cadre.jsx";
import Icone from "../ui/Icone.jsx";

const NOM_FICHIER = "boussole-cartes-acces.pdf";

function ChoixParPage({ valeur, onChange, id }) {
  return (
    <label htmlFor={id}>
      Cartes par feuille A4
      <select id={id} value={valeur} onChange={(e) => onChange(Number(e.target.value))}>
        <option value={8}>8 (format carte)</option>
        <option value={6}>6</option>
        <option value={4}>4 (grand format)</option>
      </select>
    </label>
  );
}

/** Télécharge le PDF et ramène les erreurs sous forme de message (401 : session expirée). */
async function telecharger(chemin, corps, jeton, onExpire) {
  try {
    await telechargerPost(chemin, { ...corps, origine: window.location.origin }, jeton, NOM_FICHIER);
    return null;
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) onExpire?.();
    return err.message;
  }
}

/** Cartes d'élèves déjà inscrits (ticket #23) : les codes ne sont pas conservés en clair, l'export en
 * tire donc de nouveaux, après confirmation ; les anciennes cartes cessent de fonctionner. */
export default function ExportCartes({ jeton, onExpire, onFermer, onExporte, ids = [], classes = [] }) {
  const [portee, setPortee] = useState(ids.length ? "selection" : "niveau");
  const [niveau, setNiveau] = useState(NIVEAUX[0][0]);
  const [classeId, setClasseId] = useState(classes[0]?.id ?? "");
  const [parPage, setParPage] = useState(8);
  const [compris, setCompris] = useState(false);
  const [erreur, setErreur] = useState(null);
  const [envoi, setEnvoi] = useState(false);

  async function exporter(e) {
    e.preventDefault();
    const choix =
      portee === "selection" ? { ids } : portee === "niveau" ? { niveau } : { classe_id: Number(classeId) };
    setEnvoi(true);
    setErreur(null);
    const echec = await telecharger("/admin/cartes/pdf", { ...choix, par_page: parPage, nouveaux_codes: true }, jeton, onExpire);
    setEnvoi(false);
    if (echec) setErreur(echec);
    else onExporte?.("PDF téléchargé : imprimez-le et distribuez les nouvelles cartes. Les anciennes ne fonctionnent plus.");
  }

  return (
    <Modale titre="Cartes d'accès (PDF A4)" onFermer={onFermer}>
      <form onSubmit={exporter}>
        <fieldset className="choix-portee">
          <legend>Élèves</legend>
          {ids.length > 0 && (
            <label className="case">
              <input type="radio" name="portee" checked={portee === "selection"} onChange={() => setPortee("selection")} />
              Les {ids.length} élève(s) sélectionné(s)
            </label>
          )}
          <label className="case">
            <input type="radio" name="portee" checked={portee === "niveau"} onChange={() => setPortee("niveau")} /> Tout un niveau
          </label>
          {portee === "niveau" && (
            <select aria-label="Niveau" value={niveau} onChange={(e) => setNiveau(e.target.value)}>
              {NIVEAUX.map(([v, l]) => (
                <option key={v} value={v}>{l}</option>
              ))}
            </select>
          )}
          {classes.length > 0 && (
            <label className="case">
              <input type="radio" name="portee" checked={portee === "classe"} onChange={() => setPortee("classe")} /> Une classe de
              maths
            </label>
          )}
          {portee === "classe" && (
            <select aria-label="Classe" value={classeId} onChange={(e) => setClasseId(e.target.value)}>
              {classes.map((c) => (
                <option key={c.id} value={c.id}>{c.code} ({c.enseignant})</option>
              ))}
            </select>
          )}
        </fieldset>
        <ChoixParPage id="cartes-par-page" valeur={parPage} onChange={setParPage} />
        <p className="alerte-texte">
          Les codes ne sont conservés que sous forme chiffrée : l'export crée un <strong>nouveau code</strong> pour chaque élève.
          Ses anciennes cartes cessent de fonctionner et ses sessions ouvertes se ferment. Son travail et ses inscriptions ne
          changent pas.
        </p>
        <label className="case">
          <input type="checkbox" checked={compris} onChange={(e) => setCompris(e.target.checked)} /> J'ai compris : je distribue
          les nouvelles cartes.
        </label>
        <Erreur message={erreur} />
        <div className="actions">
          <button type="submit" disabled={!compris || envoi || (portee === "classe" && !classeId)}>
            <Icone nom="telecharger" taille={18} /> {envoi ? "Préparation du PDF…" : "Télécharger le PDF"}
          </button>
          <button type="button" className="secondaire" onClick={onFermer}>
            Fermer
          </button>
        </div>
      </form>
    </Modale>
  );
}

/** Juste après un import ou une création (codes encore connus) : PDF des mêmes cartes, sans rien changer. */
export function PdfCartesConnues({ jeton, onExpire, cartes }) {
  const [parPage, setParPage] = useState(8);
  const [erreur, setErreur] = useState(null);
  const [envoi, setEnvoi] = useState(false);
  if (!cartes.length) return null;

  async function telechargerPdf() {
    setEnvoi(true);
    setErreur(null);
    const corps = { cartes: cartes.map((c) => ({ id: c.id, code: c.code })), par_page: parPage };
    setErreur(await telecharger("/admin/cartes/pdf/connues", corps, jeton, onExpire));
    setEnvoi(false);
  }

  return (
    <div className="pdf-cartes">
      <ChoixParPage id="cartes-connues-par-page" valeur={parPage} onChange={setParPage} />
      <button type="button" onClick={telechargerPdf} disabled={envoi}>
        <Icone nom="telecharger" taille={18} /> {envoi ? "Préparation du PDF…" : `Cartes en PDF A4 (${cartes.length})`}
      </button>
      <Erreur message={erreur} />
    </div>
  );
}
