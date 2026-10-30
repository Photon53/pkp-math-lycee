import { useCallback, useEffect, useState } from "react";
import { ouvrirPdf } from "../api.js";
import { Erreur } from "../composants.jsx";
import { Modale, Vide, formaterDate } from "../ui/Cadre.jsx";
import FormulaireRessource from "../ui/FormulaireRessource.jsx";
import Icone from "../ui/Icone.jsx";
import { useApi } from "./useApi.js";

/** Liens et PDF que le professeur destine à ses classes (module 3). */
export default function RessourcesEnseignant({ jeton, onExpire }) {
  const { appeler, erreur, setErreur } = useApi(jeton, onExpire);
  const [ressources, setRessources] = useState(null);
  const [chapitres, setChapitres] = useState([]);
  const [classes, setClasses] = useState([]);
  const [edition, setEdition] = useState(null); // null : fermé ; {} : nouvelle ; ressource : modification

  const charger = useCallback(() => appeler("/enseignants/ressources").then(setRessources, () => {}), [appeler]);

  useEffect(() => {
    charger();
    appeler("/enseignants/cours").then(setChapitres, () => {});
    appeler("/enseignants/classes").then(setClasses, () => {});
  }, [appeler, charger]);

  async function supprimer(r) {
    if (!window.confirm(`Supprimer « ${r.titre} » ? Vos élèves ne la verront plus.`)) return;
    try {
      await appeler(`/enseignants/ressources/${r.id}`, { methode: "DELETE" });
      charger();
    } catch {
      // erreur déjà affichée
    }
  }

  return (
    <>
      <section className="carte">
        <div className="carte-titre">
          <p className="doux" style={{ margin: 0 }}>
            Ajoutez des liens et des PDF sous les cours : vos élèves les trouvent dans « Pour aller plus loin ».
          </p>
          <button onClick={() => setEdition({})}>
            <Icone nom="plus" taille={18} /> Ajouter une ressource
          </button>
        </div>
        <Erreur message={erreur} />
        {ressources === null && <p className="doux">Chargement…</p>}
        {ressources?.length === 0 && <Vide icone="ressources">Aucune ressource pour l'instant.</Vide>}
        {ressources?.length > 0 && (
          <div className="tableau-defilant">
            <table>
              <thead>
                <tr>
                  <th>Ressource</th>
                  <th>Rattachée à</th>
                  <th>Classes</th>
                  <th className="nombre">Ouvertures</th>
                  <th>
                    <span className="visuellement-cache">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {ressources.map((r) => (
                  <tr key={r.id}>
                    <td>
                      <strong>{r.titre}</strong>
                      <div className="aide">
                        {r.type === "pdf" ? (
                          <button className="lien" style={{ padding: 0 }} onClick={() => ouvrirPdf(r.id, jeton).catch((e) => setErreur(e.message))}>
                            PDF
                          </button>
                        ) : (
                          r.domaine
                        )}{" "}
                        · ajoutée le {formaterDate(r.cree_le)}
                      </div>
                      {r.masquee && (
                        <p className="avertissement petit">Masquée par l'administrateur : {r.motif_masquage}</p>
                      )}
                      {r.echecs_lien >= 2 && <p className="avertissement petit">Ce lien ne répond plus : il est caché aux élèves.</p>}
                      {r.type === "pdf" && !r.a_un_fichier && <p className="avertissement petit">Fichier manquant.</p>}
                    </td>
                    <td>{r.rattachement}</td>
                    <td>{r.classes.join(", ")}</td>
                    <td className="nombre">{r.consultations}</td>
                    <td className="nombre">
                      <div className="actions">
                        <button className="icone" onClick={() => setEdition(r)} aria-label={`Modifier ${r.titre}`}>
                          <Icone nom="crayon" />
                        </button>
                        <button className="icone" onClick={() => supprimer(r)} aria-label={`Supprimer ${r.titre}`}>
                          <Icone nom="poubelle" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {edition && (
        <Modale titre={edition.id ? "Modifier la ressource" : "Nouvelle ressource"} onFermer={() => setEdition(null)}>
          <FormulaireRessource
            initiale={edition.id ? edition : null}
            chapitres={chapitres}
            classes={classes}
            appeler={appeler}
            jeton={jeton}
            base="/enseignants/ressources"
            onEnregistree={() => {
              setEdition(null);
              charger();
            }}
          />
        </Modale>
      )}
    </>
  );
}
