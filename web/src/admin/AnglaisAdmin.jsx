import { Fragment, useCallback, useEffect, useState } from "react";
import { telecharger } from "../anglais/SeancesAnglais.jsx";
import { Erreur, Onglets } from "../composants.jsx";
import { useApi } from "../enseignant/useApi.js";
import { Modale, Vide } from "../ui/Cadre.jsx";

const pluriel = (n) => `${n} élève${n > 1 ? "s" : ""}`;

/** PKP Anglais côté administrateur : groupes 4e/3e de tous les professeurs d'anglais, et catalogue des séances. */
export default function AnglaisAdmin({ jeton, onExpire }) {
  const [onglet, setOnglet] = useState("groupes");
  return (
    <>
      <Onglets
        valeur={onglet}
        onChange={setOnglet}
        options={[
          ["groupes", "Groupes et élèves"],
          ["seances", "Séances"],
        ]}
      />
      {onglet === "groupes" ? <Groupes jeton={jeton} onExpire={onExpire} /> : <Seances jeton={jeton} onExpire={onExpire} />}
    </>
  );
}

function Groupes({ jeton, onExpire }) {
  const { appeler, erreur } = useApi(jeton, onExpire);
  const [groupes, setGroupes] = useState(null);
  const [profs, setProfs] = useState([]);
  const [ouvert, setOuvert] = useState(null);
  const [transfert, setTransfert] = useState(null);
  const [message, setMessage] = useState(null);

  const charger = useCallback(() => appeler("/admin/anglais/groupes").then(setGroupes, () => {}), [appeler]);

  useEffect(() => {
    charger();
    appeler("/admin/enseignants").then(setProfs, () => {});
  }, [appeler, charger]);

  async function action(promesse, texte) {
    setMessage(null);
    try {
      await promesse;
      setMessage(texte);
      await charger();
      return true;
    } catch {
      return false; // erreur déjà affichée
    }
  }

  function supprimerGroupe(g) {
    if (!window.confirm(`Supprimer le groupe « ${g.nom} » de ${g.enseignant} ?\n\nSes ${pluriel(g.eleves.length)} seront supprimés définitivement.`)) return;
    action(appeler(`/admin/anglais/groupes/${g.id}`, { methode: "DELETE" }), `Groupe ${g.nom} supprimé.`);
  }

  function supprimerEleve(g, e) {
    if (!window.confirm(`Supprimer ${e.prenom} du groupe « ${g.nom} » ?\n\nSon prénom est effacé définitivement.`)) return;
    action(appeler(`/admin/anglais/eleves/${e.id}`, { methode: "DELETE" }), `${e.prenom} supprimé(e).`);
  }

  return (
    <section className="carte">
      <p className="doux">
        Groupes créés par les professeurs d'anglais, séparés des classes de maths. L'administrateur ne crée pas de groupe : il transfère
        ceux d'un professeur remplacé et efface les données à la demande (RGPD).
      </p>
      {message && (
        <p className="succes" role="status">
          {message}
        </p>
      )}
      <Erreur message={erreur} />
      {groupes === null && <p className="doux">Chargement…</p>}
      {groupes?.length === 0 && <Vide icone="classes">Aucun groupe d'anglais.</Vide>}
      {groupes?.length > 0 && (
        <div className="tableau-defilant">
          <table>
            <thead>
              <tr>
                <th>Groupe</th>
                <th>Niveau</th>
                <th>Professeur</th>
                <th className="nombre">Élèves</th>
                <th className="nombre">Actions</th>
              </tr>
            </thead>
            <tbody>
              {groupes.map((g) => (
                <Fragment key={g.id}>
                  <tr>
                    <td>{g.nom}</td>
                    <td>{g.niveau}</td>
                    <td>{g.enseignant}</td>
                    <td className="nombre">
                      <button className="lien" aria-expanded={ouvert === g.id} onClick={() => setOuvert(ouvert === g.id ? null : g.id)}>
                        {pluriel(g.eleves.length)}
                      </button>
                    </td>
                    <td className="nombre">
                      <div className="actions">
                        <button className="secondaire petit" onClick={() => setTransfert(g)}>
                          Transférer
                        </button>
                        <button className="danger petit" onClick={() => supprimerGroupe(g)} aria-label={`Supprimer le groupe ${g.nom}`}>
                          Supprimer
                        </button>
                      </div>
                    </td>
                  </tr>
                  {ouvert === g.id && (
                    <tr>
                      <td colSpan={5}>
                        {g.eleves.length === 0 ? (
                          <p className="doux">Aucun élève inscrit.</p>
                        ) : (
                          <ul className="liste-eleves-anglais">
                            {g.eleves.map((e) => (
                              <li key={e.id}>
                                <span>{e.prenom}</span>
                                <button className="lien" onClick={() => supprimerEleve(g, e)} aria-label={`Supprimer ${e.prenom}`}>
                                  Supprimer
                                </button>
                              </li>
                            ))}
                          </ul>
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {transfert && (
        <TransfertGroupe
          groupe={transfert}
          autres={profs.filter((p) => p.id !== transfert.enseignant_id && p.actif && p.enseigne_anglais)}
          onFermer={() => setTransfert(null)}
          onValider={async (versId) => {
            const ok = await action(
              appeler(`/admin/anglais/groupes/${transfert.id}/transfert`, { methode: "POST", corps: { vers_enseignant_id: versId } }),
              `Groupe ${transfert.nom} transféré.`,
            );
            if (ok) setTransfert(null);
          }}
        />
      )}
    </section>
  );
}

function TransfertGroupe({ groupe, autres, onFermer, onValider }) {
  const [vers, setVers] = useState(autres[0]?.id ?? "");
  return (
    <Modale titre={`Transférer le groupe ${groupe.nom}`} onFermer={onFermer}>
      {autres.length === 0 ? (
        <p className="doux">Aucun autre professeur d'anglais actif. Cochez la discipline Anglais d'un professeur dans « Professeurs ».</p>
      ) : (
        <>
          <p className="doux">Le groupe et ses {pluriel(groupe.eleves.length)} passent au professeur d'anglais choisi.</p>
          <label htmlFor="ta-vers">Vers</label>
          <select id="ta-vers" value={vers} onChange={(e) => setVers(Number(e.target.value))}>
            {autres.map((p) => (
              <option key={p.id} value={p.id}>
                {p.nom} ({p.email})
              </option>
            ))}
          </select>
          <div className="actions">
            <button disabled={!vers} onClick={() => onValider(Number(vers))}>
              Transférer
            </button>
          </div>
        </>
      )}
    </Modale>
  );
}

function Seances({ jeton, onExpire }) {
  const { appeler, erreur, setErreur } = useApi(jeton, onExpire);
  const [seances, setSeances] = useState(null);
  const [encours, setEncours] = useState("");

  useEffect(() => {
    appeler("/admin/anglais/seances").then(setSeances, () => {});
  }, [appeler]);

  async function pdf(code, publicCible) {
    setErreur(null);
    setEncours(`${code}-${publicCible}`);
    try {
      await telecharger(code, publicCible, jeton, "/admin/anglais");
    } catch (err) {
      setErreur(err.message);
    } finally {
      setEncours("");
    }
  }

  return (
    <section className="carte">
      <p className="doux">Séances proposées aux professeurs d'anglais. Le contenu se modifie dans le dépôt (contenu/anglais), puis est relu par un enseignant.</p>
      <Erreur message={erreur} />
      {seances === null && <p className="doux">Chargement…</p>}
      {seances?.length > 0 && (
        <div className="tableau-defilant">
          <table>
            <thead>
              <tr>
                <th>Code</th>
                <th>Niveau</th>
                <th>Titre</th>
                <th>Objectif</th>
                <th className="nombre">Cahiers PDF</th>
              </tr>
            </thead>
            <tbody>
              {seances.map((s) => (
                <tr key={s.code}>
                  <td>
                    <code>{s.code}</code>
                  </td>
                  <td>{s.niveau}</td>
                  <td>{s.titre}</td>
                  <td>{s.objectif}</td>
                  <td className="nombre">
                    <div className="actions">
                      {[["eleve", "Élève"], ["animateur", "Animateur"]].map(([publicCible, libelle]) => (
                        <button
                          key={publicCible}
                          className="secondaire petit"
                          disabled={!!encours}
                          onClick={() => pdf(s.code, publicCible)}
                          aria-label={`PDF ${libelle.toLowerCase()} ${s.code}`}
                        >
                          {encours === `${s.code}-${publicCible}` ? "…" : libelle}
                        </button>
                      ))}
                    </div>
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
