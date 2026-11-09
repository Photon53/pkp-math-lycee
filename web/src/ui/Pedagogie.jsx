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
      {methodes.map((m, i) => (
        <div key={m.titre} id={`methode-${i + 1}`} className="encadre methode">
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

/** Méthode de la leçon citée par la correction (titre contenu dans le texte, ou l'inverse), sinon la première. */
export function methodeCitee(texte, methodes) {
  if (!methodes?.length) return null;
  const t = (texte ?? "").toLowerCase();
  const i = methodes.findIndex((m) => t && (t.includes(m.toLowerCase()) || m.toLowerCase().includes(t)));
  return i >= 0 ? { titre: methodes[i], ancre: `methode-${i + 1}` } : null;
}

function Ligne({ titre, texte }) {
  if (!texte) return null;
  return (
    <p>
      <strong>{titre} :</strong> <Maths texte={texte} enLigne />
    </p>
  );
}

/** Correction en deux temps : la méthode et le résultat d'abord, le détail sur demande, avec des renvois
 * vers le cours et la fiche méthode de la leçon (`references` : { competence, methodes, onVoir(ancre) }).
 * Gabarit (ticket #27) : rappel, formule et conditions, étapes, vérification, erreurs fréquentes, autre méthode ;
 * chaque rubrique est facultative et ne s'affiche que si le corrigé la contient. */
export function Correction({ correction, references }) {
  if (!correction) return null;
  const citee = methodeCitee(correction.methode, references?.methodes);
  return (
    <div className="correction-resumee">
      <Ligne titre="Rappel" texte={correction.rappel} />
      {correction.methode && (
        <p>
          <strong>Méthode :</strong> <Maths texte={correction.methode} enLigne />
        </p>
      )}
      {correction.resultat && (
        <p>
          <strong>Résultat :</strong> <Maths texte={correction.resultat} enLigne />
        </p>
      )}
      <details className="correction">
        <summary>Voir le détail de la correction</summary>
        {correction.formule && (
          <div className="encadre">
            <strong>Formule :</strong> <Maths texte={correction.formule} enLigne />
            {correction.conditions && (
              <p className="petit" style={{ margin: "4px 0 0" }}>
                <strong>Conditions :</strong> <Maths texte={correction.conditions} enLigne />
              </p>
            )}
          </div>
        )}
        {!correction.formule && <Ligne titre="Conditions" texte={correction.conditions} />}
        <Etapes etapes={correction.etapes} />
        <Ligne titre="Vérification" texte={correction.verification} />
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
      <Ligne titre="Autre méthode" texte={correction.autre_methode} />
      {references?.onVoir && (
        <p className="renvois">
          <strong>Pour revoir :</strong>{" "}
          <button className="lien" onClick={() => references.onVoir("lecon-cours")}>
            le cours « {references.competence} »
          </button>
          {(citee ? [citee] : (references.methodes ?? []).map((titre, i) => ({ titre, ancre: `methode-${i + 1}` }))).map((m) => (
            <span key={m.ancre}>
              {" · "}
              <button className="lien" onClick={() => references.onVoir(m.ancre)}>
                la méthode « {m.titre} »
              </button>
            </span>
          ))}
        </p>
      )}
      </details>
    </div>
  );
}
