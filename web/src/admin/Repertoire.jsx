// Administrateur : répertoire de tous les élèves (un élève = un enfant de famille) et fiche élève (V3, Lot 1).
import { useCallback, useEffect, useState } from "react";
import { Erreur } from "../composants.jsx";
import { NIVEAUX } from "../parcours.js";
import { Modale, Pagination, Vide, exporterCsv, formaterDate, pourcentage } from "../ui/Cadre.jsx";
import { BarreSelection, CaseLigne, CaseTout, ConfirmationSuppression, useSelection } from "../ui/Selection.jsx";
import { avecDomaine, parametre } from "./BandeauAdmin.jsx";
import { nomComplet } from "./EnfantsFamille.jsx";
import { parcoursCourt } from "./GestionClasses.jsx";

const NOM_NIVEAU = Object.fromEntries(NIVEAUX);
const TAILLE_PAGE = 50;
export const nomResponsable = (r) => `${r.prenom} ${r.nom}`.trim() || r.email;

const ACTIONS = {
  "rattacher-enfant": "Responsable rattaché",
  "detacher-enfant": "Responsable retiré",
  "ajouter-enfant": "Ajouté à une famille",
  modifier: "Identité ou niveau modifié",
  "nouvelle-carte": "Nouvelle carte",
  bloquer: "Carte bloquée",
  debloquer: "Carte débloquée",
  "changer-niveau": "Niveau changé (en groupe)",
  supprimer: "Supprimé",
};

/** Ligne CSV d'un élève : ce qui sert à un tableur, sans code ni mot de passe. */
const ligneCsv = (e) => ({
  prenom: e.prenom,
  nom: e.nom,
  niveau: e.niveau,
  identifiant: e.identifiant,
  maths: e.maths.map((m) => `${m.code_classe}${m.principal ? "" : " (option)"}`).join(", "),
  anglais: e.anglais.map((a) => a.groupe).join(", "),
  responsables: e.responsables.map((r) => r.email).join(", "),
  bloque: e.bloque ? "oui" : "non",
  derniere_connexion: e.derniere_connexion ?? "",
  a_verifier: e.alertes.join(" ; "),
});

export default function Repertoire({ appeler, erreur, domaine = "" }) {
  const [q, setQ] = useState(() => parametre("eleve_q"));
  const [filtres, setFiltres] = useState({ niveau: "", statut: "", sans_responsable: false, sans_classe: false, a_verifier: false });
  const [tri, setTri] = useState("nom");
  const [page, setPage] = useState(1);
  const [donnees, setDonnees] = useState(null);
  const [classes, setClasses] = useState([]);
  const [message, setMessage] = useState(null);
  const [echec, setEchec] = useState(null);
  const [suppression, setSuppression] = useState(false);
  const [ouverte, setOuverte] = useState(() => Number(parametre("eleve")) || null);
  const selection = useSelection();

  const charger = useCallback(() => {
    const params = new URLSearchParams({ page: String(page), tri });
    if (q.trim()) params.set("q", q.trim());
    if (domaine) params.set("domaine", domaine);
    if (filtres.niveau) params.set("niveau", filtres.niveau);
    if (filtres.statut) params.set("statut", filtres.statut);
    for (const cle of ["sans_responsable", "sans_classe", "a_verifier"]) if (filtres[cle]) params.set(cle, "true");
    return appeler(`/admin/repertoire?${params}`).then(setDonnees, () => {});
  }, [appeler, q, filtres, tri, page, domaine]);

  useEffect(() => {
    const t = setTimeout(charger, 250);
    return () => clearTimeout(t);
  }, [charger]);
  useEffect(() => {
    appeler(avecDomaine("/admin/classes", domaine)).then(setClasses, () => {});
  }, [appeler, domaine]);

  const filtrer = (cle, valeur) => {
    setFiltres((f) => ({ ...f, [cle]: valeur }));
    setPage(1);
  };

  async function agir(promesse, succes) {
    setMessage(null);
    setEchec(null);
    try {
      const r = await promesse;
      setMessage(typeof succes === "function" ? succes(r) : succes);
      selection.vider();
      charger();
    } catch (err) {
      setEchec(err.message);
    }
  }

  const elements = donnees?.elements ?? [];
  const choisis = elements.filter((e) => selection.choisis.has(e.id));
  const niveauCommun = choisis.length && choisis.every((e) => e.niveau === choisis[0].niveau) ? choisis[0].niveau : null;

  function inscrire(ids, classeId) {
    return agir(appeler(`/admin/classes/${classeId}/enfants`, { methode: "POST", corps: { enfant_ids: ids } }), (r) => {
      if (r.refus.length) setEchec(r.refus.join(" "));
      return r.ajoutes.length ? `Inscription faite : ${r.ajoutes.join(", ")}.` : null;
    });
  }

  return (
    <section className="carte">
      <div className="filtres">
        <div style={{ flexGrow: 3 }}>
          <label htmlFor="rep-recherche">Rechercher (prénom, nom, identifiant, classe, responsable)</label>
          <input
            id="rep-recherche"
            type="search"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setPage(1);
            }}
          />
        </div>
        <div>
          <label htmlFor="rep-niveau">Niveau</label>
          <select id="rep-niveau" value={filtres.niveau} onChange={(e) => filtrer("niveau", e.target.value)}>
            <option value="">Tous</option>
            {NIVEAUX.map(([v, l]) => (
              <option key={v} value={v}>{l}</option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="rep-statut">Statut</label>
          <select id="rep-statut" value={filtres.statut} onChange={(e) => filtrer("statut", e.target.value)}>
            <option value="">Tous</option>
            <option value="actif">Actifs</option>
            <option value="bloque">Bloqués</option>
          </select>
        </div>
        <div>
          <label htmlFor="rep-tri">Trier par</label>
          <select id="rep-tri" value={tri} onChange={(e) => (setTri(e.target.value), setPage(1))}>
            <option value="nom">Prénom</option>
            <option value="niveau">Niveau</option>
            <option value="connexion">Dernière connexion</option>
            <option value="recent">Créés récemment</option>
          </select>
        </div>
      </div>
      <div className="filtres-cases">
        <label className="case">
          <input type="checkbox" checked={filtres.a_verifier} onChange={(e) => filtrer("a_verifier", e.target.checked)} /> À vérifier
        </label>
        <label className="case">
          <input type="checkbox" checked={filtres.sans_responsable} onChange={(e) => filtrer("sans_responsable", e.target.checked)} /> Sans
          responsable
        </label>
        <label className="case">
          <input type="checkbox" checked={filtres.sans_classe} onChange={(e) => filtrer("sans_classe", e.target.checked)} /> Inscrits nulle
          part
        </label>
      </div>
      <p className="aide">
        Chaque élève apparaît une fois, avec toutes ses inscriptions. Un élève suit un parcours principal en maths (tronc commun,
        spécialité, techno…) ; excellence, mise à niveau et examens sont des options. Ouvrez la fiche pour voir sa progression, ses
        responsables et son historique.
      </p>
      <Erreur message={erreur || echec} />
      {message && <p className="succes" role="status">{message}</p>}
      {donnees === null && <p className="doux">Chargement…</p>}
      {donnees?.total === 0 && <Vide icone="eleve">Aucun élève ne correspond.</Vide>}
      {elements.length > 0 && (
        <>
          <p className="doux petit">{donnees.total} élève(s)</p>
          <BarreSelection selection={selection} noms={["élève", "élèves"]}>
            <select
              value=""
              aria-label="Inscrire la sélection dans une classe"
              disabled={!niveauCommun}
              title={niveauCommun ? undefined : "Sélectionnez des élèves du même niveau"}
              onChange={(ev) => ev.target.value && inscrire(selection.ids, ev.target.value)}
            >
              <option value="">{niveauCommun ? "Inscrire dans la classe…" : "Inscrire : même niveau requis"}</option>
              {classes
                .filter((c) => c.niveau === niveauCommun)
                .map((c) => (
                  <option key={c.id} value={c.id}>{c.code} · {parcoursCourt(c.parcours)} ({c.enseignant})</option>
                ))}
            </select>
            <select
              value=""
              aria-label="Changer le niveau de la sélection"
              onChange={(ev) =>
                ev.target.value &&
                window.confirm(`Passer ${selection.nombre} élève(s) en ${NOM_NIVEAU[ev.target.value]} ? Leurs inscriptions restent.`) &&
                agir(
                  appeler("/admin/enfants/niveau", { methode: "POST", corps: { ids: selection.ids, niveau: ev.target.value } }),
                  `Niveau changé : ${NOM_NIVEAU[ev.target.value]}.`,
                )
              }
            >
              <option value="">Changer le niveau…</option>
              {NIVEAUX.map(([v, l]) => (
                <option key={v} value={v}>{l}</option>
              ))}
            </select>
            <button className="secondaire petit" onClick={() => exporterCsv("eleves.csv", choisis.map(ligneCsv))}>Exporter (CSV)</button>
            <button
              className="secondaire petit"
              onClick={() =>
                agir(appeler("/admin/enfants/blocage", { methode: "POST", corps: { ids: selection.ids, bloque: true } }), (r) =>
                  `${r.traites} carte(s) bloquée(s) : connexion suspendue dans toutes les matières.`)
              }
            >
              Bloquer
            </button>
            <button
              className="secondaire petit"
              onClick={() =>
                agir(appeler("/admin/enfants/blocage", { methode: "POST", corps: { ids: selection.ids, bloque: false } }), (r) =>
                  `${r.traites} carte(s) débloquée(s).`)
              }
            >
              Débloquer
            </button>
            <button className="danger petit" onClick={() => setSuppression(true)}>Supprimer</button>
          </BarreSelection>
          <div className="tableau-defilant">
            <table>
              <thead>
                <tr>
                  <CaseTout selection={selection} ids={elements.map((e) => e.id)} libelle="Sélectionner tous les élèves affichés" />
                  <th>Élève</th>
                  <th>Niveau</th>
                  <th>Identifiant</th>
                  <th>Maths</th>
                  <th>Anglais</th>
                  <th>Responsables</th>
                  <th>Dernière connexion</th>
                  <th>Inscrire en maths</th>
                  <th><span className="visuellement-cache">Fiche</span></th>
                </tr>
              </thead>
              <tbody>
                {elements.map((e) => (
                  <tr key={e.id}>
                    <CaseLigne selection={selection} id={e.id} libelle={`Sélectionner ${nomComplet(e)}`} />
                    <td>
                      <strong>{nomComplet(e)}</strong> {e.bloque && <span className="badge alerte insecable">Bloqué</span>}
                      {e.alertes.length > 0 && (
                        <div className="badges">
                          {e.alertes.map((a) => <span key={a} className="badge alerte">{a}</span>)}
                        </div>
                      )}
                    </td>
                    <td>{NOM_NIVEAU[e.niveau] ?? e.niveau}</td>
                    <td><code>{e.identifiant}</code></td>
                    <td>
                      {e.maths.length ? (
                        <div className="badges">
                          {e.maths.map((m) => (
                            <span key={m.eleve_id} className={m.principal ? "badge accent" : "badge neutre"} title={m.libelle_parcours}>
                              {m.code_classe}{m.principal ? "" : " · option"}{m.archivee ? " · archivée" : ""}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="doux">—</span>
                      )}
                    </td>
                    <td>{e.anglais.length ? e.anglais.map((a) => a.groupe).join(", ") : <span className="doux">—</span>}</td>
                    <td>{e.responsables.length ? e.responsables.map(nomResponsable).join(", ") : <span className="doux">—</span>}</td>
                    <td>{e.derniere_connexion ? formaterDate(e.derniere_connexion, { heure: true }) : <span className="doux">jamais</span>}</td>
                    <td>
                      <InscrireDansClasse eleve={e} classes={classes} onChoix={(classeId) => inscrire([e.id], classeId)} />
                    </td>
                    <td>
                      <button className="secondaire petit" onClick={() => setOuverte(e.id)} aria-label={`Ouvrir la fiche de ${nomComplet(e)}`}>
                        Fiche
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={page} total={donnees.total} taille={TAILLE_PAGE} onChange={setPage} />
        </>
      )}
      {ouverte && <FicheEleve id={ouverte} appeler={appeler} onFermer={() => setOuverte(null)} onChange={charger} />}
      {suppression && (
        <ConfirmationSuppression
          titre={`Supprimer ${selection.nombre} élève(s)`}
          onFermer={() => setSuppression(false)}
          onConfirmer={async (confirmation) => {
            const r = await appeler("/admin/enfants/suppression", { methode: "POST", corps: { ids: selection.ids, confirmation } });
            setSuppression(false);
            setMessage(`${r.traites} élève(s) supprimé(s), avec leurs inscriptions, leur travail et leurs archives.`);
            selection.vider();
            charger();
          }}
        >
          <p>
            Les élèves sélectionnés sont effacés (droit à l'effacement) avec toutes leurs inscriptions, séances, réponses et archives. Un
            compte responsable qui n'a plus d'enfant est supprimé aussi.
          </p>
        </ConfirmationSuppression>
      )}
    </section>
  );
}

function InscrireDansClasse({ eleve, classes, onChoix }) {
  const possibles = classes.filter((c) => c.niveau === eleve.niveau && !eleve.maths.some((m) => m.code_classe === c.code));
  return (
    <select
      value=""
      aria-label={`Inscrire ${nomComplet(eleve)} dans une classe`}
      onChange={(ev) => ev.target.value && onChoix(ev.target.value)}
      disabled={!possibles.length}
    >
      <option value="">{possibles.length ? "Choisir une classe…" : "Aucune autre classe de ce niveau"}</option>
      {possibles.map((c) => (
        <option key={c.id} value={c.id}>{c.code} · {parcoursCourt(c.parcours)} ({c.enseignant})</option>
      ))}
    </select>
  );
}

// --- Fiche élève ---------------------------------------------------------------------------------------

export function FicheEleve({ id, appeler, onFermer, onChange }) {
  const [fiche, setFiche] = useState(null);
  const [erreur, setErreur] = useState(null);
  const [message, setMessage] = useState(null);
  const [secret, setSecret] = useState(null);
  const [identite, setIdentite] = useState(null);
  const [ajout, setAjout] = useState({ email: "", prenom: "", nom: "" });
  const [archive, setArchive] = useState(null);

  const charger = useCallback(
    () =>
      appeler(`/admin/enfants/${id}/fiche`).then(
        (f) => {
          setFiche(f);
          setIdentite({ prenom: f.eleve.prenom, nom: f.eleve.nom, niveau: f.eleve.niveau });
        },
        (err) => setErreur(err.message),
      ),
    [appeler, id],
  );
  useEffect(() => {
    charger();
  }, [charger]);

  async function agir(promesse, succes) {
    setErreur(null);
    setMessage(null);
    setSecret(null);
    try {
      const r = await promesse;
      if (succes) setMessage(typeof succes === "function" ? succes(r) : succes);
      await charger();
      onChange?.();
      return r;
    } catch (err) {
      setErreur(err.message);
      return null;
    }
  }

  async function enregistrerIdentite(ev) {
    ev.preventDefault();
    await agir(appeler(`/admin/enfants/${id}`, { methode: "PATCH", corps: identite }), "Fiche mise à jour, dans toutes ses inscriptions.");
  }

  async function nouvelleCarte() {
    if (!window.confirm("Nouveau code pour cet élève ? L'ancien cesse de fonctionner dans toutes les matières.")) return;
    const r = await agir(appeler(`/admin/enfants/${id}/carte`, { methode: "POST" }));
    if (r) setSecret({ titre: "Nouvelle carte", lignes: [["Identifiant", r.identifiant], ["Code", r.code]] });
  }

  async function ajouterResponsable(ev) {
    ev.preventDefault();
    const envoyer = (confirmer) =>
      appeler(`/admin/enfants/${id}/responsables${confirmer ? "?confirmer=true" : ""}`, { methode: "POST", corps: ajout });
    let r;
    try {
      r = await envoyer(false);
    } catch (err) {
      if (err.status === 409 && /supplémentaire/.test(err.message) && window.confirm(err.message)) r = await agir(envoyer(true));
      else return setErreur(err.message);
    }
    if (!r) return;
    setAjout({ email: "", prenom: "", nom: "" });
    await charger();
    onChange?.();
    setMessage(r.cree ? "Compte responsable créé et rattaché." : "Responsable rattaché (compte existant, mot de passe inchangé).");
    if (r.mot_de_passe_provisoire) {
      setSecret({ titre: "Compte créé", lignes: [["E-mail", r.responsable.email], ["Mot de passe provisoire", r.mot_de_passe_provisoire]] });
    }
  }

  async function retirerResponsable(r) {
    const seul = fiche.eleve.responsables.length === 1;
    const texte = `Retirer ${nomResponsable(r)} des responsables de cet élève ?${
      seul ? " C'est son seul responsable." : ""
    } Un compte qui ne suit plus aucun enfant est supprimé.`;
    if (!window.confirm(texte)) return;
    await agir(appeler(`/admin/enfants/${id}/responsables/${r.id}`, { methode: "DELETE" }), "Responsable retiré.");
  }

  const e = fiche?.eleve;
  return (
    <Modale titre={e ? `Fiche de ${nomComplet(e)}` : "Fiche élève"} onFermer={onFermer} large>
      <Erreur message={erreur} />
      {message && <p className="succes" role="status">{message}</p>}
      {secret && (
        <div className="fiche-codes" role="status">
          <strong>{secret.titre} : à noter maintenant, ce ne sera plus affiché.</strong>
          <dl>
            {secret.lignes.map(([k, v]) => (
              <div key={k}>
                <dt>{k}</dt>
                <dd><code>{v}</code></dd>
              </div>
            ))}
          </dl>
        </div>
      )}
      {!fiche && !erreur && <p className="doux">Chargement…</p>}
      {e && (
        <div className="fiche-eleve">
          <section>
            <h3>Identité et accès</h3>
            <p>
              Identifiant <code>{e.identifiant}</code> · {e.a_un_code ? "carte active" : "sans code"}
              {e.bloque && <span className="badge alerte"> Bloqué</span>} · dernière connexion{" "}
              {e.derniere_connexion ? formaterDate(e.derniere_connexion, { heure: true }) : "jamais"} · créé le {formaterDate(e.cree_le)}
            </p>
            {e.alertes.length > 0 && (
              <div className="badges">
                {e.alertes.map((a) => <span key={a} className="badge alerte">{a}</span>)}
              </div>
            )}
            <form className="ligne-champs souple" onSubmit={enregistrerIdentite}>
              <div>
                <label htmlFor="fe-prenom">Prénom</label>
                <input id="fe-prenom" value={identite.prenom} onChange={(ev) => setIdentite({ ...identite, prenom: ev.target.value })} required />
              </div>
              <div>
                <label htmlFor="fe-nom">Nom (facultatif)</label>
                <input id="fe-nom" value={identite.nom} onChange={(ev) => setIdentite({ ...identite, nom: ev.target.value })} />
              </div>
              <div>
                <label htmlFor="fe-niveau">Niveau</label>
                <select id="fe-niveau" value={identite.niveau} onChange={(ev) => setIdentite({ ...identite, niveau: ev.target.value })}>
                  {NIVEAUX.map(([v, l]) => (
                    <option key={v} value={v}>{l}</option>
                  ))}
                </select>
              </div>
            </form>
            <div className="actions">
              <button onClick={enregistrerIdentite}>Enregistrer</button>
              <button className="secondaire" onClick={nouvelleCarte}>Nouvelle carte</button>
            </div>
          </section>

          <section>
            <h3>Responsables</h3>
            {e.responsables.length === 0 && <p className="alerte-texte">Aucun responsable : rattachez un compte ci-dessous.</p>}
            <ul className="liste-simple">
              {e.responsables.map((r) => (
                <li key={r.id}>
                  <strong>{nomResponsable(r)}</strong> {nomResponsable(r) !== r.email && <span className="doux">{r.email}</span>}{" "}
                  {r.mdp_provisoire && <span className="badge neutre">mot de passe provisoire</span>}{" "}
                  {r.bloque && <span className="badge alerte">bloqué</span>}{" "}
                  <button className="lien petit" onClick={() => retirerResponsable(r)}>Retirer</button>
                </li>
              ))}
            </ul>
            <form onSubmit={ajouterResponsable}>
              <div className="ligne-champs souple">
                <div style={{ flexGrow: 2 }}>
                  <label htmlFor="fe-email">E-mail du responsable</label>
                  <input id="fe-email" type="email" value={ajout.email} onChange={(ev) => setAjout({ ...ajout, email: ev.target.value })} required />
                </div>
                <div>
                  <label htmlFor="fe-r-prenom">Prénom</label>
                  <input id="fe-r-prenom" value={ajout.prenom} onChange={(ev) => setAjout({ ...ajout, prenom: ev.target.value })} />
                </div>
                <div>
                  <label htmlFor="fe-r-nom">Nom</label>
                  <input id="fe-r-nom" value={ajout.nom} onChange={(ev) => setAjout({ ...ajout, nom: ev.target.value })} />
                </div>
              </div>
              <p className="aide">Un compte existant à cette adresse est rattaché tel quel ; sinon il est créé avec un mot de passe provisoire.</p>
              <button className="secondaire" type="submit">Rattacher ce responsable</button>
            </form>
          </section>

          <section>
            <h3>Inscriptions et progression</h3>
            {fiche.maths.length === 0 && fiche.anglais.length === 0 && <p className="doux">Inscrit nulle part pour l'instant.</p>}
            {fiche.maths.length > 0 && (
              <div className="tableau-defilant">
                <table>
                  <thead>
                    <tr><th>Classe de maths</th><th>Parcours</th><th>Professeur</th><th>Séances</th><th>Réponses</th><th>Réussite</th><th>Dernière activité</th></tr>
                  </thead>
                  <tbody>
                    {fiche.maths.map((m) => (
                      <tr key={m.eleve_id}>
                        <td>{m.code_classe}</td>
                        <td>
                          {parcoursCourt(m.parcours)} <span className={m.principal ? "badge accent" : "badge neutre"}>{m.principal ? "principal" : "option"}</span>{m.archivee && <span className="badge neutre"> classe archivée</span>}
                        </td>
                        <td>{m.enseignant}</td>
                        <td>{m.seances}</td>
                        <td>{m.reponses}</td>
                        <td>{pourcentage(m.taux_reussite)}</td>
                        <td>{m.derniere_activite ? formaterDate(m.derniere_activite) : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {fiche.anglais.length > 0 && (
              <div className="tableau-defilant">
                <table>
                  <thead>
                    <tr><th>Groupe d'anglais</th><th>Professeur</th><th>Séances faites</th><th>Dernière activité</th></tr>
                  </thead>
                  <tbody>
                    {fiche.anglais.map((a) => (
                      <tr key={a.eleve_id}>
                        <td>{a.groupe}{a.archivee && <span className="badge neutre"> archivé</span>}</td>
                        <td>{a.enseignant}</td>
                        <td>{a.seances}</td>
                        <td>{a.derniere_activite ? formaterDate(a.derniere_activite) : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section>
            <h3>Inscriptions archivées</h3>
            {fiche.archives.length === 0 ? (
              <p className="doux">Aucune : le travail des classes supprimées ou des inscriptions retirées apparaîtrait ici.</p>
            ) : (
              <ul className="liste-simple">
                {fiche.archives.map((a) => (
                  <li key={a.id}>
                    <strong>{a.cours}</strong> ({a.matiere}{a.parcours ? `, ${parcoursCourt(a.parcours)}` : ""}, {a.enseignant}) — {a.motif} le{" "}
                    {formaterDate(a.archivee_le)} par {a.par} · {a.resume.seances} séance(s)
                    {a.resume.reponses != null && `, ${a.resume.reponses} réponse(s)`}{" "}
                    <button className="lien petit" onClick={() => appeler(`/admin/archives/${a.id}`).then(setArchive, (err) => setErreur(err.message))}>
                      Détail
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {archive && <DetailArchive archive={archive} onFermer={() => setArchive(null)} />}
          </section>

          <section>
            <h3>Historique administratif</h3>
            {fiche.historique.length === 0 ? (
              <p className="doux">Aucune opération enregistrée.</p>
            ) : (
              <div className="tableau-defilant">
                <table>
                  <thead>
                    <tr><th>Date</th><th>Opération</th><th>Par</th></tr>
                  </thead>
                  <tbody>
                    {fiche.historique.map((h, i) => (
                      <tr key={i}>
                        <td>{formaterDate(h.le, { heure: true })}</td>
                        <td>{ACTIONS[h.action] ?? h.action}</td>
                        <td>{h.admin ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>
      )}
    </Modale>
  );
}

function DetailArchive({ archive, onFermer }) {
  const { seances = [], progression = [] } = archive.contenu;
  return (
    <Modale titre={`Archive : ${archive.cours}`} onFermer={onFermer} large>
      <p className="doux">
        {archive.motif} le {formaterDate(archive.archivee_le, { heure: true })} par {archive.par}. Copie figée, en lecture seule.
      </p>
      {seances.length > 0 && (
        <div className="tableau-defilant">
          <table>
            <thead>
              <tr><th>Séance</th><th>Réponses</th><th>Justes</th><th>Compétences</th></tr>
            </thead>
            <tbody>
              {seances.map((s, i) => (
                <tr key={i}>
                  <td>{formaterDate(s.debut, { heure: true })}</td>
                  <td>{s.reponses.length}</td>
                  <td>{s.reponses.filter((r) => r.correcte).length}</td>
                  <td>{[...new Set(s.reponses.map((r) => r.competence))].join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {progression.length > 0 && (
        <div className="tableau-defilant">
          <table>
            <thead>
              <tr><th>Séance d'anglais</th><th>Meilleur score</th><th>Tentatives</th></tr>
            </thead>
            <tbody>
              {progression.map((p) => (
                <tr key={p.seance}>
                  <td>{p.seance}</td>
                  <td>{p.meilleur_score} / {p.total}</td>
                  <td>{p.tentatives}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {seances.length === 0 && progression.length === 0 && <p className="doux">Aucun travail enregistré dans cette inscription.</p>}
    </Modale>
  );
}
