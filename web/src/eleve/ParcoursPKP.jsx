import { useEffect, useState } from "react";
import { api } from "../api.js";
import { ETAPES } from "../Methode.jsx";

const NIVEAUX_BASES = { min: 1, max: 3 };
const NIVEAUX_AVANCES = { min: 4, max: 5 };

function aller(id) {
  document.getElementById(id)?.scrollIntoView?.({ behavior: "smooth", block: "start" });
}

/**
 * Les cinq étapes de la méthode PKP pour la compétence d'une leçon : avancement de l'élève
 * et action de chaque étape. L'étape suivante à travailler est mise en avant.
 */
export default function ParcoursPKP({ competenceId, libelle, jeton, onEntrainer, onVoirHistorique }) {
  const [av, setAv] = useState(null);

  useEffect(() => {
    let actif = true;
    api(`/eleves/moi/competences/${competenceId}/avancement`, { jeton }).then(
      (a) => actif && setAv(a),
      () => actif && setAv(null),
    );
    return () => {
      actif = false;
    };
  }, [competenceId, jeton]);

  const bases = av && av.reussies_bases >= av.objectif_bases;
  const avancees = av && av.reussies_avancees >= av.objectif_avancees;
  const acquis = { entrainer: bases, depasser: avancees, verifier: av?.maitrisee };
  const suivante = !bases ? "entrainer" : !avancees ? "depasser" : !av?.maitrisee ? "verifier" : null;

  const details = {
    comprendre: { action: "Lire le cours", faire: () => aller("lecon-cours") },
    memoriser: { action: "Ma fiche", faire: () => aller("lecon-fiche") },
    entrainer: {
      etat: av && `${Math.min(av.reussies_bases, av.objectif_bases)} / ${av.objectif_bases} réussies (niveaux 1 à 3)`,
      action: "S'entraîner",
      faire: () => onEntrainer(competenceId, libelle, NIVEAUX_BASES),
    },
    depasser: {
      etat: av && `${Math.min(av.reussies_avancees, av.objectif_avancees)} / ${av.objectif_avancees} réussies (niveaux 4 et 5)`,
      action: "Me dépasser",
      faire: () => onEntrainer(competenceId, libelle, NIVEAUX_AVANCES),
    },
    verifier: {
      etat: av && `Maîtrise : ${Math.round(av.maitrise * 100)} %${av.maitrisee ? " · acquise" : ""}`,
      action: "Mon historique",
      faire: () => onVoirHistorique(competenceId),
    },
  };

  return (
    <nav className="parcours-pkp" aria-label="Méthode PKP pour cette compétence">
      <ol>
        {ETAPES.map((e, i) => {
          const d = details[e.cle];
          const classe = acquis[e.cle] ? "acquis" : suivante === e.cle ? "suivante" : "";
          return (
            <li key={e.cle} className={classe} aria-current={suivante === e.cle ? "step" : undefined}>
              <span className="titre-etape">
                <span className="numero" aria-hidden="true">
                  {acquis[e.cle] ? "✓" : i + 1}
                </span>
                {e.titre}
              </span>
              {d.etat && <span className="doux">{d.etat}</span>}
              <button className={suivante === e.cle ? "petit" : "secondaire petit"} onClick={d.faire}>
                {d.action}
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
