import { useState } from "react";
import { AccesReserve, CLE_COMPTE, ConnexionEnseignant, NouveauMotDePasse, PageSimple } from "../enseignant/EspaceEnseignant.jsx";
import { ecrire, lire } from "../stockage.js";
import { CadreApplication, EntetePage } from "../ui/Cadre.jsx";
import Icone from "../ui/Icone.jsx";
import GroupesAnglais from "./GroupesAnglais.jsx";
import SeancesAnglais from "./SeancesAnglais.jsx";

const MARQUE = "Anglais";
const PAGES = [
  { vers: "/anglais", libelle: "Séances 4e et 3e", icone: "cours" },
  { vers: "/anglais/groupes", libelle: "Mes groupes", icone: "classes" },
];

/** Espace PKP Anglais : séparé de l'espace professeur de maths, ouvert aux comptes dont la discipline anglais est cochée. */
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
        <ConnexionEnseignant titre="Connexion PKP Anglais" onConnexion={connecter} />
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
  if (!compte.enseigne_anglais) {
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

  const page = PAGES.find((p) => p.vers !== "/anglais" && (chemin === p.vers || chemin.startsWith(`${p.vers}/`))) ?? PAGES[0];

  return (
    <CadreApplication
      espace="PKP Anglais"
      marque={MARQUE}
      liens={PAGES}
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
      <EntetePage titre={page.libelle} fil="PKP Anglais" />
      {page.vers === "/anglais/groupes" ? (
        <GroupesAnglais jeton={compte.jeton} onExpire={deconnecter} />
      ) : (
        <SeancesAnglais jeton={compte.jeton} onExpire={deconnecter} />
      )}
    </CadreApplication>
  );
}
