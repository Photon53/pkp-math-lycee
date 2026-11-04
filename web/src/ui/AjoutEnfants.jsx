// Ajouter à une classe (ou à un groupe d'anglais) des enfants déjà créés par l'administrateur dans leur
// famille : recherche par prénom, nom ou identifiant, limitée au niveau de la classe.
import { useEffect, useState } from "react";
import { Erreur } from "../composants.jsx";

export default function AjoutEnfants({ chercher, ajouter, onAjoutes, libelle = "Ajouter des élèves" }) {
  const [q, setQ] = useState("");
  const [trouves, setTrouves] = useState(null);
  const [choisis, setChoisis] = useState([]);
  const [resultat, setResultat] = useState(null);
  const [erreur, setErreur] = useState(null);

  useEffect(() => {
    if (q.trim().length < 2) {
      setTrouves(null);
      return undefined;
    }
    let actif = true;
    const t = setTimeout(() => {
      chercher(q.trim()).then(
        (liste) => actif && (setTrouves(liste), setErreur(null)),
        (err) => actif && setErreur(err.message),
      );
    }, 250);
    return () => {
      actif = false;
      clearTimeout(t);
    };
  }, [q, chercher]);

  async function valider(e) {
    e.preventDefault();
    try {
      const r = await ajouter(choisis.map((c) => c.id));
      setResultat(r);
      setChoisis([]);
      setQ("");
      onAjoutes?.();
    } catch (err) {
      setErreur(err.message);
    }
  }

  return (
    <form onSubmit={valider} className="ajout-enfants">
      <label htmlFor="recherche-enfant">{libelle}</label>
      <input
        id="recherche-enfant"
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Prénom, nom ou identifiant (ex. ines-k7m4)"
        autoComplete="off"
      />
      <p className="aide">
        Les élèves sont créés par l'administrateur avec leur famille et leur niveau. Seuls ceux du même niveau
        apparaissent ; ils gardent leur carte pour toutes leurs matières.
      </p>
      {trouves && (
        trouves.length === 0 ? (
          <p className="doux">Aucun élève de ce niveau ne correspond.</p>
        ) : (
          <ul className="liste-inscriptions">
            {trouves.map((t) => {
              const pris = choisis.some((c) => c.id === t.id);
              return (
                <li key={t.id}>
                  <span>
                    <strong>{t.nom}</strong> <span className="doux">· {t.niveau} · {t.identifiant}</span>
                  </span>
                  {t.deja_inscrit ? (
                    <span className="badge ok">Déjà inscrit</span>
                  ) : (
                    <button
                      type="button"
                      className="secondaire"
                      onClick={() => setChoisis(pris ? choisis.filter((c) => c.id !== t.id) : [...choisis, t])}
                    >
                      {pris ? "Retirer" : "Choisir"}
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        )
      )}
      {choisis.length > 0 && (
        <p>
          À ajouter : {choisis.map((c) => c.nom).join(", ")}
        </p>
      )}
      <Erreur message={erreur} />
      {resultat && (
        <div role="status">
          {resultat.ajoutes.length > 0 && <p className="succes">Ajouté(s) : {resultat.ajoutes.join(", ")}.</p>}
          {resultat.refus.map((r) => (
            <p key={r} className="erreur">{r}</p>
          ))}
        </div>
      )}
      <div className="actions">
        <button type="submit" className="secondaire" disabled={!choisis.length}>
          Ajouter {choisis.length > 1 ? `les ${choisis.length} élèves` : "l'élève"}
        </button>
      </div>
    </form>
  );
}
