// Bandeau commun à toutes les pages de l'admin (CDC V2, § 6.1) : sélecteur de domaine, qui filtre les listes
// (EA.2, recette 5), et recherche globale (EA.1).
import { useEffect, useRef, useState } from "react";
import { useApi } from "../enseignant/useApi.js";
import { naviguer } from "../navigation.js";

/** Ajoute `domaine=` à un chemin d'API quand un domaine est choisi. */
export function avecDomaine(chemin, domaine) {
  if (!domaine) return chemin;
  return `${chemin}${chemin.includes("?") ? "&" : "?"}domaine=${encodeURIComponent(domaine)}`;
}

/** Paramètre de l'adresse de la page (`?q=`, `?onglet=`…), posé par un résultat de la recherche globale. */
export const parametre = (nom) => new URLSearchParams(window.location.search).get(nom) ?? "";

/** Message des pages sans contenu dans le domaine choisi (le contenu des maths n'existe qu'en Maths lycée…). */
export function libelleDomaine(domaines, code) {
  return domaines.find((d) => d.code === code)?.libelle ?? code;
}

export default function BandeauAdmin({ jeton, onExpire, domaines, domaine, onDomaine, onOuvrir }) {
  const { appeler } = useApi(jeton, onExpire);
  const [saisie, setSaisie] = useState("");
  const [resultats, setResultats] = useState(null);
  const [ouvert, setOuvert] = useState(false);
  const zone = useRef(null);

  useEffect(() => {
    const q = saisie.trim();
    if (q.length < 2) {
      setResultats(null);
      return undefined;
    }
    const minuterie = setTimeout(() => {
      const params = new URLSearchParams({ q });
      if (domaine) params.set("domaine", domaine);
      appeler(`/admin/recherche?${params}`).then(
        (r) => {
          setResultats(r);
          setOuvert(true);
        },
        () => setResultats([]),
      );
    }, 250);
    return () => clearTimeout(minuterie);
  }, [appeler, saisie, domaine]);

  useEffect(() => {
    const fermer = (e) => zone.current && !zone.current.contains(e.target) && setOuvert(false);
    document.addEventListener("mousedown", fermer);
    return () => document.removeEventListener("mousedown", fermer);
  }, []);

  function choisir(vers) {
    setOuvert(false);
    setSaisie("");
    naviguer(vers);
    onOuvrir();
  }

  return (
    <div className="bandeau-admin">
      <div className="bandeau-domaine">
        <label htmlFor="admin-domaine">Domaine</label>
        <select id="admin-domaine" value={domaine} onChange={(e) => onDomaine(e.target.value)}>
          <option value="">Tous les domaines</option>
          {domaines.map((d) => (
            <option key={d.code} value={d.code}>
              {d.libelle}
              {d.actif ? "" : " (fermé)"}
            </option>
          ))}
        </select>
      </div>
      <div className="bandeau-recherche" ref={zone}>
        <label htmlFor="admin-recherche">Recherche globale</label>
        <input
          id="admin-recherche"
          type="search"
          placeholder="Compte, élève, classe, chapitre, code…"
          value={saisie}
          onChange={(e) => setSaisie(e.target.value)}
          onFocus={() => resultats && setOuvert(true)}
          onKeyDown={(e) => e.key === "Escape" && setOuvert(false)}
          autoComplete="off"
          aria-controls="admin-resultats"
          aria-expanded={ouvert}
        />
        {ouvert && resultats && (
          <div id="admin-resultats" className="resultats-recherche" role="listbox" aria-label="Résultats de la recherche">
            {resultats.length === 0 ? (
              <p className="doux">Aucun résultat{domaine ? ` dans ${libelleDomaine(domaines, domaine)}` : ""}.</p>
            ) : (
              resultats.map((r, i) => (
                <button key={`${r.type}-${i}`} type="button" className="resultat" role="option" aria-selected="false" onClick={() => choisir(r.vers)}>
                  <span className="badge neutre">{r.type}</span>
                  <strong>{r.libelle}</strong>
                  {r.detail && <span className="doux">{r.detail}</span>}
                </button>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}
