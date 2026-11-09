import { useEffect, useState } from "react";
import { Erreur } from "../composants.jsx";
import { naviguer } from "../navigation.js";
import { libelleNiveauParcours, trierChapitres } from "../parcours.js";
import { EditeurLecon } from "../admin/Contenu.jsx";
import Exercices from "../admin/Exercices.jsx";
import { useApi } from "./useApi.js";

const BASE = "/enseignants/validation";
const RACINE = "/enseignant/validation";

/**
 * Page « Validation » d'un professeur validateur en maths (ticket #29) : il consulte, modifie et valide les
 * exercices et les cours de son périmètre (domaine et niveau de ses habilitations). L'API revérifie chaque action.
 * /enseignant/validation : exercices ; /enseignant/validation/cours : cours ; /enseignant/validation/cours/<id> : leçon.
 */
export default function Validation({ jeton, onExpire, chemin = RACINE }) {
  const { appeler, erreur } = useApi(jeton, onExpire);
  const [perimetre, setPerimetre] = useState(null);
  const morceaux = chemin.split("/");
  const competenceId = morceaux[3] === "cours" ? Number(morceaux[4]) || null : null;
  const volet = morceaux[3] === "cours" ? "cours" : "exercices";

  useEffect(() => {
    appeler(`${BASE}/perimetre`).then(setPerimetre, () => {});
  }, [appeler]);

  if (competenceId) {
    return <EditeurLecon jeton={jeton} onExpire={onExpire} competenceId={competenceId} base={BASE} retour={`${RACINE}/cours`} />;
  }

  return (
    <>
      <section className="carte">
        <p className="doux" style={{ marginTop: 0 }}>
          Vous validez :{" "}
          {perimetre
            ? perimetre.map((p) => `${p.libelle}${p.niveau ? ` (${p.niveau})` : " (tous niveaux)"}`).join(", ")
            : "…"}
          . Une question validée que vous modifiez repart « à valider ». Vous ne pouvez pas valider une question dont vous êtes
          l'auteur.
        </p>
        <Erreur message={erreur} />
        <div className="onglets" role="tablist">
          {[
            ["exercices", "Exercices", RACINE],
            ["cours", "Cours", `${RACINE}/cours`],
          ].map(([v, l, vers]) => (
            <button key={v} role="tab" aria-selected={volet === v} className={volet === v ? "onglet actif" : "onglet"} onClick={() => naviguer(vers)}>
              {l}
            </button>
          ))}
        </div>
      </section>
      {volet === "exercices" ? (
        <Exercices jeton={jeton} onExpire={onExpire} base={BASE} />
      ) : (
        <CoursAValider jeton={jeton} onExpire={onExpire} />
      )}
    </>
  );
}

function CoursAValider({ jeton, onExpire }) {
  const { appeler, erreur } = useApi(jeton, onExpire);
  const [chapitres, setChapitres] = useState(null);

  useEffect(() => {
    appeler(`${BASE}/contenu`).then(setChapitres, () => {});
  }, [appeler]);

  return (
    <section className="carte">
      <Erreur message={erreur} />
      {chapitres === null && !erreur && <p className="doux">Chargement…</p>}
      {chapitres?.length === 0 && <p className="doux">Aucun cours dans votre périmètre.</p>}
      {chapitres &&
        trierChapitres(chapitres).map((ch) => (
          <div key={ch.id} style={{ marginBottom: 16 }}>
            <div className="fil">{libelleNiveauParcours(ch.niveau, ch.parcours)}</div>
            <h3 style={{ margin: "2px 0 6px" }}>{ch.titre}</h3>
            <ul style={{ margin: 0, paddingLeft: 20 }}>
              {ch.competences.map((c) => (
                <li key={c.id}>
                  <button className="lien" style={{ padding: 0 }} onClick={() => naviguer(`${RACINE}/cours/${c.id}`)}>
                    {c.libelle}
                  </button>{" "}
                  <span className="doux petit">
                    {c.code} · {c.nb_questions} question(s){c.a_une_lecon ? "" : " · sans cours"}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ))}
    </section>
  );
}
