// Issue #148 — Accueils Boussole et PKP (Claude)
// « Comment bien travailler ? » : aide facultative et repliée, toujours la même pour tous les élèves.
// Aucun questionnaire, aucune personnalisation, aucune donnée enregistrée.
import { CONSEILS, ETAPES } from "../methodeEtapes.js";

export default function ConseilsTravail() {
  return (
    <details className="conseils-travail">
      <summary>Comment bien travailler ?</summary>
      <ol className="methode-courte">
        {ETAPES.map((e) => (
          <li key={e.cle}>
            <strong>{e.titre}</strong>
            <span className="doux">{e.court}</span>
          </li>
        ))}
      </ol>
      <ul className="conseils">
        <li>{CONSEILS.essayer}</li>
        <li>{CONSEILS.rappel}</li>
        <li>{CONSEILS.erreur}</li>
      </ul>
      <p className="petit">
        <a href="/methode">Lire la méthode en détail</a>
      </p>
    </details>
  );
}
