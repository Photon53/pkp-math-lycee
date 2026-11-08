import QRCode from "qrcode";
import { Fragment, useCallback, useEffect, useState } from "react";
import { api } from "../api.js";
import { Erreur, Onglets } from "../composants.jsx";
import Historique from "../eleve/Historique.jsx";
import { ListeProgression } from "../eleve/Progression.jsx";
import {
  LIBELLES_PARCOURS,
  MATIERES_CLASSES,
  NIVEAUX,
  NIVEAUX_COLLEGE,
  NIVEAUX_FRANCAIS,
  PARCOURS_PAR_NIVEAU,
  libelleClasse,
  libelleNiveauParcours,
} from "../parcours.js";
import AjoutEnfants from "../ui/AjoutEnfants.jsx";
import ParentsEleve from "./ParentsEleve.jsx";
import { useApi } from "./useApi.js";

export { LIBELLES_PARCOURS };

const pourcent = (x) => (x == null ? "—" : `${Math.round(x * 100)} %`);
const ignorer = () => {};

export default function Classes({ jeton, onExpire, maths = true, francais = false }) {
  const { appeler, erreur } = useApi(jeton, onExpire);
  const [classes, setClasses] = useState(null);
  const [classeId, setClasseId] = useState(null);
  const [eleves, setEleves] = useState(null);
  const [detail, setDetail] = useState(null); // { eleveId, competences }
  const [matiere, setMatiere] = useState(maths ? "maths" : "francais");
  const [niveau, setNiveau] = useState("2nde");
  const [parcours, setParcours] = useState("tronc-commun");
  const matieresPermises = Object.keys(MATIERES_CLASSES).filter((m) => (m === "maths" ? maths : francais));
  const enFrancais = matiere === "francais";
  const [message, setMessage] = useState(null);
  const [codesAffiches, setCodesAffiches] = useState(null); // [{ prenom, code }] : affichés une seule fois
  // Autres parcours d'un élève : { eleveId, liees, suggestions } (GET /enseignants/eleves/{id}/liens).
  const [liens, setLiens] = useState(null);
  const [parentsDe, setParentsDe] = useState(null); // id de l'élève dont on gère les comptes parents

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

  // Les élèves sont créés par l'administrateur dans leur famille : le professeur les ajoute à sa classe.
  const chercherEnfants = useCallback(
    (q) => api(`/enseignants/classes/${classeId}/enfants?q=${encodeURIComponent(q)}`, { jeton }),
    [classeId, jeton],
  );

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

  async function cartesDeLaClasse() {
    const ok = window.confirm(
      "Imprimer les cartes de toute la classe ?\n\nChaque élève reçoit un nouveau code personnel : les anciens codes ne fonctionneront plus " +
        "et les sessions en cours seront fermées. Les identifiants ne changent pas.",
    );
    if (!ok) return;
    try {
      setCodesAffiches(await appeler(`/enseignants/classes/${classeId}/cartes`, { methode: "POST" }));
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
      const corps = enFrancais ? { matiere, niveau } : { niveau, parcours };
      const classe = await appeler("/enseignants/classes", { methode: "POST", corps });
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

  async function basculerLiens(eleveId) {
    if (liens?.eleveId === eleveId) return setLiens(null);
    try {
      setLiens({ eleveId, ...(await appeler(`/enseignants/eleves/${eleveId}/liens`)) });
    } catch {
      // erreur déjà affichée
    }
  }

  async function relier(eleve, autre) {
    const ok = window.confirm(
      `Relier ${eleve.prenom} (${classes.find((c) => c.id === classeId)?.code}) et ${autre.prenom} (${autre.code_classe}) ?

` +
        `C'est le même élève : il passera d'un parcours à l'autre avec un seul code, celui de cette classe. ` +
        `L'ancien code de ${autre.code_classe} ne fonctionnera plus.`,
    );
    if (!ok) return;
    try {
      const r = await appeler(`/enseignants/eleves/${eleve.id}/liens`, { methode: "POST", corps: { eleve_id: autre.eleve_id } });
      setLiens({ eleveId: eleve.id, ...r });
      setMessage(`${eleve.prenom} suit désormais aussi ${autre.code_classe}, avec le code de cette classe.`);
      await chargerEleves(classeId);
    } catch {
      // erreur déjà affichée
    }
  }

  async function delier(eleve) {
    try {
      const r = await appeler(`/enseignants/eleves/${eleve.id}/liens`, { methode: "DELETE" });
      setLiens({ eleveId: eleve.id, ...r });
      setMessage(`${eleve.prenom} n'est plus relié·e à ses autres parcours dans cette classe.`);
      await chargerEleves(classeId);
    } catch {
      // erreur déjà affichée
    }
  }

  async function renommer(eleve) {
    const prenom = window.prompt(`Corriger le prénom de ${eleve.prenom} :`, eleve.prenom);
    if (!prenom?.trim() || prenom.trim() === eleve.prenom) return;
    try {
      const r = await appeler(`/enseignants/eleves/${eleve.id}`, { methode: "PATCH", corps: { prenom: prenom.trim() } });
      setMessage(`Prénom corrigé : ${r.prenom}.`);
      await chargerEleves(classeId);
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
                  {NIVEAUX.find(([v]) => v === c.niveau)?.[1]} · {libelleClasse(c, LIBELLES_PARCOURS)} · {c.nb_eleves} élève{c.nb_eleves > 1 ? "s" : ""}
                </span>
              </button>
            ))}
          </div>
        )}
        <form className="actions" onSubmit={creer}>
          {matieresPermises.length > 1 && (
            <>
              <label htmlFor="matiere" className="visuellement-cache">
                Matière de la nouvelle classe
              </label>
              <select
                id="matiere"
                value={matiere}
                onChange={(e) => {
                  setMatiere(e.target.value);
                  if (e.target.value === "francais" && !NIVEAUX_FRANCAIS.includes(niveau)) setNiveau("2nde");
                }}
                style={{ width: "auto" }}
              >
                {matieresPermises.map((m) => (
                  <option key={m} value={m}>
                    {MATIERES_CLASSES[m]}
                  </option>
                ))}
              </select>
            </>
          )}
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
            {[["Collège", true], ["Lycée", false]].map(([groupe, college]) => (
              <optgroup key={groupe} label={groupe}>
                {NIVEAUX.filter(([v]) => NIVEAUX_COLLEGE.includes(v) === college && (!enFrancais || NIVEAUX_FRANCAIS.includes(v))).map(([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
          {!enFrancais && PARCOURS_PAR_NIVEAU[niveau].length > 1 && (
            <>
              <label htmlFor="parcours" className="visuellement-cache">
                Parcours de la nouvelle classe
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
            Chaque élève se connecte avec son <strong>identifiant</strong> et son <strong>code personnel</strong>, imprimés sur sa
            carte avec un QR code (ou, sans carte, avec son prénom, ce code classe et son code personnel).{" "}
            <button className="lien" onClick={cartesDeLaClasse} disabled={!eleves?.length}>
              Imprimer les cartes de toute la classe
            </button>
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
                          {e.identifiant && (
                            <span className="doux petit" style={{ display: "block" }}>
                              <code>{e.identifiant}</code>
                            </span>
                          )}
                          {e.classes_liees?.length > 0 && (
                            <span className="doux petit" style={{ display: "block" }}>
                              aussi : {e.classes_liees.join(", ")}
                            </span>
                          )}
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
                          <button
                            className="lien petit"
                            aria-expanded={liens?.eleveId === e.id}
                            onClick={() => basculerLiens(e.id)}
                            aria-label={`Autres parcours de ${e.prenom}`}
                          >
                            Parcours
                          </button>
                          <button
                            className="lien petit"
                            aria-expanded={parentsDe === e.id}
                            onClick={() => setParentsDe(parentsDe === e.id ? null : e.id)}
                            aria-label={`Comptes parents de ${e.prenom}`}
                          >
                            Parents
                          </button>
                          <button className="lien petit" onClick={() => renommer(e)} aria-label={`Corriger le prénom de ${e.prenom}`}>
                            Renommer
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
                      {liens?.eleveId === e.id && (
                        <tr className="detail">
                          <td colSpan={5}>
                            <ParcoursLies eleve={e} liens={liens} onRelier={relier} onDelier={delier} />
                          </td>
                        </tr>
                      )}
                      {parentsDe === e.id && (
                        <tr className="detail">
                          <td colSpan={5}>
                            <ParentsEleve eleve={e} appeler={appeler} />
                          </td>
                        </tr>
                      )}
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
          <AjoutEnfants
            key={classe.id}
            chercher={chercherEnfants}
            ajouter={(ids) => appeler(`/enseignants/classes/${classeId}/enfants`, { methode: "POST", corps: { enfant_ids: ids } })}
            onAjoutes={() => Promise.all([chargerEleves(classeId), chargerClasses()])}
          />
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

/** Codes en clair : affichés une seule fois (stockés hachés). Imprimés sous forme de cartes à découper :
 * identifiant + code personnel + QR code qui connecte l'élève directement depuis son téléphone. */
/** Cartes à imprimer ; PKP Anglais passe son propre intitulé et sa page de connexion (`/anglais/eleve`). */
export function FicheCodes({ classe, codes, onFermer, intitule = `Classe ${classe}`, chemin = "/eleve" }) {
  const [qr, setQr] = useState({}); // identifiant → SVG du QR code

  useEffect(() => {
    let actif = true;
    Promise.all(
      codes
        .filter((c) => c.identifiant)
        .map(async (c) => [c.identifiant, await QRCode.toString(lienCarte(c, chemin), { type: "svg", margin: 1, width: 110 })]),
    ).then((paires) => actif && setQr(Object.fromEntries(paires)), () => {});
    return () => {
      actif = false;
    };
  }, [codes, chemin]);

  return (
    <div className="fiche-codes" role="region" aria-label="Codes personnels à distribuer">
      <h3>Cartes de connexion — {intitule}</h3>
      <p className="aide">
        Ces codes ne seront plus affichés : imprimez les cartes maintenant. Un code perdu se remplace par « Nouveau code » ;
        l'identifiant, lui, ne change pas. À la maison, l'élève scanne son QR code ou saisit son identifiant et son code.
      </p>
      {codes.length === 0 ? (
        <p className="doux">Aucun nouveau code.</p>
      ) : (
        <ul className="cartes-eleves">
          {codes.map((c) => (
            <li key={c.id ?? c.prenom} className="carte-eleve">
              <div>
                <strong>{c.prenom}</strong>
                <span className="doux petit">{intitule}</span>
                {c.identifiant && (
                  <span>
                    Identifiant : <code className="identifiant-eleve">{c.identifiant}</code>
                  </span>
                )}
                <span>
                  Code personnel : <code className="code-personnel">{c.code}</code>
                </span>
                <span className="doux petit">{window.location.origin}{chemin}</span>
              </div>
              {qr[c.identifiant] && (
                <span
                  className="qr-eleve"
                  role="img"
                  aria-label={`QR code de connexion de ${c.prenom}`}
                  dangerouslySetInnerHTML={{ __html: qr[c.identifiant] }}
                />
              )}
            </li>
          ))}
        </ul>
      )}
      <div className="actions">
        <button onClick={() => window.print()} disabled={codes.length === 0}>
          Imprimer les cartes
        </button>
        <button className="secondaire" onClick={onFermer}>
          J'ai imprimé les cartes
        </button>
      </div>
    </div>
  );
}

/** Lien encodé dans le QR code : le code est dans le fragment (#), jamais envoyé au serveur. */
export function lienCarte({ identifiant, code }, chemin = "/eleve") {
  return `${window.location.origin}${chemin}#carte=${identifiant}.${code}`;
}

/** Le même élève dans vos autres classes (spécialité, mise à niveau, excellence…) : un seul code, bascule libre. */
function ParcoursLies({ eleve, liens, onRelier, onDelier }) {
  return (
    <div className="parcours-lies">
      <strong>Autres parcours de {eleve.prenom}</strong>
      {liens.liees.length > 0 ? (
        <>
          <ul>
            {liens.liees.map((i) => (
              <li key={i.eleve_id}>
                {i.code_classe} · {libelleNiveauParcours(i.niveau, i.parcours)}
              </li>
            ))}
          </ul>
          <p className="aide">
            Un seul code pour toutes ces classes ; une fois connecté·e, {eleve.prenom} change de parcours depuis son espace.
          </p>
          <button className="lien petit" onClick={() => onDelier(eleve)}>
            Détacher cette classe des autres parcours
          </button>
        </>
      ) : (
        <p className="doux">Aucun autre parcours relié.</p>
      )}
      {liens.suggestions.length > 0 && (
        <>
          <p>Même prénom dans vos autres classes : est-ce le même élève ?</p>
          <ul>
            {liens.suggestions.map((s) => (
              <li key={s.eleve_id}>
                {s.prenom} · {s.code_classe} · {libelleNiveauParcours(s.niveau, s.parcours)}{" "}
                <button className="secondaire petit" onClick={() => onRelier(eleve, s)}>
                  Relier
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
      {liens.liees.length === 0 && liens.suggestions.length === 0 && (
        <p className="aide">
          Pour relier une autre inscription, inscrivez {eleve.prenom} avec le même prénom dans votre autre classe : elle
          apparaîtra ici.
        </p>
      )}
    </div>
  );
}
