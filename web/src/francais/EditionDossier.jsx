// Issue #217 — Parcours du français au niveau de l'anglais (Claude)
//
// Édition d'un dossier par l'administrateur, comme une séance d'anglais : même contrat que le fichier d'import
// (docs/francais/FORMAT-IMPORT.md). Une version validée n'est jamais modifiée : l'enregistrement crée un brouillon,
// soumis ensuite à la validation d'un autre validateur.
import { useEffect, useState } from "react";

export default function EditionDossier({ code, appeler, onEnregistre }) {
  const [etat, setEtat] = useState(null);
  const [texte, setTexte] = useState("");
  const [erreurs, setErreurs] = useState([]);
  const [message, setMessage] = useState(null);

  useEffect(() => {
    appeler(`/francais/dossiers/${code}/source`).then(
      (r) => {
        setEtat(r);
        setTexte(JSON.stringify(r.source, null, 2));
      },
      () => {},
    );
  }, [appeler, code]);

  async function enregistrer() {
    setErreurs([]);
    setMessage(null);
    let corps;
    try {
      corps = JSON.parse(texte);
    } catch (err) {
      setErreurs([`JSON invalide : ${err.message}`]);
      return;
    }
    try {
      const r = await appeler(`/francais/dossiers/${code}/brouillon`, { methode: "PUT", corps });
      setEtat((e) => ({ ...e, statut: r.statut, version_affichee: r.version }));
      setMessage(`Brouillon v${r.version} enregistré. Soumettez-le pour qu'un validateur le relise.`);
      onEnregistre?.();
    } catch (err) {
      setErreurs([err.message]);
    }
  }

  async function soumettre() {
    setMessage(null);
    try {
      const r = await appeler(`/francais/dossiers/${code}/soumettre`, { methode: "POST" });
      setEtat((e) => ({ ...e, statut: r.statut }));
      setMessage(`v${r.version} soumise à la validation. Vous ne pourrez pas la valider vous-même.`);
      onEnregistre?.();
    } catch {
      // erreur affichée par la page
    }
  }

  if (!etat) return <p className="doux">Chargement…</p>;
  return (
    <div className="carte">
      <p className="doux petit">
        Version courante v{etat.version_affichee} ({etat.statut}). Même format que le fichier d'import : partie élève, partie
        professeur, quiz (bonne réponse = rang du choix, à partir de 0). Le code, le domaine et le niveau ne changent pas.
      </p>
      <label htmlFor="source-dossier">Contenu du dossier (JSON)</label>
      <textarea
        id="source-dossier"
        className="code"
        rows={24}
        spellCheck={false}
        value={texte}
        onChange={(e) => setTexte(e.target.value)}
      />
      {erreurs.length > 0 && (
        <div className="erreur" role="alert">
          <ul>
            {erreurs.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        </div>
      )}
      {message && (
        <p className="succes" role="status">
          {message}
        </p>
      )}
      <div className="actions">
        <button onClick={enregistrer}>Enregistrer un brouillon</button>
        <button className="secondaire" disabled={etat.statut !== "brouillon"} onClick={soumettre}>
          Soumettre à la validation
        </button>
      </div>
    </div>
  );
}
