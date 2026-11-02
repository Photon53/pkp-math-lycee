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

const MEDIAS = { audio: "Audio", video: "Vidéo" };

/** Liens ouverts dans un nouvel onglet, sans lecteur intégré : aucun traceur tiers dans l'application. */
function LienRessource({ ressource }) {
  return <p>
    <a href={ressource.url} target="_blank" rel="noopener noreferrer"><strong>{ressource.title}</strong></a>{" "}
    <span className="doux">· {MEDIAS[ressource.media] ?? "En ligne"} · {ressource.level} · {ressource.source} · vérifié le {ressource.verified_on}</span>
  </p>;
}

/** Dialogue « Nom: réplique » en bulles alternées, comme dans le cahier ; un texte suivi reste un paragraphe. */
function Bulles({ texte }) {
  const repliques = texte.split("\n").map((ligne) => ligne.split(/:(.*)/s));
  if (repliques.length < 2 || repliques.some((r) => r.length < 2 || r[0].length > 15)) {
    return <p className="anglais-texte">{texte}</p>;
  }
  const noms = [...new Set(repliques.map(([nom]) => nom.trim()))];
  return <div className="anglais-bulles">
    {repliques.map(([nom, replique], i) => (
      <p key={i} className={noms.indexOf(nom.trim()) % 2 === 0 ? "bulle gauche" : "bulle droite"}>
        <strong>{nom.trim()}:</strong> {replique.trim()}
      </p>
    ))}
  </div>;
}

function Rubrique({ numero, titre, children }) {
  return <article className="carte anglais-rubrique">
    <h3>{numero ? `${numero}. ` : ""}{titre}</h3>
    {children}
  </article>;
}

function Reponse({ children }) {
  return <details className="correction"><summary>Réponse</summary>{children}</details>;
}

/** Le cours tel qu'il est imprimé dans le cahier élève, rubrique par rubrique, avec les réponses repliées. */
function Cahier({ cahier, fiches }) {
  const ecoute = cahier.listening;
  return <>
    <Rubrique numero={1} titre="Get curious - Choose your idea">
      <ul className="anglais-visuels">
        {cahier.visual.map((v) => <li key={v.label}><img src={v.image} alt="" width="64" height="64" />{v.label}</li>)}
      </ul>
      <p>Which one interests you most? Explain your choice to a partner.</p>
    </Rubrique>

    <Rubrique numero={2} titre="Word power - Learn and remember">
      <div className="tableau-defilant"><table>
        <thead><tr><th>English</th><th>Français</th><th>In a sentence</th></tr></thead>
        <tbody>{cahier.vocab.map(([en, fr, exemple]) => <tr key={en}><td><strong>{en}</strong></td><td>{fr}</td><td><em>{exemple}</em></td></tr>)}</tbody>
      </table></div>
      <p className="anglais-encadre prononciation"><strong>Say it right!</strong> {cahier.pronunciation}</p>
    </Rubrique>

    <Rubrique numero={3} titre={`Grammar focus - ${cahier.grammar.title}`}>
      <div className="anglais-encadre grammaire">
        <p>{cahier.grammar.rule}</p>
        <ul>{cahier.grammar.examples.map((e) => <li key={e}>{e}</li>)}</ul>
      </div>
    </Rubrique>

    <Rubrique numero={4} titre="Listen and watch">
      <LienRessource ressource={ecoute} />
      <p className="doux">À ouvrir et tester avant la séance (téléphone ou ordinateur avec haut-parleur). Le cahier élève contient le QR code.</p>
      <ol>{ecoute.questions.map((q, i) => <li key={i}>{q}<Reponse><p>{ecoute.answers[i]}</p></Reponse></li>)}</ol>
      <details className="correction"><summary>Script de secours (sans réseau, à lire deux fois)</summary>
        <Bulles texte={ecoute.fallback} />
      </details>
    </Rubrique>

    <Rubrique numero={5} titre="Read the model">
      <Bulles texte={cahier.model} />
      <p>Highlight useful expressions. Find one sentence you can reuse.</p>
      <p className="anglais-encadre culture"><strong>Did you know?</strong> {cahier.did_you_know}</p>
    </Rubrique>

    <Rubrique numero={6} titre="Practise - Try it yourself">
      <ol>{cahier.practice.map((q, i) => <li key={i}>{q}<Reponse><p>{cahier.practice_answers[i]}</p></Reponse></li>)}</ol>
    </Rubrique>

    <Rubrique numero={7} titre="Choose your challenge - A / B / C">
      {fiches.map((fiche) => <div key={fiche.parcours}>
        <h4>Track {fiche.parcours}</h4>
        <p style={{ whiteSpace: "pre-wrap" }}>{fiche.enonce}</p>
        {fiche.parcours === "A" && <p className="anglais-encadre"><strong>Need help? Start with:</strong> {cahier.starters.join("  /  ")}</p>}
        <details className="correction"><summary>Corrigé / critères</summary><p style={{ whiteSpace: "pre-wrap" }}>{fiche.corrige}</p></details>
      </div>)}
    </Rubrique>

    <Rubrique numero={8} titre="Final mission"><p className="anglais-encadre">{cahier.mission}</p></Rubrique>

    <Rubrique numero={9} titre="Check yourself - I can...">
      <ul>{cahier.can_do.map((c) => <li key={c}>{c}</li>)}</ul>
      <p className="doux">Dans le cahier, l'élève coche : Not yet / Almost / Yes!</p>
    </Rubrique>

    <Rubrique numero={10} titre="Remember for next time"><p>{cahier.memory}</p></Rubrique>

    {cahier.go_further.length > 0 && <Rubrique titre="Go further at home">
      {cahier.go_further.map((r) => <div key={r.url}><LienRessource ressource={r} /><p className="doux">{r.task}</p></div>)}
    </Rubrique>}
  </>;
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
        {seance.cahier && <p className="anglais-accroche">{seance.cahier.hook}</p>}
        <p><strong>Objectif :</strong> {seance.objectif}</p>
        <p><strong>Niveau :</strong> {seance.niveau} · <strong>Durée :</strong> 90 minutes</p>
        <div className="actions">
          <button type="button" disabled={!!telechargement} onClick={() => pdf("eleve")}>PDF élève</button>
          <button type="button" disabled={!!telechargement} onClick={() => pdf("animateur")}>PDF animateur + corrigés</button>
        </div>
      </div>
      {seance.cahier && <>
        <h2>Le cours</h2>
        <p className="doux">Même contenu et même ordre que le cahier élève ; les réponses sont repliées.</p>
        <Cahier cahier={seance.cahier} fiches={seance.fiches} />
      </>}
      <h2>Guide animateur : déroulé des 90 minutes</h2>
      {seance.etapes.map((etape, i) => <article className="carte" key={i}>
        <h4>{i + 1}. {etape.titre} ({etape.duree_minutes} min)</h4>
        <p><strong>Élève :</strong> {etape.consigne_eleve}</p>
        <p><strong>Animateur :</strong> {etape.consigne_animateur}</p>
      </article>)}
    </>}
  </section>;
}
