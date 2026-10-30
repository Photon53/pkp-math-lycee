import { Fragment, useEffect, useState } from "react";
import { Erreur } from "../composants.jsx";
import { useApi } from "../enseignant/useApi.js";
import { Pagination, Vide, formaterDate } from "../ui/Cadre.jsx";

const OBJETS = ["enseignant", "eleve", "chapitre", "competence", "lecon", "question", "ressource", "domaine"];

/** Journal des actions d'administration, en lecture seule (EA3.23). */
export default function Journal({ jeton, onExpire }) {
  const { appeler, erreur } = useApi(jeton, onExpire);
  const [objet, setObjet] = useState("");
  const [page, setPage] = useState(1);
  const [donnees, setDonnees] = useState(null);
  const [detail, setDetail] = useState(null);

  useEffect(() => {
    const params = new URLSearchParams({ page: String(page) });
    if (objet) params.set("objet", objet);
    appeler(`/admin/journal?${params}`).then(setDonnees, () => {});
  }, [appeler, objet, page]);

  return (
    <section className="carte">
      <div className="filtres">
        <div style={{ maxWidth: 260 }}>
          <label htmlFor="j-objet">Objet</label>
          <select
            id="j-objet"
            value={objet}
            onChange={(e) => {
              setObjet(e.target.value);
              setPage(1);
            }}
          >
            <option value="">Tous</option>
            {OBJETS.map((o) => (
              <option key={o} value={o}>
                {o}
              </option>
            ))}
          </select>
        </div>
      </div>
      <Erreur message={erreur} />
      {donnees === null && <p className="doux">Chargement…</p>}
      {donnees?.total === 0 && <Vide icone="journal">Aucune action enregistrée.</Vide>}
      {donnees?.total > 0 && (
        <>
          <div className="tableau-defilant">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Administrateur</th>
                  <th>Action</th>
                  <th>Objet</th>
                  <th>
                    <span className="visuellement-cache">Détail</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {donnees.elements.map((j) => (
                  <Fragment key={j.id}>
                    <tr>
                      <td className="chiffres">{formaterDate(j.le, { heure: true })}</td>
                      <td>{j.admin ?? "—"}</td>
                      <td>
                        <span className="badge neutre">{j.action}</span>
                      </td>
                      <td>
                        {j.objet}
                        {j.objet_id != null && <span className="doux"> #{j.objet_id}</span>}
                      </td>
                      <td className="nombre">
                        {(j.avant || j.apres) && (
                          <button className="lien petit" onClick={() => setDetail(detail === j.id ? null : j.id)}>
                            {detail === j.id ? "Masquer" : "Avant / après"}
                          </button>
                        )}
                      </td>
                    </tr>
                    {detail === j.id && (
                      <tr className="detail">
                        <td colSpan={5}>
                          <div className="ligne">
                            <pre className="petit">{JSON.stringify(j.avant, null, 2) ?? "—"}</pre>
                            <pre className="petit">{JSON.stringify(j.apres, null, 2) ?? "—"}</pre>
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={page} total={donnees.total} onChange={setPage} />
        </>
      )}
    </section>
  );
}
