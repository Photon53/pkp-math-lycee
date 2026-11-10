import { useCallback, useEffect, useState } from "react";
import { Erreur } from "../composants.jsx";
import { useApi } from "../enseignant/useApi.js";
import { Maths } from "../maths.jsx";

const BASE = "/admin/prevalidation-ia";

export const RESULTATS = {
  "aucune-anomalie": ["Aucune anomalie détectée", "ok"],
  "a-revoir": ["À revoir", "alerte"],
  "erreur-detectee": ["Erreur détectée", "ko"],
  incertain: ["Vérification incertaine", "neutre"],
};
const STATUTS = { "en-attente": "En attente", terminee: "Rapport rendu", annulee: "Annulée" };
const GRAVITES = { erreur: ["Erreur", "ko"], "a-revoir": ["À revoir", "alerte"], mineure: ["Mineure", "neutre"] };
const ELEMENTS = {
  enonce: "Énoncé", reponse: "Réponse attendue", etape: "Étape", methode: "Méthode", niveau: "Niveau",
  competence: "Compétence", ambiguite: "Ambiguïté", autre: "Autre",
};
const AVIS_ETAPE = { correcte: "Correcte", "a-revoir": "À revoir", erronee: "Erronée", "non-verifiee": "Non vérifiée" };
const ISSUES = { confirme: "Confirmé", ecart: "Écart", impossible: "Impossible", incertain: "Incertain" };
const VALIDATION_HUMAINE = { "a-valider": "à valider", validee: "validé", "a-corriger": "à corriger" };
const NIVEAUX = ["6e", "5e", "4e", "3e", "2nde", "1re", "Tle"];

const date = (d) => (d ? new Date(d).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" }) : "—");

function Resultat({ valeur }) {
  if (!valeur) return <span className="doux">—</span>;
  const [libelle, ton] = RESULTATS[valeur] ?? [valeur, "neutre"];
  return <span className={`badge ${ton}`}>{libelle}</span>;
}

/**
 * Prévalidation IA des exercices (ticket #48), réservée aux administrateurs : l'API le revérifie à chaque appel.
 * Premier contrôle automatique : il ne valide ni ne publie rien, et ne modifie aucun exercice.
 */
export default function PrevalidationIA({ jeton, onExpire }) {
  const [onglet, setOnglet] = useState("rapports");
  const [rechargement, setRechargement] = useState(0);
  return (
    <section className="carte">
      <p className="avertissement">
        Premier contrôle par une IA, visible des seuls administrateurs. Il ne valide ni ne publie un exercice et n'en modifie
        jamais le contenu : la validation par un professeur reste nécessaire. Deux IA peuvent partager la même erreur.
      </p>
      <div className="onglets" role="tablist">
        {[
          ["rapports", "Rapports"],
          ["lancer", "Lancer un contrôle"],
          ["bilan", "Bilan de l'essai"],
          ["service", "Compte de service"],
        ].map(([v, l]) => (
          <button key={v} role="tab" aria-selected={onglet === v} className={onglet === v ? "onglet actif" : "onglet"} onClick={() => setOnglet(v)}>
            {l}
          </button>
        ))}
      </div>
      {onglet === "rapports" && <Rapports jeton={jeton} onExpire={onExpire} rechargement={rechargement} />}
      {onglet === "lancer" && (
        <Lancer
          jeton={jeton}
          onExpire={onExpire}
          onLance={() => {
            setRechargement((n) => n + 1);
            setOnglet("rapports");
          }}
        />
      )}
      {onglet === "bilan" && <Bilan jeton={jeton} onExpire={onExpire} />}
      {onglet === "service" && <CompteService jeton={jeton} onExpire={onExpire} />}
    </section>
  );
}

function Lancer({ jeton, onExpire, onLance }) {
  const { appeler, erreur } = useApi(jeton, onExpire);
  const [mode, setMode] = useState("echantillon");
  const [ids, setIds] = useState("");
  const [echantillon, setEchantillon] = useState({ taille: 10, niveau: "", auteur_ia: true });
  const [envoi, setEnvoi] = useState(false);
  const [lance, setLance] = useState(null);

  async function lancer(e) {
    e.preventDefault();
    const corps =
      mode === "ids"
        ? { question_ids: ids.split(/[\s,;]+/).filter(Boolean).map(Number) }
        : { echantillon: { taille: Number(echantillon.taille), auteur_ia: echantillon.auteur_ia, ...(echantillon.niveau ? { niveau: echantillon.niveau } : {}) } };
    setEnvoi(true);
    try {
      const r = await appeler(`${BASE}/demandes`, { methode: "POST", corps });
      setLance(r);
    } catch {
      // Message affiché par useApi.
    } finally {
      setEnvoi(false);
    }
  }

  const idsValides = ids.split(/[\s,;]+/).filter(Boolean).every((x) => /^\d+$/.test(x)) && ids.trim() !== "";

  return (
    <form onSubmit={lancer}>
      <p className="doux">
        Le vérificateur IA résout d'abord l'énoncé sans le corrigé, puis compare sa réponse et chaque étape de la correction proposée.
        Pour le premier essai, une dizaine d'exercices variés suffit.
      </p>
      <fieldset className="filtres-cases">
        <label>
          <input type="radio" name="mode" checked={mode === "echantillon"} onChange={() => setMode("echantillon")} /> Un échantillon tiré au hasard
        </label>
        <label>
          <input type="radio" name="mode" checked={mode === "ids"} onChange={() => setMode("ids")} /> Des exercices choisis
        </label>
      </fieldset>
      {mode === "ids" ? (
        <label>
          Numéros des exercices (séparés par des virgules)
          <input value={ids} onChange={(e) => setIds(e.target.value)} placeholder="12, 57, 203" />
        </label>
      ) : (
        <div className="filtres">
          <label>
            Nombre d'exercices
            <input type="number" min={1} max={50} value={echantillon.taille} onChange={(e) => setEchantillon({ ...echantillon, taille: e.target.value })} />
          </label>
          <label>
            Niveau
            <select value={echantillon.niveau} onChange={(e) => setEchantillon({ ...echantillon, niveau: e.target.value })}>
              <option value="">Tous</option>
              {NIVEAUX.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <label style={{ alignSelf: "center" }}>
            <input type="checkbox" checked={echantillon.auteur_ia} onChange={(e) => setEchantillon({ ...echantillon, auteur_ia: e.target.checked })} /> Seulement
            les exercices générés par IA
          </label>
        </div>
      )}
      <Erreur message={erreur} />
      <div className="actions">
        <button type="submit" disabled={envoi || (mode === "ids" && !idsValides)}>
          Lancer la prévalidation
        </button>
      </div>
      {lance && (
        <div className="info" style={{ padding: 12, borderRadius: 8, marginTop: 12 }}>
          <p>
            Lot <strong>{lance.lot}</strong> : {lance.creees.length} demande{lance.creees.length > 1 ? "s" : ""} en attente du vérificateur
            {lance.deja_en_attente.length > 0 && ` (${lance.deja_en_attente.length} déjà en attente, non relancée${lance.deja_en_attente.length > 1 ? "s" : ""})`}.
          </p>
          <button type="button" className="secondaire" onClick={onLance}>
            Voir les rapports
          </button>
        </div>
      )}
    </form>
  );
}

function Rapports({ jeton, onExpire, rechargement }) {
  const { appeler, erreur } = useApi(jeton, onExpire);
  const [filtres, setFiltres] = useState({ statut: "", resultat: "", lot: "" });
  const [liste, setListe] = useState(null);
  const [ouverte, setOuverte] = useState(null);

  const charger = useCallback(() => {
    const p = new URLSearchParams(Object.entries(filtres).filter(([, v]) => v)).toString();
    appeler(p ? `${BASE}?${p}` : BASE).then(setListe, () => {});
  }, [appeler, filtres]);

  useEffect(() => {
    charger();
  }, [charger, rechargement]);

  const changer = (cle) => (e) => setFiltres({ ...filtres, [cle]: e.target.value });

  return (
    <>
      <div className="filtres">
        <label>
          Statut
          <select value={filtres.statut} onChange={changer("statut")}>
            <option value="">Tous</option>
            {Object.entries(STATUTS).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </label>
        <label>
          Résultat
          <select value={filtres.resultat} onChange={changer("resultat")}>
            <option value="">Tous</option>
            {Object.entries(RESULTATS).map(([v, [l]]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </label>
        <label>
          Lot
          <input value={filtres.lot} onChange={changer("lot")} placeholder="L-20261110-…" />
        </label>
      </div>
      <Erreur message={erreur} />
      {liste === null && !erreur && <p className="doux">Chargement…</p>}
      {liste?.length === 0 && <p className="vide">Aucune prévalidation pour le moment.</p>}
      {liste?.length > 0 && (
        <div className="tableau-defilant">
          <table>
            <thead>
              <tr>
                <th>N°</th>
                <th>Exercice</th>
                <th>Niveau · compétence</th>
                <th>Statut</th>
                <th>Résultat</th>
                <th>Demandée</th>
              </tr>
            </thead>
            <tbody>
              {liste.map((p) => (
                <LigneRapport
                  key={p.id}
                  p={p}
                  ouverte={ouverte === p.id}
                  onBasculer={() => setOuverte(ouverte === p.id ? null : p.id)}
                  appeler={appeler}
                  onMaj={(maj) => setListe((l) => l.map((x) => (x.id === maj.id ? maj : x)))}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function LigneRapport({ p, ouverte, onBasculer, appeler, onMaj }) {
  return (
    <>
      <tr>
        <td>
          <button className="lien" onClick={onBasculer} aria-expanded={ouverte}>
            {p.id}
          </button>
          <div className="doux petit">{p.lot}</div>
        </td>
        <td>
          {p.question_code ?? `#${p.question_id}`}
          <div className="doux petit">version {p.version}</div>
        </td>
        <td>
          {p.niveau} · {p.competence}
        </td>
        <td>
          {STATUTS[p.statut]}
          {p.obsolete && (
            <>
              {" "}
              <span className="badge alerte" title="L'exercice a été modifié depuis : ce rapport ne le décrit plus.">
                Obsolète
              </span>
            </>
          )}
        </td>
        <td>
          <Resultat valeur={p.resultat} />
          {p.nb_anomalies > 0 && <div className="doux petit">{p.nb_anomalies} anomalie{p.nb_anomalies > 1 ? "s" : ""}</div>}
        </td>
        <td>
          {date(p.demandee_le)}
          <div className="doux petit">par {p.demandee_par}</div>
        </td>
      </tr>
      {ouverte && (
        <tr>
          <td colSpan={6}>
            <Detail id={p.id} appeler={appeler} onMaj={onMaj} />
          </td>
        </tr>
      )}
    </>
  );
}

function Detail({ id, appeler, onMaj }) {
  const [d, setD] = useState(null);
  const [verite, setVerite] = useState("");
  const [commentaire, setCommentaire] = useState("");

  useEffect(() => {
    appeler(`${BASE}/${id}`).then((r) => {
      setD(r);
      setVerite(r.verite_humaine ?? "");
      setCommentaire(r.verite_commentaire ?? "");
    }, () => {});
  }, [appeler, id]);

  async function enregistrer(chemin, corps) {
    try {
      const r = await appeler(`${BASE}/${id}/${chemin}`, { methode: "POST", corps });
      setD(r);
      onMaj(r);
    } catch {
      // Message affiché par useApi.
    }
  }

  if (!d) return <p className="doux">Chargement…</p>;
  const r = d.rapport;
  return (
    <div className="fiche-eleve">
      <section>
        <h3>Exercice examiné</h3>
        <Maths texte={d.exercice.enonce} />
        <p className="doux">
          Réponse attendue : {d.exercice.solution} · auteur : {d.exercice.auteur ?? "—"} · validation par un professeur :{" "}
          <strong>{VALIDATION_HUMAINE[d.exercice.statut_validation] ?? d.exercice.statut_validation}</strong>
          {d.exercice.valide_par ? ` (${d.exercice.valide_par})` : ""}
        </p>
        {d.tirage && <p className="doux">Exemplaire examiné : {Object.entries(d.tirage).map(([k, v]) => `${k} = ${v}`).join(", ")}</p>}
        {d.obsolete && <p className="avertissement">L'exercice a été modifié depuis la demande : ce rapport ne décrit plus sa version actuelle. Relancez un contrôle.</p>}
      </section>
      <section>
        <h3>Traçabilité</h3>
        <ul>
          <li>Demandée le {date(d.demandee_le)} par {d.demandee_par} (lot {d.lot})</li>
          <li>Version examinée : <code>{d.version_complete}</code></li>
          <li>Énoncé lu le {date(d.enonce_lu_le)} · corrigé lu le {date(d.corrige_lu_le)} · rapport rendu le {date(d.rendue_le)}</li>
          <li>
            Modèle : {d.modele ?? "—"}
            {d.version_modele ? ` (version ${d.version_modele})` : ""} · compte de service : {d.compte_service ?? "—"}
          </li>
        </ul>
        {d.statut === "en-attente" && (
          <button className="secondaire" onClick={() => enregistrer("annuler")}>
            Annuler la demande
          </button>
        )}
      </section>
      {r && (
        <section>
          <h3>
            Rapport du vérificateur <Resultat valeur={d.resultat} />
          </h3>
          <p style={{ whiteSpace: "pre-wrap" }}>{r.synthese}</p>
          {r.reponse_independante && <p><strong>Réponse trouvée sans le corrigé :</strong> {r.reponse_independante}</p>}
          {r.remarques_enonce && <p><strong>Énoncé :</strong> {r.remarques_enonce}</p>}
          {r.remarques_reponse && <p><strong>Réponse attendue :</strong> {r.remarques_reponse}</p>}
          {r.controle_programme && <p><strong>Niveau et programme :</strong> {r.controle_programme}</p>}
          {r.etapes?.length > 0 && (
            <>
              <h4>Étapes de la correction</h4>
              <ol className="etapes">
                {r.etapes.map((e) => (
                  <li key={e.numero} value={e.numero}>
                    {AVIS_ETAPE[e.avis]}
                    {e.remarque ? ` : ${e.remarque}` : ""}
                  </li>
                ))}
              </ol>
            </>
          )}
          {r.anomalies?.length > 0 && (
            <>
              <h4>Anomalies</h4>
              <ul>
                {r.anomalies.map((a, i) => (
                  <li key={i}>
                    <span className={`badge ${GRAVITES[a.gravite][1]}`}>{GRAVITES[a.gravite][0]}</span> {ELEMENTS[a.element]}
                    {a.etape ? ` ${a.etape}` : ""} : {a.description}
                    {a.justification && <div className="doux">Justification : {a.justification}</div>}
                    {a.suggestion && <div>Suggestion de correction : {a.suggestion}</div>}
                  </li>
                ))}
              </ul>
            </>
          )}
          {r.verifications?.length > 0 && (
            <>
              <h4>Vérifications par calcul</h4>
              <ul>
                {r.verifications.map((v, i) => (
                  <li key={i}>
                    {ISSUES[v.issue]} — {v.description}
                    {v.outil ? ` (${v.outil})` : ""}
                  </li>
                ))}
              </ul>
            </>
          )}
          {r.points_incertains?.length > 0 && (
            <>
              <h4>Vérifications impossibles ou incertaines</h4>
              <ul>
                {r.points_incertains.map((t, i) => (
                  <li key={i}>{t}</li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}
      {d.statut === "terminee" && (
        <section>
          <h3>Essai : ce que savent les professeurs</h3>
          <p className="doux">Pour un lot relu par des professeurs : sert seulement à mesurer les erreurs que l'IA n'a pas vues.</p>
          <div className="filtres">
            <label>
              L'exercice était
              <select value={verite} onChange={(e) => setVerite(e.target.value)}>
                <option value="">Non renseigné</option>
                <option value="erronee">Erroné</option>
                <option value="correcte">Correct</option>
              </select>
            </label>
            <label>
              Commentaire
              <input value={commentaire} onChange={(e) => setCommentaire(e.target.value)} maxLength={1000} />
            </label>
          </div>
          <button onClick={() => enregistrer("verite", { verite: verite || null, commentaire })}>Enregistrer</button>
        </section>
      )}
    </div>
  );
}

function Bilan({ jeton, onExpire }) {
  const { appeler, erreur } = useApi(jeton, onExpire);
  const [lot, setLot] = useState("");
  const [b, setB] = useState(null);

  const charger = useCallback(() => {
    appeler(lot.trim() ? `${BASE}/bilan?lot=${encodeURIComponent(lot.trim())}` : `${BASE}/bilan`).then(setB, () => {});
  }, [appeler, lot]);

  useEffect(() => {
    charger();
    // Rechargé ensuite à la demande (bouton « Calculer »), pas à chaque lettre tapée.
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      <div className="filtres">
        <label>
          Lot (vide : tous)
          <input value={lot} onChange={(e) => setLot(e.target.value)} placeholder="L-20261110-…" />
        </label>
        <button className="secondaire" onClick={charger} style={{ flex: "0 0 auto" }}>
          Calculer
        </button>
      </div>
      <Erreur message={erreur} />
      {b && (
        <>
          <div className="kpis">
            <Kpi libelle="Rapports rendus" valeur={b.rendues} />
            <Kpi libelle="Erreurs connues" valeur={b.erronees_connues} sous={`sur ${b.relues_par_un_professeur} exercices relus`} />
            <Kpi libelle="Erreurs détectées" valeur={b.detectees} />
            <Kpi
              libelle="Erreurs non détectées"
              valeur={b.non_detectees}
              sous={b.taux_non_detection === null ? "aucune erreur connue" : `${Math.round(b.taux_non_detection * 100)} % des erreurs connues`}
            />
            <Kpi libelle="Fausses alertes" valeur={b.fausses_alertes} sous={`sur ${b.correctes_connues} exercices corrects`} />
          </div>
          <p className="doux">
            {Object.entries(b.par_resultat)
              .map(([r, n]) => `${RESULTATS[r][0]} : ${n}`)
              .join(" · ")}
          </p>
          {b.non_detectees_ids.length > 0 && <p className="avertissement">Non détectées : prévalidations n° {b.non_detectees_ids.join(", ")}.</p>}
        </>
      )}
    </>
  );
}

const Kpi = ({ libelle, valeur, sous }) => (
  <div className="kpi">
    <div className="libelle">{libelle}</div>
    <div className="valeur">{valeur}</div>
    {sous && <div className="sous">{sous}</div>}
  </div>
);

const ETATS = { actif: ["Actif", "ok"], expire: ["Expiré", "neutre"], revoque: ["Révoqué", "ko"] };

function CompteService({ jeton, onExpire }) {
  const { appeler, erreur } = useApi(jeton, onExpire);
  const [comptes, setComptes] = useState(null);
  const [acces, setAcces] = useState(null);
  const [nom, setNom] = useState("Vérificateur IA");
  const [duree, setDuree] = useState(30);
  const [nouveau, setNouveau] = useState(null);

  const charger = useCallback(() => {
    appeler(`${BASE}/comptes`).then(setComptes, () => {});
  }, [appeler]);

  useEffect(() => {
    charger();
  }, [charger]);

  async function emettre(chemin, corps) {
    try {
      setNouveau(await appeler(chemin, { methode: "POST", corps }));
      charger();
    } catch {
      // Message affiché par useApi.
    }
  }

  async function revoquer(c) {
    if (!window.confirm(`Révoquer le jeton « ${c.nom} » (${c.prefixe}…) ? Le service IA ne pourra plus se connecter avec.`)) return;
    try {
      await appeler(`${BASE}/comptes/${c.id}/revoquer`, { methode: "POST" });
      charger();
    } catch {
      // Message affiché par useApi.
    }
  }

  return (
    <>
      <p className="doux">
        Le service IA se connecte avec un jeton dédié, distinct des comptes humains : il lit seulement les exercices demandés et dépose
        ses rapports. Il n'accède ni aux élèves, ni aux comptes, ni à la validation ou à la publication. Le jeton n'est montré
        qu'une fois : rangez-le dans le gestionnaire de secrets du service IA, jamais dans un navigateur ou un prompt.
      </p>
      <div className="filtres">
        <label>
          Nom du compte
          <input value={nom} onChange={(e) => setNom(e.target.value)} maxLength={80} />
        </label>
        <label>
          Durée de validité (jours, 90 au plus)
          <input type="number" min={1} max={90} value={duree} onChange={(e) => setDuree(e.target.value)} />
        </label>
        <button style={{ flex: "0 0 auto" }} disabled={nom.trim().length < 2} onClick={() => emettre(`${BASE}/comptes`, { nom: nom.trim(), duree_jours: Number(duree) })}>
          Créer un jeton
        </button>
      </div>
      <Erreur message={erreur} />
      {nouveau && (
        <div className="info" style={{ padding: 12, borderRadius: 8 }}>
          <p>
            Jeton de « {nouveau.compte.nom} », valable jusqu'au {date(nouveau.compte.expire_le)}. Copiez-le maintenant : il ne sera plus affiché.
          </p>
          <code className="secret" style={{ overflowWrap: "anywhere" }}>{nouveau.jeton}</code>
          <div className="actions">
            <button className="secondaire" onClick={() => setNouveau(null)}>
              C'est copié
            </button>
          </div>
        </div>
      )}
      {comptes?.length > 0 && (
        <div className="tableau-defilant">
          <table>
            <thead>
              <tr>
                <th>Compte</th>
                <th>État</th>
                <th>Expire le</th>
                <th>Dernier usage</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {comptes.map((c) => (
                <tr key={c.id}>
                  <td>
                    {c.nom}
                    <div className="doux petit">
                      <code>{c.prefixe}…</code>
                    </div>
                  </td>
                  <td>
                    <span className={`badge ${ETATS[c.etat][1]}`}>{ETATS[c.etat][0]}</span>
                  </td>
                  <td>{date(c.expire_le)}</td>
                  <td>{date(c.dernier_usage_le)}</td>
                  <td>
                    {c.etat === "actif" && (
                      <div className="actions" style={{ margin: 0 }}>
                        <button className="secondaire" onClick={() => emettre(`${BASE}/comptes/${c.id}/renouveler`, { duree_jours: Number(duree) })}>
                          Renouveler
                        </button>
                        <button className="secondaire" onClick={() => revoquer(c)}>
                          Révoquer
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {comptes?.length === 0 && <p className="vide">Aucun jeton de service pour le moment.</p>}
      <details style={{ marginTop: 16 }} onToggle={(e) => e.currentTarget.open && acces === null && appeler(`${BASE}/acces`).then(setAcces, () => {})}>
        <summary>Journal des accès du service</summary>
        {acces?.length === 0 && <p className="doux">Aucun accès.</p>}
        {acces?.length > 0 && (
          <div className="tableau-defilant">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Compte</th>
                  <th>Action</th>
                  <th>Prévalidation</th>
                  <th>Code</th>
                  <th>Adresse</th>
                </tr>
              </thead>
              <tbody>
                {acces.map((a) => (
                  <tr key={a.id}>
                    <td>{date(a.le)}</td>
                    <td>{a.compte_id ?? "inconnu"}</td>
                    <td>{a.action}</td>
                    <td>{a.prevalidation_id ?? "—"}</td>
                    <td>{a.code_http}</td>
                    <td>{a.ip ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </details>
    </>
  );
}
