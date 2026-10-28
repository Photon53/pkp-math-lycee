import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Erreur } from "../composants.jsx";
import { Maths } from "../maths.jsx";

/**
 * Sommaire des cours du niveau de l'élève, et lecture d'une leçon (résumé puis cours).
 * `competenceId` ouvre directement une leçon (lien « Revoir le cours » depuis un exercice).
 */
export default function Cours({ jeton, onExpire, competenceId, onChoisir }) {
  const [sommaire, setSommaire] = useState(null);
  const [lecon, setLecon] = useState(null);
  const [erreur, setErreur] = useState(null);

  function gerer(err) {
    if (err.status === 401) onExpire();
    else if (err.status === 404) setErreur("Pas encore de cours pour cette compétence.");
    else setErreur(err.message);
  }

  useEffect(() => {
    api("/cours", { jeton }).then(setSommaire, gerer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jeton]);

  useEffect(() => {
    setLecon(null);
    setErreur(null);
    if (competenceId == null) return;
    let actif = true;
    api(`/cours/${competenceId}`, { jeton }).then(
      (l) => actif && setLecon(l),
      (err) => actif && gerer(err),
    );
    window.scrollTo?.(0, 0);
    return () => {
      actif = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [competenceId, jeton]);

  if (competenceId != null) {
    return (
      <article className="carte lecon">
        <button className="lien" onClick={() => onChoisir(null)}>
          ← Tous les cours
        </button>
        <Erreur message={erreur} />
        {lecon === null && !erreur && <p className="doux">Chargement…</p>}
        {lecon && (
          <>
            <p className="doux">{lecon.chapitre}</p>
            <h2>{lecon.libelle}</h2>
            <section className="resume" aria-labelledby="titre-resume">
              <h3 id="titre-resume">L'essentiel</h3>
              <Maths texte={lecon.resume} />
            </section>
            <Maths texte={lecon.cours} />
          </>
        )}
      </article>
    );
  }

  return (
    <section className="carte">
      <h2>Cours</h2>
      <Erreur message={erreur} />
      {sommaire === null && !erreur && <p className="doux">Chargement…</p>}
      {sommaire?.length === 0 && <p className="doux">Aucun cours pour ton niveau pour l'instant.</p>}
      {sommaire?.map((chapitre) => (
        <div key={chapitre.id}>
          <h3>{chapitre.titre}</h3>
          <ul className="liste-cours">
            {chapitre.competences.map((c) => (
              <li key={c.id}>
                {c.a_une_lecon ? (
                  <button className="lien" onClick={() => onChoisir(c.id)}>
                    {c.libelle}
                  </button>
                ) : (
                  <span className="doux">{c.libelle} (cours à venir)</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  );
}
