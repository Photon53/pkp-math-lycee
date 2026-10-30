import Icone from "./ui/Icone.jsx";

/** Page d'accueil publique (EA6.10) : présentation et choix de l'espace. */
export default function Accueil() {
  return (
    <>
      <section className="accueil-hero">
        <span className="badge accent">Seconde · Première · Terminale</span>
        <h1>Les mathématiques du lycée, à son rythme.</h1>
        <p>
          Des exercices corrigés instantanément, choisis selon ce que chaque élève maîtrise déjà, et des cours
          clairs pour revoir l'essentiel. Le professeur suit sa classe compétence par compétence.
        </p>
      </section>

      <div className="choix-espace">
        <a href="/eleve">
          <Icone nom="eleve" taille={32} />
          <strong>Je suis élève</strong>
          <span className="doux">Connexion avec le code de ma classe, mon prénom et mon code personnel.</span>
        </a>
        <a href="/enseignant">
          <Icone nom="classes" taille={32} />
          <strong>Je suis professeur</strong>
          <span className="doux">Mes classes, le suivi de mes élèves, les cours et les ressources.</span>
        </a>
      </div>

      <section className="atouts" aria-label="Points forts">
        <div>
          <strong>Correction immédiate</strong>
          <span className="doux">
            Fractions, racines, expressions : la valeur compte, pas l'écriture.
          </span>
        </div>
        <div>
          <strong>Progression adaptée</strong>
          <span className="doux">Les questions suivent la maîtrise de chaque compétence.</span>
        </div>
        <div>
          <strong>Respect des élèves</strong>
          <span className="doux">Prénom seul, aucune publicité, données supprimées après un an d'inactivité.</span>
        </div>
      </section>
    </>
  );
}
