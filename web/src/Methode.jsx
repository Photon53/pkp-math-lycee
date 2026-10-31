import { Maths } from "./maths.jsx";

/** Les cinq étapes de la méthode PKP, et où l'élève les trouve dans chaque leçon. */
export const ETAPES = [
  {
    cle: "comprendre",
    titre: "Je comprends",
    dans: "Objectifs et cours structuré de chaque leçon.",
    critere: "Je sais expliquer la notion avec mes propres mots et reconnaitre ce qu'on me demande.",
  },
  {
    cle: "memoriser",
    titre: "Je mémorise",
    dans: "« L'essentiel », les méthodes avec exemple résolu, l'encadré « Attention à… ».",
    critere: "Ma fiche contient les définitions, propriétés, formules, un exemple résolu et les erreurs classiques.",
  },
  {
    cle: "entrainer",
    titre: "Je m'entraîne",
    dans: "Exercices des niveaux 1 à 3, avec la réponse attendue et la partie du cours à utiliser.",
    critere: "J'applique une méthode connue, puis je gagne en autonomie.",
  },
  {
    cle: "depasser",
    titre: "Je me dépasse",
    dans: "Exercices des niveaux 4 et 5 : synthèse et problèmes.",
    critere: "Je choisis une méthode, je combine plusieurs notions, je cherche une solution.",
  },
  {
    cle: "verifier",
    titre: "Je vérifie",
    dans: "Ma maîtrise de la compétence et mon historique.",
    critere: "Je contrôle mes résultats, j'identifie mes erreurs et je retravaille ce qui n'est pas acquis.",
  },
];

const GESTES = [
  {
    titre: "Lire un énoncé",
    quoi: "Identifier les données, la question et les contraintes.",
    exemple: "« $x$ est un réel strictement positif » : la contrainte $x > 0$ servira pour le logarithme ou une racine.",
  },
  {
    titre: "Reformuler",
    quoi: "Dire avec ses mots ce qu'il faut trouver ou démontrer.",
    exemple: "« Résoudre $f(x) > 0$ » devient : « pour quelles valeurs de $x$ la courbe est-elle au-dessus de l'axe des abscisses ? »",
  },
  {
    titre: "Représenter",
    quoi: "Choisir le bon support : schéma, tableau, courbe ou arbre.",
    exemple: "Une expérience en deux étapes se lit sur un arbre ; un signe se lit dans un tableau de signes ; une fonction sur sa courbe.",
  },
  {
    titre: "Identifier une méthode",
    quoi: "Reconnaitre la propriété ou l'outil qui s'applique.",
    exemple: "Un produit égal à zéro appelle « produit nul » ; une somme et un produit de racines connus appellent $x^2 - sx + p$.",
  },
  {
    titre: "Commencer simplement",
    quoi: "Tester un exemple ou un cas particulier pour comprendre.",
    exemple: "Avant de démontrer que $n^2 + n$ est pair, tester $n = 1, 2, 3$ : $2$, $6$, $12$.",
  },
  {
    titre: "Rédiger",
    quoi: "Justifier chaque étape et structurer la réponse.",
    exemple: "« Comme $\\Delta = 25 > 0$, l'équation admet deux solutions : … » plutôt qu'une suite de calculs sans phrase.",
  },
  {
    titre: "Vérifier",
    quoi: "Contrôler le résultat, les signes, les unités et la cohérence.",
    exemple: "Une probabilité doit être entre $0$ et $1$ ; une racine trouvée se remplace dans l'équation pour la contrôler.",
  },
  {
    titre: "Analyser ses erreurs",
    quoi: "Comprendre pourquoi une réponse est fausse et comment la corriger.",
    exemple: "Noter dans un carnet : « j'ai écrit $-3^2 = 9$ ; il fallait $(-3)^2 = 9$ et $-3^2 = -9$ ».",
  },
  {
    titre: "Réviser activement",
    quoi: "Se tester sans regarder le cours, et revoir les notions à intervalles réguliers.",
    exemple: "Cours fermé, réécrire la formule du discriminant et un exemple, puis comparer avec « L'essentiel ».",
  },
  {
    titre: "Persévérer intelligemment",
    quoi: "Décomposer un problème et demander de l'aide sur un point précis.",
    exemple: "« Je sais calculer $\\Delta$ mais je ne sais pas conclure quand $\\Delta < 0$ » est une question à laquelle on peut répondre.",
  },
];

export default function Methode() {
  return (
    <>
      <section className="accueil-hero">
        <span className="badge accent">La méthode PKP</span>
        <h1>Apprendre les mathématiques, étape par étape.</h1>
        <p>
          On ne réussit pas en mathématiques parce qu'on est né fort : on progresse en comprenant, en pratiquant et en
          persévérant. La méthode PKP est la même dans chaque chapitre, pour que tu saches toujours quoi faire ensuite.
        </p>
      </section>

      <section className="carte" aria-labelledby="titre-etapes">
        <h2 id="titre-etapes">Les cinq étapes</h2>
        <ol className="etapes-methode">
          {ETAPES.map((e, i) => (
            <li key={e.cle}>
              <span className="numero" aria-hidden="true">
                {i + 1}
              </span>
              <div>
                <strong>{e.titre}</strong>
                <p className="doux">Dans PKP : {e.dans}</p>
                <p>{e.critere}</p>
              </div>
            </li>
          ))}
        </ol>
        <p className="aide">
          Dans chaque leçon, ces étapes apparaissent en haut de page, avec ton avancement et un bouton pour passer à la suivante.
        </p>
      </section>

      <section className="carte" aria-labelledby="titre-gestes">
        <h2 id="titre-gestes">Les dix gestes mathématiques</h2>
        <p className="doux">Des réflexes à prendre devant chaque exercice, illustrés par un exemple.</p>
        <div className="tableau-defilant">
          <table>
            <thead>
              <tr>
                <th>Geste</th>
                <th>Ce que tu apprends à faire</th>
                <th>Exemple</th>
              </tr>
            </thead>
            <tbody>
              {GESTES.map((g, i) => (
                <tr key={g.titre}>
                  <td>
                    <strong>
                      {i + 1}. {g.titre}
                    </strong>
                  </td>
                  <td>{g.quoi}</td>
                  <td>
                    <Maths texte={g.exemple} enLigne />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="carte" aria-labelledby="titre-memoire">
        <h2 id="titre-memoire">Retenir dans la durée</h2>
        <ul>
          <li>
            <strong>Récupération active :</strong> ferme le cours et essaie de retrouver une définition, une formule ou une
            méthode de mémoire. Ce qui revient difficilement est ce qu'il faut retravailler.
          </li>
          <li>
            <strong>Révision espacée :</strong> revois une notion plusieurs fois, avec des intervalles de plus en plus longs,
            par exemple le lendemain, puis 3 jours, 7 jours et un mois après. Ce sont des repères, pas une règle.
          </li>
          <li>
            <strong>Carnet d'erreurs :</strong> pour chaque erreur, note ce que tu as fait, pourquoi c'était faux, la bonne
            méthode, et refais un exercice semblable deux jours plus tard sans regarder la correction.
          </li>
        </ul>
        <div className="actions">
          <a className="bouton" href="/eleve">
            Commencer à m'entraîner
          </a>
        </div>
      </section>
    </>
  );
}
