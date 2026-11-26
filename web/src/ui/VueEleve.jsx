// Issue #184 — Vue élève simulée (Claude)
import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Erreur } from "../composants.jsx";
import { naviguer } from "../navigation.js";
import { libelleNiveauParcours } from "../parcours.js";
import { entrerEnSimulation } from "../simulation.js";

const CHEMINS = {
  enseignant: { liste: "/enseignants/simulation/classes", ouvrir: "/enseignants/simulation" },
  admin: { liste: "/admin/simulation/classes", ouvrir: "/admin/simulation" },
};

/** « Voir comme un élève » : choix de la classe, puis l'espace élève avec un élève fictif (espaces professeur et
 * administrateur). Le serveur ne propose que les classes autorisées et revérifie le droit à chaque requête. */
export default function VueEleve({ jeton, onExpire, role = "enseignant" }) {
  const [classes, setClasses] = useState(null);
  const [erreur, setErreur] = useState(null);
  const [envoi, setEnvoi] = useState(null);
  const chemins = CHEMINS[role];

  useEffect(() => {
    api(chemins.liste, { jeton }).then(setClasses, (err) => (err.status === 401 ? onExpire() : setErreur(err.message)));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- onExpire change à chaque rendu du parent
  }, [jeton, chemins.liste]);

  async function ouvrir(classe) {
    setErreur(null);
    setEnvoi(classe.classe_id);
    try {
      entrerEnSimulation(await api(chemins.ouvrir, { methode: "POST", jeton, corps: { classe_id: classe.classe_id } }));
      naviguer("/eleve");
    } catch (err) {
      if (err.status === 401) return onExpire();
      setErreur(err.message);
      setEnvoi(null);
    }
  }

  return (
    <section className="carte">
      <p>
        Parcourez l'espace élève exactement comme un élève de la classe choisie : mêmes chapitres, cours, ressources,
        exercices et corrections, avec un <strong>élève fictif</strong> qui vous est propre.
      </p>
      <ul className="doux">
        <li>Vos réponses et votre progression sont fictives : elles n'apparaissent ni dans vos listes, ni dans les
          statistiques, ni chez les familles. Vous pouvez les effacer à tout moment.</li>
        <li>Aucun pouvoir {role === "admin" ? "d'administration" : "de professeur"} n'est disponible pendant la
          simulation ; un bouton vous ramène à votre espace.</li>
        <li>Pas encore inclus : les groupes de PKP Anglais, l'espace parent et la vue d'un élève réel.</li>
      </ul>
      <Erreur message={erreur} />
      {classes === null && !erreur && <p className="doux">Chargement…</p>}
      {classes?.length === 0 && <p className="doux">Aucune classe active à simuler.</p>}
      {classes?.length > 0 && (
        <div className="tableau-defilant">
          <table>
            <thead>
              <tr>
                <th scope="col">Classe</th>
                <th scope="col">Matière et niveau</th>
                {role === "admin" && <th scope="col">Professeur</th>}
                <th scope="col">Accès des élèves</th>
                <th scope="col"><span className="visuellement-cache">Action</span></th>
              </tr>
            </thead>
            <tbody>
              {classes.map((c) => (
                <tr key={c.classe_id}>
                  <td>{c.code_classe}</td>
                  <td>
                    {c.domaine} · {c.matiere === "maths" ? libelleNiveauParcours(c.niveau, c.parcours) : c.niveau}
                  </td>
                  {role === "admin" && <td>{c.professeur}</td>}
                  <td>{c.ouverte_aux_eleves ? "Ouvert" : <span className="doux">Fermé : {c.motif_fermeture}</span>}</td>
                  <td>
                    <button
                      type="button"
                      disabled={envoi !== null}
                      aria-label={`Voir comme un élève de ${c.code_classe}`}
                      onClick={() => ouvrir(c)}
                    >
                      {c.en_cours ? "Reprendre la simulation" : "Voir comme un élève"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
