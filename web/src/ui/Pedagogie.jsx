// Contenu pédagogique structuré : objectifs, méthodes avec exemple résolu, erreurs fréquentes,
// correction détaillée (voir docs/CONTENU.md). Tout le texte passe par <Maths> (Markdown + LaTeX).
import { Maths } from "../maths.jsx";

export function Objectifs({ objectifs }) {
  if (!objectifs?.length) return null;
  return (
    <section className="encadre objectifs" aria-labelledby="titre-objectifs">
      <h3 id="titre-objectifs">Objectifs</h3>
      <ul>
        {objectifs.map((o) => (
          <li key={o}>
            <Maths texte={o} enLigne />
          </li>
        ))}
      </ul>
    </section>
  );
}

function Etapes({ etapes }) {
  return (
    <ol className="etapes">
      {etapes.map((e, i) => (
        <li key={i}>
          <Maths texte={e} enLigne />
        </li>
      ))}
    </ol>
  );
}

export function Methodes({ methodes }) {
  if (!methodes?.length) return null;
  return (
    <section aria-labelledby="titre-methodes">
      <h3 id="titre-methodes">Méthodes</h3>
      {methodes.map((m) => (
        <div key={m.titre} className="encadre methode">
          <h4>Comment {m.titre.charAt(0).toLowerCase() + m.titre.slice(1)}</h4>
          {m.quand && (
            <p className="doux">
              <Maths texte={`Quand l'utiliser : ${m.quand}`} enLigne />
            </p>
          )}
          <Etapes etapes={m.etapes} />
          <div className="exemple">
            <p>
              <strong>Exemple résolu.</strong> <Maths texte={m.exemple.enonce} enLigne />
            </p>
            <Etapes etapes={m.exemple.resolution} />
            {m.exemple.resultat && (
              <p>
                <strong>Résultat :</strong> <Maths texte={m.exemple.resultat} enLigne />
              </p>
            )}
          </div>
        </div>
      ))}
    </section>
  );
}

export function ErreursFrequentes({ erreurs }) {
  if (!erreurs?.length) return null;
  return (
    <section className="encadre attention" aria-labelledby="titre-erreurs">
      <h3 id="titre-erreurs">Attention à…</h3>
      <ul>
        {erreurs.map((e) => (
          <li key={e.erreur}>
            <strong>
              <Maths texte={e.erreur} enLigne />
            </strong>{" "}
            <Maths texte={e.explication} enLigne />
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Correction détaillée d'une question, affichée après la réponse de l'élève. */
export function Correction({ correction }) {
  if (!correction) return null;
  return (
    <details className="correction">
      <summary>Voir la correction détaillée</summary>
      {correction.methode && (
        <p>
          <strong>Méthode :</strong> <Maths texte={correction.methode} enLigne />
        </p>
      )}
      <Etapes etapes={correction.etapes} />
      {correction.resultat && (
        <p>
          <strong>Résultat :</strong> <Maths texte={correction.resultat} enLigne />
        </p>
      )}
      {correction.erreurs_frequentes?.length > 0 && (
        <div className="encadre attention">
          <strong>Erreurs fréquentes</strong>
          <ul>
            {correction.erreurs_frequentes.map((e) => (
              <li key={e}>
                <Maths texte={e} enLigne />
              </li>
            ))}
          </ul>
        </div>
      )}
    </details>
  );
}
