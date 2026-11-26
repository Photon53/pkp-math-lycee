// Issue #172 — Accueil et demandes : contacts adultes et demandes (Claude)
import { useCallback, useEffect, useState } from "react";
import { telechargerFichier } from "../api.js";
import { MATIERES, TYPES_STRUCTURE } from "../Collaborer.jsx";
import { Erreur, Onglets } from "../composants.jsx";
import { useApi } from "../enseignant/useApi.js";

export const FILES = {
  famille: "Familles et préinscriptions",
  information: "Informations et questions",
  candidature: "Candidatures de professeurs",
  partenariat: "Partenariats de structures",
};
export const STATUTS = { nouveau: "Nouveau", "a-traiter": "À traiter", traite: "Traité" };
export const ISSUES = {
  "suite-demandee": "Suite demandée",
  "inscription-effective": "Inscription effective",
  refus: "Refus",
  cloture: "Clôture",
};
// Même règle que l'API : seule une demande de famille aboutit à une inscription effective.
const ISSUES_PAR_FILE = {
  famille: ["suite-demandee", "inscription-effective", "refus", "cloture"],
  information: ["suite-demandee", "cloture"],
  candidature: ["suite-demandee", "refus", "cloture"],
  partenariat: ["suite-demandee", "refus", "cloture"],
};
const ORIGINES = { "formulaire-collaboration": "Formulaire « Enseigner ou collaborer »", "saisie-admin": "Saisie par l'équipe" };
const LIBELLES_MATIERES = Object.fromEntries(MATIERES);
const LIBELLES_STRUCTURES = Object.fromEntries(TYPES_STRUCTURE);

/**
 * Accueil et demandes (#172) : les demandes des adultes qui ne sont pas encore inscrits, une file par finalité.
 * Une demande ne vaut ni inscription ni compte : son issue est notée explicitement. Les retours des utilisateurs
 * déjà inscrits restent dans « Remarques ».
 */
export default function AccueilDemandes({ jeton, onExpire }) {
  const { appeler, erreur } = useApi(jeton, onExpire);
  const [files, setFiles] = useState(null);
  const [file, setFile] = useState("famille");
  const [filtres, setFiltres] = useState({ statut: "", q: "", depuis: "" });
  const [page, setPage] = useState(1);
  const [resultat, setResultat] = useState(null);
  const [ouverte, setOuverte] = useState(null);
  const [saisie, setSaisie] = useState(false);

  const chargerFiles = useCallback(() => {
    appeler("/admin/accueil/files").then(setFiles, () => {});
  }, [appeler]);

  const charger = useCallback(() => {
    const p = new URLSearchParams({ categorie: file, page: String(page) });
    if (filtres.statut) p.set("statut", filtres.statut);
    if (filtres.q.trim()) p.set("q", filtres.q.trim());
    if (filtres.depuis) p.set("depuis", new Date(filtres.depuis).toISOString());
    appeler(`/admin/accueil/demandes?${p}`).then(setResultat, () => {});
  }, [appeler, file, page, filtres]);

  useEffect(() => {
    chargerFiles();
  }, [chargerFiles]);

  useEffect(() => {
    charger();
  }, [charger]);

  function rafraichir() {
    charger();
    chargerFiles();
  }

  const changer = (cle) => (e) => {
    setFiltres({ ...filtres, [cle]: e.target.value });
    setPage(1);
  };
  const infoFile = files?.find((f) => f.categorie === file);
  const pages = resultat ? Math.max(1, Math.ceil(resultat.total / resultat.taille_page)) : 1;
  const saisissable = file === "famille" || file === "information";

  return (
    <section className="carte">
      <Onglets
        valeur={file}
        options={Object.entries(FILES).map(([c, l]) => {
          const n = files?.find((f) => f.categorie === c)?.nouvelles;
          return [c, n ? `${l} (${n})` : l];
        })}
        onChange={(f) => {
          setFile(f);
          setPage(1);
          setOuverte(null);
          setSaisie(false);
        }}
      />
      {infoFile && !infoFile.conservation_jours && (
        <p className="info">Durée de conservation non fixée pour cette file (décision RGPD-3) : aucune nouvelle demande n'y est enregistrée.</p>
      )}
      {infoFile?.conservation_jours && (
        <p className="doux petit">Conservation : {infoFile.conservation_jours} jours après le dernier traitement, puis suppression automatique.</p>
      )}
      <p className="doux petit">
        Les retours des élèves, parents et professeurs déjà inscrits se traitent dans <a href="/admin/remarques">Remarques</a>.
      </p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "end" }}>
        <label>
          Rechercher
          <input type="search" value={filtres.q} onChange={changer("q")} maxLength={100} placeholder="Référence, nom, e-mail, structure" />
        </label>
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
          Depuis le
          <input type="date" value={filtres.depuis} onChange={changer("depuis")} />
        </label>
        {saisissable && infoFile?.conservation_jours && (
          <button className="secondaire" onClick={() => setSaisie(!saisie)} aria-expanded={saisie}>
            Saisir une demande
          </button>
        )}
      </div>
      {saisie && (
        <Saisie
          categorie={file}
          appeler={appeler}
          onEnregistree={(d) => {
            setSaisie(false);
            setOuverte(d.id);
            rafraichir();
          }}
        />
      )}
      <Erreur message={erreur} />
      {resultat === null && !erreur && <p className="doux">Chargement…</p>}
      {resultat?.total === 0 && <p className="doux">Aucune demande dans cette file.</p>}
      {resultat?.demandes.length > 0 && (
        <div className="tableau-defilant">
          <table>
            <thead>
              <tr>
                <th>Référence</th>
                <th>Date</th>
                <th>Contact</th>
                <th>Statut</th>
                <th>Responsable</th>
              </tr>
            </thead>
            <tbody>
              {resultat.demandes.map((d) => (
                <tr key={d.id}>
                  <td>
                    <button className="lien" aria-expanded={ouverte === d.id} onClick={() => setOuverte(ouverte === d.id ? null : d.id)}>
                      {d.reference}
                    </button>
                  </td>
                  <td>{new Date(d.cree_le).toLocaleDateString("fr-FR")}</td>
                  <td>{d.organisation ? `${d.organisation} (${d.contact})` : d.contact}</td>
                  <td>
                    {STATUTS[d.statut]}
                    {d.issue && ` · ${ISSUES[d.issue]}`}
                  </td>
                  <td>{d.responsable ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {pages > 1 && (
        <div className="actions">
          <button className="secondaire" disabled={page <= 1} onClick={() => setPage(page - 1)}>
            Précédentes
          </button>
          <span className="doux">
            Page {page} sur {pages}
          </span>
          <button className="secondaire" disabled={page >= pages} onClick={() => setPage(page + 1)}>
            Suivantes
          </button>
        </div>
      )}
      {ouverte && (
        <Fiche
          key={ouverte}
          id={ouverte}
          jeton={jeton}
          onExpire={onExpire}
          onOuvrir={setOuverte}
          onChange={rafraichir}
          onSupprimee={() => {
            setOuverte(null);
            rafraichir();
          }}
        />
      )}
    </section>
  );
}

/** Demande reçue hors formulaire (téléphone, rencontre) : coordonnées de l'adulte et besoin exprimé, rien d'autre. */
function Saisie({ categorie, appeler, onEnregistree }) {
  const [v, setV] = useState({ prenom: "", nom: "", email: "", telephone: "", message: "" });
  const [envoi, setEnvoi] = useState(false);
  const changer = (cle) => (e) => setV({ ...v, [cle]: e.target.value });

  async function enregistrer(e) {
    e.preventDefault();
    if (envoi) return;
    setEnvoi(true);
    try {
      onEnregistree(await appeler("/admin/accueil/demandes", { methode: "POST", corps: { ...v, telephone: v.telephone || null, categorie } }));
    } catch {
      setEnvoi(false); // message affiché par useApi
    }
  }

  return (
    <form className="carte" onSubmit={enregistrer} aria-label="Saisir une demande">
      <p className="doux petit">Adulte seulement. Ne notez ni le nom, ni les résultats, ni d'autres informations sur un enfant.</p>
      <label>
        Prénom
        <input value={v.prenom} onChange={changer("prenom")} required maxLength={60} />
      </label>
      <label>
        Nom
        <input value={v.nom} onChange={changer("nom")} required maxLength={80} />
      </label>
      <label>
        E-mail
        <input type="email" value={v.email} onChange={changer("email")} required maxLength={254} />
      </label>
      <label>
        Téléphone (facultatif)
        <input type="tel" value={v.telephone} onChange={changer("telephone")} maxLength={30} />
      </label>
      <label>
        Besoin ou question
        <textarea value={v.message} onChange={changer("message")} required minLength={3} maxLength={3000} rows={3} />
      </label>
      <div className="actions">
        <button type="submit" disabled={envoi}>
          Enregistrer la demande
        </button>
      </div>
    </form>
  );
}

function Details({ d }) {
  const x = d.details ?? {};
  if (d.categorie === "candidature")
    return (
      <>
        <dt>Matières</dt>
        <dd>{(x.matieres ?? []).map((m) => LIBELLES_MATIERES[m] ?? m).join(", ") || "—"}</dd>
        <dt>Niveaux</dt>
        <dd>{(x.niveaux ?? []).join(", ") || "—"}</dd>
        <dt>Disponibilités</dt>
        <dd>{x.disponibilites ?? "—"}</dd>
      </>
    );
  if (d.categorie === "partenariat")
    return (
      <>
        <dt>Structure</dt>
        <dd>
          {d.organisation} ({LIBELLES_STRUCTURES[x.structure_type] ?? x.structure_type})
        </dd>
        {x.fonction && (
          <>
            <dt>Fonction du contact</dt>
            <dd>{x.fonction}</dd>
          </>
        )}
      </>
    );
  return null;
}

function Fiche({ id, jeton, onExpire, onOuvrir, onChange, onSupprimee }) {
  const { appeler, erreur, setErreur } = useApi(jeton, onExpire);
  const [d, setD] = useState(null);
  const [moi, setMoi] = useState(null);
  const [notes, setNotes] = useState("");
  const [issue, setIssue] = useState("");

  function afficher(x) {
    setD(x);
    setNotes(x.notes_internes ?? "");
    setIssue(x.issue ?? "");
  }

  useEffect(() => {
    appeler(`/admin/accueil/demandes/${id}`).then(afficher, () => {});
    appeler("/admin/moi").then(setMoi, () => {});
  }, [appeler, id]);

  async function envoyer(chemin, options) {
    try {
      const reponse = await appeler(chemin, options);
      if (reponse) afficher(reponse);
      onChange();
      return true;
    } catch {
      return false; // message affiché par useApi
    }
  }

  const traiter = (changements) => envoyer(`/admin/accueil/demandes/${id}`, { methode: "POST", corps: changements });

  async function telecharger(chemin, nom) {
    try {
      await telechargerFichier(chemin, jeton, nom);
    } catch (e) {
      setErreur(e.message);
    }
  }

  async function supprimer(chemin, question) {
    if (!window.confirm(question)) return;
    if (await envoyer(chemin, { methode: "DELETE" })) onSupprimee();
  }

  if (!d) return <Erreur message={erreur} />;
  const c = d.contact_fiche;
  return (
    <article className="carte" aria-label={`Demande ${d.reference}`}>
      <h3>
        {d.reference} — {FILES[d.categorie]}
      </h3>
      <dl>
        <dt>Coordonnées saisies</dt>
        <dd>
          {d.prenom} {d.nom} · {d.email}
          {d.telephone && ` · ${d.telephone}`}
        </dd>
        <Details d={d} />
        <dt>{d.categorie === "partenariat" ? "Partenariat envisagé" : "Besoin ou message"}</dt>
        <dd style={{ whiteSpace: "pre-wrap" }}>{d.message ?? "—"}</dd>
        <dt>Origine</dt>
        <dd>{ORIGINES[d.origine] ?? d.origine}</dd>
        <dt>Reçue le</dt>
        <dd>{new Date(d.cree_le).toLocaleString("fr-FR")}</dd>
      </dl>
      {d.a_un_cv && (
        <div className="actions">
          <button className="secondaire" onClick={() => telecharger(`/admin/accueil/demandes/${id}/cv`, `CV-${d.reference}.pdf`)}>
            Télécharger le CV
          </button>
        </div>
      )}

      <h4>Traitement</h4>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "end" }}>
        <label>
          Statut
          <select value={d.statut} onChange={(e) => e.target.value !== "traite" && traiter({ statut: e.target.value })}>
            {Object.entries(STATUTS).map(([v, l]) => (
              <option key={v} value={v} disabled={v === "traite"}>
                {l}
              </option>
            ))}
          </select>
        </label>
        <label>
          Issue
          <select value={issue} onChange={(e) => setIssue(e.target.value)}>
            <option value="">Choisir…</option>
            {ISSUES_PAR_FILE[d.categorie].map((v) => (
              <option key={v} value={v}>
                {ISSUES[v]}
              </option>
            ))}
          </select>
        </label>
        <button disabled={!issue} onClick={() => traiter({ statut: "traite", issue })}>
          Marquer traitée
        </button>
        {moi?.id && d.responsable_id !== moi.id && (
          <button className="lien" onClick={() => traiter({ responsable_id: moi.id })}>
            M'en charger
          </button>
        )}
        {d.responsable && <span className="doux">Responsable : {d.responsable}</span>}
      </div>
      <label>
        Notes internes (visibles des administrateurs seulement)
        <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} maxLength={3000} />
      </label>
      <div className="actions">
        <button className="secondaire" onClick={() => traiter({ notes_internes: notes })}>
          Enregistrer les notes
        </button>
        <button className="danger" onClick={() => supprimer(`/admin/accueil/demandes/${id}`, `Supprimer définitivement la demande ${d.reference}${d.a_un_cv ? " et son CV" : ""} ?`)}>
          Supprimer cette demande
        </button>
      </div>

      <h4>Contact</h4>
      <p>
        {c.prenom} {c.nom} · {c.email}
        {c.telephone && ` · ${c.telephone}`}
      </p>
      {d.autres_demandes.length > 0 ? (
        <>
          <p className="doux petit">Autres demandes avec la même adresse e-mail (rattachement automatique, sans aucun accès ni lien vers un compte) :</p>
          <ul>
            {d.autres_demandes.map((a) => (
              <li key={a.id}>
                <button className="lien" onClick={() => onOuvrir(a.id)}>
                  {a.reference}
                </button>{" "}
                — {FILES[a.categorie]}, {STATUTS[a.statut]}
                {a.issue && ` · ${ISSUES[a.issue]}`}, {new Date(a.cree_le).toLocaleDateString("fr-FR")}
              </li>
            ))}
          </ul>
          <button className="lien" onClick={() => envoyer(`/admin/accueil/demandes/${id}/detacher`, { methode: "POST" })}>
            Ce n'est pas la même personne : détacher cette demande
          </button>
        </>
      ) : (
        <p className="doux petit">Aucune autre demande pour ce contact.</p>
      )}
      <div className="actions">
        <button className="secondaire" onClick={() => telecharger(`/admin/accueil/contacts/${c.id}/export`, `contact-${c.id}.json`)}>
          Exporter le contact (droit d'accès)
        </button>
        <button
          className="danger"
          onClick={() => supprimer(`/admin/accueil/contacts/${c.id}`, `Supprimer définitivement ce contact, ses ${d.autres_demandes.length + 1} demande(s) et leurs CV ?`)}
        >
          Effacer le contact et toutes ses demandes
        </button>
      </div>
      <p className="doux petit">Traiter une demande ne crée ni compte, ni inscription, ni habilitation, ni contrat, et n'envoie aucun message.</p>
      <Erreur message={erreur} />
    </article>
  );
}
