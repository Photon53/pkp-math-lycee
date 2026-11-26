// Issue #171 — Candidatures de professeurs et demandes de partenariat (Claude)
import { useEffect, useState } from "react";
import { api } from "./api.js";
import { Erreur } from "./composants.jsx";

export const MATIERES = [
  ["maths", "Mathématiques"],
  ["francais", "Français"],
  ["anglais", "Anglais"],
];
export const NIVEAUX = ["6e", "5e", "4e", "3e", "2nde", "1re", "Tle"];
export const TYPES_STRUCTURE = [
  ["ecole", "École ou établissement scolaire"],
  ["institut", "Institut ou centre de formation"],
  ["association", "Association"],
  ["autre", "Autre structure"],
];

/** Lit un fichier en base64 (sans l'en-tête « data: »), comme l'attend l'API. */
function lireBase64(fichier) {
  return new Promise((resoudre, rejeter) => {
    const lecteur = new FileReader();
    lecteur.onload = () => resoudre(String(lecteur.result).split(",")[1] ?? "");
    lecteur.onerror = () => rejeter(new Error("Le fichier n'a pas pu être lu."));
    lecteur.readAsDataURL(fichier);
  });
}

/**
 * « Enseigner ou collaborer avec nous » : deux circuits, professeur candidat ou structure partenaire.
 * Aucun compte n'est créé : la demande arrive dans « Accueil et demandes », traitée par l'équipe.
 */
export default function Collaborer() {
  const [etat, setEtat] = useState(null);
  const [profil, setProfil] = useState(null);
  const [accuse, setAccuse] = useState(null);

  useEffect(() => {
    api("/collaboration/etat").then(setEtat, () => setEtat({ ouvert: false }));
  }, []);

  if (etat === null) return <p className="doux">Chargement…</p>;
  if (accuse) return <Confirmation accuse={accuse} />;
  return (
    <section className="carte" aria-labelledby="titre-collaborer">
      <h1 id="titre-collaborer">Enseigner ou collaborer avec nous</h1>
      {!etat.ouvert ? (
        <p>Les candidatures et les demandes de partenariat ne sont pas encore ouvertes. Revenez prochainement.</p>
      ) : (
        <>
          <fieldset>
            <legend>Vous êtes</legend>
            <label>
              <input type="radio" name="profil" checked={profil === "candidature"} onChange={() => setProfil("candidature")} /> Professeur ou
              professeure, et vous souhaitez enseigner avec nous
            </label>
            <label>
              <input type="radio" name="profil" checked={profil === "partenariat"} onChange={() => setProfil("partenariat")} /> Une école, un
              institut ou une association, et vous souhaitez collaborer
            </label>
          </fieldset>
          {profil && <Information etat={etat} profil={profil} />}
          {profil === "candidature" && <FormulaireCandidature etat={etat} onEnvoye={setAccuse} />}
          {profil === "partenariat" && <FormulairePartenariat onEnvoye={setAccuse} />}
        </>
      )}
    </section>
  );
}

function Information({ etat, profil }) {
  const jours = etat.conservation_jours?.[profil];
  const duree = jours ? `${jours} jours` : "la durée indiquée par l'équipe";
  return (
    <details className="carte" open>
      <summary>Comment nous utilisons ces informations</summary>
      <ul>
        <li>
          {profil === "candidature"
            ? "Elles servent uniquement à étudier votre candidature et à vous recontacter à son sujet."
            : "Elles servent uniquement à étudier votre proposition de partenariat et à vous recontacter à son sujet."}
        </li>
        <li>Seuls les administrateurs de Boussole les consultent. Aucun envoi publicitaire, aucune revente, aucun partage.</li>
        {profil === "candidature" && <li>Votre CV est conservé dans un espace privé et n'est jamais publié.</li>}
        <li>
          Sans suite donnée, votre demande{profil === "candidature" ? " et votre CV sont supprimés" : " est supprimée"} {duree} après son
          dernier traitement.
        </li>
        <li>Vous pouvez demander à tout moment à consulter ou à supprimer vos informations, en rappelant la référence de votre demande.</li>
        <li>Une demande ne vaut ni engagement ni contrat, de votre part comme de la nôtre.</li>
      </ul>
    </details>
  );
}

/** Champs communs : coordonnées de l'adulte, accord de lecture et piège à robots. */
function useFormulaire(initial) {
  const [valeurs, setValeurs] = useState({ prenom: "", nom: "", email: "", telephone: "", information_lue: false, site_web: "", ...initial });
  const changer = (cle) => (e) => setValeurs((v) => ({ ...v, [cle]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));
  return [valeurs, setValeurs, changer];
}

function Contact({ valeurs, changer, legende }) {
  return (
    <fieldset>
      <legend>{legende}</legend>
      <label>
        Prénom (obligatoire)
        <input value={valeurs.prenom} onChange={changer("prenom")} required maxLength={60} autoComplete="given-name" />
      </label>
      <label>
        Nom (obligatoire)
        <input value={valeurs.nom} onChange={changer("nom")} required maxLength={80} autoComplete="family-name" />
      </label>
      <label>
        E-mail (obligatoire, pour vous répondre)
        <input type="email" value={valeurs.email} onChange={changer("email")} required maxLength={254} autoComplete="email" />
      </label>
      <label>
        Téléphone (facultatif)
        <input type="tel" value={valeurs.telephone} onChange={changer("telephone")} maxLength={30} autoComplete="tel" />
      </label>
      {/* Piège à robots : invisible et ignoré par les lecteurs d'écran ; une personne le laisse vide. */}
      <div aria-hidden="true" style={{ position: "absolute", left: "-10000px" }}>
        <label>
          Site web
          <input tabIndex={-1} autoComplete="off" value={valeurs.site_web} onChange={changer("site_web")} />
        </label>
      </div>
    </fieldset>
  );
}

function Envoi({ valeurs, changer, envoi, erreur }) {
  return (
    <>
      <label>
        <input type="checkbox" checked={valeurs.information_lue} onChange={changer("information_lue")} /> J'ai lu comment ces informations sont
        utilisées et conservées (obligatoire).
      </label>
      <Erreur message={erreur} />
      <div className="actions">
        <button type="submit" disabled={envoi || !valeurs.information_lue}>
          {envoi ? "Envoi en cours…" : "Envoyer ma demande"}
        </button>
      </div>
    </>
  );
}

/** Envoi unique : le bouton est désactivé pendant l'envoi (pas de double demande). */
function useEnvoi(onEnvoye) {
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState("");
  async function envoyer(chemin, corps) {
    if (envoi) return;
    setEnvoi(true);
    setErreur("");
    try {
      onEnvoye(await api(chemin, { methode: "POST", corps }));
    } catch (e) {
      setErreur(e.message || "L'envoi a échoué. Réessayez.");
      setEnvoi(false);
    }
  }
  return { envoi, erreur, setErreur, envoyer };
}

function coordonnees(v) {
  return { prenom: v.prenom, nom: v.nom, email: v.email, telephone: v.telephone || null, information_lue: v.information_lue, site_web: v.site_web };
}

function FormulaireCandidature({ etat, onEnvoye }) {
  const [valeurs, setValeurs, changer] = useFormulaire({ matieres: [], niveaux: [], disponibilites: "", message: "" });
  const [cv, setCv] = useState(null);
  const { envoi, erreur, setErreur, envoyer } = useEnvoi(onEnvoye);
  const tailleMax = (etat.cv_taille_max_mo ?? 5) * 1024 * 1024;

  const basculer = (cle, valeur) => setValeurs((v) => ({ ...v, [cle]: v[cle].includes(valeur) ? v[cle].filter((x) => x !== valeur) : [...v[cle], valeur] }));

  function choisirCv(e) {
    const fichier = e.target.files?.[0] ?? null;
    setErreur("");
    if (fichier && fichier.size > tailleMax) {
      setErreur(`Le CV dépasse ${etat.cv_taille_max_mo} Mo.`);
      e.target.value = "";
      return setCv(null);
    }
    if (fichier && fichier.type && fichier.type !== "application/pdf") {
      setErreur("Le CV doit être un fichier PDF.");
      e.target.value = "";
      return setCv(null);
    }
    setCv(fichier);
  }

  async function soumettre(e) {
    e.preventDefault();
    if (!valeurs.matieres.length || !valeurs.niveaux.length) return setErreur("Choisissez au moins une matière et un niveau.");
    let cv_base64 = null;
    try {
      cv_base64 = cv ? await lireBase64(cv) : null;
    } catch (err) {
      return setErreur(err.message);
    }
    envoyer("/collaboration/candidatures", {
      ...coordonnees(valeurs), matieres: valeurs.matieres, niveaux: valeurs.niveaux,
      disponibilites: valeurs.disponibilites || null, message: valeurs.message || null, cv_base64,
    });
  }

  return (
    <form onSubmit={soumettre}>
      <Contact valeurs={valeurs} changer={changer} legende="Vos coordonnées" />
      <fieldset>
        <legend>Matières enseignées (au moins une)</legend>
        {MATIERES.map(([v, l]) => (
          <label key={v}>
            <input type="checkbox" checked={valeurs.matieres.includes(v)} onChange={() => basculer("matieres", v)} /> {l}
          </label>
        ))}
      </fieldset>
      <fieldset>
        <legend>Niveaux (au moins un)</legend>
        {NIVEAUX.map((n) => (
          <label key={n}>
            <input type="checkbox" checked={valeurs.niveaux.includes(n)} onChange={() => basculer("niveaux", n)} /> {n}
          </label>
        ))}
      </fieldset>
      <label>
        Disponibilités (facultatif)
        <input value={valeurs.disponibilites} onChange={changer("disponibilites")} maxLength={500} placeholder="Par exemple : mercredi après-midi" />
      </label>
      <label>
        Message (facultatif)
        <textarea value={valeurs.message} onChange={changer("message")} rows={4} maxLength={3000} />
      </label>
      <label>
        CV (facultatif) — PDF seulement, {etat.cv_taille_max_mo} Mo au plus
        <input type="file" accept="application/pdf,.pdf" onChange={choisirCv} />
      </label>
      <p className="doux petit">Inutile d'y mettre votre adresse postale, une photo ou votre date de naissance.</p>
      <Envoi valeurs={valeurs} changer={changer} envoi={envoi} erreur={erreur} />
    </form>
  );
}

function FormulairePartenariat({ onEnvoye }) {
  const [valeurs, , changer] = useFormulaire({ structure_nom: "", structure_type: "", fonction: "", partenariat: "" });
  const { envoi, erreur, setErreur, envoyer } = useEnvoi(onEnvoye);

  function soumettre(e) {
    e.preventDefault();
    if (!valeurs.structure_type) return setErreur("Choisissez le type de structure.");
    envoyer("/collaboration/partenariats", {
      ...coordonnees(valeurs), structure_nom: valeurs.structure_nom, structure_type: valeurs.structure_type,
      fonction: valeurs.fonction || null, partenariat: valeurs.partenariat,
    });
  }

  return (
    <form onSubmit={soumettre}>
      <fieldset>
        <legend>Votre structure</legend>
        <label>
          Nom de la structure (obligatoire)
          <input value={valeurs.structure_nom} onChange={changer("structure_nom")} required maxLength={150} autoComplete="organization" />
        </label>
        <label>
          Type de structure (obligatoire)
          <select value={valeurs.structure_type} onChange={changer("structure_type")} required>
            <option value="">Choisir…</option>
            {TYPES_STRUCTURE.map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </label>
      </fieldset>
      <Contact valeurs={valeurs} changer={changer} legende="La personne à contacter" />
      <label>
        Votre fonction dans la structure (facultatif)
        <input value={valeurs.fonction} onChange={changer("fonction")} maxLength={100} autoComplete="organization-title" />
      </label>
      <label>
        Partenariat envisagé (obligatoire)
        <textarea value={valeurs.partenariat} onChange={changer("partenariat")} rows={5} required minLength={10} maxLength={3000} />
      </label>
      <Envoi valeurs={valeurs} changer={changer} envoi={envoi} erreur={erreur} />
    </form>
  );
}

function Confirmation({ accuse }) {
  return (
    <section className="carte" aria-live="polite">
      <h1>Demande bien reçue</h1>
      <p>
        Merci. Votre {accuse.type === "candidature" ? "candidature" : "demande de partenariat"} est enregistrée sous la référence{" "}
        <strong>{accuse.reference}</strong>. Notez-la : elle vous servira pour toute question ou demande de suppression.
      </p>
      <p>L'équipe l'étudiera et vous répondra par e-mail. Cette réponse n'est pas automatique et peut prendre quelques jours.</p>
      <p>
        <a href="/">Retour à l'accueil</a>
      </p>
    </section>
  );
}
