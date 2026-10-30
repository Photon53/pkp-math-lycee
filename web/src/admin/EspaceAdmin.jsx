import { useState } from "react";
import { api } from "../api.js";
import { Erreur } from "../composants.jsx";
import { ecrire, lire } from "../stockage.js";
import { CadreApplication, EntetePage } from "../ui/Cadre.jsx";
import Icone, { Logo } from "../ui/Icone.jsx";
import Contenu from "./Contenu.jsx";
import Eleves from "./Eleves.jsx";
import Exercices from "./Exercices.jsx";
import Journal from "./Journal.jsx";
import Professeurs from "./Professeurs.jsx";
import RessourcesAdmin from "./RessourcesAdmin.jsx";
import TableauDeBord from "./TableauDeBord.jsx";

const CLE_COMPTE = "pkp.admin";

const PAGES = [
  { vers: "/admin", libelle: "Tableau de bord", icone: "tableau", Page: TableauDeBord },
  { vers: "/admin/professeurs", libelle: "Professeurs", icone: "professeurs", Page: Professeurs },
  { vers: "/admin/eleves", libelle: "Élèves et classes", icone: "classes", Page: Eleves },
  { vers: "/admin/cours", libelle: "Cours", icone: "cours", Page: Contenu },
  { vers: "/admin/exercices", libelle: "Exercices", icone: "exercices", Page: Exercices },
  { vers: "/admin/ressources", libelle: "Ressources", icone: "ressources", Page: RessourcesAdmin },
  { vers: "/admin/journal", libelle: "Journal", icone: "journal", Page: Journal },
];

/** Espace administrateur (module 1) : session de 30 minutes, second facteur en production. */
export default function EspaceAdmin({ chemin = "/admin" }) {
  const [compte, setCompte] = useState(() => lire(CLE_COMPTE));

  function connecter(nouveau) {
    const avecExpiration = { ...nouveau, expire_le: Date.now() + nouveau.expire_dans_min * 60_000 };
    ecrire(CLE_COMPTE, avecExpiration);
    setCompte(avecExpiration);
  }

  function deconnecter() {
    ecrire(CLE_COMPTE, null);
    setCompte(null);
  }

  if (!compte || compte.expire_le < Date.now()) return <ConnexionAdmin onConnexion={connecter} expiree={!!compte} />;

  const page = PAGES.filter((p) => chemin === p.vers || chemin.startsWith(`${p.vers}/`)).sort(
    (a, b) => b.vers.length - a.vers.length,
  )[0] ?? PAGES[0];
  const { Page } = page;

  return (
    <CadreApplication
      espace="Administration"
      liens={PAGES}
      cheminActif={chemin}
      pied={
        <>
          <div className="compte">{compte.nom}</div>
          <a href="/enseignant">
            <Icone nom="classes" /> Espace professeur
          </a>
          <button className="nav" onClick={deconnecter}>
            <Icone nom="sortie" /> Se déconnecter
          </button>
        </>
      }
    >
      <EntetePage titre={page.libelle} fil="Administration" />
      <Page jeton={compte.jeton} onExpire={deconnecter} chemin={chemin} />
    </CadreApplication>
  );
}

function ConnexionAdmin({ onConnexion, expiree }) {
  const [email, setEmail] = useState("");
  const [motDePasse, setMotDePasse] = useState("");
  const [code, setCode] = useState("");
  const [erreur, setErreur] = useState(expiree ? "Session expirée : reconnectez-vous." : null);
  const [envoi, setEnvoi] = useState(false);

  async function soumettre(e) {
    e.preventDefault();
    setErreur(null);
    setEnvoi(true);
    try {
      onConnexion(
        await api("/admin/connexion", {
          methode: "POST",
          corps: { email, mot_de_passe: motDePasse, code_totp: code.trim() || null },
        }),
      );
    } catch (err) {
      setErreur(err.message);
      setCode("");
    } finally {
      setEnvoi(false);
    }
  }

  return (
    <div className="page">
      <header className="entete">
        <Logo />
        <nav aria-label="Espaces">
          <a href="/enseignant">Espace professeur</a>
        </nav>
      </header>
      <form className="carte carte-etroite" onSubmit={soumettre}>
        <h1>
          <Icone nom="bouclier" taille={24} /> Administration
        </h1>
        <p className="doux">Accès réservé à l'équipe PKP. Toutes les actions sont journalisées.</p>
        <label htmlFor="a-email">Email</label>
        <input id="a-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" required />
        <label htmlFor="a-mdp">Mot de passe</label>
        <input
          id="a-mdp"
          type="password"
          value={motDePasse}
          onChange={(e) => setMotDePasse(e.target.value)}
          autoComplete="current-password"
          required
        />
        <label htmlFor="a-code">Code de l'application d'authentification</label>
        <input
          id="a-code"
          inputMode="numeric"
          autoComplete="one-time-code"
          pattern="[0-9 ]{6,7}"
          maxLength={7}
          placeholder="123 456"
          value={code}
          onChange={(e) => setCode(e.target.value)}
        />
        <p className="aide">Obligatoire en production. Session de 30 minutes.</p>
        <Erreur message={erreur} />
        <div className="actions">
          <button type="submit" disabled={envoi}>
            {envoi ? "Connexion…" : "Se connecter"}
          </button>
        </div>
      </form>
    </div>
  );
}
