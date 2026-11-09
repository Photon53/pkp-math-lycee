import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Erreur } from "../composants.jsx";

// Ticket #30 : catégories regroupées pour être faciles à choisir sur un téléphone.
export const GROUPES_CATEGORIES = [
  ["Problème technique", [["bug", "Bug"], ["dysfonctionnement", "Dysfonctionnement"], ["lien-inaccessible", "Lien inaccessible"]]],
  [
    "Contenu pédagogique",
    [
      ["erreur-pedagogique", "Erreur dans un cours, un exercice ou un corrigé"],
      ["amelioration-pedagogique", "Amélioration pédagogique"],
    ],
  ],
  ["Idées et questions", [["amelioration-fonctionnelle", "Amélioration fonctionnelle"], ["question", "Question"], ["autre", "Autre"]]],
];
export const LIBELLES_CATEGORIES = Object.fromEntries(GROUPES_CATEGORIES.flatMap(([, l]) => l));
export const LIBELLES_STATUTS = { recue: "Reçue", "en-cours": "En cours", resolue: "Résolue", fermee: "Fermée" };

const date = (iso) => new Date(iso).toLocaleDateString("fr-FR");

/**
 * Onglet « Remarques et suggestions » des espaces élève, parent et professeur : envoyer une remarque avec son
 * nom ou anonyme, la suivre avec sa référence et son code, retrouver celles envoyées avec son nom.
 */
export default function Remarques({ jeton, onExpire, tutoiement = false }) {
  const tu = (avecTu, avecVous) => (tutoiement ? avecTu : avecVous);
  return (
    <>
      <NouvelleRemarque jeton={jeton} onExpire={onExpire} tu={tu} />
      <SuiviRemarque tu={tu} />
      <MesRemarques jeton={jeton} onExpire={onExpire} tu={tu} />
    </>
  );
}

function NouvelleRemarque({ jeton, onExpire, tu }) {
  const vide = { categorie: "", description: "", page: "", anonyme: null };
  const [f, setF] = useState(vide);
  const [accuse, setAccuse] = useState(null);
  const [erreur, setErreur] = useState(null);
  const [envoi, setEnvoi] = useState(false);
  const maj = (cle) => (e) => setF({ ...f, [cle]: e.target.value });

  async function envoyer(e) {
    e.preventDefault();
    setErreur(null);
    setEnvoi(true);
    try {
      setAccuse(await api("/remarques", { methode: "POST", corps: { ...f, page: f.page || null }, jeton }));
      setF(vide);
    } catch (err) {
      if (err.status === 401) onExpire?.();
      else setErreur(err.message);
    } finally {
      setEnvoi(false);
    }
  }

  if (accuse) {
    return (
      <section className="carte" role="status">
        <h2>Merci, {tu("ta remarque est bien reçue", "votre remarque est bien reçue")}</h2>
        <p>
          Référence : <strong>{accuse.reference}</strong>
          <br />
          Code de suivi : <strong>{accuse.code_suivi}</strong>
        </p>
        <p className="avertissement">
          {tu("Note ce code ou fais une capture d'écran", "Notez ce code ou faites une capture d'écran")} : il ne sera plus affiché.
          Avec la référence, il permet de suivre la remarque et de lire la réponse
          {accuse.anonyme ? ", sans que personne ne sache qui l'a envoyée." : "."}
        </p>
        <div className="actions">
          <button className="secondaire" onClick={() => setAccuse(null)}>
            Envoyer une autre remarque
          </button>
        </div>
      </section>
    );
  }

  return (
    <form className="carte formulaire" onSubmit={envoyer}>
      <h2>Remarques et suggestions</h2>
      <p className="doux">
        Un bug, une erreur dans un exercice, une idée ? {tu("Dis-le nous", "Dites-le nous")} : chaque remarque est lue par l'équipe.
      </p>
      <label>
        Catégorie
        <select value={f.categorie} onChange={maj("categorie")} required>
          <option value="" disabled>
            Choisir…
          </option>
          {GROUPES_CATEGORIES.map(([groupe, options]) => (
            <optgroup key={groupe} label={groupe}>
              {options.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
      </label>
      <label>
        Description
        <textarea value={f.description} onChange={maj("description")} required minLength={5} maxLength={3000} rows={5} />
      </label>
      <label>
        Page, cours ou exercice concerné (facultatif)
        <input value={f.page} onChange={maj("page")} maxLength={300} placeholder="ex. cours « Fonctions affines », exercice 2NDE-AFF-04" />
      </label>
      <fieldset>
        <legend>{tu("Comment veux-tu l'envoyer ?", "Comment souhaitez-vous l'envoyer ?")}</legend>
        <label className="case">
          <input type="radio" name="mode" checked={f.anonyme === false} onChange={() => setF({ ...f, anonyme: false })} required /> Avec mon
          nom
        </label>
        <label className="case">
          <input type="radio" name="mode" checked={f.anonyme === true} onChange={() => setF({ ...f, anonyme: true })} /> Anonyme
        </label>
        <p className="doux petit">
          « Anonyme » : ni {tu("ton", "votre")} nom, ni {tu("ton", "votre")} compte ne sont enregistrés avec la remarque, et les
          personnes qui la traitent ne peuvent pas savoir qui l'a envoyée. Ce n'est pas un anonymat absolu : {tu("tu es", "vous êtes")}{" "}
          {tu("connecté·e", "connecté·e")}, et ce que {tu("tu écris", "vous écrivez")} dans la description peut permettre de{" "}
          {tu("te", "vous")} reconnaître. Avec {tu("ton", "votre")} nom, l'équipe peut {tu("te", "vous")} répondre plus facilement.
        </p>
      </fieldset>
      <Erreur message={erreur} />
      <div className="actions">
        <button type="submit" disabled={envoi || f.anonyme === null}>
          Envoyer
        </button>
      </div>
    </form>
  );
}

function SuiviRemarque({ tu }) {
  const [f, setF] = useState({ reference: "", code: "" });
  const [suivi, setSuivi] = useState(null);
  const [erreur, setErreur] = useState(null);

  async function chercher(e) {
    e.preventDefault();
    setErreur(null);
    setSuivi(null);
    try {
      setSuivi(await api("/remarques/suivi", { methode: "POST", corps: f }));
    } catch (err) {
      setErreur(err.message);
    }
  }

  return (
    <details className="carte">
      <summary>Suivre une remarque avec son code</summary>
      <form className="formulaire" onSubmit={chercher}>
        <label>
          Référence
          <input value={f.reference} onChange={(e) => setF({ ...f, reference: e.target.value })} required placeholder="R-…" />
        </label>
        <label>
          Code de suivi
          <input value={f.code} onChange={(e) => setF({ ...f, code: e.target.value })} required autoComplete="off" />
        </label>
        <Erreur message={erreur} />
        <div className="actions">
          <button type="submit" className="secondaire">
            Voir où en est la remarque
          </button>
        </div>
      </form>
      {suivi && <FicheSuivi r={suivi} tu={tu} />}
    </details>
  );
}

function FicheSuivi({ r, tu }) {
  return (
    <div className="encadre" role="status">
      <p>
        <strong>{r.reference}</strong> · {LIBELLES_CATEGORIES[r.categorie]} · envoyée le {date(r.cree_le)} · statut :{" "}
        <strong>{LIBELLES_STATUTS[r.statut]}</strong>
      </p>
      {r.reponse ? (
        <p>
          <strong>Réponse :</strong> {r.reponse}
        </p>
      ) : (
        <p className="doux">Pas encore de réponse.</p>
      )}
    </div>
  );
}

function MesRemarques({ jeton, onExpire, tu }) {
  const [liste, setListe] = useState(null);

  useEffect(() => {
    api("/remarques/miennes", { jeton }).then(setListe, (err) => {
      if (err.status === 401) onExpire?.();
      setListe([]);
    });
    // Une fois par jeton : `onExpire` change à chaque rendu du parent.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jeton]);

  if (!liste?.length) return null;
  return (
    <section className="carte">
      <h3>{tu("Tes remarques envoyées avec ton nom", "Vos remarques envoyées avec votre nom")}</h3>
      {liste.map((r) => (
        <FicheSuivi key={r.reference} r={r} tu={tu} />
      ))}
    </section>
  );
}
