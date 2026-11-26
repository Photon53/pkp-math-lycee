// Issue #179 — Rédaction en ligne et correction par le professeur (Claude)
//
// L'élève choisit un sujet, écrit, enregistre son brouillon, puis le remet ; il lit ensuite le commentaire de son
// professeur et peut réécrire dans une nouvelle version. Fermé tant que la rédaction en ligne n'est pas ouverte (403).
import { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";
import { Erreur } from "../composants.jsx";

const STATUTS = { brouillon: "Brouillon", remise: "Remise, en attente de correction", corrigee: "Corrigée" };
export const RAPPEL =
  "N'écris ni ton adresse, ni tes coordonnées, ni d'informations intimes sur toi ou sur d'autres personnes : " +
  "préfère des personnages et des lieux imaginaires.";

export default function Redaction({ jeton, onExpire }) {
  const [sujets, setSujets] = useState(null);
  const [ouvert, setOuvert] = useState(null);
  const [erreur, setErreur] = useState(null);

  const echec = useCallback((err) => (err.status === 401 && onExpire ? onExpire() : setErreur(err.message)), [onExpire]);
  const charger = useCallback(() => api("/eleves/moi/redactions", { jeton }).then(setSujets, echec), [jeton, echec]);
  useEffect(() => {
    charger();
  }, [charger]);

  if (ouvert)
    return <Sujet questionId={ouvert} jeton={jeton} echec={echec} onRetour={() => { setOuvert(null); charger(); }} />;
  if (erreur) return <Erreur message={erreur} />;
  if (!sujets) return <p className="doux">Chargement des sujets…</p>;
  return (
    <section className="carte" aria-labelledby="titre-redaction">
      <h2 id="titre-redaction">Rédaction</h2>
      {sujets.length === 0 ? (
        <p className="doux">Pas encore de sujet de rédaction ouvert par ta professeure.</p>
      ) : (
        <ul className="liste-sujets">
          {sujets.map((s) => (
            <li key={s.question_id}>
              <button className="lien" onClick={() => setOuvert(s.question_id)}>{s.chapitre} — {s.competence}</button>{" "}
              <span className="doux petit">{s.statut ? STATUTS[s.statut] : "À écrire"}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function Sujet({ questionId, jeton, echec, onRetour }) {
  const [detail, setDetail] = useState(null);
  const [texte, setTexte] = useState("");
  const [message, setMessage] = useState(null);
  const [erreur, setErreur] = useState(null);

  const recevoir = useCallback((d) => {
    setDetail(d);
    const derniere = d.versions.at(-1);
    setTexte(derniere?.statut === "brouillon" ? derniere.texte : "");
  }, []);
  useEffect(() => {
    api(`/eleves/moi/redactions/${questionId}`, { jeton }).then(recevoir, echec);
  }, [questionId, jeton, recevoir, echec]);

  async function envoyer(remettre) {
    setMessage(null);
    setErreur(null);
    try {
      let d = await api(`/eleves/moi/redactions/${questionId}`, { jeton, methode: "PUT", corps: { texte } });
      if (remettre) d = await api(`/eleves/moi/redactions/${questionId}/remise`, { jeton, methode: "POST" });
      recevoir(d);
      setMessage(remettre ? "Rédaction remise à ta professeure." : "Brouillon enregistré.");
    } catch (err) {
      if (err.status === 401) echec(err);
      else setErreur(err.message);
    }
  }

  if (!detail) return <p className="doux">Chargement…</p>;
  const derniere = detail.versions.at(-1);
  const enAttente = derniere?.statut === "remise";
  return (
    <section className="carte" aria-labelledby="titre-sujet">
      <button className="lien" onClick={onRetour}>← Tous les sujets</button>
      <h2 id="titre-sujet">Sujet</h2>
      <p>{detail.enonce}</p>
      <p className="aide" role="note">{RAPPEL}</p>
      {message && <p className="succes" role="status">{message}</p>}
      <Erreur message={erreur} />
      {enAttente ? (
        <p className="doux">Ta rédaction est remise : ta professeure va la corriger.</p>
      ) : (
        <>
          <label htmlFor="texte-redaction">
            {derniere?.statut === "corrigee" ? `Réécriture (version ${derniere.version + 1})` : "Ta rédaction"}
          </label>
          <textarea id="texte-redaction" rows={14} maxLength={10000} value={texte} onChange={(e) => setTexte(e.target.value)} />
          <div className="actions">
            <button className="secondaire" disabled={!texte.trim()} onClick={() => envoyer(false)}>Enregistrer le brouillon</button>
            <button disabled={!texte.trim()} onClick={() => envoyer(true)}>Remettre à ma professeure</button>
          </div>
        </>
      )}
      {detail.versions.filter((v) => v.statut !== "brouillon").reverse().map((v) => (
        <article key={v.id} className="encadre">
          <strong>Version {v.version} — {STATUTS[v.statut]}</strong>
          <p className="texte-redaction">{v.texte}</p>
          {v.commentaire && <p><strong>Commentaire :</strong> {v.commentaire}</p>}
        </article>
      ))}
      {detail.conserver_jusqu_au && (
        <p className="doux petit">Tes rédactions sont conservées jusqu'au {new Date(detail.conserver_jusqu_au).toLocaleDateString("fr-FR")}, puis supprimées.</p>
      )}
    </section>
  );
}
