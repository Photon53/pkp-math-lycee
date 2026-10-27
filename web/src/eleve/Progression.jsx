import { useEffect, useState } from "react";
import { api } from "../api.js";
import { BarreMaitrise, Erreur } from "../composants.jsx";

export function grouperParChapitre(competences) {
  const groupes = new Map();
  for (const c of competences) {
    if (!groupes.has(c.chapitre)) groupes.set(c.chapitre, []);
    groupes.get(c.chapitre).push(c);
  }
  return [...groupes];
}

/** Liste des compétences d'un élève, utilisée côté élève et côté enseignant. */
export function ListeProgression({ competences }) {
  if (competences.length === 0) return <p className="doux">Aucune compétence pour ce niveau pour l'instant.</p>;
  return grouperParChapitre(competences).map(([chapitre, liste]) => (
    <section key={chapitre}>
      <h3>{chapitre}</h3>
      {liste.map((c) => (
        <div key={c.competence_id}>
          <BarreMaitrise valeur={c.maitrise} maitrisee={c.maitrisee} libelle={c.libelle} />
          <p className="aide">
            {c.nb_reponses === 0 ? "Pas encore travaillée" : `${c.nb_reponses} réponse${c.nb_reponses > 1 ? "s" : ""}`}
          </p>
        </div>
      ))}
    </section>
  ));
}

export default function Progression({ jeton, onExpire }) {
  const [competences, setCompetences] = useState(null);
  const [erreur, setErreur] = useState(null);

  useEffect(() => {
    let actif = true;
    api("/eleves/moi/progression", { jeton })
      .then((d) => actif && setCompetences(d))
      .catch((err) => {
        if (err.status === 401) onExpire();
        else if (actif) setErreur(err.message);
      });
    return () => {
      actif = false;
    };
    // onExpire change à chaque rendu du parent : ne pas recharger pour autant.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jeton]);

  return (
    <section className="carte">
      <h2>Ma progression</h2>
      <p className="doux">Une compétence est maîtrisée à partir de 80 %, soit environ 5 bonnes réponses d'affilée.</p>
      <Erreur message={erreur} />
      {competences ? <ListeProgression competences={competences} /> : !erreur && <p className="doux">Chargement…</p>}
    </section>
  );
}
