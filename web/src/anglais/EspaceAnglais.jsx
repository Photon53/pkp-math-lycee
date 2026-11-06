import { useState } from "react";
import { AccesReserve, CLE_COMPTE, ConnexionEnseignant, NouveauMotDePasse, PageSimple } from "../enseignant/EspaceEnseignant.jsx";
import { ecrire, lire } from "../stockage.js";
import { CadreApplication, EntetePage } from "../ui/Cadre.jsx";
import Icone from "../ui/Icone.jsx";
import GroupesAnglais from "./GroupesAnglais.jsx";
import SeancesAnglais from "./SeancesAnglais.jsx";
import ValidationAnglais from "./ValidationAnglais.jsx";

const MARQUE = "Anglais";
const PAGES = [
  { vers: "/anglais", libelle: "Séances 4e et 3e", icone: "cours" },
  { vers: "/anglais/groupes", libelle: "Mes groupes", icone: "classes" },
];
// Ouverte aux validateurs qualifiés en anglais, qu'ils y enseignent ou non (EX.9-bis) ; l'API le revérifie.
const VALIDATION = { vers: "/anglais/validation", libelle: "Validation", icone: "bouclier" };

/** Espace PKP Anglais : séparé de l'espace professeur de maths, ouvert aux professeurs d'anglais et, pour la seule
 * page Validation, aux validateurs d'anglais qui n'y enseignent pas. */
export default function EspaceAnglais({ chemin = "/anglais" }) {
  const [compte, setCompte] = useState(() => lire(CLE_COMPTE));

  function connecter(nouveau) {
    ecrire(CLE_COMPTE, nouveau);
    setCompte(nouveau);
  }

  function deconnecter() {
    ecrire(CLE_COMPTE, null);
    setCompte(null);
  }

  if (!compte) {
    return (
      <PageSimple marque={MARQUE}>
        <ConnexionEnseignant titre="Connexion Boussole Anglais" onConnexion={connecter} />
      </PageSimple>
    );
  }
  if (compte.mdp_provisoire) {
    return (
      <PageSimple marque={MARQUE}>
        <NouveauMotDePasse compte={compte} onChange={connecter} onAnnuler={deconnecter} retour="/anglais" />
      </PageSimple>
    );
  }
  if (!compte.enseigne_anglais && !compte.referent_anglais) {
    return (
      <PageSimple marque={MARQUE}>
        <AccesReserve
          titre="Espace réservé aux professeurs d'anglais"
          compte={compte}
          autreEspace={compte.enseigne_maths !== false && { vers: "/enseignant", libelle: "Aller à l'espace professeur" }}
          onDeconnexion={deconnecter}
        />
      </PageSimple>
    );
  }

  const pages = compte.enseigne_anglais ? (compte.referent_anglais ? [...PAGES, VALIDATION] : PAGES) : [VALIDATION];
  const page =
    pages.find((p) => p.vers !== "/anglais" && (chemin === p.vers || chemin.startsWith(`${p.vers}/`))) ?? pages[0];

  return (
    <CadreApplication
      espace="Boussole Anglais"
      marque={MARQUE}
      liens={pages}
      cheminActif={chemin}
      pied={
        <>
          <div className="compte">{compte.nom}</div>
          {compte.enseigne_maths !== false && (
            <a href="/enseignant">
              <Icone nom="classes" /> Espace professeur de maths
            </a>
          )}
          <button className="nav" onClick={deconnecter}>
            <Icone nom="sortie" /> Se déconnecter
          </button>
        </>
      }
    >
      <EntetePage titre={page.libelle} fil="Boussole Anglais" />
      {page.vers === "/anglais/groupes" ? (
        <GroupesAnglais jeton={compte.jeton} onExpire={deconnecter} />
      ) : page.vers === "/anglais/validation" ? (
        <ValidationAnglais jeton={compte.jeton} onExpire={deconnecter} />
      ) : (
        <SeancesAnglais jeton={compte.jeton} onExpire={deconnecter} />
      )}
    </CadreApplication>
  );
}
