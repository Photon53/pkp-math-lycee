import { lazy, Suspense, useEffect, useState } from "react";
import { api } from "./api.js";
import { DOMAINES_PAR_DEFAUT, ETATS, repartirParcours } from "./parcoursPublics.js";
import Icone from "./ui/Icone.jsx";

// KaTeX n'est chargé que pour la question d'essai, pas pour le reste de l'accueil.
const ExempleQuestion = lazy(() => import("./ExempleQuestion.jsx"));

/** Lit une route publique de l'accueil ; garde `initial` si l'API ne répond pas. */
function useDonneePublique(chemin, initial, valide) {
  const [valeur, setValeur] = useState(initial);
  useEffect(() => {
    let actif = true;
    api(chemin)
      .then((v) => {
        if (actif && valide(v)) setValeur(v);
      })
      .catch(() => {}); // hors ligne : on garde l'état connu
    return () => {
      actif = false;
    };
  }, [chemin]); // eslint-disable-line react-hooks/exhaustive-deps
  return valeur;
}

// --- Choix de l'espace, par profil -------------------------------------------------------------

/** Lien d'espace : le profil, invisible à l'écran, reste dans le nom lu par un lecteur d'écran. */
function LienEspace({ href, profil, children, secondaire = false }) {
  return (
    <a className={`bouton${secondaire ? " secondaire" : ""}`} href={href}>
      <span className="visuellement-cache">{profil} — </span>
      {children}
    </a>
  );
}

function Profils() {
  return (
    <section aria-labelledby="titre-espaces" className="accueil-profils">
      <h2 id="titre-espaces">Accéder à mon espace</h2>
      <ul className="profils">
        <li className="carte profil">
          <Icone nom="eleve" taille={32} />
          <h3>Je suis élève</h3>
          <p>Avance à ton rythme : des leçons claires, des exercices corrigés pas à pas et un entraînement adapté à ton niveau.</p>
          <div className="profil-liens">
            <LienEspace href="/eleve" profil="Élève">
              Maths
            </LienEspace>
            <LienEspace href="/anglais/eleve" profil="Élève" secondaire>
              Anglais
            </LienEspace>
          </div>
          <p className="doux profil-aide">Tu te connectes avec le code que t'a donné ton professeur.</p>
        </li>
        <li className="carte profil">
          <Icone nom="professeurs" taille={32} />
          <h3>Je suis parent</h3>
          <p>Suivez les progrès de votre enfant, son travail et ses réussites, depuis un téléphone ou un ordinateur.</p>
          <div className="profil-liens">
            <LienEspace href="/parent" profil="Parent">
              Espace parent
            </LienEspace>
          </div>
          <p className="doux profil-aide">Votre accès vous est remis par le professeur de votre enfant.</p>
        </li>
        <li className="carte profil">
          <Icone nom="classes" taille={32} />
          <h3>Je suis professeur</h3>
          <p>Des séances prêtes à l'emploi, des contenus relus par des collègues et le suivi de vos classes en un coup d'œil.</p>
          <div className="profil-liens">
            <LienEspace href="/enseignant" profil="Professeur">
              Maths
            </LienEspace>
            <LienEspace href="/anglais" profil="Professeur" secondaire>
              Anglais
            </LienEspace>
          </div>
          <p className="doux profil-aide">Classes, groupes, séances, packs PDF et ressources.</p>
        </li>
      </ul>
    </section>
  );
}

// --- Chiffres clés -----------------------------------------------------------------------------

// Espace insécable normale entre les milliers : l'espace fine de fr-FR est presque invisible à l'écran.
const nombre = (n) => n.toLocaleString("fr-FR").replace(/ /g, " ");

function Chiffres() {
  const chiffres = useDonneePublique("/domaines/chiffres", null, (c) => c && typeof c.questions === "number");
  const elements = [
    chiffres?.questions > 0 && { valeur: nombre(chiffres.questions), texte: "questions corrigées en maths" },
    chiffres?.chapitres > 0 && { valeur: nombre(chiffres.chapitres), texte: "chapitres du programme" },
    chiffres?.seances_anglais > 0 && { valeur: nombre(chiffres.seances_anglais), texte: "séances d'anglais de 90 minutes" },
    { valeur: "Par des profs", texte: "chaque cours et chaque exercice, écrits et relus par des professeurs" },
  ].filter(Boolean);
  return (
    <section aria-labelledby="titre-chiffres">
      <h2 id="titre-chiffres" className="visuellement-cache">
        En quelques chiffres
      </h2>
      <ul className="chiffres-cles">
        {elements.map((e) => (
          <li key={e.texte}>
            <strong>{e.valeur}</strong> <span>{e.texte}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

// --- Comment ça marche --------------------------------------------------------------------------

function Etapes() {
  return (
    <section aria-labelledby="titre-etapes">
      <h2 id="titre-etapes">Comment ça marche</h2>
      <ol className="etapes-accueil">
        <li>
          <h3>Le professeur crée sa classe</h3>
          <p className="doux">Il choisit les chapitres ou les séances, et remet à chaque élève son code de connexion.</p>
        </li>
        <li>
          <h3>L'élève s'entraîne</h3>
          <p className="doux">Leçons, méthodes et exercices progressifs : chaque erreur est expliquée, chaque réussite compte.</p>
        </li>
        <li>
          <h3>Le parent suit les progrès</h3>
          <p className="doux">Il voit le travail fait, les notions acquises et celles à revoir, sans rien installer.</p>
        </li>
      </ol>
    </section>
  );
}

// --- Parcours prêts et en chantier ---------------------------------------------------------------

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
  const domaines = useDonneePublique("/domaines/publics", DOMAINES_PAR_DEFAUT, (l) => Array.isArray(l) && l.length > 0);
  const { prets, chantiers } = repartirParcours(domaines);

  return (
    <section aria-labelledby="titre-parcours" className="accueil-parcours">
      <h2 id="titre-parcours">Les parcours</h2>

      <h3 id="titre-prets">Prêts : ouverts aux élèves</h3>
      <ul className="matieres" aria-labelledby="titre-prets">
        {prets.map((d) => (
          <li key={d.code} className={`carte parcours-pret matiere-${d.matiere}`}>
            <div className="parcours-entete">
              <span className="badge">{d.niveauxLisibles}</span>
              <span className="etat-parcours etat-ouvert">
                <span className="point-etat" aria-hidden="true" />
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
              <li key={d.code} className={`carte parcours-chantier matiere-${d.matiere}`}>
                <div className="parcours-entete">
                  <span className="badge neutre">{d.niveauxLisibles}</span>
                  <span className={`etat-parcours etat-${d.etat}`} title={ETATS[d.etat].detail}>
                    <span className="point-etat" aria-hidden="true" />
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

// --- Questions fréquentes ------------------------------------------------------------------------

// `masquee` : réponse rédigée mais retirée de la page pour l'instant (choix du professeur, bêta).
const FAQ = [
  {
    masquee: true,
    question: "Quelles données sont enregistrées sur mon enfant ?",
    reponse:
      "Uniquement son prénom et sa classe : ni nom de famille, ni adresse e-mail, ni date de naissance. Son code personnel est " +
      "enregistré sous une forme illisible (haché). Le site n'utilise aucun traceur publicitaire, et les comptes restés inactifs " +
      "longtemps sont supprimés automatiquement.",
  },
  {
    question: "Que voit le parent dans son espace ?",
    reponse:
      "Le travail de son enfant : les séances faites, les notions acquises, celles à revoir et le temps passé. Un parent ne voit " +
      "que ses propres enfants.",
  },
  {
    question: "Faut-il installer une application ?",
    reponse:
      "Non. PKP Éducation s'utilise dans le navigateur d'un téléphone, d'une tablette ou d'un ordinateur. Fermer l'onglet " +
      "déconnecte, pratique sur un poste partagé.",
  },
  {
    masquee: true,
    question: "Qui prépare les cours et les exercices ?",
    reponse:
      "Des professeurs. Les questions sont relues et validées au fil de la bêta par l'équipe pédagogique, et les parcours " +
      "en chantier n'ouvrent qu'une fois leur contenu prêt.",
  },
];

function QuestionsFrequentes() {
  return (
    <section aria-labelledby="titre-faq">
      <h2 id="titre-faq">Questions fréquentes</h2>
      <div className="faq">
        {FAQ.filter((f) => !f.masquee).map((f) => (
          <details key={f.question}>
            <summary>{f.question}</summary>
            <p>{f.reponse}</p>
          </details>
        ))}
      </div>
    </section>
  );
}

// --- Page ---------------------------------------------------------------------------------------

/** Page d'accueil publique : une entrée par profil, le fonctionnement, un essai, les parcours, puis les questions fréquentes. */
export default function Accueil() {
  return (
    <div className="accueil">
      <section className="accueil-hero">
        <span className="badge accent">Collège · Lycée</span>
        <h1>Comprendre, progresser, prendre confiance !</h1>
        <p>
          <strong>Des cours clairs, des exercices corrigés pas à pas et un entraînement à ton rythme</strong>, préparés et relus par des
          professeurs.
        </p>
        <div className="actions">
          <a className="bouton" href="#titre-exemple">
            Essayer une question
          </a>
          <a className="bouton secondaire" href="/methode">
            Découvrir la méthode PKP
          </a>
        </div>
      </section>

      <Profils />
      <Chiffres />
      <Etapes />

      <section aria-labelledby="titre-exemple" className="accueil-exemple">
        <h2 id="titre-exemple">Essaie une question</h2>
        <p className="doux">Sans compte et sans rien enregistrer : choisis ta réponse, puis découvre la correction détaillée.</p>
        <Suspense fallback={<p className="doux">Chargement de la question…</p>}>
          <ExempleQuestion />
        </Suspense>
      </section>

      <Parcours />
      <QuestionsFrequentes />

      <p className="accroche">
        On ne réussit pas parce qu'on est né fort : on progresse en comprenant, en pratiquant et en persévérant.
        <br />
        Comprendre aujourd'hui, réussir demain !
      </p>
    </div>
  );
}
