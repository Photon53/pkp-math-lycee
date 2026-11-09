import { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";
import { Erreur, Onglets } from "../composants.jsx";
import Historique from "../eleve/Historique.jsx";
import { ListeProgression } from "../eleve/Progression.jsx";
import { ConnexionEnseignant, NouveauMotDePasse, PageSimple } from "../enseignant/EspaceEnseignant.jsx";
import { useApi } from "../enseignant/useApi.js";
import { NIVEAUX, libelleNiveauParcours } from "../parcours.js";
import PkpMath from "../pkpmath/PkpMath.jsx";
import { ecrire, lire } from "../stockage.js";
import { formaterDate, pourcentage } from "../ui/Cadre.jsx";
import Remarques from "../ui/Remarques.jsx";

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
            Votre compte est créé par l'établissement (ou par le professeur de votre enfant), avec un mot de passe
            provisoire que vous changez à la première connexion. Mot de passe oublié : demandez-en un nouveau.
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

const NOM_NIVEAU = Object.fromEntries(NIVEAUX);

function SuiviEnfants({ compte, onDeconnexion }) {
  const { appeler, erreur } = useApi(compte.jeton, onDeconnexion);
  const [enfants, setEnfants] = useState(null);
  const [enfantId, setEnfantId] = useState(null);

  // Enfants de la famille (une carte, toutes matières) puis, à part, les inscriptions rattachées une à une
  // par un professeur (ancien mode) qui n'appartiennent à aucun enfant de la famille.
  const charger = useCallback(
    () =>
      Promise.all([appeler("/parents/famille"), appeler("/parents/enfants")]).then(([famille, inscriptions]) => {
        const dejaVues = new Set(famille.flatMap((f) => f.enfant.maths.map((m) => m.eleve_id)));
        const liste = [
          ...famille.map((f) => ({ id: `f${f.enfant.id}`, libelle: f.enfant.prenom, famille: f })),
          ...inscriptions
            .filter((e) => !dejaVues.has(e.id))
            .map((e) => ({ id: `i${e.id}`, libelle: `${e.prenom} · ${e.code_classe}`, eleveId: e.id })),
        ];
        setEnfants(liste);
        setEnfantId((id) => (liste.some((e) => e.id === id) ? id : liste[0]?.id ?? null));
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
          <p className="doux">Aucun enfant n'est rattaché à votre compte pour l'instant. Contactez l'établissement.</p>
        ) : (
          enfants.length > 1 && (
            <Onglets
              valeur={enfantId}
              onChange={setEnfantId}
              options={enfants.map((e) => [e.id, e.libelle])}
            />
          )
        )}
      </section>
      {enfants?.filter((e) => e.id === enfantId).map((e) =>
        e.famille ? (
          <SuiviFamille key={e.id} suivi={e.famille} appeler={appeler} compte={compte} onExpire={onDeconnexion} onChange={charger} />
        ) : (
          <TableauEnfant key={e.id} enfantId={e.eleveId} appeler={appeler} compte={compte} onExpire={onDeconnexion} onCode={charger} />
        ),
      )}
      <details className="carte">
        <summary>Remarques et suggestions</summary>
        <Remarques jeton={compte.jeton} onExpire={onDeconnexion} />
      </details>
    </>
  );
}

/** Un enfant de la famille : ses matières (maths par parcours, anglais, français à venir), les fiches de
 * son niveau et l'accès à son compte. */
function SuiviFamille({ suivi, appeler, compte, onExpire, onChange }) {
  const { enfant } = suivi;
  const [vue, setVue] = useState("maths");
  const [inscription, setInscription] = useState(suivi.maths[0]?.id ?? null);
  const niveau = NOM_NIVEAU[enfant.niveau] ?? enfant.niveau;
  const options = suivi.matieres.map((m) => [m.code, m.libelle]);

  return (
    <>
      <section className="carte">
        <h2>
          {enfant.prenom} {enfant.nom} <span className="doux petit">{niveau} · identifiant {enfant.identifiant}</span>
        </h2>
        <p className="doux petit">
          Dernière connexion : {enfant.derniere_connexion ? formaterDate(enfant.derniere_connexion, { heure: true }) : "jamais"}
        </p>
        <Onglets valeur={vue} onChange={setVue} options={[...options, ["fiches", "Cours et fiches PDF"], ["acces", "Accès de l'enfant"]]} />
      </section>

      {vue === "maths" &&
        (suivi.maths.length === 0 ? (
          <section className="carte">
            <p className="doux">{enfant.prenom} n'est encore inscrit dans aucune classe de maths.</p>
          </section>
        ) : (
          <>
            {suivi.maths.length > 1 && (
              <section className="carte">
                <label htmlFor="inscription">Parcours suivi</label>
                <select id="inscription" value={inscription ?? ""} onChange={(e) => setInscription(Number(e.target.value))}>
                  {suivi.maths.map((m) => (
                    <option key={m.id} value={m.id}>
                      {libelleNiveauParcours(m.niveau, m.parcours)} ({m.code_classe})
                    </option>
                  ))}
                </select>
              </section>
            )}
            {inscription && (
              <TableauEnfant key={inscription} enfantId={inscription} appeler={appeler} compte={compte} onExpire={onExpire} avecCode={false} />
            )}
          </>
        ))}

      {vue === "anglais" && (
        <section className="carte">
          <h2>Boussole Anglais</h2>
          {suivi.anglais.length === 0 ? (
            <p className="doux">{enfant.prenom} n'est encore inscrit dans aucun groupe d'anglais.</p>
          ) : (
            <div className="kpis" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))" }}>
              {suivi.anglais.map((a) => (
                <div key={a.groupe} className="kpi">
                  <div className="libelle">Groupe {a.groupe} ({a.niveau})</div>
                  <div className="valeur">{a.seances_faites} séance{a.seances_faites > 1 ? "s" : ""}</div>
                  <div className="sous">
                    Score moyen aux quiz : {pourcentage(a.score_moyen)} · {a.i_can} « I can » cochés
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {vue === "francais" && (
        <section className="carte">
          <h2>Boussole Français</h2>
          <p className="doux">Le français arrive bientôt sur Boussole : {enfant.prenom} y aura accès avec la même carte.</p>
        </section>
      )}

      {vue === "fiches" && (
        <section className="carte">
          <PkpMath
            jeton={compte.jeton}
            onExpire={onExpire}
            niveauParDefaut={enfant.niveau}
            intro={`Les cours de ${niveau} pour accompagner ${enfant.prenom} : résumé, cours complet, fiche d'exercices et corrigé, à lire ici ou à exporter en PDF.`}
          />
        </section>
      )}

      {vue === "acces" && (
        <section className="carte">
          <AccesEnfant enfant={enfant} jeton={compte.jeton} onExpire={onExpire} onChange={onChange} />
        </section>
      )}
    </>
  );
}

/** Le parent réinitialise l'accès de son enfant : nouveau code tiré au hasard, ou code choisi. */
function AccesEnfant({ enfant, jeton, onExpire, onChange }) {
  const [carte, setCarte] = useState(null);
  const [erreur, setErreur] = useState(null);
  const [choisir, setChoisir] = useState(false);

  async function nouveauCode() {
    setErreur(null);
    try {
      setCarte(await api(`/parents/famille/${enfant.id}/acces`, { methode: "POST", corps: {}, jeton }));
    } catch (err) {
      if (err.status === 401) onExpire();
      else setErreur(err.message);
    }
  }

  return (
    <>
      <h2>Accès de {enfant.prenom}</h2>
      <p className="doux">
        {enfant.prenom} se connecte sur l'<a href="/eleve">espace élève</a> avec l'identifiant <code>{enfant.identifiant}</code> et
        son code personnel, pour toutes ses matières. Code perdu ou divulgué : réinitialisez-le. L'ancien code cesse aussitôt
        de fonctionner et les sessions ouvertes de {enfant.prenom} sont fermées.
      </p>
      <Erreur message={erreur} />
      {carte?.code && (
        <div className="encadre" role="status">
          <p>Nouveau code, à donner à {enfant.prenom} (il ne sera plus affiché) :</p>
          <p className="carte-enfant-codes">
            {carte.identifiant} · <strong>{carte.code}</strong>
          </p>
        </div>
      )}
      <div className="actions">
        <button onClick={nouveauCode}>Générer un nouveau code</button>
        <button className="secondaire" onClick={() => setChoisir((c) => !c)}>
          Choisir le code moi-même
        </button>
      </div>
      {choisir && (
        <ChoixCode
          enfant={enfant}
          jeton={jeton}
          onExpire={onExpire}
          onCode={onChange}
          chemin={`/parents/famille/${enfant.id}/acces`}
          methode="POST"
        />
      )}
    </>
  );
}

function TableauEnfant({ enfantId, appeler, compte, onExpire, onCode, avecCode = true }) {
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
            ...(avecCode ? [["code", "Code de connexion"]] : []),
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
function ChoixCode({ enfant, jeton, onExpire, onCode, chemin = null, methode = "PUT" }) {
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
      const r = await api(chemin ?? `/parents/enfants/${enfant.id}/code`, { methode, corps: { code }, jeton });
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
