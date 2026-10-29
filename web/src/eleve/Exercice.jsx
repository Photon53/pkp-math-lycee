import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { BarreMaitrise, Difficulte, Erreur, LIBELLES_TYPE } from "../composants.jsx";
import { Maths } from "../maths.jsx";
import { ecrire, lire } from "../stockage.js";

export const CLE_SEANCE = "pkp.seance";
export const CLE_BILAN = "pkp.bilan";
const BILAN_VIDE = { reponses: 0, reussies: 0 };

const AIDE = {
  numerique: "Écris 1/2, 0,5 ou -3, ou une valeur exacte comme ln(5), e^2, sqrt(2).",
  expression: "Écris x^2 ou x², 2x pour 2×x, sqrt(…), ln(x), e^x. Parenthèses conseillées : ln(2x).",
  qcm: "Écris la lettre de la bonne réponse.",
};

// « … ? A) positif  B) négatif » → intitulé + options cliquables.
export function decouperQcm(enonce) {
  const options = [...enonce.matchAll(/\b([A-F])\)\s*(.*?)(?=\s+[A-F]\)|$)/g)];
  if (options.length < 2) return { intitule: enonce, options: null };
  return {
    intitule: enonce.slice(0, options[0].index).trim(),
    options: options.map((m) => ({ lettre: m[1], texte: m[2].trim() })),
  };
}

/**
 * Déroulé d'une séance : accueil → question → résultat → question… → bilan.
 * La séance en cours est mémorisée : recharger la page reprend la même question.
 */
export default function Exercice({ jeton, onExpire, onVoirCours }) {
  const [seanceId, setSeanceId] = useState(() => lire(CLE_SEANCE));
  const [etape, setEtape] = useState(seanceId ? "chargement" : "accueil");
  const [question, setQuestion] = useState(null);
  const [saisie, setSaisie] = useState("");
  const [resultat, setResultat] = useState(null);
  const [bilan, setBilan] = useState(() => lire(CLE_BILAN) ?? BILAN_VIDE);
  const [erreur, setErreur] = useState(null);
  const [envoi, setEnvoi] = useState(false);
  const champ = useRef(null);

  function changerSeance(id) {
    ecrire(CLE_SEANCE, id);
    setSeanceId(id);
  }

  async function appeler(chemin, options) {
    setErreur(null);
    setEnvoi(true);
    try {
      return await api(chemin, { ...options, jeton });
    } catch (err) {
      if (err.status === 401) onExpire();
      throw err;
    } finally {
      setEnvoi(false);
    }
  }

  async function chargerQuestion(id) {
    try {
      const q = await appeler(`/seances/${id}/question`);
      setResultat(null);
      setSaisie("");
      if (q === null) {
        setEtape("epuise");
      } else {
        setQuestion(q);
        setEtape("question");
      }
    } catch (err) {
      if (err.status === 404 || err.status === 409) {
        // Séance terminée ou introuvable (autre appareil, purge…) : on repart de zéro.
        changerSeance(null);
        setEtape("accueil");
      } else if (err.status !== 401) {
        setErreur(err.message);
      }
    }
  }

  useEffect(() => {
    if (seanceId) chargerQuestion(seanceId);
    // Uniquement au montage : reprise d'une séance mémorisée.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (etape === "question") champ.current?.focus();
  }, [etape, question]);

  // Le compteur suit la séance mémorisée : un rechargement ne le remet pas à zéro.
  useEffect(() => {
    ecrire(CLE_BILAN, bilan);
  }, [bilan]);

  // Chapitres ouverts par le professeur ; par défaut, tous ceux qui ont des questions sont cochés.
  const [chapitres, setChapitres] = useState(null);
  const [coches, setCoches] = useState(new Set());

  useEffect(() => {
    if (etape !== "accueil" && etape !== "bilan") return;
    let actif = true;
    api("/eleves/moi/chapitres", { jeton }).then(
      (liste) => {
        if (!actif) return;
        setChapitres(liste);
        setCoches(new Set(liste.filter((c) => c.nb_questions > 0).map((c) => c.id)));
      },
      (err) => actif && (err.status === 401 ? onExpire() : setErreur(err.message)),
    );
    return () => {
      actif = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [etape, jeton]);

  function basculer(id) {
    setCoches((avant) => {
      const apres = new Set(avant);
      apres.has(id) ? apres.delete(id) : apres.add(id);
      return apres;
    });
  }

  async function demarrer() {
    try {
      const seance = await appeler("/seances", { methode: "POST", corps: { chapitre_ids: [...coches] } });
      changerSeance(seance.id);
      setBilan(BILAN_VIDE);
      await chargerQuestion(seance.id);
    } catch (err) {
      if (err.status !== 401) setErreur(err.message);
    }
  }

  async function repondre(valeur) {
    try {
      const r = await appeler(`/seances/${seanceId}/reponses`, {
        methode: "POST",
        corps: { question_id: question.id, reponse_donnee: valeur },
      });
      setSaisie(valeur);
      setResultat(r);
      setBilan((b) => ({ reponses: b.reponses + 1, reussies: b.reussies + (r.correcte ? 1 : 0) }));
      setEtape("resultat");
    } catch (err) {
      if (err.status === 409) await chargerQuestion(seanceId);
      else if (err.status !== 401) setErreur(err.message);
    }
  }

  async function terminer() {
    try {
      await appeler(`/seances/${seanceId}/fin`, { methode: "POST" });
    } catch (err) {
      if (err.status === 401) return;
      // 404/409 : déjà terminée ailleurs, on affiche quand même le bilan.
    }
    changerSeance(null);
    setEtape("bilan");
  }

  if (etape === "accueil" || etape === "bilan") {
    return (
      <section className="carte">
        {etape === "bilan" ? (
          <>
            <h2>Séance terminée</h2>
            <p>
              {bilan.reponses === 0
                ? "Aucune réponse cette fois-ci."
                : `${bilan.reussies} bonne${bilan.reussies > 1 ? "s" : ""} réponse${bilan.reussies > 1 ? "s" : ""} sur ${bilan.reponses}.`}
            </p>
          </>
        ) : (
          <>
            <h2>Prêt·e à t'entraîner ?</h2>
            <p className="doux">
              Choisis un ou plusieurs chapitres. Les questions s'adaptent à ton niveau : on travaille d'abord ce qui est le
              moins maîtrisé.
            </p>
          </>
        )}
        {chapitres === null ? (
          <p className="doux">Chargement des chapitres…</p>
        ) : chapitres.length === 0 ? (
          <p className="doux">Ton professeur n'a pas encore ouvert de chapitre.</p>
        ) : (
          <fieldset className="choix-chapitres">
            <legend>Chapitres à travailler</legend>
            {chapitres.map((c) => (
              <label key={c.id} className="case">
                <input
                  type="checkbox"
                  checked={coches.has(c.id)}
                  onChange={() => basculer(c.id)}
                  disabled={c.nb_questions === 0}
                />
                {c.titre}
                <span className="doux">
                  {c.nb_questions === 0 ? " (bientôt disponible)" : ` (${c.nb_questions} question${c.nb_questions > 1 ? "s" : ""})`}
                </span>
              </label>
            ))}
          </fieldset>
        )}
        <Erreur message={erreur} />
        <div className="actions">
          <button onClick={demarrer} disabled={envoi || coches.size === 0}>
            {etape === "bilan" ? "Nouvelle séance" : "Démarrer une séance"}
          </button>
        </div>
      </section>
    );
  }

  if (etape === "chargement") return <p className="doux">Chargement…</p>;

  const enCours = (
    <div className="bilan" aria-live="polite">
      <span>
        Réponses : <strong>{bilan.reponses}</strong>
      </span>
      <span>
        Réussies : <strong>{bilan.reussies}</strong>
      </span>
    </div>
  );

  if (etape === "epuise") {
    return (
      <section className="carte">
        <h2>Plus de question disponible</h2>
        <p className="doux">Ton professeur n'a pas encore ajouté de questions pour ton niveau.</p>
        <Erreur message={erreur} />
        <div className="actions">
          <button onClick={terminer}>Terminer la séance</button>
        </div>
      </section>
    );
  }

  const { intitule, options } = question.type === "qcm" ? decouperQcm(question.enonce) : { intitule: question.enonce, options: null };
  const repondue = etape === "resultat";

  return (
    <>
      {enCours}
      <article className="carte">
        <div className="meta">
          <span className="badge">{LIBELLES_TYPE[question.type]}</span>
          <Difficulte niveau={question.difficulte} />
        </div>
        <p className="enonce">
          <Maths enLigne texte={intitule} />
        </p>

        {options ? (
          <div className="options">
            {options.map((o) => (
              <button key={o.lettre} onClick={() => repondre(o.lettre)} disabled={envoi || repondue}>
                <span className="lettre">{o.lettre}</span>
                <Maths enLigne texte={o.texte} />
              </button>
            ))}
          </div>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (saisie.trim()) repondre(saisie);
            }}
          >
            <label htmlFor="saisie">Ta réponse</label>
            <input
              id="saisie"
              ref={champ}
              value={saisie}
              onChange={(e) => setSaisie(e.target.value)}
              readOnly={repondue}
              autoComplete="off"
              spellCheck={false}
              maxLength={200}
            />
            <p className="aide">{AIDE[question.type]}</p>
            {!repondue && (
              <div className="actions">
                <button type="submit" disabled={envoi || !saisie.trim()}>
                  Valider
                </button>
              </div>
            )}
          </form>
        )}
        <Erreur message={erreur} />
      </article>

      {repondue && (
        <article className={`carte resultat ${resultat.correcte ? "ok" : "ko"}`} role="status">
          <p className="verdict">{resultat.correcte ? "Bonne réponse !" : "Pas tout à fait."}</p>
          {!resultat.correcte && (
            <p>
              Réponse attendue : <code>{resultat.solution}</code>
            </p>
          )}
          <BarreMaitrise valeur={resultat.maitrise} maitrisee={resultat.maitrisee} libelle="Maîtrise de cette compétence" />
          <div className="actions">
            <button autoFocus onClick={() => chargerQuestion(seanceId)} disabled={envoi}>
              Question suivante
            </button>
            {onVoirCours && (
              <button className="secondaire" onClick={() => onVoirCours(question.competence_id)}>
                Revoir le cours
              </button>
            )}
            <button className="lien" onClick={terminer} disabled={envoi}>
              Terminer la séance
            </button>
          </div>
        </article>
      )}

      {!repondue && (
        <div className="actions">
          <button className="lien" onClick={terminer} disabled={envoi}>
            Terminer la séance
          </button>
        </div>
      )}
    </>
  );
}
