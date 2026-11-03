import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Erreur } from "../composants.jsx";
import { ecrire, lire } from "../stockage.js";
import { CadreApplication, EntetePage } from "../ui/Cadre.jsx";
import Icone, { Logo } from "../ui/Icone.jsx";
import AnglaisAdmin from "./AnglaisAdmin.jsx";
import BandeauAdmin, { libelleDomaine } from "./BandeauAdmin.jsx";
import Configuration from "./Configuration.jsx";
import Contenu from "./Contenu.jsx";
import Eleves from "./Eleves.jsx";
import Exercices from "./Exercices.jsx";
import Familles from "./Familles.jsx";
import Journal from "./Journal.jsx";
import Professeurs from "./Professeurs.jsx";
import RessourcesAdmin from "./RessourcesAdmin.jsx";
import { DOMAINES_PAR_DEFAUT } from "./Qualifications.jsx";
import TableauDeBord from "./TableauDeBord.jsx";

const CLE_COMPTE = "pkp.admin";
const CLE_DOMAINE = "pkp.admin.domaine";

// Quatre espaces (CDC V2, § 6.1) : piloter, gérer les comptes, produire le contenu, configurer.
// `permission` : chaque page n'apparaît qu'aux comptes qui l'ont (EX.7, EA.3) ; l'API la revérifie.
const PAGES = [
  { groupe: "Pilotage", vers: "/admin", libelle: "Tableau de bord", icone: "tableau", Page: TableauDeBord, permission: "pilotage.global" },
  { groupe: "Pilotage", vers: "/admin/journal", libelle: "Journal", icone: "journal", Page: Journal, permission: "pilotage.global" },
  { groupe: "Comptes", vers: "/admin/professeurs", libelle: "Équipe", icone: "professeurs", Page: Professeurs, permission: "comptes.gerer" },
  { groupe: "Comptes", vers: "/admin/familles", libelle: "Familles", icone: "eleve", Page: Familles, permission: "parents.gerer" },
  { groupe: "Comptes", vers: "/admin/eleves", libelle: "Élèves et classes", icone: "classes", Page: Eleves, permission: "comptes.gerer" },
  { groupe: "Pédagogie", vers: "/admin/cours", libelle: "Cours", icone: "cours", Page: Contenu, permission: "contenu.modifier", matiere: "maths" },
  { groupe: "Pédagogie", vers: "/admin/exercices", libelle: "Exercices", icone: "exercices", Page: Exercices, permission: "contenu.modifier", matiere: "maths" },
  { groupe: "Pédagogie", vers: "/admin/ressources", libelle: "Ressources", icone: "ressources", Page: RessourcesAdmin, permission: "contenu.modifier", matiere: "maths" },
  { groupe: "Pédagogie", vers: "/admin/anglais", libelle: "PKP Anglais", icone: "eleve", Page: AnglaisAdmin, permission: "contenu.modifier", matiere: "anglais" },
  { groupe: "Configuration", vers: "/admin/configuration", libelle: "Domaines", icone: "bouclier", Page: Configuration, permission: "configuration" },
];

/** Page propre à une matière (cours de maths, PKP Anglais) consultée avec un domaine d'une autre matière. */
function horsMatiere(page, domaine, domaines) {
  const choisi = domaines.find((d) => d.code === domaine);
  return Boolean(page.matiere && choisi && choisi.matiere !== page.matiere);
}

/** Pages permises : toutes tant que /admin/moi n'a pas répondu (l'API refuse de toute façon ce qui n'est pas permis). */
export const pagesPermises = (permissions) => (permissions ? PAGES.filter((p) => permissions.includes(p.permission)) : PAGES);

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

  // Domaine choisi : mémorisé pour la session de l'onglet, il filtre toutes les listes (recette 5 du lot A).
  const [domaine, setDomaine] = useState(() => lire(CLE_DOMAINE) ?? "");
  const [domaines, setDomaines] = useState(DOMAINES_PAR_DEFAUT);
  const [permissions, setPermissions] = useState(null);
  // Incrémenté à chaque résultat de recherche ouvert : la page se recharge avec le filtre de son adresse.
  const [ouverture, setOuverture] = useState(0);
  const valide = compte && compte.expire_le >= Date.now();
  const jeton = valide ? compte.jeton : null;

  useEffect(() => {
    if (!jeton) return;
    const erreur = (err) => err.status === 401 && deconnecter();
    api("/admin/moi", { jeton }).then((m) => setPermissions(m.permissions ?? null), erreur);
    api("/admin/domaines", { jeton }).then(setDomaines, erreur);
  }, [jeton]);

  function choisirDomaine(code) {
    ecrire(CLE_DOMAINE, code || null);
    setDomaine(code);
  }

  if (!valide) return <ConnexionAdmin onConnexion={connecter} expiree={!!compte} />;

  const liens = pagesPermises(permissions);
  const page = liens.filter((p) => chemin === p.vers || chemin.startsWith(`${p.vers}/`)).sort(
    (a, b) => b.vers.length - a.vers.length,
  )[0] ?? liens[0];

  return (
    <CadreApplication
      espace="Administration"
      liens={liens}
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
      <BandeauAdmin
        jeton={compte.jeton}
        onExpire={deconnecter}
        domaines={domaines}
        domaine={domaine}
        onDomaine={choisirDomaine}
        onOuvrir={() => setOuverture((n) => n + 1)}
      />
      {page ? (
        <>
          <EntetePage titre={page.libelle} fil={`Administration · ${page.groupe}`} />
          {horsMatiere(page, domaine, domaines) && (
            <p className="info note-domaine">
              <span>
                Cet écran gère le contenu {page.matiere === "maths" ? "de mathématiques" : "d'anglais"} :{" "}
                {libelleDomaine(domaines, domaine)} n'y a rien. Choisissez « Tous les domaines » pour tout revoir.
              </span>
            </p>
          )}
          <page.Page
            key={`${page.vers}:${ouverture}`}
            jeton={compte.jeton}
            onExpire={deconnecter}
            chemin={chemin}
            domaine={domaine}
            domaines={domaines}
          />
        </>
      ) : (
        <p className="doux">Votre compte n'a accès à aucun espace de l'administration.</p>
      )}
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
