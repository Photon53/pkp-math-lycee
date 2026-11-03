import Icone from "./ui/Icone.jsx";

/** Page d'accueil publique : la plateforme PKP Éducation, ses matières, puis le choix de l'espace. */
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

      <section aria-labelledby="titre-matieres">
        <h2 id="titre-matieres">Les matières</h2>
        <div className="matieres">
          <div className="carte">
            <span className="badge">Seconde · Première · Terminale</span>
            <h3>
              PKP <em>Maths</em>
            </h3>
            <p className="doux">
              Tout le programme du lycée, chapitre par chapitre : leçons, méthodes, exercices corrigés et entraînement adapté au niveau de
              chaque élève.
            </p>
          </div>
          <div className="carte">
            <span className="badge">4e · 3e</span>
            <h3>
              PKP <em>Anglais</em>
            </h3>
            <p className="doux">
              Des séances de 90 minutes, une par objectif du programme : compréhension, expression orale et écrite, avec un pack élève et un
              pack animateur.
            </p>
          </div>
        </div>
      </section>

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
