// Issue #180 — Mon cours : fiches de la professeure au fil du cours (Claude)
//
// Les chapitres que la professeure a ouverts à la classe, dans l'ordre du cours, avec les liens et fiches qu'elle y a
// rattachés. L'API applique les règles d'accès (classes pilotes, #176) et ne renvoie que ce que l'élève peut voir.
import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Erreur } from "../composants.jsx";
import DossiersFrancais from "./DossiersFrancais.jsx";
import { Ressources } from "./Cours.jsx";

export default function MonCours({ jeton, onExpire }) {
  const [chapitres, setChapitres] = useState(null);
  const [erreur, setErreur] = useState(null);

  useEffect(() => {
    api("/cours/mon-cours", { jeton }).then(setChapitres, (err) =>
      err.status === 401 && onExpire ? onExpire() : setErreur(err.message),
    );
  }, [jeton, onExpire]);

  if (erreur) return <Erreur message={erreur} />;
  if (!chapitres) return <p className="doux">Chargement de ton cours…</p>;

  return (
    <>
      <DossiersFrancais jeton={jeton} onExpire={onExpire} />
      <section className="carte" aria-labelledby="titre-mon-cours">
        <h2 id="titre-mon-cours">Mon cours</h2>
        <p className="doux">Les fiches et les liens de ta professeure, chapitre par chapitre, au fil du cours.</p>
        {chapitres.length === 0 ? (
          <p className="doux">Ta professeure n'a pas encore ouvert de chapitre.</p>
        ) : (
          chapitres.map((c) => (
            <div key={c.id} className="chapitre-mon-cours">
              {c.ressources.length ? (
                <Ressources ressources={c.ressources} jeton={jeton} titre={c.titre} />
              ) : (
                <>
                  <h3>{c.titre}</h3>
                  <p className="doux petit">Pas encore de fiche pour ce chapitre.</p>
                </>
              )}
            </div>
          ))
        )}
      </section>
    </>
  );
}
