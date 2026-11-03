import { useEffect, useState } from "react";
import { Erreur } from "../composants.jsx";
import { useApi } from "../enseignant/useApi.js";

/** Domaines pédagogiques (CDC V2, EX.1 à EX.4) : « activé » ouvre la production à l'équipe,
 * « ouvert aux élèves » permet les nouvelles séances. Fermer ne supprime ni contenu ni historique. */
export default function Configuration({ jeton, onExpire }) {
  const { appeler, erreur } = useApi(jeton, onExpire);
  const [domaines, setDomaines] = useState(null);
  const [message, setMessage] = useState(null);

  useEffect(() => {
    appeler("/admin/domaines").then(setDomaines, () => {});
  }, [appeler]);

  async function regler(d, reglage) {
    const suivant = { actif: d.actif, public: d.public, ...reglage };
    if (reglage.public === false && d.public &&
        !window.confirm(`Fermer ${d.libelle} aux élèves ? Plus aucune nouvelle séance, ni nouvelle classe ou nouveau groupe ; rien n'est supprimé.`)) return;
    setMessage(null);
    try {
      setDomaines(await appeler(`/admin/domaines/${d.code}`, { methode: "POST", corps: suivant }));
      setMessage(`${d.libelle} : ${suivant.public ? "ouvert aux élèves" : suivant.actif ? "activé pour l'équipe" : "désactivé"}.`);
    } catch {
      // erreur déjà affichée
    }
  }

  return (
    <section className="carte">
      <h2>Domaines pédagogiques</h2>
      <p className="doux">
        Chaque matière s'ouvre à son rythme. Un domaine activé reçoit des professeurs et des validateurs pour préparer son contenu ;
        il n'est ouvert aux élèves qu'une fois le contenu validé.
      </p>
      {message && (
        <p className="succes" role="status">
          {message}
        </p>
      )}
      <Erreur message={erreur} />
      {domaines === null ? (
        <p className="doux">Chargement…</p>
      ) : (
        <div className="tableau-defilant">
          <table>
            <thead>
              <tr>
                <th>Domaine</th>
                <th>Niveaux</th>
                <th className="nombre">Professeurs</th>
                <th className="nombre">Validateurs</th>
                <th className="centre">Activé (équipe)</th>
                <th className="centre">Ouvert aux élèves</th>
              </tr>
            </thead>
            <tbody>
              {domaines.map((d) => (
                <tr key={d.code} className={d.actif ? "" : "estompe"}>
                  <td>
                    <strong>{d.libelle}</strong>
                  </td>
                  <td>{d.niveaux.join(", ")}</td>
                  <td className="nombre">{d.nb_professeurs}</td>
                  <td className="nombre">
                    {d.nb_validateurs}
                    {d.actif && d.nb_validateurs === 0 && <div className="badge alerte">Aucun validateur</div>}
                  </td>
                  <td className="centre">
                    <input
                      type="checkbox"
                      aria-label={`${d.libelle} activé pour l'équipe`}
                      checked={d.actif}
                      onChange={(e) => regler(d, e.target.checked ? { actif: true } : { actif: false, public: false })}
                    />
                  </td>
                  <td className="centre">
                    <input
                      type="checkbox"
                      aria-label={`${d.libelle} ouvert aux élèves`}
                      checked={d.public}
                      disabled={!d.actif}
                      onChange={(e) => regler(d, { public: e.target.checked })}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="aide">
        Un domaine où des comptes sont encore habilités ne peut pas être désactivé : retirez d'abord leurs qualifications.
      </p>
    </section>
  );
}
