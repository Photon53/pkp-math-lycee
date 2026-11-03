import { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";
import { Erreur, Onglets } from "../composants.jsx";
import Historique from "../eleve/Historique.jsx";
import { ListeProgression } from "../eleve/Progression.jsx";
import { ConnexionEnseignant, NouveauMotDePasse, PageSimple } from "../enseignant/EspaceEnseignant.jsx";
import { useApi } from "../enseignant/useApi.js";
import { libelleNiveauParcours } from "../parcours.js";
import { ecrire, lire } from "../stockage.js";
import { formaterDate, pourcentage } from "../ui/Cadre.jsx";

const CLE_COMPTE = "pkp.parent";
// Mêmes règles que l'API (app/security.py) : vérifiées ici pour un message immédiat.
const CODE_MIN = 8;
const CODE_MAX = 16;

const minutes = (m) => (m < 60 ? `${Math.round(m)} min` : `${Math.floor(m / 60)} h ${String(Math.round(m % 60)).padStart(2, "0")}`);

/** Espace parents : compte créé par le professeur, suivi du travail des enfants, code de connexion de l'enfant. */
export default function EspaceParent() {
  const [compte, setCompte] = useState(() => lire(CLE_COMPTE));

  function connecter(nouveau) {
    ecrire(CLE_COMPTE, nouveau);
    setCompte(nouveau);
  }

  function deconnecter() {
    ecrire(CLE_COMPTE, null);
    setCompte(null);
  }

  if (!compte) {
    return (
      <PageSimple>
        <ConnexionEnseignant titre="Espace parents" chemin="/parents/connexion" onConnexion={connecter}>
          <p className="doux">
            Votre compte est créé par le professeur de mathématiques de votre enfant. Mot de passe oublié : demandez-lui
            un nouveau mot de passe provisoire.
          </p>
        </ConnexionEnseignant>
      </PageSimple>
    );
  }
  if (compte.mdp_provisoire) {
    return (
      <PageSimple>
        <NouveauMotDePasse
          compte={compte}
          chemin="/parents/mot-de-passe"
          retour="/parent"
          onChange={connecter}
          onAnnuler={deconnecter}
        />
      </PageSimple>
    );
  }
  return (
    <PageSimple>
      <SuiviEnfants compte={compte} onDeconnexion={deconnecter} />
    </PageSimple>
  );
}

function SuiviEnfants({ compte, onDeconnexion }) {
  const { appeler, erreur } = useApi(compte.jeton, onDeconnexion);
  const [enfants, setEnfants] = useState(null);
  const [enfantId, setEnfantId] = useState(null);

  const charger = useCallback(
    () =>
      appeler("/parents/enfants").then((liste) => {
        setEnfants(liste);
        setEnfantId((id) => id ?? liste[0]?.id ?? null);
      }, () => {}),
    [appeler],
  );
  useEffect(() => {
    charger();
  }, [charger]);

  return (
    <>
      <section className="carte">
        <div className="barre-session">
          <h1>Espace parents</h1>
          <span>
            <span className="doux petit">{compte.email}</span>{" "}
            <button className="lien" onClick={onDeconnexion}>
              Se déconnecter
            </button>
          </span>
        </div>
        <Erreur message={erreur} />
        {enfants === null ? (
          !erreur && <p className="doux">Chargement…</p>
        ) : enfants.length === 0 ? (
          <p className="doux">Aucun enfant n'est rattaché à votre compte pour l'instant. Contactez son professeur.</p>
        ) : (
          enfants.length > 1 && (
            <Onglets
              valeur={enfantId}
              onChange={setEnfantId}
              options={enfants.map((e) => [e.id, `${e.prenom} · ${e.code_classe}`])}
            />
          )
        )}
      </section>
      {enfantId && <TableauEnfant key={enfantId} enfantId={enfantId} appeler={appeler} compte={compte} onExpire={onDeconnexion} onCode={charger} />}
    </>
  );
}

function TableauEnfant({ enfantId, appeler, compte, onExpire, onCode }) {
  const [tableau, setTableau] = useState(null);
  const [vue, setVue] = useState("progression");

  useEffect(() => {
    appeler(`/parents/enfants/${enfantId}`).then(setTableau, () => {});
  }, [appeler, enfantId]);

  if (!tableau) return null;
  const { enfant, activite } = tableau;
  const maxMinutes = Math.max(1, ...activite.map((j) => j.minutes));

  return (
    <>
      <section className="carte">
        <h2>
          {enfant.prenom} <span className="doux petit">{enfant.code_classe} · {libelleNiveauParcours(enfant.niveau, enfant.parcours)}</span>
        </h2>
        <div className="kpis" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))" }}>
          <Indicateur libelle="Compétences maîtrisées" valeur={`${enfant.competences_maitrisees} / ${enfant.competences_total}`} />
          <Indicateur libelle="Taux de réussite" valeur={pourcentage(enfant.taux_reussite)} sous={`${enfant.nb_reponses} réponses en tout`} />
          <Indicateur libelle="Travail sur 7 jours" valeur={minutes(enfant.minutes_7_jours)} sous={`${minutes(tableau.minutes_30_jours)} sur 30 jours`} />
          <Indicateur
            libelle="Dernière séance"
            valeur={enfant.derniere_activite ? formaterDate(enfant.derniere_activite) : "—"}
            sous={`${tableau.seances_30_jours} séance(s) sur 30 jours`}
          />
        </div>
        <h3>Activité des 14 derniers jours</h3>
        <div className="barres" aria-label="Temps de travail par jour">
          {activite.map((j) => (
            <div className="barre" key={j.jour}>
              <span className="nom">{new Date(`${j.jour}T12:00:00`).toLocaleDateString("fr-FR", { weekday: "short", day: "numeric", month: "short" })}</span>
              <span className="piste">
                <span className="rempli" style={{ width: `${(j.minutes / maxMinutes) * 100}%` }} />
              </span>
              <span className="val">{j.nb_reponses ? minutes(j.minutes) : "—"}</span>
            </div>
          ))}
        </div>
        <p className="aide">Temps passé à répondre aux exercices (au plus 10 minutes comptées par question).</p>
      </section>

      <section className="carte">
        <h2>Chapitres ouverts par le professeur</h2>
        {tableau.chapitres.length === 0 ? (
          <p className="doux">Aucun chapitre n'est encore ouvert.</p>
        ) : (
          <div className="barres">
            {tableau.chapitres.map((c) => (
              <div className="barre" key={c.titre}>
                <span className="nom" title={c.titre}>{c.titre}</span>
                <span className="piste">
                  <span className="rempli ok" style={{ width: `${c.competences_total ? (c.competences_maitrisees / c.competences_total) * 100 : 0}%` }} />
                </span>
                <span className="val">
                  {c.competences_maitrisees}/{c.competences_total}
                </span>
              </div>
            ))}
          </div>
        )}
        <p className="aide">Compétences maîtrisées sur le nombre de compétences du chapitre.</p>
      </section>

      <section className="carte">
        <Onglets
          valeur={vue}
          onChange={setVue}
          options={[
            ["progression", "Progression par compétence"],
            ["historique", "Historique des réponses"],
            ["code", "Code de connexion"],
          ]}
        />
        {vue === "progression" && <ListeProgression competences={tableau.progression} />}
        {vue === "historique" && (
          <Historique jeton={compte.jeton} onExpire={onExpire} chemin={`/parents/enfants/${enfantId}/historique`} eleve={false} />
        )}
        {vue === "code" && <ChoixCode enfant={enfant} jeton={compte.jeton} onExpire={onExpire} onCode={onCode} />}
      </section>
    </>
  );
}

function Indicateur({ libelle, valeur, sous }) {
  return (
    <div className="kpi">
      <div className="libelle">{libelle}</div>
      <div className="valeur">{valeur}</div>
      {sous && <div className="sous">{sous}</div>}
    </div>
  );
}

/** Le parent choisit le code personnel de son enfant (l'ancien cesse de fonctionner). */
function ChoixCode({ enfant, jeton, onExpire, onCode }) {
  const [code, setCode] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [probleme, setProbleme] = useState(null);
  const [identifiant, setIdentifiant] = useState(null);

  async function soumettre(e) {
    e.preventDefault();
    const normalise = code.toUpperCase().replace(/[\s-]/g, "");
    if (normalise.length < CODE_MIN || normalise.length > CODE_MAX) {
      return setProbleme(`Le code doit compter de ${CODE_MIN} à ${CODE_MAX} caractères.`);
    }
    if (code !== confirmation) return setProbleme("Les deux saisies diffèrent.");
    setProbleme(null);
    try {
      const r = await api(`/parents/enfants/${enfant.id}/code`, { methode: "PUT", corps: { code }, jeton });
      setIdentifiant(r.identifiant);
      setCode("");
      setConfirmation("");
      onCode();
    } catch (err) {
      // Message de l'API (code trop simple, prénom dedans…) affiché sous le formulaire.
      if (err.status === 401) onExpire();
      else setProbleme(err.message);
    }
  }

  return (
    <form onSubmit={soumettre}>
      <p className="doux">
        {enfant.prenom} se connecte avec son identifiant{enfant.identifiant ? <> <code>{enfant.identifiant}</code></> : null} et
        son code personnel. Vous pouvez choisir ce code : l'ancien ne fonctionnera plus et les sessions ouvertes de{" "}
        {enfant.prenom} seront fermées.
      </p>
      <label htmlFor="code-enfant">Nouveau code</label>
      <input
        id="code-enfant"
        value={code}
        onChange={(e) => setCode(e.target.value)}
        autoComplete="off"
        maxLength={20}
        required
      />
      <p className="aide">
        De {CODE_MIN} à {CODE_MAX} lettres et chiffres, avec au moins une lettre et un chiffre, sans le prénom de l'enfant.
        Majuscules et minuscules sont équivalentes.
      </p>
      <label htmlFor="code-confirmation">Confirmation</label>
      <input id="code-confirmation" value={confirmation} onChange={(e) => setConfirmation(e.target.value)} autoComplete="off" required />
      <Erreur message={probleme} />
      {identifiant && (
        <p className="succes" role="status">
          Code enregistré. {enfant.prenom} se connecte désormais avec l'identifiant <code>{identifiant}</code> et ce nouveau code.
        </p>
      )}
      <div className="actions">
        <button type="submit">Enregistrer le code</button>
      </div>
    </form>
  );
}
