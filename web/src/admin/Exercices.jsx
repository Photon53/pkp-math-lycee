import { useCallback, useEffect, useState } from "react";
import { Difficulte, Erreur, LIBELLES_TYPE } from "../composants.jsx";
import { NIVEAUX } from "../enseignant/CoursEnseignant.jsx";
import { useApi } from "../enseignant/useApi.js";
import { Maths, formulesInvalides } from "../maths.jsx";
import { Modale, Pagination, Vide, exporterCsv, pourcentage } from "../ui/Cadre.jsx";
import Icone from "../ui/Icone.jsx";

const STATUTS = {
  "a-valider": ["À valider", ""],
  validee: ["Validée", "ok"],
  "a-corriger": ["À corriger", "ko"],
};

const VIDE = {
  competence_id: "", enonce: "", type: "numerique", solution: "", difficulte: 2,
  source: "PKP Math", source_url: "", licence_source: "", adaptation: "originale", auteur: "",
};

/** Banque d'exercices : filtres, édition testée par le moteur, validation, archivage (EA3.15 à EA3.19). */
export default function Exercices({ jeton, onExpire }) {
  const { appeler, erreur } = useApi(jeton, onExpire);
  const [filtres, setFiltres] = useState(() => ({
    niveau: "", type: "", statut: "", archivees: false,
    q: new URLSearchParams(window.location.search).get("q") ?? "",
  }));
  const [page, setPage] = useState(1);
  const [donnees, setDonnees] = useState(null);
  const [competences, setCompetences] = useState([]);
  const [edition, setEdition] = useState(null);

  const charger = useCallback(() => {
    const params = new URLSearchParams({ page: String(page), archivees: String(filtres.archivees) });
    for (const cle of ["niveau", "type", "statut", "q"]) if (filtres[cle]) params.set(cle, filtres[cle]);
    return appeler(`/admin/questions?${params}`).then(setDonnees, () => {});
  }, [appeler, filtres, page]);

  useEffect(() => {
    const minuterie = setTimeout(charger, 250);
    return () => clearTimeout(minuterie);
  }, [charger]);

  useEffect(() => {
    appeler("/admin/contenu").then(
      (arbre) => setCompetences(arbre.flatMap((ch) => ch.competences.map((c) => ({ ...c, chapitre: ch.titre, niveau: ch.niveau })))),
      () => {},
    );
  }, [appeler]);

  const filtre = (cle) => ({
    value: filtres[cle],
    onChange: (e) => {
      setFiltres({ ...filtres, [cle]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
      setPage(1);
    },
  });

  async function valider(q, statut) {
    try {
      await appeler(`/admin/questions/${q.id}/validation`, { methode: "POST", corps: { statut } });
      charger();
    } catch {
      // erreur déjà affichée
    }
  }

  async function archiver(q) {
    const texte = q.archivee
      ? "Remettre cette question dans les tirages ?"
      : "Archiver cette question ? Elle ne sera plus proposée aux élèves ; leur historique est conservé.";
    if (!window.confirm(texte)) return;
    try {
      await appeler(`/admin/questions/${q.id}/archivage`, { methode: "POST", corps: { archivee: !q.archivee } });
      charger();
    } catch {
      // erreur déjà affichée
    }
  }

  return (
    <>
      <section className="carte">
        <div className="filtres" role="search">
          <div>
            <label htmlFor="x-niveau">Niveau</label>
            <select id="x-niveau" {...filtre("niveau")}>
              <option value="">Tous</option>
              {NIVEAUX.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="x-type">Type</label>
            <select id="x-type" {...filtre("type")}>
              <option value="">Tous</option>
              {Object.entries(LIBELLES_TYPE).map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="x-statut">Validation</label>
            <select id="x-statut" {...filtre("statut")}>
              <option value="">Tous</option>
              {Object.entries(STATUTS).map(([v, [l]]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </div>
          <div style={{ flexGrow: 2 }}>
            <label htmlFor="x-q">Code ou énoncé</label>
            <input id="x-q" type="search" {...filtre("q")} />
          </div>
          <label className="case" style={{ flexGrow: 0 }}>
            <input type="checkbox" checked={filtres.archivees} onChange={filtre("archivees").onChange} /> Archivées
          </label>
        </div>
        <div className="actions" style={{ marginTop: 0, justifyContent: "space-between" }}>
          <span className="doux petit">{donnees ? `${donnees.total} question(s)` : ""}</span>
          <span className="actions" style={{ marginTop: 0 }}>
            <button className="secondaire" onClick={() => exporterCsv("questions.csv", donnees?.elements ?? [])} disabled={!donnees?.elements.length}>
              CSV
            </button>
            <button onClick={() => setEdition(VIDE)}>
              <Icone nom="plus" taille={18} /> Nouvelle question
            </button>
          </span>
        </div>
        <Erreur message={erreur} />
        {donnees === null && <p className="doux">Chargement…</p>}
        {donnees?.total === 0 && <Vide icone="exercices">Aucune question ne correspond.</Vide>}
        {donnees?.total > 0 && (
          <>
            <div className="tableau-defilant">
              <table>
                <thead>
                  <tr>
                    <th>Énoncé</th>
                    <th>Solution</th>
                    <th>Difficulté</th>
                    <th>Validation</th>
                    <th className="nombre">Réponses</th>
                    <th className="nombre">Réussite</th>
                    <th>
                      <span className="visuellement-cache">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {donnees.elements.map((q) => (
                    <tr key={q.id} className={q.archivee ? "estompe" : ""}>
                      <td style={{ maxWidth: 420 }}>
                        <Maths enLigne texte={q.enonce} />
                        <div className="aide">
                          {q.code ?? `#${q.id}`} · {LIBELLES_TYPE[q.type]} · {q.niveau} · {q.competence}
                          {q.archivee && <span className="pastille archivee">Archivée</span>}
                        </div>
                      </td>
                      <td>
                        <code>{q.solution}</code>
                      </td>
                      <td>
                        <Difficulte niveau={q.difficulte} />
                      </td>
                      <td>
                        <span className={`badge ${STATUTS[q.statut_validation][1]}`}>{STATUTS[q.statut_validation][0]}</span>
                        {q.valide_par && <div className="aide">{q.valide_par}</div>}
                      </td>
                      <td className="nombre">{q.nb_reponses}</td>
                      <td className="nombre">{pourcentage(q.taux_reussite)}</td>
                      <td className="nombre">
                        <div className="actions">
                          <button className="icone" title="Modifier" aria-label={`Modifier la question ${q.code ?? q.id}`} onClick={() => setEdition(q)}>
                            <Icone nom="crayon" />
                          </button>
                          {q.statut_validation !== "validee" && (
                            <button className="secondaire petit" onClick={() => valider(q, "validee")}>
                              Valider
                            </button>
                          )}
                          {q.statut_validation !== "a-corriger" && (
                            <button className="secondaire petit" onClick={() => valider(q, "a-corriger")}>
                              À corriger
                            </button>
                          )}
                          <button className="secondaire petit" onClick={() => archiver(q)}>
                            {q.archivee ? "Désarchiver" : "Archiver"}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={page} total={donnees.total} onChange={setPage} />
          </>
        )}
      </section>

      {edition && (
        <EditionQuestion
          initiale={edition}
          competences={competences}
          appeler={appeler}
          onFermer={() => setEdition(null)}
          onEnregistree={() => {
            setEdition(null);
            charger();
          }}
        />
      )}
    </>
  );
}

function EditionQuestion({ initiale, competences, appeler, onFermer, onEnregistree }) {
  const [v, setV] = useState(() => ({
    ...VIDE,
    ...Object.fromEntries(Object.entries(initiale).map(([k, x]) => [k, x ?? ""])),
    competence_id: String(initiale.competence_id || competences[0]?.id || ""),
  }));
  const [essai, setEssai] = useState("");
  const [resultatEssai, setResultatEssai] = useState(null);
  const [erreur, setErreur] = useState(null);
  const repondue = initiale.nb_reponses > 0;
  const champ = (cle) => ({ value: v[cle], onChange: (e) => setV({ ...v, [cle]: e.target.value }) });
  const invalides = formulesInvalides(v.enonce);

  async function tester() {
    setResultatEssai(null);
    try {
      setResultatEssai(
        await appeler("/admin/questions/tester", { methode: "POST", corps: { type: v.type, solution: v.solution, reponse: essai || v.solution } }),
      );
    } catch (err) {
      setErreur(err.message);
    }
  }

  async function soumettre(e) {
    e.preventDefault();
    setErreur(null);
    const corps = {
      competence_id: Number(v.competence_id), enonce: v.enonce, type: v.type, solution: v.solution,
      difficulte: Number(v.difficulte), source: v.source || "PKP Math", source_url: v.source_url || null,
      licence_source: v.licence_source || null, adaptation: v.adaptation, auteur: v.auteur || null,
    };
    try {
      await appeler(initiale.id ? `/admin/questions/${initiale.id}` : "/admin/questions", { methode: "POST", corps });
      onEnregistree();
    } catch (err) {
      setErreur(err.message);
    }
  }

  return (
    <Modale titre={initiale.id ? `Question ${initiale.code ?? `#${initiale.id}`}` : "Nouvelle question"} large onFermer={onFermer}>
      <form onSubmit={soumettre}>
        {repondue && (
          <p className="avertissement">
            Déjà {initiale.nb_reponses} réponse(s) : l'énoncé, le type, la solution et la compétence ne changent plus. Pour les
            modifier, archivez cette question et créez-en une nouvelle.
          </p>
        )}
        <label htmlFor="q-competence">Compétence</label>
        <select id="q-competence" required disabled={repondue} {...champ("competence_id")}>
          {competences.map((c) => (
            <option key={c.id} value={c.id}>
              {c.niveau} · {c.chapitre} — {c.libelle}
            </option>
          ))}
        </select>
        <div className="deux-volets" style={{ marginTop: 8 }}>
          <div>
            <label htmlFor="q-enonce">Énoncé (Markdown et LaTeX)</label>
            <textarea id="q-enonce" rows={5} maxLength={2000} required disabled={repondue} style={{ minHeight: 120 }} {...champ("enonce")} />
            <p className="aide">Pour un QCM, écrire les choix dans l'énoncé : « … ? A) 0  B) 1  C) 2 ».</p>
          </div>
          <div>
            <span className="petit" style={{ fontWeight: 600 }}>Aperçu</span>
            <div className="apercu enonce" style={{ minHeight: 120, marginTop: 6 }}>
              <Maths texte={v.enonce || "…"} />
            </div>
          </div>
        </div>
        {invalides.length > 0 && <p className="erreur">Formule invalide : {invalides[0]}</p>}
        <div className="ligne-3">
          <div>
            <label htmlFor="q-type">Type</label>
            <select id="q-type" disabled={repondue} {...champ("type")}>
              {Object.entries(LIBELLES_TYPE).map(([k, l]) => (
                <option key={k} value={k}>
                  {l}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="q-solution">Solution</label>
            <input id="q-solution" maxLength={200} required disabled={repondue} {...champ("solution")} />
          </div>
          <div>
            <label htmlFor="q-difficulte">Difficulté (1 à 5)</label>
            <input id="q-difficulte" type="number" min={1} max={5} required {...champ("difficulte")} />
          </div>
        </div>

        <fieldset className="choix-chapitres">
          <legend>Tester ma réponse</legend>
          <div className="filtres" style={{ marginBottom: 0 }}>
            <div style={{ flexGrow: 3 }}>
              <label htmlFor="q-essai">Réponse d'élève à essayer (vide : la solution elle-même)</label>
              <input id="q-essai" value={essai} onChange={(e) => setEssai(e.target.value)} placeholder="ex. (x-2)^2" />
            </div>
            <button type="button" className="secondaire" style={{ flexGrow: 0 }} disabled={!v.solution} onClick={tester}>
              Tester
            </button>
          </div>
          {resultatEssai && (
            <p className={resultatEssai.solution_lisible && resultatEssai.correcte ? "succes" : "erreur"} role="status">
              {!resultatEssai.solution_lisible
                ? "La solution est illisible par le moteur : aucun élève ne pourrait réussir."
                : resultatEssai.correcte
                  ? "Réponse acceptée par le moteur."
                  : "Réponse refusée par le moteur."}
            </p>
          )}
        </fieldset>

        <details>
          <summary>Source, licence et auteur</summary>
          <div className="ligne">
            <div>
              <label htmlFor="q-source">Source</label>
              <input id="q-source" maxLength={200} {...champ("source")} />
            </div>
            <div>
              <label htmlFor="q-adaptation">Lien avec la source</label>
              <select id="q-adaptation" {...champ("adaptation")}>
                <option value="originale">Originale</option>
                <option value="inspiree">Inspirée</option>
                <option value="adaptee">Adaptée</option>
                <option value="reproduite">Reproduite</option>
              </select>
            </div>
            <div>
              <label htmlFor="q-licence">Licence de la source</label>
              <input id="q-licence" maxLength={100} {...champ("licence_source")} />
            </div>
            <div>
              <label htmlFor="q-url">Adresse de la source</label>
              <input id="q-url" type="url" maxLength={500} {...champ("source_url")} />
            </div>
          </div>
          <label htmlFor="q-auteur">Auteur (par défaut : vous)</label>
          <input id="q-auteur" maxLength={100} {...champ("auteur")} />
          <p className="aide">Le relecteur qui valide la question doit être une autre personne que l'auteur.</p>
        </details>

        <Erreur message={erreur} />
        <div className="actions">
          <button type="submit" disabled={invalides.length > 0}>
            Enregistrer
          </button>
        </div>
      </form>
    </Modale>
  );
}
