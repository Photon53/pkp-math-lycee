import { useEffect, useState } from "react";
import { Erreur } from "../composants.jsx";
import Cours from "../eleve/Cours.jsx";
import { naviguer } from "../navigation.js";
import { useApi } from "./useApi.js";

export const NIVEAUX = [
  ["2nde", "Seconde"],
  ["1re", "Première"],
  ["Tle", "Terminale"],
];

/**
 * Tous les cours de la banque, y compris les chapitres pas encore ouverts aux élèves (module 2).
 * L'adresse /enseignant/cours/<id> ouvre une leçon : elle peut être partagée ou mise en favori.
 */
export default function CoursEnseignant({ jeton, onExpire, chemin }) {
  const { appeler, erreur } = useApi(jeton, onExpire);
  const [niveau, setNiveau] = useState("");
  const [recherche, setRecherche] = useState("");
  const [terme, setTerme] = useState("");
  const [sommaire, setSommaire] = useState(null);
  const competenceId = Number(chemin.split("/")[3]) || null;

  // Recherche lancée 300 ms après la dernière frappe.
  useEffect(() => {
    const minuterie = setTimeout(() => setTerme(recherche.trim()), 300);
    return () => clearTimeout(minuterie);
  }, [recherche]);

  useEffect(() => {
    const params = new URLSearchParams();
    if (niveau) params.set("niveau", niveau);
    if (terme) params.set("q", terme);
    setSommaire(null);
    appeler(`/enseignants/cours${params.size ? `?${params}` : ""}`).then(setSommaire, () => setSommaire([]));
  }, [appeler, niveau, terme]);

  const choisir = (id) => naviguer(id == null ? "/enseignant/cours" : `/enseignant/cours/${id}`);

  return (
    <>
      {competenceId == null && (
        <div className="carte filtres" role="search">
          <div>
            <label htmlFor="cours-niveau">Niveau</label>
            <select id="cours-niveau" value={niveau} onChange={(e) => setNiveau(e.target.value)}>
              <option value="">Tous</option>
              {NIVEAUX.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </div>
          <div style={{ flexGrow: 3 }}>
            <label htmlFor="cours-recherche">Rechercher dans les cours</label>
            <input
              id="cours-recherche"
              type="search"
              placeholder="ex. logarithme, second degré, vecteurs…"
              value={recherche}
              onChange={(e) => setRecherche(e.target.value)}
            />
          </div>
        </div>
      )}
      <Erreur message={erreur} />
      <Cours
        jeton={jeton}
        onExpire={onExpire}
        base="/enseignants/cours"
        enseignant
        sommaireFourni={sommaire}
        competenceId={competenceId}
        onChoisir={choisir}
      />
    </>
  );
}
