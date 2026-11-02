import { useEffect, useState } from "react";
import { api } from "../api.js";

async function telecharger(code, publicCible, jeton) {
  const reponse = await fetch(`/api/anglais/seances/${encodeURIComponent(code)}/pdf/${publicCible}`, {
    headers: { Authorization: `Bearer ${jeton}` },
  });
  if (!reponse.ok) {
    const data = await reponse.json().catch(() => null);
    throw new Error(data?.detail || "Impossible de générer le PDF.");
  }
  const url = URL.createObjectURL(await reponse.blob());
  const lien = document.createElement("a");
  lien.href = url;
  lien.download = `pkp-anglais-${code}-${publicCible}.pdf`;
  document.body.appendChild(lien);
  lien.click();
  lien.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

export default function SeancesAnglais({ jeton, onExpire }) {
  const [liste, setListe] = useState([]);
  const [code, setCode] = useState("");
  const [seance, setSeance] = useState(null);
  const [erreur, setErreur] = useState("");
  const [chargement, setChargement] = useState(true);
  const [telechargement, setTelechargement] = useState("");

  useEffect(() => {
    let actif = true;
    api("/anglais/seances", { jeton }).then((items) => {
      if (!actif) return;
      setListe(items);
      setCode(items[0]?.code || "");
    }).catch((err) => {
      if (!actif) return;
      setErreur(err.message);
      if (err.status === 401) onExpire();
    }).finally(() => { if (actif) setChargement(false); });
    return () => { actif = false; };
  }, [jeton, onExpire]);

  useEffect(() => {
    if (!code) return;
    let actif = true;
    setSeance(null);
    setErreur("");
    api(`/anglais/seances/${encodeURIComponent(code)}`, { jeton }).then((data) => {
      if (actif) setSeance(data);
    }).catch((err) => {
      if (!actif) return;
      setErreur(err.message);
      if (err.status === 401) onExpire();
    });
    return () => { actif = false; };
  }, [code, jeton, onExpire]);

  async function pdf(publicCible) {
    setErreur("");
    setTelechargement(publicCible);
    try {
      await telecharger(code, publicCible, jeton);
    } catch (err) {
      setErreur(err.message);
    } finally {
      setTelechargement("");
    }
  }

  return <section>
    <p className="doux">Séances pilotes 4e et 3e · 90 minutes · contenus en attente de validation pédagogique.</p>
    {chargement && <p>Chargement des séances…</p>}
    {erreur && <p role="alert" className="erreur">{erreur}</p>}
    {liste.length > 0 && <div className="carte">
      <label htmlFor="anglais-seance">Séance</label>
      <select id="anglais-seance" value={code} onChange={(e) => setCode(e.target.value)}>
        {liste.map((item) => <option key={item.code} value={item.code}>{item.niveau} · {item.titre}</option>)}
      </select>
    </div>}
    {seance && <>
      <div className="carte">
        <h2>{seance.titre}</h2>
        <p><strong>Objectif :</strong> {seance.objectif}</p>
        <p><strong>Niveau :</strong> {seance.niveau} · <strong>Durée :</strong> 90 minutes</p>
        <div className="actions">
          <button type="button" disabled={!!telechargement} onClick={() => pdf("eleve")}>PDF élève</button>
          <button type="button" disabled={!!telechargement} onClick={() => pdf("animateur")}>PDF animateur + corrigés</button>
        </div>
      </div>
      <h3>Déroulé de la séance</h3>
      {seance.etapes.map((etape, i) => <article className="carte" key={i}>
        <h4>{i + 1}. {etape.titre} ({etape.duree_minutes} min)</h4>
        <p><strong>Élève :</strong> {etape.consigne_eleve}</p>
        <p><strong>Animateur :</strong> {etape.consigne_animateur}</p>
      </article>)}
      <h3>Exercices différenciés</h3>
      {seance.fiches.map((fiche) => <article className="carte" key={fiche.parcours}>
        <h4>Parcours {fiche.parcours}</h4>
        <p style={{ whiteSpace: "pre-wrap" }}>{fiche.enonce}</p>
        <details><summary>Voir le corrigé / les critères</summary><p style={{ whiteSpace: "pre-wrap" }}>{fiche.corrige}</p></details>
      </article>)}
    </>}
  </section>;
}
