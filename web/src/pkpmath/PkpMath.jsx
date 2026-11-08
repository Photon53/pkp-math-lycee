// PKP Math : résumés de cours, fiches d'exercices et corrigés par chapitre, à lire à l'écran ou à exporter
// en PDF. Même module pour l'élève, l'enfant d'une famille, le parent, le professeur et l'administrateur :
// l'API ne renvoie que ce que chacun a le droit de lire (voir api/app/routes/pkp_math.py).
//
// L'export passe par l'impression du navigateur (« Enregistrer au format PDF ») : les formules, rendues par
// KaTeX, gardent toute leur qualité. Tant qu'un contenu n'est pas validé, chaque page porte « NON VALIDÉ ».
import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../api.js";
import { Difficulte, Erreur, Onglets, solutionLisible } from "../composants.jsx";
import { Maths } from "../maths.jsx";
import { NIVEAUX, PARCOURS_PAR_NIVEAU } from "../parcours.js";
import { Modale } from "../ui/Cadre.jsx";

export const DOCUMENTS = [
  ["resume", "Résumé de cours"],
  ["cours", "Cours complet"],
  ["exercices", "Fiche d'exercices"],
  ["corrige", "Corrigé"],
];
const NOM_NIVEAU = Object.fromEntries(NIVEAUX);

function rang(ch) {
  const niveaux = NIVEAUX.map(([v]) => v);
  return [niveaux.indexOf(ch.niveau), (PARCOURS_PAR_NIVEAU[ch.niveau] ?? []).indexOf(ch.parcours), ch.ordre];
}

function trier(chapitres) {
  return [...chapitres].sort((a, b) => {
    const [x, y] = [rang(a), rang(b)];
    return x[0] - y[0] || x[1] - y[1] || x[2] - y[2];
  });
}

/** Catalogue des chapitres puis document du chapitre choisi. `niveauParDefaut` : niveau de l'élève. */
export default function PkpMath({ jeton, onExpire, niveauParDefaut = null, intro = null }) {
  const [chapitres, setChapitres] = useState(null);
  const [erreur, setErreur] = useState(null);
  const [niveau, setNiveau] = useState(niveauParDefaut ?? "");
  const [parcours, setParcours] = useState("");
  const [ouvert, setOuvert] = useState(null);

  useEffect(() => {
    api("/pkp-math/catalogue", { jeton }).then(
      (liste) => {
        const tries = trier(liste);
        setChapitres(tries);
        // Le niveau proposé n'a pas de chapitre : on montre tout ce qui est permis.
        const niveaux = new Set(tries.map((c) => c.niveau));
        setNiveau((n) => (niveaux.has(n) ? n : niveaux.size === 1 ? [...niveaux][0] : ""));
      },
      (err) => (err.status === 401 && onExpire ? onExpire() : setErreur(err.message)),
    );
  }, [jeton, onExpire]);

  if (ouvert) return <DocumentChapitre id={ouvert} jeton={jeton} onExpire={onExpire} onRetour={() => setOuvert(null)} />;
  if (erreur) return <Erreur message={erreur} />;
  if (!chapitres) return <p className="doux">Chargement des chapitres…</p>;

  const niveaux = [...new Set(chapitres.map((c) => c.niveau))];
  const visibles = chapitres.filter((c) => (!niveau || c.niveau === niveau) && (!parcours || c.parcours === parcours));
  const parcoursDispo = [...new Map(chapitres.filter((c) => !niveau || c.niveau === niveau).map((c) => [c.parcours, c.libelle_parcours]))];
  const groupes = [];
  for (const ch of visibles) {
    const cle = `${ch.niveau} · ${ch.libelle_parcours}`;
    if (groupes.at(-1)?.cle !== cle) groupes.push({ cle, niveau: ch.niveau, libelle: ch.libelle_parcours, chapitres: [] });
    groupes.at(-1).chapitres.push(ch);
  }

  return (
    <section className="pkp-math" aria-labelledby="titre-pkp-math">
      <div className="pkp-math-entete">
        <h2 id="titre-pkp-math">Boussole Maths</h2>
        <p className="doux">
          {intro ?? "Pour chaque chapitre : le résumé de cours, le cours complet, une fiche d'exercices et son corrigé, à lire ici ou à exporter en PDF."}
        </p>
      </div>
      {chapitres.length === 0 ? (
        <p className="doux">Aucun chapitre n'est encore disponible.</p>
      ) : (
        <>
          <div className="filtres-pkp">
            {niveaux.length > 1 && (
              <label>
                Niveau
                <select value={niveau} onChange={(e) => { setNiveau(e.target.value); setParcours(""); }}>
                  <option value="">Tous les niveaux</option>
                  {niveaux.map((n) => <option key={n} value={n}>{NOM_NIVEAU[n] ?? n}</option>)}
                </select>
              </label>
            )}
            {parcoursDispo.length > 1 && (
              <label>
                Parcours
                <select value={parcours} onChange={(e) => setParcours(e.target.value)}>
                  <option value="">Tous les parcours</option>
                  {parcoursDispo.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </label>
            )}
          </div>
          {groupes.map((g) => (
            <div key={g.cle} className="groupe-chapitres">
              <h3>{NOM_NIVEAU[g.niveau] ?? g.niveau} — {g.libelle}</h3>
              <ul className="liste-chapitres-pkp">
                {g.chapitres.map((ch) => (
                  <li key={ch.id}>
                    <button className="chapitre-pkp" onClick={() => setOuvert(ch.id)}>
                      <span className="chapitre-pkp-titre">{ch.titre}</span>
                      <span className="doux">
                        {ch.nb_competences} compétence{ch.nb_competences > 1 ? "s" : ""} · {ch.nb_questions} exercice{ch.nb_questions > 1 ? "s" : ""}
                      </span>
                      {!ch.valide && <span className="badge alerte">Non validé</span>}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </>
      )}
    </section>
  );
}

function DocumentChapitre({ id, jeton, onExpire, onRetour }) {
  const [doc, setDoc] = useState(null);
  const [erreur, setErreur] = useState(null);
  const [onglet, setOnglet] = useState("resume");
  const [exporter, setExporter] = useState(false);
  const [impression, setImpression] = useState(null); // réglages de l'export en cours

  useEffect(() => {
    api(`/pkp-math/chapitres/${id}`, { jeton }).then(setDoc, (err) =>
      err.status === 401 && onExpire ? onExpire() : setErreur(err.message),
    );
  }, [id, jeton, onExpire]);

  // Impression : le document choisi est rendu hors de l'application, puis la boîte d'impression s'ouvre.
  useEffect(() => {
    if (!impression) return undefined;
    const titre = document.title;
    document.title = `Boussole Maths - ${doc.titre}`;
    document.body.classList.add("pkp-imprime");
    const fin = () => setImpression(null);
    window.addEventListener("afterprint", fin);
    const t = setTimeout(() => window.print(), 50);
    return () => {
      clearTimeout(t);
      window.removeEventListener("afterprint", fin);
      document.body.classList.remove("pkp-imprime");
      document.title = titre;
    };
  }, [impression, doc]);

  if (erreur) return <><button className="lien" onClick={onRetour}>← Tous les chapitres</button><Erreur message={erreur} /></>;
  if (!doc) return <p className="doux">Chargement du chapitre…</p>;

  return (
    <section className="pkp-math" aria-labelledby="titre-chapitre-pkp">
      <button className="lien" onClick={onRetour}>← Tous les chapitres</button>
      <div className="pkp-math-entete">
        <p className="doux">{NOM_NIVEAU[doc.niveau] ?? doc.niveau} — {doc.libelle_parcours}</p>
        <h2 id="titre-chapitre-pkp">{doc.titre}</h2>
        {!doc.valide && (
          <p className="bandeau-non-valide" role="note">
            <strong>Non validé.</strong> Ce chapitre contient des contenus en cours de relecture par l'équipe pédagogique.
          </p>
        )}
        <div className="actions">
          <button onClick={() => setExporter(true)}>Exporter en PDF</button>
        </div>
      </div>
      <Onglets valeur={onglet} onChange={setOnglet} options={DOCUMENTS} />
      <ContenuDocument doc={doc} type={onglet} competences={doc.competences.map((c) => c.id)} difficultes={[1, 5]} ecran />
      {exporter && (
        <ReglagesExport
          doc={doc}
          ongletActuel={onglet}
          onAnnuler={() => setExporter(false)}
          onExporter={(reglages) => {
            setExporter(false);
            setImpression(reglages);
          }}
        />
      )}
      {impression &&
        createPortal(
          <div id="pkp-impression" className="pkp-impression">
            {!doc.valide && <div className="filigrane" aria-hidden="true">NON VALIDÉ</div>}
            {impression.documents.map((type, i) => (
              <div key={type} className={i > 0 ? "saut-page" : undefined}>
                <EntetePdf doc={doc} type={type} />
                <ContenuDocument doc={doc} type={type} competences={impression.competences} difficultes={impression.difficultes} />
              </div>
            ))}
          </div>,
          document.body,
        )}
    </section>
  );
}

function ReglagesExport({ doc, ongletActuel, onAnnuler, onExporter }) {
  const [documents, setDocuments] = useState([ongletActuel]);
  const [competences, setCompetences] = useState(doc.competences.map((c) => c.id));
  const [min, setMin] = useState(1);
  const [max, setMax] = useState(5);
  const basculer = (liste, setListe, v) => setListe(liste.includes(v) ? liste.filter((x) => x !== v) : [...liste, v]);
  const avecExercices = documents.some((d) => d === "exercices" || d === "corrige");

  return (
    <Modale titre="Exporter en PDF" onFermer={onAnnuler}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const ordre = DOCUMENTS.map(([v]) => v);
          onExporter({ documents: [...documents].sort((a, b) => ordre.indexOf(a) - ordre.indexOf(b)), competences, difficultes: [min, max] });
        }}
      >
        <fieldset>
          <legend>Documents</legend>
          {DOCUMENTS.map(([v, l]) => (
            <label key={v} className="case">
              <input type="checkbox" checked={documents.includes(v)} onChange={() => basculer(documents, setDocuments, v)} /> {l}
            </label>
          ))}
        </fieldset>
        {doc.competences.length > 1 && (
          <fieldset>
            <legend>Compétences</legend>
            {doc.competences.map((c) => (
              <label key={c.id} className="case">
                <input type="checkbox" checked={competences.includes(c.id)} onChange={() => basculer(competences, setCompetences, c.id)} /> {c.libelle}
              </label>
            ))}
          </fieldset>
        )}
        {avecExercices && (
          <fieldset>
            <legend>Difficulté des exercices</legend>
            <div className="ligne-champs">
              <label>
                de
                <select value={min} onChange={(e) => { const v = Number(e.target.value); setMin(v); if (v > max) setMax(v); }}>
                  {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
                </select>
              </label>
              <label>
                à
                <select value={max} onChange={(e) => { const v = Number(e.target.value); setMax(v); if (v < min) setMin(v); }}>
                  {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
                </select>
              </label>
            </div>
          </fieldset>
        )}
        <p className="aide">
          La fenêtre d'impression s'ouvre : choisissez « Enregistrer au format PDF » comme imprimante.
          {!doc.valide && " Chaque page portera la mention NON VALIDÉ."}
        </p>
        <div className="actions">
          <button type="button" className="secondaire" onClick={onAnnuler}>Annuler</button>
          <button type="submit" disabled={!documents.length || !competences.length}>Exporter</button>
        </div>
      </form>
    </Modale>
  );
}

function EntetePdf({ doc, type }) {
  const libelle = Object.fromEntries(DOCUMENTS)[type];
  return (
    <header className="entete-pdf">
      <p>Boussole Maths · {NOM_NIVEAU[doc.niveau] ?? doc.niveau} — {doc.libelle_parcours}</p>
      <h1>{doc.titre}</h1>
      <p className="type-pdf">{libelle}{!doc.valide && " · NON VALIDÉ"}</p>
    </header>
  );
}

/** Un document du chapitre (résumé, cours, exercices ou corrigé), pour l'écran comme pour l'impression. */
export function ContenuDocument({ doc, type, competences, difficultes, ecran = false }) {
  const choisies = doc.competences.filter((c) => competences.includes(c.id));
  // Numérotation continue des exercices, la même dans la fiche et dans le corrigé.
  const numeros = useMemo(() => {
    const n = new Map();
    let i = 0;
    for (const c of choisies)
      for (const q of c.questions) if (q.difficulte >= difficultes[0] && q.difficulte <= difficultes[1]) n.set(q.id, ++i);
    return n;
  }, [choisies, difficultes]);

  if (type === "exercices" || type === "corrige") {
    if (!numeros.size)
      return (
        <p className="doux">
          {doc.competences.some((c) => c.questions.length)
            ? "Aucun exercice pour ces réglages (compétences ou difficultés choisies)."
            : "Les exercices de ce chapitre ne sont pas encore disponibles : ils apparaîtront ici dès qu'ils auront été relus par l'équipe pédagogique."}
        </p>
      );
    return (
      <div className={`document-pkp ${type}`}>
        {choisies.map((c) => {
          const questions = c.questions.filter((q) => numeros.has(q.id));
          if (!questions.length) return null;
          return (
            <section key={c.id} className="competence-pkp">
              <h3>{c.libelle}</h3>
              <ol className="exercices-pkp">
                {questions.map((q) => (
                  <li key={q.id} value={numeros.get(q.id)} className="exercice-pkp">
                    <div className="exercice-entete">
                      <strong>Exercice {numeros.get(q.id)}</strong> <Difficulte niveau={q.difficulte} />
                      {ecran && !q.validee && <span className="badge alerte">Non validé</span>}
                    </div>
                    {type === "exercices" ? (
                      <>
                        <Maths texte={q.enonce} />
                        {!ecran && <div className="zone-reponse" aria-hidden="true" />}
                      </>
                    ) : (
                      <Corrige q={q} />
                    )}
                  </li>
                ))}
              </ol>
            </section>
          );
        })}
      </div>
    );
  }

  return (
    <div className={`document-pkp ${type}`}>
      {choisies.map((c) => (
        <section key={c.id} className="competence-pkp">
          <h3>{c.libelle}</h3>
          {c.objectifs.length > 0 && (
            <div className="encadre objectifs">
              <strong>Objectifs</strong>
              <ul>{c.objectifs.map((o) => <li key={o}><Maths texte={o} enLigne /></li>)}</ul>
            </div>
          )}
          {type === "cours" ? (
            c.cours ? <Maths texte={c.cours} /> : <p className="doux">Pas encore de cours pour cette compétence.</p>
          ) : (
            <>
              {c.resume ? <div className="resume"><Maths texte={c.resume} /></div> : <p className="doux">Pas encore de résumé.</p>}
              {c.methodes.map((m) => (
                <div key={m.titre} className="encadre methode">
                  <strong>Méthode : {m.titre}</strong>
                  <ol>{(m.etapes ?? []).map((e, i) => <li key={i}><Maths texte={e} enLigne /></li>)}</ol>
                  {m.exemple && (
                    <div className="exemple">
                      <p><strong>Exemple.</strong> <Maths texte={m.exemple.enonce} enLigne /></p>
                      <ol>{(m.exemple.resolution ?? []).map((e, i) => <li key={i}><Maths texte={e} enLigne /></li>)}</ol>
                      {m.exemple.resultat && <p><strong>Résultat :</strong> <Maths texte={m.exemple.resultat} enLigne /></p>}
                    </div>
                  )}
                </div>
              ))}
              {c.erreurs_frequentes.length > 0 && (
                <div className="encadre attention">
                  <strong>Attention à…</strong>
                  <ul>
                    {c.erreurs_frequentes.map((e) => (
                      <li key={e.erreur}><strong><Maths texte={e.erreur} enLigne /></strong> <Maths texte={e.explication} enLigne /></li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
        </section>
      ))}
    </div>
  );
}

function Corrige({ q }) {
  const c = q.correction;
  return (
    <div className="corrige-pkp">
      <p className="doux"><Maths texte={q.enonce} enLigne /></p>
      {c?.methode && <p><strong>Méthode :</strong> <Maths texte={c.methode} enLigne /></p>}
      {c?.etapes?.length > 0 && <ol>{c.etapes.map((e, i) => <li key={i}><Maths texte={e} enLigne /></li>)}</ol>}
      <p><strong>Réponse :</strong> <Maths texte={c?.resultat ?? (q.type === "qcm" ? q.solution : q.type === "texte" ? solutionLisible("texte", q.solution) : `$${q.solution}$`)} enLigne /></p>
    </div>
  );
}
