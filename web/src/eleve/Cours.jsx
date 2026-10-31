import { useEffect, useState } from "react";
import { api, ouvrirLien, ouvrirPdf } from "../api.js";
import { Difficulte, Erreur, LIBELLES_TYPE } from "../composants.jsx";
import { Maths } from "../maths.jsx";
import { libelleNiveauParcours, trierChapitres } from "../parcours.js";
import Icone from "../ui/Icone.jsx";
import { ErreursFrequentes, Methodes, Objectifs } from "../ui/Pedagogie.jsx";
import ParcoursPKP from "./ParcoursPKP.jsx";

/**
 * Sommaire des cours et lecture d'une leçon (résumé, cours, ressources).
 * Partagé par l'élève (`base` = "/cours", chapitres ouverts de sa classe) et le professeur
 * (`base` = "/enseignants/cours", toute la banque, avec projection, impression et exercices).
 * `competenceId` ouvre directement une leçon (lien « Revoir le cours » depuis un exercice).
 */
export default function Cours({
  jeton,
  onExpire,
  competenceId,
  onChoisir,
  base = "/cours",
  enseignant = false,
  sommaireFourni,
  onRetourExercice = null,
  onEntrainer = null,
  onVoirHistorique = null,
}) {
  const [sommaire, setSommaire] = useState(null);
  const [lecon, setLecon] = useState(null);
  const [erreur, setErreur] = useState(null);

  function gerer(err) {
    if (err.status === 401) onExpire();
    else if (err.status === 404) setErreur("Pas encore de cours pour cette compétence.");
    else setErreur(err.message);
  }

  useEffect(() => {
    if (sommaireFourni) return;
    api(base, { jeton }).then(setSommaire, gerer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jeton, base, sommaireFourni]);

  useEffect(() => {
    setLecon(null);
    setErreur(null);
    if (competenceId == null) return;
    let actif = true;
    api(`${base}/${competenceId}`, { jeton }).then(
      (l) => actif && setLecon(l),
      (err) => actif && gerer(err),
    );
    window.scrollTo?.(0, 0);
    return () => {
      actif = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [competenceId, jeton, base]);

  if (competenceId != null) {
    return (
      <Lecon
        lecon={lecon}
        erreur={erreur}
        jeton={jeton}
        enseignant={enseignant}
        base={base}
        onRetour={() => onChoisir(null)}
        onRetourExercice={onRetourExercice}
        onEntrainer={onEntrainer}
        onVoirHistorique={onVoirHistorique}
      />
    );
  }

  const brut = sommaireFourni ?? sommaire;
  // Le professeur voit toute la banque : on la range par niveau puis par parcours (voie générale, technologique…).
  const chapitres = enseignant && brut ? trierChapitres(brut) : brut;
  const groupe = (ch) => `${ch.niveau}|${ch.parcours}`;
  return (
    <section className="carte">
      {!enseignant && <h2>Cours</h2>}
      <Erreur message={erreur} />
      {chapitres === null && !erreur && <p className="doux">Chargement…</p>}
      {chapitres?.length === 0 && (
        <p className="doux">{enseignant ? "Aucun cours ne correspond." : "Aucun cours pour ton niveau pour l'instant."}</p>
      )}
      {chapitres?.map((chapitre, i) => (
        <div key={chapitre.id}>
          {enseignant && chapitre.parcours && (i === 0 || groupe(chapitres[i - 1]) !== groupe(chapitre)) && (
            <h2 className="titre-parcours">{libelleNiveauParcours(chapitre.niveau, chapitre.parcours)}</h2>
          )}
          <h3>
            {chapitre.titre}
            {enseignant && (
              <span className="petit" style={{ fontWeight: 400, marginLeft: 8 }}>
                {chapitre.ouvert_dans?.length ? (
                  <span className="badge ok">Ouvert : {chapitre.ouvert_dans.join(", ")}</span>
                ) : (
                  <span className="badge neutre">Fermé dans vos classes</span>
                )}
              </span>
            )}
          </h3>
          <ul className="liste-cours">
            {chapitre.competences.map((c) => (
              <li key={c.id}>
                {c.a_une_lecon ? (
                  <button className="lien" onClick={() => onChoisir(c.id)}>
                    {c.libelle}
                  </button>
                ) : (
                  <span className="doux">{c.libelle} (cours à venir)</span>
                )}
                {enseignant && <span className="doux petit">{c.nb_questions} exercice(s)</span>}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  );
}

function Lecon({ lecon, erreur, jeton, enseignant, base, onRetour, onRetourExercice, onEntrainer, onVoirHistorique }) {
  const [projection, setProjection] = useState(false);

  useEffect(() => {
    if (!projection) return;
    const touche = (e) => e.key === "Escape" && setProjection(false);
    document.addEventListener("keydown", touche);
    return () => document.removeEventListener("keydown", touche);
  }, [projection]);

  return (
    <article className={projection ? "carte lecon projection" : "carte lecon"}>
      <div className="outils-lecon">
        {onRetourExercice && !projection ? (
          <button onClick={onRetourExercice}>← Revenir à l'exercice</button>
        ) : (
          <button className="lien" onClick={projection ? () => setProjection(false) : onRetour}>
            {projection ? "Quitter la projection (Échap)" : "← Tous les cours"}
          </button>
        )}
        {enseignant && lecon && !projection && (
          <span className="actions" style={{ marginTop: 0 }}>
            <button className="secondaire petit" onClick={() => setProjection(true)}>
              <Icone nom="ecran" taille={16} /> Projeter
            </button>
            <button className="secondaire petit" onClick={() => window.print()}>
              <Icone nom="imprimer" taille={16} /> Imprimer
            </button>
          </span>
        )}
      </div>
      <Erreur message={erreur} />
      {lecon === null && !erreur && <p className="doux">Chargement…</p>}
      {lecon && (
        <>
          <p className="doux">{lecon.chapitre}</p>
          <h2>{lecon.libelle}</h2>
          {onEntrainer && onVoirHistorique && (
            <ParcoursPKP
              competenceId={lecon.competence_id}
              libelle={lecon.libelle}
              jeton={jeton}
              onEntrainer={onEntrainer}
              onVoirHistorique={onVoirHistorique}
            />
          )}
          <Objectifs objectifs={lecon.objectifs} />
          <section id="lecon-fiche" className="resume" aria-labelledby="titre-resume">
            <h3 id="titre-resume">L'essentiel</h3>
            <Maths texte={lecon.resume} />
          </section>
          <div id="lecon-cours">
            <Maths texte={lecon.cours} />
          </div>
          <Methodes methodes={lecon.methodes} />
          <ErreursFrequentes erreurs={lecon.erreurs_frequentes} />
          <Ressources ressources={lecon.ressources ?? []} jeton={jeton} />
          {onEntrainer && (
            <div className="actions">
              <button onClick={() => onEntrainer(lecon.competence_id, lecon.libelle)}>S'entraîner sur cette compétence</button>
              {onRetourExercice && (
                <button className="secondaire" onClick={onRetourExercice}>
                  Revenir à l'exercice
                </button>
              )}
            </div>
          )}
          {enseignant && !projection && <ExercicesDeLaCompetence base={base} competenceId={lecon.competence_id} jeton={jeton} />}
        </>
      )}
    </article>
  );
}

export function Ressources({ ressources, jeton }) {
  const [erreur, setErreur] = useState(null);
  if (!ressources.length) return null;

  async function ouvrir(r) {
    setErreur(null);
    try {
      await ouvrirPdf(r.id, jeton);
    } catch (err) {
      setErreur(err.message);
    }
  }

  return (
    <section className="ressources" aria-labelledby="titre-ressources">
      <h3 id="titre-ressources">Pour aller plus loin</h3>
      <Erreur message={erreur} />
      <ul>
        {ressources.map((r) => (
          <li key={r.id} className="ressource">
            <Icone nom={r.type === "pdf" ? "pdf" : "lien"} />
            <div>
              <div className="titre">
                {r.type === "pdf" ? (
                  <button className="lien" onClick={() => ouvrir(r)}>
                    {r.titre}
                  </button>
                ) : (
                  <a href={r.url} target="_blank" rel="noopener noreferrer" onClick={() => ouvrirLien(r, jeton)}>
                    {r.titre}
                  </a>
                )}
              </div>
              <div className="doux petit">
                {r.type === "pdf" ? `PDF${r.taille_octets ? ` · ${Math.ceil(r.taille_octets / 1024)} Ko` : ""}` : r.domaine}
                {r.description && ` — ${r.description}`}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ExercicesDeLaCompetence({ base, competenceId, jeton }) {
  const [questions, setQuestions] = useState(null);
  const [ouvert, setOuvert] = useState(false);

  useEffect(() => {
    if (!ouvert || questions) return;
    api(`${base}/${competenceId}/questions`, { jeton }).then(setQuestions, () => setQuestions([]));
  }, [ouvert, questions, base, competenceId, jeton]);

  return (
    <details className="ressources" onToggle={(e) => setOuvert(e.currentTarget.open)}>
      <summary>
        <strong>Exercices de cette compétence, avec solutions</strong>
      </summary>
      {questions === null && <p className="doux">Chargement…</p>}
      {questions?.length === 0 && <p className="doux">Aucun exercice.</p>}
      {questions?.length > 0 && (
        <div className="tableau-defilant">
          <table>
            <thead>
              <tr>
                <th>Énoncé</th>
                <th>Type</th>
                <th>Difficulté</th>
                <th>Solution</th>
              </tr>
            </thead>
            <tbody>
              {questions.map((q) => (
                <tr key={q.id}>
                  <td>
                    <Maths texte={q.enonce} enLigne />
                  </td>
                  <td>{LIBELLES_TYPE[q.type]}</td>
                  <td>
                    <Difficulte niveau={q.difficulte} />
                  </td>
                  <td>
                    <code>{q.solution}</code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </details>
  );
}
