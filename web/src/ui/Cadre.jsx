// Mises en page de la charte : application à navigation latérale (professeur, administrateur),
// en-tête de page, fenêtre modale, état vide.
import { Fragment, useEffect, useRef, useState } from "react";
import { Lien } from "../navigation.js";
import Icone, { Monogramme } from "./Icone.jsx";

/**
 * `liens` : [{ vers, libelle, icone, groupe? }] ; `cheminActif` : l'entrée dont le chemin préfixe celui-ci est active.
 * `groupe` : titre affiché au-dessus du premier lien de chaque groupe.
 * `pied` : contenu du bas de la navigation (compte, déconnexion). `marque` : « Éducation » (par défaut), « Maths » ou « Anglais ».
 */
export function CadreApplication({ espace, liens, cheminActif, pied, marque = "Éducation", children }) {
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
            Boussole <em>{marque}</em>
          </span>
        </a>
        <div className="espace">{espace}</div>
        {liens.map((l, i) => (
          <Fragment key={l.vers}>
            {l.groupe && l.groupe !== liens[i - 1]?.groupe && <div className="groupe-nav">{l.groupe}</div>}
            <Lien vers={l.vers} actif={l === actif}>
              <Icone nom={l.icone} />
              {l.libelle}
            </Lien>
          </Fragment>
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
  // Référence à jour de onFermer : la page derrière peut se redessiner (chargement d'une liste) sans que
  // l'effet ne se relance, sinon le focus reviendrait sur le premier champ pendant la saisie.
  const fermer = useRef(onFermer);
  fermer.current = onFermer;
  useEffect(() => {
    const echap = (e) => e.key === "Escape" && fermer.current();
    document.addEventListener("keydown", echap);
    boite.current?.querySelector("input, textarea, select, button")?.focus();
    return () => document.removeEventListener("keydown", echap);
  }, []);
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

// L'API enregistre les heures en UTC ; sous SQLite elles reviennent sans fuseau (« 2026-11-03T19:50:11 »),
// que le navigateur lirait comme une heure locale (1 à 2 h d'écart en France). Sans fuseau = UTC.
export const versDate = (iso) => new Date(/T\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/.test(iso) ? `${iso}Z` : iso);

export const formaterDate = (iso, { heure = false } = {}) =>
  iso
    ? versDate(iso).toLocaleString("fr-FR", heure ? { dateStyle: "short", timeStyle: "short" } : { dateStyle: "medium" })
    : "—";

export const pourcentage = (v) => (v == null ? "—" : `${Math.round(v * 100)} %`);

/**
 * Repère des pages de connexion élève : dit clairement que la page est celle de l'élève
 * (et non du parent ou du professeur) et renvoie les adultes vers leur espace.
 */
export function RepereEleve({ matiere }) {
  return <span className="badge accent">Espace élève · {matiere}</span>;
}

export function AutresEspaces({ professeur = "/enseignant" }) {
  return (
    <p className="aide autres-espaces">
      Ces codes sont ceux de l'<strong>élève</strong>, donnés par son professeur.
      <br />
      Vous êtes parent ? <a href="/parent">Espace parent</a> · Vous êtes professeur ? <a href={professeur}>Espace professeur</a>
    </p>
  );
}
