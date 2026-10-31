import { useEffect, useState } from "react";
import { Erreur } from "../composants.jsx";
import Cours from "../eleve/Cours.jsx";
import { naviguer } from "../navigation.js";
import { LIBELLES_PARCOURS, NIVEAUX, PARCOURS_PAR_NIVEAU } from "../parcours.js";
import { useApi } from "./useApi.js";

export { NIVEAUX };

/**
 * Tous les cours de la banque, y compris les chapitres pas encore ouverts aux élèves (module 2).
 * L'adresse /enseignant/cours/<id> ouvre une leçon : elle peut être partagée ou mise en favori.
 */
export default function CoursEnseignant({ jeton, onExpire, chemin }) {
  const { appeler, erreur } = useApi(jeton, onExpire);
  const [niveau, setNiveau] = useState("");
  const [parcours, setParcours] = useState("");
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
    if (parcours) params.set("parcours", parcours);
    if (terme) params.set("q", terme);
    setSommaire(null);
    appeler(`/enseignants/cours${params.size ? `?${params}` : ""}`).then(setSommaire, () => setSommaire([]));
  }, [appeler, niveau, parcours, terme]);

  const choisir = (id) => naviguer(id == null ? "/enseignant/cours" : `/enseignant/cours/${id}`);

  return (
    <>
      {competenceId == null && (
        <div className="carte filtres" role="search">
          <div>
            <label htmlFor="cours-niveau">Niveau</label>
            <select
              id="cours-niveau"
              value={niveau}
              onChange={(e) => {
                setNiveau(e.target.value);
                setParcours("");
              }}
            >
              <option value="">Tous</option>
              {NIVEAUX.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </div>
          {PARCOURS_PAR_NIVEAU[niveau]?.length > 1 && (
            <div>
              <label htmlFor="cours-parcours">Parcours</label>
              <select id="cours-parcours" value={parcours} onChange={(e) => setParcours(e.target.value)}>
                <option value="">Tous</option>
                {PARCOURS_PAR_NIVEAU[niveau].map((p) => (
                  <option key={p} value={p}>
                    {LIBELLES_PARCOURS[p]}
                  </option>
                ))}
              </select>
            </div>
          )}
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
