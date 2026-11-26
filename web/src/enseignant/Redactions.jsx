// Issue #179 — Rédaction en ligne et correction par le professeur (Claude)
//
// Rédactions remises par les élèves d'une classe de français ; le professeur lit le texte et le guide du sujet, puis
// écrit son commentaire. Les brouillons des élèves ne lui sont jamais montrés.
import { useCallback, useEffect, useState } from "react";
import { Erreur } from "../composants.jsx";
import { useApi } from "./useApi.js";

const STATUTS = { remise: "À corriger", corrigee: "Corrigée" };

export default function Redactions({ jeton, onExpire }) {
  const { appeler, erreur } = useApi(jeton, onExpire);
  const [classes, setClasses] = useState(null);
  const [classe, setClasse] = useState("");
  const [liste, setListe] = useState(null);
  const [ouverte, setOuverte] = useState(null);

  useEffect(() => {
    appeler("/enseignants/classes").then((l) => setClasses(l.filter((c) => c.matiere === "francais")), () => {});
  }, [appeler]);
  const charger = useCallback(() => {
    if (classe) appeler(`/enseignants/classes/${classe}/redactions`).then(setListe, () => {});
  }, [appeler, classe]);
  useEffect(() => {
    setListe(null);
    charger();
  }, [charger]);

  if (ouverte) return <Correction id={ouverte} appeler={appeler} erreur={erreur} onRetour={() => { setOuverte(null); charger(); }} />;
  return (
    <section className="carte">
      <Erreur message={erreur} />
      {classes === null ? (
        <p className="doux">Chargement…</p>
      ) : classes.length === 0 ? (
        <p className="doux">Aucune classe de français.</p>
      ) : (
        <label>
          Classe
          <select value={classe} onChange={(e) => setClasse(e.target.value)}>
            <option value="">Choisir…</option>
            {classes.map((c) => <option key={c.id} value={c.id}>{c.code}</option>)}
          </select>
        </label>
      )}
      {liste && (liste.length === 0 ? (
        <p className="doux">Aucune rédaction remise pour l'instant.</p>
      ) : (
        <ul className="liste-redactions">
          {liste.map((r) => (
            <li key={r.id}>
              <button className="lien" onClick={() => setOuverte(r.id)}>{r.eleve} — version {r.version}</button>{" "}
              <span className={`badge ${r.statut === "remise" ? "alerte" : "ok"}`}>{STATUTS[r.statut]}</span>
            </li>
          ))}
        </ul>
      ))}
    </section>
  );
}

function Correction({ id, appeler, erreur, onRetour }) {
  const [r, setR] = useState(null);
  const [commentaire, setCommentaire] = useState("");
  const [message, setMessage] = useState(null);
  useEffect(() => {
    appeler(`/enseignants/redactions/${id}`).then((x) => { setR(x); setCommentaire(x.commentaire ?? ""); }, () => {});
  }, [appeler, id]);

  async function envoyer(e) {
    e.preventDefault();
    setMessage(null);
    try {
      setR(await appeler(`/enseignants/redactions/${id}/correction`, { methode: "POST", corps: { commentaire } }));
      setMessage("Correction envoyée à l'élève.");
    } catch {
      // erreur déjà affichée
    }
  }

  if (!r) return <p className="doux">Chargement…</p>;
  return (
    <section className="carte">
      <button className="lien" onClick={onRetour}>← Toutes les rédactions</button>
      <h2>{r.eleve} — version {r.version}</h2>
      <p className="doux">{r.sujet}</p>
      <p className="texte-redaction">{r.texte}</p>
      <details>
        <summary>Guide de correction</summary>
        <p>{r.guide}</p>
        {r.correction?.etapes?.length > 0 && <ul>{r.correction.etapes.map((e, i) => <li key={i}>{e}</li>)}</ul>}
      </details>
      {message && <p className="succes" role="status">{message}</p>}
      <Erreur message={erreur} />
      <form onSubmit={envoyer}>
        <label htmlFor="commentaire-redaction">Commentaire pour l'élève</label>
        <textarea id="commentaire-redaction" rows={6} maxLength={10000} value={commentaire} onChange={(e) => setCommentaire(e.target.value)} />
        <button type="submit" disabled={!commentaire.trim()}>Envoyer la correction</button>
      </form>
    </section>
  );
}
