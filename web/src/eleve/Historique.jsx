import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Erreur, LIBELLES_TYPE } from "../composants.jsx";
import { Maths } from "../maths.jsx";
import { Pagination, formaterDate } from "../ui/Cadre.jsx";
import { Correction } from "../ui/Pedagogie.jsx";

const TAILLE_PAGE = 30;

/**
 * Historique des réponses : la question, la réponse donnée, la réponse attendue et la correction.
 * Partagé par l'élève (`chemin` = "/eleves/moi/historique", avec les boutons Cours et S'entraîner)
 * et par le professeur qui suit un élève (`chemin` = "/enseignants/eleves/<id>/historique").
 */
export default function Historique({
  jeton,
  onExpire,
  chemin,
  onVoirCours,
  onEntrainer,
  eleve = true,
  competenceId = null,
  onToutVoir,
}) {
  const [page, setPage] = useState(1);
  const [erreursSeulement, setErreursSeulement] = useState(false);
  const [donnees, setDonnees] = useState(null);
  const [erreur, setErreur] = useState(null);

  useEffect(() => {
    let actif = true;
    setErreur(null);
    const filtre = competenceId ? `&competence_id=${competenceId}` : "";
    api(`${chemin}?page=${page}&erreurs=${erreursSeulement}${filtre}`, { jeton }).then(
      (d) => actif && setDonnees(d),
      (err) => actif && (err.status === 401 ? onExpire() : setErreur(err.message)),
    );
    return () => {
      actif = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chemin, page, erreursSeulement, jeton, competenceId]);

  const tu = (moi, lui) => (eleve ? moi : lui);

  return (
    <section className={eleve ? "carte" : ""}>
      {eleve && <h2>Mon historique</h2>}
      {competenceId && donnees?.elements[0] && (
        <p className="info petit">
          Compétence : <strong>{donnees.elements[0].competence}</strong>
          {onToutVoir && (
            <button className="lien petit" onClick={onToutVoir}>
              Voir tout mon historique
            </button>
          )}
        </p>
      )}
      <Erreur message={erreur} />
      {donnees === null && !erreur && <p className="doux">Chargement…</p>}
      {donnees && (
        <>
          <div className="filtres" style={{ alignItems: "center" }}>
            <p className="doux" style={{ margin: 0 }}>
              {donnees.total} réponse{donnees.total > 1 ? "s" : ""} · {donnees.erreurs} erreur{donnees.erreurs > 1 ? "s" : ""}
            </p>
            <label className="case" style={{ margin: 0, flexGrow: 0 }}>
              <input
                type="checkbox"
                checked={erreursSeulement}
                onChange={(e) => {
                  setErreursSeulement(e.target.checked);
                  setPage(1);
                }}
              />
              {tu("Seulement mes erreurs", "Seulement les erreurs")}
            </label>
          </div>
          {donnees.elements.length === 0 && (
            <p className="doux">
              {erreursSeulement
                ? tu("Aucune erreur : bravo !", "Aucune erreur.")
                : tu("Pas encore de réponse : lance une séance dans « S'entraîner ».", "Pas encore de réponse.")}
            </p>
          )}
          <ol className="historique">
            {donnees.elements.map((r) => (
              <Reponse key={r.id} r={r} onVoirCours={onVoirCours} onEntrainer={onEntrainer} eleve={eleve} />
            ))}
          </ol>
          <Pagination page={page} total={donnees.total} taille={TAILLE_PAGE} onChange={setPage} />
        </>
      )}
    </section>
  );
}

function Reponse({ r, onVoirCours, onEntrainer, eleve }) {
  return (
    <li className={`reponse-historique ${r.correcte ? "ok" : "ko"}`}>
      <div className="meta">
        <span className="doux petit">
          {formaterDate(r.repondu_le, { heure: true })} · {r.chapitre} › {r.competence}
        </span>
        <span className={`badge ${r.correcte ? "ok" : "ko"}`}>{r.correcte ? "Réussie" : "À revoir"}</span>
      </div>
      <Maths texte={r.enonce} enLigne />
      <p className="petit">
        {eleve ? "Ta réponse" : "Réponse donnée"} : <code>{r.reponse_donnee}</code>
        {!r.correcte && (
          <>
            {" "}
            · Réponse attendue : <code>{r.solution}</code>
          </>
        )}{" "}
        <span className="doux">
          · {LIBELLES_TYPE[r.type]} · {r.duree_s} s
        </span>
      </p>
      <Correction correction={r.correction} />
      {(onVoirCours || onEntrainer) && (
        <div className="actions" style={{ marginTop: 4 }}>
          {onVoirCours && (
            <button className="secondaire petit" onClick={() => onVoirCours(r.competence_id)}>
              Revoir le cours
            </button>
          )}
          {onEntrainer && (
            <button className="secondaire petit" onClick={() => onEntrainer(r.competence_id, r.competence)}>
              S'entraîner sur cette compétence
            </button>
          )}
        </div>
      )}
    </li>
  );
}
