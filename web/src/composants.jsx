// Petits composants partagés entre l'espace élève et l'espace enseignant.

export function Erreur({ message }) {
  if (!message) return null;
  return (
    <p className="erreur" role="alert">
      {message}
    </p>
  );
}

export function BarreMaitrise({ valeur, maitrisee, libelle = "Maîtrise" }) {
  const pct = Math.round(valeur * 100);
  return (
    <div className="maitrise">
      <div className="maitrise-entete">
        <span>{libelle}</span>
        <span>
          {pct} %{maitrisee && <span className="pastille ok">Maîtrisée</span>}
        </span>
      </div>
      <div className="jauge" role="progressbar" aria-label={libelle} aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct}>
        <div className={`jauge-remplie${maitrisee ? " atteinte" : ""}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export function Onglets({ valeur, options, onChange }) {
  return (
    <div className="onglets" role="tablist">
      {options.map(([cle, libelle]) => (
        <button
          key={cle}
          role="tab"
          aria-selected={valeur === cle}
          className={valeur === cle ? "onglet actif" : "onglet"}
          onClick={() => onChange(cle)}
        >
          {libelle}
        </button>
      ))}
    </div>
  );
}

export function Difficulte({ niveau }) {
  return (
    <span className="difficulte" aria-label={`Difficulté ${niveau} sur 5`} title={`Difficulté ${niveau}/5`}>
      {"●".repeat(niveau)}
      <span className="eteint">{"●".repeat(5 - niveau)}</span>
    </span>
  );
}

export const LIBELLES_TYPE = { qcm: "QCM", numerique: "Numérique", expression: "Expression" };
