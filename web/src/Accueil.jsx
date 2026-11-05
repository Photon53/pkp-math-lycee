import { useEffect, useState } from "react";
import { api } from "./api.js";
import { DOMAINES_PAR_DEFAUT, ETATS, repartirParcours } from "./parcoursPublics.js";
import Icone from "./ui/Icone.jsx";

/** Titre d'un parcours : « PKP Maths », puis le cycle. */
function TitreParcours({ domaine }) {
  return (
    <h4>
      PKP <em>{domaine.matiereLisible}</em> <span className="parcours-cycle">{domaine.cycleLisible}</span>
    </h4>
  );
}

/** Les parcours prêts puis les chantiers ; l'état suit les réglages des domaines, avec un repli statique hors ligne. */
function Parcours() {
  const [domaines, setDomaines] = useState(DOMAINES_PAR_DEFAUT);
  useEffect(() => {
    let actif = true;
    api("/domaines/publics")
      .then((liste) => {
        if (actif && Array.isArray(liste) && liste.length) setDomaines(liste);
      })
      .catch(() => {}); // l'API ne répond pas : on garde l'état connu
    return () => {
      actif = false;
    };
  }, []);
  const { prets, chantiers } = repartirParcours(domaines);

  return (
    <section aria-labelledby="titre-parcours" className="accueil-parcours">
      <h2 id="titre-parcours">Les parcours</h2>

      <h3 id="titre-prets">Prêts : ouverts aux élèves</h3>
      <ul className="matieres" aria-labelledby="titre-prets">
        {prets.map((d) => (
          <li key={d.code} className="carte parcours-pret">
            <div className="parcours-entete">
              <span className="badge">{d.niveauxLisibles}</span>
              <span className="etat-parcours etat-ouvert">
                <span className="pastille" aria-hidden="true" />
                {ETATS.ouvert.libelle}
              </span>
            </div>
            <TitreParcours domaine={d} />
            {d.description && <p className="doux">{d.description}</p>}
          </li>
        ))}
      </ul>

      {chantiers.length > 0 && (
        <>
          <h3 id="titre-chantiers">En chantier</h3>
          <p className="doux parcours-intro">
            Ces parcours sont en construction. Ils ouvriront dès que leurs cours et exercices auront été rédigés et validés par des
            professeurs.
          </p>
          <ul className="matieres chantiers" aria-labelledby="titre-chantiers">
            {chantiers.map((d) => (
              <li key={d.code} className="carte parcours-chantier">
                <div className="parcours-entete">
                  <span className="badge neutre">{d.niveauxLisibles}</span>
                  <span className={`etat-parcours etat-${d.etat}`} title={ETATS[d.etat].detail}>
                    <span className="pastille" aria-hidden="true" />
                    {ETATS[d.etat].libelle}
                  </span>
                </div>
                <TitreParcours domaine={d} />
                <p className="doux">{ETATS[d.etat].detail}.</p>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

/** Page d'accueil publique : la plateforme PKP Éducation, ses parcours (prêts ou en chantier), puis le choix de l'espace. */
export default function Accueil() {
  return (
    <>
      <section className="accueil-hero">
        <span className="badge accent">Collège · Lycée</span>
        <h1>Comprendre, progresser, prendre confiance !</h1>
        <p>
          <strong>PKP Éducation accompagne chaque élève pour apprendre à son rythme, comprendre les méthodes et développer son raisonnement.</strong>{" "}
          Des cours structurés, des exemples corrigés et des exercices progressifs, préparés et validés par des professeurs, pour avancer
          étape par étape vers l'autonomie.
        </p>
        <p>
          <strong>On ne réussit pas parce qu'on est né fort : on progresse en comprenant, en pratiquant et en persévérant.</strong>
        </p>
        <div className="actions">
          <a className="bouton" href="/methode">
            Découvrir la méthode PKP
          </a>
        </div>
      </section>

      <Parcours />

      <section aria-labelledby="titre-espaces">
        <h2 id="titre-espaces">Accéder à mon espace</h2>
        <div className="choix-espace">
          <a href="/eleve">
            <Icone nom="eleve" taille={32} />
            <strong>Élève — Maths</strong>
            <span className="doux">Connexion avec le code de ma classe, mon prénom et mon code personnel.</span>
          </a>
          <a href="/anglais/eleve">
            <Icone nom="eleve" taille={32} />
            <strong>Élève — Anglais</strong>
            <span className="doux">Connexion avec l'identifiant et le code personnel de ma carte d'anglais.</span>
          </a>
          <a href="/parent">
            <Icone nom="professeurs" taille={32} />
            <strong>Parent</strong>
            <span className="doux">Suivre le travail de mon enfant et choisir son code de connexion. Compte créé par son professeur.</span>
          </a>
          <a href="/enseignant">
            <Icone nom="classes" taille={32} />
            <strong>Professeur — Maths</strong>
            <span className="doux">Mes classes, le suivi de mes élèves, les cours et les ressources.</span>
          </a>
          <a href="/anglais">
            <Icone nom="cours" taille={32} />
            <strong>Professeur — Anglais</strong>
            <span className="doux">Mes groupes, les séances de 4e et de 3e, les packs PDF élève et animateur.</span>
          </a>
        </div>
      </section>

      <p className="accroche">Comprendre aujourd'hui, réussir demain !</p>
    </>
  );
}
