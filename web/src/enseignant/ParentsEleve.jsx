import { useEffect, useState } from "react";
import { formaterDate } from "../ui/Cadre.jsx";

/**
 * Comptes parents d'un élève : le professeur les crée (e-mail + mot de passe provisoire à transmettre),
 * les retire, et redonne un mot de passe provisoire en cas d'oubli. Aucun courriel n'est envoyé.
 */
export default function ParentsEleve({ eleve, appeler }) {
  const [parents, setParents] = useState(null);
  const [email, setEmail] = useState("");
  // Mot de passe provisoire affiché une seule fois : { email, mot_de_passe }.
  const [provisoire, setProvisoire] = useState(null);
  const [message, setMessage] = useState(null);

  useEffect(() => {
    appeler(`/enseignants/eleves/${eleve.id}/parents`).then(setParents, () => {});
  }, [appeler, eleve.id]);

  async function ajouter(e) {
    e.preventDefault();
    setMessage(null);
    setProvisoire(null);
    try {
      const r = await appeler(`/enseignants/eleves/${eleve.id}/parents`, { methode: "POST", corps: { email } });
      setEmail("");
      setParents(await appeler(`/enseignants/eleves/${eleve.id}/parents`));
      if (r.mot_de_passe_provisoire) setProvisoire({ email: r.parent.email, mot_de_passe: r.mot_de_passe_provisoire });
      else setMessage(`${r.parent.email} avait déjà un compte : ${eleve.prenom} y est ajouté(e), son mot de passe ne change pas.`);
    } catch {
      // erreur affichée par la page
    }
  }

  async function reinitialiser(p) {
    if (!window.confirm(`Donner un nouveau mot de passe provisoire à ${p.email} ?\n\nL'ancien ne fonctionnera plus.`)) return;
    setMessage(null);
    try {
      const r = await appeler(`/enseignants/parents/${p.id}/mot-de-passe`, { methode: "POST" });
      setProvisoire({ email: p.email, mot_de_passe: r.mot_de_passe_provisoire });
      setParents(await appeler(`/enseignants/eleves/${eleve.id}/parents`));
    } catch {
      // erreur affichée par la page
    }
  }

  async function retirer(p) {
    if (!window.confirm(`${p.email} ne suivra plus ${eleve.prenom}.\n\nSans autre enfant suivi, son compte sera supprimé.`)) return;
    setProvisoire(null);
    try {
      setParents(await appeler(`/enseignants/eleves/${eleve.id}/parents/${p.id}`, { methode: "DELETE" }));
      setMessage(`${p.email} ne suit plus ${eleve.prenom}.`);
    } catch {
      // erreur affichée par la page
    }
  }

  return (
    <div>
      <h3>Comptes parents de {eleve.prenom}</h3>
      <p className="doux">
        Le parent se connecte sur <code>/parent</code> avec son e-mail et le mot de passe provisoire, qu'il remplace à la
        première connexion. Il suit le travail de {eleve.prenom} et peut choisir son code de connexion.
      </p>
      {provisoire && (
        <p className="succes" role="status">
          Mot de passe provisoire de <strong>{provisoire.email}</strong> : <code className="identifiant-eleve">{provisoire.mot_de_passe}</code>
          <br />
          Notez-le maintenant et transmettez-le au parent : il ne sera plus affiché.
        </p>
      )}
      {message && (
        <p className="succes" role="status">
          {message}
        </p>
      )}
      {parents === null ? (
        <p className="doux">Chargement…</p>
      ) : parents.length === 0 ? (
        <p className="doux">Aucun compte parent pour l'instant.</p>
      ) : (
        <ul>
          {parents.map((p) => (
            <li key={p.id}>
              {p.email}{" "}
              <span className="doux petit">
                {p.mdp_provisoire ? "mot de passe provisoire pas encore changé" : `dernière connexion : ${formaterDate(p.derniere_connexion)}`}
              </span>{" "}
              <button className="lien petit" onClick={() => reinitialiser(p)}>
                Nouveau mot de passe
              </button>
              <button className="danger petit" onClick={() => retirer(p)} aria-label={`Retirer ${p.email}`}>
                Retirer
              </button>
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={ajouter}>
        <label htmlFor={`email-parent-${eleve.id}`}>E-mail du parent</label>
        <input
          id={`email-parent-${eleve.id}`}
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="off"
          required
        />
        <p className="aide">
          Un compte par responsable légal. L'adresse sert d'identifiant de connexion ; PKP n'envoie aucun courriel.
        </p>
        <div className="actions">
          <button type="submit" className="secondaire">
            Créer le compte parent
          </button>
        </div>
      </form>
    </div>
  );
}
