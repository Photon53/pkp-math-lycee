import { Fragment, useCallback, useEffect, useState } from "react";
import { Erreur, Onglets } from "../composants.jsx";
import Historique from "../eleve/Historique.jsx";
import { ListeProgression } from "../eleve/Progression.jsx";
import { useApi } from "./useApi.js";

export const LIBELLES_PARCOURS = {
  "tronc-commun": "Tronc commun",
  specialite: "Spécialité",
  complementaires: "Maths complémentaires",
  expertes: "Maths expertes",
};
// Parcours permis par niveau (même règle que l'API, app/referentiel.py).
const PARCOURS_PAR_NIVEAU = {
  "2nde": ["tronc-commun"],
  "1re": ["specialite"],
  Tle: ["specialite", "complementaires", "expertes"],
};

const NIVEAUX = [
  ["2nde", "Seconde"],
  ["1re", "Première"],
  ["Tle", "Terminale"],
];

const pourcent = (x) => (x == null ? "—" : `${Math.round(x * 100)} %`);
const ignorer = () => {};

export default function Classes({ jeton, onExpire }) {
  const { appeler, erreur } = useApi(jeton, onExpire);
  const [classes, setClasses] = useState(null);
  const [classeId, setClasseId] = useState(null);
  const [eleves, setEleves] = useState(null);
  const [detail, setDetail] = useState(null); // { eleveId, competences }
  const [niveau, setNiveau] = useState("2nde");
  const [parcours, setParcours] = useState("tronc-commun");
  const [message, setMessage] = useState(null);
  const [prenomsSaisis, setPrenomsSaisis] = useState("");
  const [codesAffiches, setCodesAffiches] = useState(null); // [{ prenom, code }] : affichés une seule fois

  const chargerClasses = useCallback(() => appeler("/enseignants/classes").then(setClasses, ignorer), [appeler]);
  const chargerEleves = useCallback(
    (id) => appeler(`/enseignants/classes/${id}/eleves`).then(setEleves, ignorer),
    [appeler],
  );

  useEffect(() => {
    chargerClasses();
  }, [chargerClasses]);

  function choisir(id) {
    setClasseId(id);
    setEleves(null);
    setDetail(null);
    setMessage(null);
    setCodesAffiches(null);
    chargerEleves(id);
  }

  async function inscrire(e) {
    e.preventDefault();
    const prenoms = prenomsSaisis.split(/\r?\n/).map((p) => p.trim()).filter(Boolean);
    try {
      const r = await appeler(`/enseignants/classes/${classeId}/eleves`, { methode: "POST", corps: { prenoms } });
      setCodesAffiches(r.crees);
      setPrenomsSaisis("");
      setMessage(r.deja_presents.length ? `Déjà inscrit(s), ignoré(s) : ${r.deja_presents.join(", ")}.` : null);
      await Promise.all([chargerEleves(classeId), chargerClasses()]);
    } catch {
      // erreur déjà affichée (prénom invalide, par exemple)
    }
  }

  async function nouveauCode(eleve) {
    const ok = window.confirm(
      `Générer un nouveau code pour ${eleve.prenom} ?\n\nL'ancien code ne fonctionnera plus et sa session en cours sera fermée.`,
    );
    if (!ok) return;
    try {
      setCodesAffiches([await appeler(`/enseignants/eleves/${eleve.id}/code`, { methode: "POST" })]);
      setMessage(null);
      await chargerEleves(classeId);
    } catch {
      // erreur déjà affichée
    }
  }

  async function codesManquants() {
    try {
      setCodesAffiches(await appeler(`/enseignants/classes/${classeId}/codes-manquants`, { methode: "POST" }));
      setMessage(null);
      await chargerEleves(classeId);
    } catch {
      // erreur déjà affichée
    }
  }

  async function creer(e) {
    e.preventDefault();
    try {
      const classe = await appeler("/enseignants/classes", { methode: "POST", corps: { niveau, parcours } });
      await chargerClasses();
      choisir(classe.id);
      setMessage(`Classe créée. Code à donner aux élèves : ${classe.code}`);
    } catch {
      // erreur déjà affichée
    }
  }

  async function basculerDetail(eleveId) {
    if (detail?.eleveId === eleveId) return setDetail(null);
    try {
      setDetail({ eleveId, competences: await appeler(`/enseignants/eleves/${eleveId}/progression`) });
    } catch {
      // erreur déjà affichée
    }
  }

  async function supprimer(eleve) {
    const ok = window.confirm(
      `Supprimer définitivement ${eleve.prenom} et tout son historique (séances, réponses) ?\n\nCette action est irréversible.`,
    );
    if (!ok) return;
    try {
      await appeler(`/enseignants/eleves/${eleve.id}`, { methode: "DELETE" });
      setDetail(null);
      setMessage(`${eleve.prenom} a été supprimé·e avec tout son historique.`);
      await Promise.all([chargerEleves(classeId), chargerClasses()]);
    } catch {
      // erreur déjà affichée
    }
  }

  async function exporter(eleve) {
    try {
      const donnees = await appeler(`/enseignants/eleves/${eleve.id}/export`);
      const lien = document.createElement("a");
      lien.href = URL.createObjectURL(new Blob([JSON.stringify(donnees, null, 2)], { type: "application/json" }));
      lien.download = `pkp-${donnees.eleve.classe}-${eleve.prenom}.json`;
      lien.click();
      URL.revokeObjectURL(lien.href);
    } catch {
      // erreur déjà affichée
    }
  }

  async function supprimerClasse(c) {
    const ok = window.confirm(
      `Supprimer définitivement la classe ${c.code}, ses ${c.nb_eleves} élève(s) et tout leur historique ?\n\nCette action est irréversible.`,
    );
    if (!ok) return;
    try {
      await appeler(`/enseignants/classes/${c.id}`, { methode: "DELETE" });
      setClasseId(null);
      setEleves(null);
      setMessage(`La classe ${c.code} a été supprimée avec tous ses élèves.`);
      await chargerClasses();
    } catch {
      // erreur déjà affichée
    }
  }

  const classe = classes?.find((c) => c.id === classeId);

  return (
    <>
      <section className="carte">
        <h2>Mes classes</h2>
        {classes === null ? (
          <p className="doux">Chargement…</p>
        ) : classes.length === 0 ? (
          <p className="doux">Aucune classe pour l'instant : créez-en une ci-dessous.</p>
        ) : (
          <div className="grille-classes">
            {classes.map((c) => (
              <button
                key={c.id}
                className={c.id === classeId ? "classe choisie" : "classe"}
                aria-pressed={c.id === classeId}
                onClick={() => choisir(c.id)}
              >
                <span className="code">{c.code}</span>
                <span className="doux">
                  {NIVEAUX.find(([v]) => v === c.niveau)?.[1]} · {LIBELLES_PARCOURS[c.parcours]} · {c.nb_eleves} élève{c.nb_eleves > 1 ? "s" : ""}
                </span>
              </button>
            ))}
          </div>
        )}
        <form className="actions" onSubmit={creer}>
          <label htmlFor="niveau" className="visuellement-cache">
            Niveau de la nouvelle classe
          </label>
          <select
            id="niveau"
            value={niveau}
            onChange={(e) => {
              setNiveau(e.target.value);
              setParcours(PARCOURS_PAR_NIVEAU[e.target.value][0]);
            }}
            style={{ width: "auto" }}
          >
            {NIVEAUX.map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
          {PARCOURS_PAR_NIVEAU[niveau].length > 1 && (
            <>
              <label htmlFor="parcours" className="visuellement-cache">
                Spécialité de la nouvelle classe
              </label>
              <select id="parcours" value={parcours} onChange={(e) => setParcours(e.target.value)} style={{ width: "auto" }}>
                {PARCOURS_PAR_NIVEAU[niveau].map((p) => (
                  <option key={p} value={p}>
                    {LIBELLES_PARCOURS[p]}
                  </option>
                ))}
              </select>
            </>
          )}
          <button type="submit" className="secondaire">
            Créer une classe
          </button>
        </form>
        {message && (
          <p className="succes" role="status">
            {message}
          </p>
        )}
        <Erreur message={erreur} />
      </section>

      {classe && (
        <section className="carte">
          <h2>
            Classe <code>{classe.code}</code>
          </h2>
          <p className="doux">
            Chaque élève se connecte avec son prénom, ce code classe et son <strong>code personnel</strong>.
          </p>
          {codesAffiches && (
            <FicheCodes classe={classe.code} codes={codesAffiches} onFermer={() => setCodesAffiches(null)} />
          )}
          {eleves?.some((e) => !e.a_un_code) && (
            <p className="erreur" role="status">
              Des élèves n'ont pas encore de code personnel et ne peuvent pas se connecter.{" "}
              <button className="lien" onClick={codesManquants}>
                Générer les codes manquants
              </button>
            </p>
          )}
          {eleves === null ? (
            <p className="doux">Chargement…</p>
          ) : eleves.length === 0 ? (
            <p className="doux">Aucun élève inscrit pour l'instant.</p>
          ) : (
            <div className="tableau-defilant">
              <table>
                <thead>
                  <tr>
                    <th>Élève</th>
                    <th className="nombre">Réponses</th>
                    <th className="nombre">Réussite</th>
                    <th className="nombre">Compétences maîtrisées</th>
                    <th>
                      <span className="visuellement-cache">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {eleves.map((e) => (
                    <Fragment key={e.id}>
                      <tr>
                        <td>
                          {e.prenom}
                          {!e.a_un_code && <span className="pastille archivee">sans code</span>}
                        </td>
                        <td className="nombre">{e.nb_reponses}</td>
                        <td className="nombre">{pourcent(e.taux_reussite)}</td>
                        <td className="nombre">
                          {e.competences_maitrisees} / {e.competences_total}
                        </td>
                        <td className="nombre">
                          <button className="lien petit" aria-expanded={detail?.eleveId === e.id} onClick={() => basculerDetail(e.id)}>
                            {detail?.eleveId === e.id ? "Masquer" : "Détail"}
                          </button>
                          <button className="lien petit" onClick={() => nouveauCode(e)} aria-label={`Nouveau code pour ${e.prenom}`}>
                            Nouveau code
                          </button>
                          <button className="lien petit" onClick={() => exporter(e)} aria-label={`Exporter les données de ${e.prenom}`}>
                            Exporter
                          </button>
                          <button className="danger petit" onClick={() => supprimer(e)} aria-label={`Supprimer ${e.prenom}`}>
                            Supprimer
                          </button>
                        </td>
                      </tr>
                      {detail?.eleveId === e.id && (
                        <tr className="detail">
                          <td colSpan={5}>
                            <DetailEleve eleve={e} competences={detail.competences} jeton={jeton} onExpire={onExpire} />
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <form onSubmit={inscrire}>
            <label htmlFor="prenoms">Inscrire des élèves (un prénom par ligne)</label>
            <textarea
              id="prenoms"
              rows={4}
              value={prenomsSaisis}
              onChange={(e) => setPrenomsSaisis(e.target.value)}
              placeholder={"Lina\nYanis\nInès"}
            />
            <p className="aide">Prénom seulement, sans nom de famille. Un code personnel est généré pour chacun.</p>
            <div className="actions">
              <button type="submit" className="secondaire" disabled={!prenomsSaisis.trim()}>
                Inscrire et générer les codes
              </button>
            </div>
          </form>
          <div className="actions">
            <button className="danger" onClick={() => supprimerClasse(classe)}>
              Supprimer la classe (fin d'année)
            </button>
          </div>
        </section>
      )}
      {classe && <ChapitresProposes key={classe.id} classe={classe} appeler={appeler} />}
    </>
  );
}

/** Programme de la classe : l'enseignant coche les chapitres ouverts à ses élèves. */
/** Suivi d'un élève : maîtrise par compétence, et historique de ses réponses avec les corrections. */
function DetailEleve({ eleve, competences, jeton, onExpire }) {
  const [vue, setVue] = useState("progression");
  return (
    <>
      <Onglets
        valeur={vue}
        onChange={setVue}
        options={[
          ["progression", "Progression"],
          ["historique", `Historique de ${eleve.prenom}`],
        ]}
      />
      {vue === "progression" ? (
        <ListeProgression competences={competences} />
      ) : (
        <Historique jeton={jeton} onExpire={onExpire} chemin={`/enseignants/eleves/${eleve.id}/historique`} eleve={false} />
      )}
    </>
  );
}

function ChapitresProposes({ classe, appeler }) {
  const [chapitres, setChapitres] = useState(null);
  const [coches, setCoches] = useState(new Set());
  const [message, setMessage] = useState(null);

  const appliquer = useCallback((liste) => {
    setChapitres(liste);
    setCoches(new Set(liste.filter((c) => c.propose).map((c) => c.id)));
  }, []);

  useEffect(() => {
    appeler(`/enseignants/classes/${classe.id}/chapitres`).then(appliquer, () => {});
  }, [appeler, appliquer, classe.id]);

  function basculer(id) {
    setMessage(null);
    setCoches((avant) => {
      const apres = new Set(avant);
      apres.has(id) ? apres.delete(id) : apres.add(id);
      return apres;
    });
  }

  async function enregistrer() {
    try {
      const liste = await appeler(`/enseignants/classes/${classe.id}/chapitres`, {
        methode: "PUT",
        corps: { chapitre_ids: [...coches] },
      });
      appliquer(liste);
      setMessage(`${coches.size} chapitre(s) ouvert(s) aux élèves de ${classe.code}.`);
    } catch {
      // erreur affichée par le composant parent
    }
  }

  const modifie = chapitres !== null && chapitres.some((c) => c.propose !== coches.has(c.id));

  return (
    <section className="carte">
      <h2>Chapitres proposés aux élèves</h2>
      <p className="doux">
        Cochez les chapitres que vos élèves peuvent travailler. Ils choisissent ensuite, à chaque séance, un ou plusieurs
        de ces chapitres.
      </p>
      {chapitres === null ? (
        <p className="doux">Chargement…</p>
      ) : chapitres.length === 0 ? (
        <p className="doux">Aucun chapitre n'existe encore pour ce niveau et cette spécialité.</p>
      ) : (
        <fieldset className="choix-chapitres">
          <legend>Programme de la classe</legend>
          {chapitres.map((c) => (
            <label key={c.id} className="case">
              <input type="checkbox" checked={coches.has(c.id)} onChange={() => basculer(c.id)} />
              {c.ordre}. {c.titre}
              <span className="doux">
                {c.nb_questions === 0 ? " — pas encore de questions" : ` — ${c.nb_questions} question(s)`}
              </span>
            </label>
          ))}
        </fieldset>
      )}
      <div className="actions">
        <button onClick={enregistrer} disabled={!modifie}>
          Enregistrer
        </button>
      </div>
      {message && (
        <p className="succes" role="status">
          {message}
        </p>
      )}
    </section>
  );
}

/** Codes en clair : affichés une seule fois (stockés hachés). Imprimables pour être distribués. */
function FicheCodes({ classe, codes, onFermer }) {
  return (
    <div className="fiche-codes" role="region" aria-label="Codes personnels à distribuer">
      <h3>Codes à distribuer — classe {classe}</h3>
      <p className="aide">
        Ces codes ne seront plus affichés : imprimez-les ou notez-les maintenant. Un code perdu se remplace par « Nouveau code ».
      </p>
      {codes.length === 0 ? (
        <p className="doux">Aucun nouveau code.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Élève</th>
              <th>Code personnel</th>
            </tr>
          </thead>
          <tbody>
            {codes.map((c) => (
              <tr key={c.prenom}>
                <td>{c.prenom}</td>
                <td>
                  <code className="code-personnel">{c.code}</code>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div className="actions">
        <button onClick={() => window.print()} disabled={codes.length === 0}>
          Imprimer
        </button>
        <button className="secondaire" onClick={onFermer}>
          J'ai noté les codes
        </button>
      </div>
    </div>
  );
}
