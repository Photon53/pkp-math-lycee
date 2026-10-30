import { useCallback, useEffect, useState } from "react";
import { ouvrirPdf } from "../api.js";
import { Erreur, Onglets } from "../composants.jsx";
import { useApi } from "../enseignant/useApi.js";
import { Modale, Vide, formaterDate } from "../ui/Cadre.jsx";
import FormulaireRessource from "../ui/FormulaireRessource.jsx";
import Icone from "../ui/Icone.jsx";

/** Ressources communes, modération des ressources des professeurs, domaines interdits (EA5.1 à EA5.10). */
export default function RessourcesAdmin({ jeton, onExpire }) {
  const { appeler, erreur, setErreur } = useApi(jeton, onExpire);
  const [onglet, setOnglet] = useState("communes");
  const [liste, setListe] = useState(null);
  const [chapitres, setChapitres] = useState([]);
  const [edition, setEdition] = useState(null);
  const [masquage, setMasquage] = useState(null);

  const charger = useCallback(() => {
    if (onglet === "domaines") return Promise.resolve();
    setListe(null);
    return appeler(`/admin/ressources?portee=${onglet === "communes" ? "commune" : "classe"}`).then(setListe, () => {});
  }, [appeler, onglet]);

  useEffect(() => {
    charger();
  }, [charger]);

  useEffect(() => {
    appeler("/admin/contenu").then(setChapitres, () => {});
  }, [appeler]);

  async function basculerMasquage(r, motif) {
    try {
      await appeler(`/admin/ressources/${r.id}/masquage`, { methode: "POST", corps: { masquee: !r.masquee, motif } });
      setMasquage(null);
      charger();
    } catch {
      // erreur déjà affichée
    }
  }

  async function supprimer(r) {
    if (!window.confirm(`Supprimer définitivement « ${r.titre} » ?`)) return;
    try {
      await appeler(`/admin/ressources/${r.id}`, { methode: "DELETE" });
      charger();
    } catch {
      // erreur déjà affichée
    }
  }

  return (
    <>
      <Onglets
        valeur={onglet}
        onChange={setOnglet}
        options={[
          ["communes", "Ressources communes"],
          ["professeurs", "Ressources des professeurs"],
          ["domaines", "Domaines interdits"],
        ]}
      />
      {onglet === "domaines" ? (
        <Domaines appeler={appeler} erreur={erreur} />
      ) : (
        <section className="carte">
          <div className="carte-titre">
            <p className="doux" style={{ margin: 0 }}>
              {onglet === "communes"
                ? "Visibles par tous les professeurs, et par les élèves dont la classe a ouvert le chapitre."
                : "Ajoutées par les professeurs pour leurs classes. Masquez une ressource inadaptée : le professeur voit le motif."}
            </p>
            {onglet === "communes" && (
              <button onClick={() => setEdition({})}>
                <Icone nom="plus" taille={18} /> Ajouter une ressource
              </button>
            )}
          </div>
          <Erreur message={erreur} />
          {liste === null && <p className="doux">Chargement…</p>}
          {liste?.length === 0 && <Vide icone="ressources">Aucune ressource.</Vide>}
          {liste?.length > 0 && (
            <div className="tableau-defilant">
              <table>
                <thead>
                  <tr>
                    <th>Ressource</th>
                    <th>Rattachée à</th>
                    {onglet === "professeurs" && <th>Auteur</th>}
                    <th>État</th>
                    <th className="nombre">Ouvertures</th>
                    <th>
                      <span className="visuellement-cache">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {liste.map((r) => (
                    <tr key={r.id} className={r.masquee ? "estompe" : ""}>
                      <td>
                        <strong>{r.titre}</strong>
                        <div className="aide">
                          {r.type === "pdf" ? (
                            <button className="lien" style={{ padding: 0 }} onClick={() => ouvrirPdf(r.id, jeton).catch((e) => setErreur(e.message))}>
                              PDF{r.licence && ` · ${r.licence}`}
                            </button>
                          ) : (
                            <a href={r.url} target="_blank" rel="noopener noreferrer">
                              {r.domaine}
                            </a>
                          )}{" "}
                          · {formaterDate(r.cree_le)}
                        </div>
                      </td>
                      <td>{r.rattachement}</td>
                      {onglet === "professeurs" && (
                        <td>
                          {r.auteur}
                          <div className="aide">{r.classes.join(", ")}</div>
                        </td>
                      )}
                      <td>
                        {r.masquee ? (
                          <span className="badge neutre" title={r.motif_masquage}>Masquée</span>
                        ) : r.echecs_lien >= 2 ? (
                          <span className="badge ko">Lien mort</span>
                        ) : r.echecs_lien === 1 ? (
                          <span className="badge alerte">Lien à vérifier</span>
                        ) : (
                          <span className="badge ok">Visible</span>
                        )}
                      </td>
                      <td className="nombre">{r.consultations}</td>
                      <td className="nombre">
                        <div className="actions">
                          {onglet === "communes" && (
                            <button className="icone" aria-label={`Modifier ${r.titre}`} onClick={() => setEdition(r)}>
                              <Icone nom="crayon" />
                            </button>
                          )}
                          <button
                            className="secondaire petit"
                            onClick={() => (r.masquee ? basculerMasquage(r, null) : setMasquage(r))}
                          >
                            {r.masquee ? "Réafficher" : "Masquer"}
                          </button>
                          <button className="icone" aria-label={`Supprimer ${r.titre}`} onClick={() => supprimer(r)}>
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
      )}

      {edition && (
        <Modale titre={edition.id ? "Modifier la ressource commune" : "Nouvelle ressource commune"} onFermer={() => setEdition(null)}>
          <FormulaireRessource
            initiale={edition.id ? edition : null}
            chapitres={chapitres}
            appeler={appeler}
            jeton={jeton}
            base="/admin/ressources"
            onEnregistree={() => {
              setEdition(null);
              charger();
            }}
          />
        </Modale>
      )}
      {masquage && <Masquage ressource={masquage} onFermer={() => setMasquage(null)} onValider={(motif) => basculerMasquage(masquage, motif)} />}
    </>
  );
}

function Masquage({ ressource, onFermer, onValider }) {
  const [motif, setMotif] = useState("");
  return (
    <Modale titre={`Masquer « ${ressource.titre} »`} onFermer={onFermer}>
      <label htmlFor="m-motif">Motif (visible par le professeur)</label>
      <textarea id="m-motif" rows={3} maxLength={300} value={motif} onChange={(e) => setMotif(e.target.value)} />
      <div className="actions">
        <button disabled={!motif.trim()} onClick={() => onValider(motif.trim())}>
          Masquer
        </button>
      </div>
    </Modale>
  );
}

function Domaines({ appeler, erreur }) {
  const [domaines, setDomaines] = useState(null);
  const [nouveau, setNouveau] = useState("");

  const charger = useCallback(() => appeler("/admin/domaines-interdits").then(setDomaines, () => {}), [appeler]);
  useEffect(() => {
    charger();
  }, [charger]);

  async function ajouter(e) {
    e.preventDefault();
    try {
      await appeler("/admin/domaines-interdits", { methode: "POST", corps: { domaine: nouveau } });
      setNouveau("");
      charger();
    } catch {
      // erreur déjà affichée
    }
  }

  async function retirer(d) {
    try {
      await appeler(`/admin/domaines-interdits/${d.id}`, { methode: "DELETE" });
      charger();
    } catch {
      // erreur déjà affichée
    }
  }

  return (
    <section className="carte">
      <p className="doux">Un lien vers un de ces domaines, ou un de leurs sous-domaines, est refusé à l'enregistrement.</p>
      <form className="filtres" onSubmit={ajouter}>
        <div style={{ flexGrow: 3 }}>
          <label htmlFor="d-domaine">Domaine</label>
          <input id="d-domaine" required placeholder="ex. exemple.com" value={nouveau} onChange={(e) => setNouveau(e.target.value)} />
        </div>
        <button type="submit" style={{ flexGrow: 0 }}>
          Interdire
        </button>
      </form>
      <Erreur message={erreur} />
      {domaines?.length === 0 && <p className="doux">Aucun domaine interdit.</p>}
      <ul className="liste-cours">
        {domaines?.map((d) => (
          <li key={d.id}>
            <code>{d.domaine}</code>
            <button className="lien petit" onClick={() => retirer(d)}>
              Retirer
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
