import Icone from "./ui/Icone.jsx";

/** Page d'accueil publique (EA6.10) : courte, avec le choix de l'espace et la méthode PKP. */
export default function Accueil() {
  return (
    <>
      <section className="accueil-hero">
        <span className="badge accent">Seconde · Première · Terminale</span>
        <h1>Comprendre, progresser, prendre confiance en mathématiques !</h1>
        <p>
          <strong>PKP Math t'accompagne pour apprendre à ton rythme, comprendre les méthodes et développer ton raisonnement.</strong>{" "}
          Grâce à des cours structurés, des exemples corrigés et des exercices progressifs, tu avances étape par étape vers
          l'autonomie.
        </p>
        <p>
          <strong>
            En mathématiques, on ne réussit pas parce qu'on est né fort : on progresse en comprenant, en pratiquant et en
            persévérant.
          </strong>
        </p>
        <div className="actions">
          <a className="bouton" href="/methode">
            Découvrir la méthode PKP
          </a>
        </div>
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

      <p className="accroche">Comprendre aujourd'hui, réussir demain !</p>
    </>
  );
}
