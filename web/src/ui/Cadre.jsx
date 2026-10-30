// Mises en page de la charte : application à navigation latérale (professeur, administrateur),
// en-tête de page, fenêtre modale, état vide.
import { useEffect, useRef, useState } from "react";
import { Lien } from "../navigation.js";
import Icone, { Monogramme } from "./Icone.jsx";

/**
 * `liens` : [{ vers, libelle, icone }] ; `cheminActif` : l'entrée dont le chemin préfixe celui-ci est active.
 * `pied` : contenu du bas de la navigation (compte, déconnexion).
 */
export function CadreApplication({ espace, liens, cheminActif, pied, children }) {
  const [ouverte, setOuverte] = useState(false);
  const actif = liens
    .filter((l) => cheminActif === l.vers || cheminActif.startsWith(`${l.vers}/`))
    .sort((a, b) => b.vers.length - a.vers.length)[0];

  useEffect(() => setOuverte(false), [cheminActif]);

  return (
    <div className="app">
      <nav className={ouverte ? "app-nav ouverte" : "app-nav"} aria-label={`Navigation ${espace}`}>
        <a className="logo" href="/">
          <Monogramme taille={28} />
          <span>
            PKP <em>Math Lycée</em>
          </span>
        </a>
        <div className="espace">{espace}</div>
        {liens.map((l) => (
          <Lien key={l.vers} vers={l.vers} actif={l === actif}>
            <Icone nom={l.icone} />
            {l.libelle}
          </Lien>
        ))}
        <div className="bas">{pied}</div>
      </nav>
      <div className="app-contenu">
        <button className="secondaire petit bouton-menu" onClick={() => setOuverte(true)} aria-label="Ouvrir le menu">
          <Icone nom="menu" /> Menu
        </button>
        {children}
      </div>
    </div>
  );
}

export function EntetePage({ titre, sousTitre, fil, children }) {
  return (
    <header className="app-entete">
      <div>
        {fil && <div className="fil">{fil}</div>}
        <h1>{titre}</h1>
        {sousTitre && <p className="doux">{sousTitre}</p>}
      </div>
      {children && <div className="actions">{children}</div>}
    </header>
  );
}

export function Modale({ titre, onFermer, large = false, children }) {
  const boite = useRef(null);
  useEffect(() => {
    const echap = (e) => e.key === "Escape" && onFermer();
    document.addEventListener("keydown", echap);
    boite.current?.querySelector("input, textarea, select, button")?.focus();
    return () => document.removeEventListener("keydown", echap);
  }, [onFermer]);
  return (
    <div className="voile" onMouseDown={(e) => e.target === e.currentTarget && onFermer()}>
      <div className={large ? "modale large" : "modale"} role="dialog" aria-modal="true" aria-label={titre} ref={boite}>
        <div className="carte-titre">
          <h2>{titre}</h2>
          <button className="icone" onClick={onFermer} aria-label="Fermer">
            <Icone nom="fermer" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Vide({ icone = "recherche", children }) {
  return (
    <div className="vide">
      <Icone nom={icone} taille={40} />
      <p>{children}</p>
    </div>
  );
}

export function Pagination({ page, total, taille = 50, onChange }) {
  const pages = Math.max(1, Math.ceil(total / taille));
  if (pages <= 1) return null;
  return (
    <nav className="pagination" aria-label="Pagination">
      <button className="secondaire petit" disabled={page <= 1} onClick={() => onChange(page - 1)}>
        Précédent
      </button>
      <span className="chiffres">
        Page {page} / {pages}
      </span>
      <button className="secondaire petit" disabled={page >= pages} onClick={() => onChange(page + 1)}>
        Suivant
      </button>
    </nav>
  );
}

/** Export CSV côté navigateur (EA3.22) : `lignes` est une liste d'objets aux mêmes clés. */
export function exporterCsv(nom, lignes) {
  if (!lignes.length) return;
  const colonnes = Object.keys(lignes[0]);
  const cellule = (v) => `"${String(v ?? "").replaceAll('"', '""')}"`;
  const texte = [colonnes.join(";"), ...lignes.map((l) => colonnes.map((c) => cellule(l[c])).join(";"))].join("\n");
  const url = URL.createObjectURL(new Blob(["﻿" + texte], { type: "text/csv;charset=utf-8" }));
  const lien = Object.assign(document.createElement("a"), { href: url, download: nom });
  lien.click();
  URL.revokeObjectURL(url);
}

export const formaterDate = (iso, { heure = false } = {}) =>
  iso
    ? new Date(iso).toLocaleString("fr-FR", heure ? { dateStyle: "short", timeStyle: "short" } : { dateStyle: "medium" })
    : "—";

export const pourcentage = (v) => (v == null ? "—" : `${Math.round(v * 100)} %`);
