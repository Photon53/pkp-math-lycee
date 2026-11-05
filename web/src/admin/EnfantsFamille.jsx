// Familles créées par l'administrateur : un compte parent (mot de passe provisoire) et ses enfants, chacun avec
// son niveau et une carte unique (identifiant + code) pour toutes ses matières. L'administrateur peut aussi
// inscrire l'enfant dans une classe de maths (tronc commun, excellence, mise à niveau…) ou un groupe d'anglais.
import { useCallback, useEffect, useState } from "react";
import { Erreur } from "../composants.jsx";
import { FicheCodes } from "../enseignant/Classes.jsx";
import { NIVEAUX, libelleNiveauParcours } from "../parcours.js";
import { Modale, formaterDate } from "../ui/Cadre.jsx";
import Icone from "../ui/Icone.jsx";

const NOM_NIVEAU = Object.fromEntries(NIVEAUX);
const VIDE = { prenom: "", nom: "", niveau: "6e" };
export const nomComplet = (e) => `${e.prenom} ${e.nom ?? ""}`.trim();

/** Cartes à imprimer : affichées une seule fois (le serveur ne garde que l'empreinte du code). */
export function cartesAImprimer(cartes) {
  return cartes.map((c) => ({ id: c.id, prenom: `${nomComplet(c)} (${NOM_NIVEAU[c.niveau] ?? c.niveau})`, identifiant: c.identifiant, code: c.code }));
}

function LigneEnfant({ enfant, onChange, onRetirer, index }) {
  return (
    <div className="ligne-enfant">
      <div>
        <label htmlFor={`e-prenom-${index}`}>Prénom</label>
        <input id={`e-prenom-${index}`} required maxLength={50} value={enfant.prenom} onChange={(e) => onChange({ ...enfant, prenom: e.target.value })} />
      </div>
      <div>
        <label htmlFor={`e-nom-${index}`}>Nom ou initiale (facultatif)</label>
        <input id={`e-nom-${index}`} maxLength={50} value={enfant.nom} onChange={(e) => onChange({ ...enfant, nom: e.target.value })} />
      </div>
      <div>
        <label htmlFor={`e-niveau-${index}`}>Niveau</label>
        <select id={`e-niveau-${index}`} value={enfant.niveau} onChange={(e) => onChange({ ...enfant, niveau: e.target.value })}>
          {NIVEAUX.map(([v, l]) => (
            <option key={v} value={v}>{l}</option>
          ))}
        </select>
      </div>
      {onRetirer && (
        <button type="button" className="icone" onClick={onRetirer} aria-label={`Retirer l'enfant ${index + 1}`}>
          <Icone nom="fermer" />
        </button>
      )}
    </div>
  );
}

export function NouvelleFamille({ appeler, onFermer, onCreee }) {
  const [email, setEmail] = useState("");
  const [tuteur, setTuteur] = useState({ prenom: "", nom: "" });
  const [enfants, setEnfants] = useState([{ ...VIDE }]);
  const [erreur, setErreur] = useState(null);
  const [envoi, setEnvoi] = useState(false);

  async function soumettre(e) {
    e.preventDefault();
    setErreur(null);
    setEnvoi(true);
    try {
      onCreee(await appeler("/admin/familles", { methode: "POST", corps: { email, ...tuteur, enfants } }));
    } catch (err) {
      setErreur(err.message);
    } finally {
      setEnvoi(false);
    }
  }

  return (
    <Modale titre="Nouvelle famille" onFermer={onFermer} large>
      <form onSubmit={soumettre}>
        <h3>Responsable légal</h3>
        <div className="ligne-champs souple">
          <div>
            <label htmlFor="nf-prenom">Prénom</label>
            <input id="nf-prenom" value={tuteur.prenom} maxLength={50} onChange={(e) => setTuteur({ ...tuteur, prenom: e.target.value })} />
          </div>
          <div>
            <label htmlFor="nf-nom">Nom</label>
            <input id="nf-nom" value={tuteur.nom} maxLength={50} onChange={(e) => setTuteur({ ...tuteur, nom: e.target.value })} />
          </div>
          <div style={{ flexGrow: 2 }}>
            <label htmlFor="nf-email">E-mail du parent</label>
            <input id="nf-email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
        </div>
        <h3>Enfants</h3>
        {enfants.map((enf, i) => (
          <LigneEnfant
            key={i}
            index={i}
            enfant={enf}
            onChange={(v) => setEnfants(enfants.map((x, j) => (j === i ? v : x)))}
            onRetirer={enfants.length > 1 ? () => setEnfants(enfants.filter((_, j) => j !== i)) : null}
          />
        ))}
        <button type="button" className="secondaire petit" onClick={() => setEnfants([...enfants, { ...VIDE }])} disabled={enfants.length >= 8}>
          <Icone nom="plus" taille={16} /> Ajouter un enfant
        </button>
        <p className="aide">
          Le parent reçoit un mot de passe provisoire, qu'il change à sa première connexion. Chaque enfant reçoit une carte
          (identifiant et code) qui lui sert pour toutes ses matières. Si l'adresse a déjà un compte, les enfants s'ajoutent à
          cette famille.
        </p>
        <Erreur message={erreur} />
        <div className="actions">
          <button type="submit" disabled={envoi || !email.trim() || enfants.some((x) => !x.prenom.trim())}>
            {envoi ? "Création…" : "Créer la famille"}
          </button>
        </div>
      </form>
    </Modale>
  );
}

/** Après la création : mot de passe provisoire du parent (s'il est nouveau) et cartes des enfants. */
export function FamilleCreee({ resultat, onFermer }) {
  return (
    <Modale titre={`Famille ${resultat.email}`} onFermer={onFermer} large>
      {resultat.mot_de_passe_provisoire ? (
        <>
          <p>
            Mot de passe provisoire de <strong>{resultat.email}</strong>, à transmettre par un canal sûr (il ne sera plus
            affiché) :
          </p>
          <p className="secret">{resultat.mot_de_passe_provisoire}</p>
        </>
      ) : (
        <p>Les enfants ont été ajoutés au compte existant de {resultat.email} (mot de passe inchangé).</p>
      )}
      <FicheCodes classe="Famille" intitule={`Famille ${resultat.email}`} codes={cartesAImprimer(resultat.cartes)} onFermer={onFermer} />
    </Modale>
  );
}

/** Enfants d'une famille, dans la fenêtre « Gérer » de l'administrateur. */
export function EnfantsDeLaFamille({ parentId, appeler }) {
  const [enfants, setEnfants] = useState(null);
  const [classes, setClasses] = useState([]);
  const [groupes, setGroupes] = useState([]);
  const [ajout, setAjout] = useState(null);
  const [cartes, setCartes] = useState(null);
  const [message, setMessage] = useState(null);
  const [erreur, setErreur] = useState(null);

  const charger = useCallback(
    () => appeler(`/admin/parents/${parentId}/famille`).then(setEnfants, (err) => setErreur(err.message)),
    [appeler, parentId],
  );
  useEffect(() => {
    charger();
    appeler("/admin/classes").then(setClasses, () => {});
    appeler("/admin/anglais/groupes").then(setGroupes, () => {});
  }, [appeler, charger]);

  async function agir(promesse, texte) {
    setErreur(null);
    setMessage(null);
    try {
      const r = await promesse;
      if (texte) setMessage(typeof texte === "function" ? texte(r) : texte);
      await charger();
      return r;
    } catch (err) {
      setErreur(err.message);
      return undefined;
    }
  }

  async function ajouter(e) {
    e.preventDefault();
    const carte = await agir(appeler(`/admin/parents/${parentId}/famille`, { methode: "POST", corps: ajout }));
    if (carte) {
      setAjout(null);
      setCartes([carte]);
    }
  }

  async function nouvelleCarte(enfant) {
    if (!window.confirm(`Nouvelle carte pour ${nomComplet(enfant)} ? L'ancien code cessera de fonctionner, dans toutes ses matières.`)) return;
    const carte = await agir(appeler(`/admin/enfants/${enfant.id}/carte`, { methode: "POST" }));
    if (carte) setCartes([carte]);
  }

  const [renommage, setRenommage] = useState(null); // { id, prenom, nom }
  async function renommer(e) {
    e.preventDefault();
    const { id, prenom, nom } = renommage;
    const r = await agir(appeler(`/admin/enfants/${id}`, { methode: "PATCH", corps: { prenom, nom } }), "Nom corrigé, dans toutes ses classes.");
    if (r) setRenommage(null);
  }

  const changerNiveau = (enfant, niveau) =>
    agir(appeler(`/admin/enfants/${enfant.id}`, { methode: "PATCH", corps: { niveau } }), `${enfant.prenom} passe en ${NOM_NIVEAU[niveau]}.`);

  const resume = (r) => [r.ajoutes.length ? `Inscription faite : ${r.ajoutes.join(", ")}.` : "", ...r.refus].filter(Boolean).join(" ");
  const inscrireClasse = (enfant, classeId) =>
    agir(appeler(`/admin/classes/${classeId}/enfants`, { methode: "POST", corps: { enfant_ids: [enfant.id] } }), resume);
  const inscrireGroupe = (enfant, groupeId) =>
    agir(appeler(`/admin/anglais/groupes/${groupeId}/enfants`, { methode: "POST", corps: { enfant_ids: [enfant.id] } }), resume);

  async function supprimer(enfant) {
    const saisie = window.prompt(
      `Supprimer ${nomComplet(enfant)} et tout son travail (toutes matières) ? Cette action est définitive.\n\nPour confirmer, saisissez son identifiant : ${enfant.identifiant}`,
    );
    if (saisie == null) return;
    await agir(
      appeler(`/admin/enfants/${enfant.id}?${new URLSearchParams({ confirmation: saisie })}`, { methode: "DELETE" }),
      `${nomComplet(enfant)} a été supprimé·e.`,
    );
  }

  if (cartes)
    return (
      <FicheCodes classe="Famille" intitule="Carte de connexion" codes={cartesAImprimer(cartes)} onFermer={() => setCartes(null)} />
    );

  return (
    <>
      <h3>Enfants de la famille</h3>
      <Erreur message={erreur} />
      {message && <p className="succes" role="status">{message}</p>}
      {enfants === null ? (
        <p className="doux">Chargement…</p>
      ) : enfants.length === 0 ? (
        <p className="doux">Aucun enfant créé dans cette famille.</p>
      ) : (
        <ul className="liste-enfants-famille">
          {enfants.map((e) => (
            <li key={e.id} className="encadre">
              <div className="barre-session">
                {renommage?.id === e.id ? (
                  <form onSubmit={renommer} className="ligne-champs">
                    <label>
                      Prénom
                      <input required maxLength={50} value={renommage.prenom} onChange={(ev) => setRenommage({ ...renommage, prenom: ev.target.value })} />
                    </label>
                    <label>
                      Nom
                      <input maxLength={50} value={renommage.nom} onChange={(ev) => setRenommage({ ...renommage, nom: ev.target.value })} />
                    </label>
                    <button type="button" className="secondaire petit" onClick={() => setRenommage(null)}>Annuler</button>
                    <button type="submit" className="petit">Enregistrer</button>
                  </form>
                ) : (
                  <p>
                    <strong>{nomComplet(e)}</strong> <span className="doux">· identifiant <code>{e.identifiant}</code></span>{" "}
                    <button type="button" className="lien petit" onClick={() => setRenommage({ id: e.id, prenom: e.prenom, nom: e.nom ?? "" })}>
                      Modifier le nom
                    </button>
                  </p>
                )}
                <label className="en-ligne">
                  Niveau{" "}
                  <select value={e.niveau} onChange={(ev) => changerNiveau(e, ev.target.value)}>
                    {NIVEAUX.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                </label>
              </div>
              <p className="doux petit">
                Dernière connexion : {e.derniere_connexion ? formaterDate(e.derniere_connexion, { heure: true }) : "jamais"}
              </p>
              <p>
                <strong>Maths :</strong>{" "}
                {e.maths.length ? e.maths.map((m) => `${libelleNiveauParcours(m.niveau, m.parcours)} (${m.code_classe}, ${m.enseignant})`).join(" · ") : <span className="doux">aucune classe</span>}
              </p>
              <p>
                <strong>Anglais :</strong>{" "}
                {e.anglais.length ? e.anglais.map((a) => `${a.groupe} (${a.enseignant})`).join(" · ") : <span className="doux">aucun groupe</span>}
              </p>
              <div className="ligne-champs">
                <label>
                  Inscrire en maths
                  <select value="" onChange={(ev) => ev.target.value && inscrireClasse(e, ev.target.value)}>
                    <option value="">Choisir une classe de {NOM_NIVEAU[e.niveau]}…</option>
                    {classes.filter((c) => c.niveau === e.niveau && !e.maths.some((m) => m.code_classe === c.code)).map((c) => (
                      <option key={c.id} value={c.id}>{libelleNiveauParcours(c.niveau, c.parcours)} · {c.code} ({c.enseignant})</option>
                    ))}
                  </select>
                </label>
                <label>
                  Inscrire en anglais
                  <select value="" onChange={(ev) => ev.target.value && inscrireGroupe(e, ev.target.value)}>
                    <option value="">Choisir un groupe de {NOM_NIVEAU[e.niveau]}…</option>
                    {groupes.filter((g) => g.niveau === e.niveau && !e.anglais.some((a) => a.groupe === g.nom)).map((g) => (
                      <option key={g.id} value={g.id}>{g.nom} ({g.enseignant})</option>
                    ))}
                  </select>
                </label>
              </div>
              <div className="actions">
                <button className="secondaire petit" onClick={() => nouvelleCarte(e)}>
                  <Icone nom="cle" taille={16} /> Nouvelle carte
                </button>
                <button className="danger petit" onClick={() => supprimer(e)}>
                  Supprimer l'enfant
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
      {ajout ? (
        <form onSubmit={ajouter}>
          <LigneEnfant index={99} enfant={ajout} onChange={setAjout} />
          <div className="actions">
            <button type="button" className="secondaire" onClick={() => setAjout(null)}>Annuler</button>
            <button type="submit" disabled={!ajout.prenom.trim()}>Ajouter l'enfant</button>
          </div>
        </form>
      ) : (
        <button className="secondaire petit" onClick={() => setAjout({ ...VIDE })}>
          <Icone nom="plus" taille={16} /> Ajouter un enfant
        </button>
      )}
    </>
  );
}
