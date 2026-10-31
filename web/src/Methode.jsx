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

// Exemples variés (algèbre, analyse, géométrie, statistiques, probabilités) : les gestes sont transversaux.
const GESTES = [
  {
    titre: "Lire un énoncé",
    quoi: "Identifier les données, la question et les contraintes.",
    exemples: [
      "« $x$ est un réel strictement positif » : la contrainte $x > 0$ servira pour le logarithme ou une racine.",
      "« Une série de $25$ notes » : l'effectif est impair, la médiane est la $13^e$ valeur rangée.",
    ],
  },
  {
    titre: "Reformuler",
    quoi: "Dire avec ses mots ce qu'il faut trouver ou démontrer.",
    exemples: [
      "« Résoudre $f(x) > 0$ » devient : « pour quelles valeurs de $x$ la courbe est-elle au-dessus de l'axe des abscisses ? »",
      "« Démontrer que $ABC$ est rectangle en $A$ » devient : « montrer que $BC^2 = AB^2 + AC^2$ ».",
    ],
  },
  {
    titre: "Représenter",
    quoi: "Choisir le bon support : figure, tableau, courbe, arbre ou diagramme.",
    exemples: [
      "Une expérience en deux étapes se lit sur un arbre ; un signe dans un tableau de signes ; une fonction sur sa courbe.",
      "Une configuration géométrique se lit sur une figure codée ; une série statistique sur un diagramme en boîte.",
    ],
  },
  {
    titre: "Identifier une méthode",
    quoi: "Reconnaitre la propriété ou l'outil qui s'applique.",
    exemples: [
      "Un produit égal à zéro appelle « produit nul » ; une somme et un produit de racines connus appellent $x^2 - sx + p$.",
      "Montrer que deux droites sont parallèles appelle la colinéarité de vecteurs directeurs.",
    ],
  },
  {
    titre: "Commencer simplement",
    quoi: "Tester un exemple ou un cas particulier pour comprendre.",
    exemples: [
      "Avant d'étudier le nombre de solutions de $x^2 + mx + 4 = 0$ selon $m$, tester $m = 0$ (aucune solution) puis $m = 4$ (une seule : $x = -2$).",
    ],
  },
  {
    titre: "Rédiger",
    quoi: "Justifier chaque étape et structurer la réponse.",
    exemples: [
      "« Comme $\\Delta = 25 > 0$, l'équation admet deux solutions : … » plutôt qu'une suite de calculs sans phrase.",
    ],
  },
  {
    titre: "Vérifier",
    quoi: "Contrôler le résultat, les signes, les unités et la cohérence.",
    exemples: [
      "Une probabilité est entre $0$ et $1$ ; une longueur est positive ; une moyenne est entre la plus petite et la plus grande valeur.",
      "Une racine trouvée se remplace dans l'équation pour la contrôler.",
    ],
  },
  {
    titre: "Analyser ses erreurs",
    quoi: "Comprendre pourquoi une réponse est fausse et comment la corriger.",
    exemples: ["« J'ai écrit $-3^2 = 9$ ; en fait $-3^2 = -9$, alors que $(-3)^2 = 9$. »"],
  },
  {
    titre: "Se tester de mémoire",
    quoi: "Retrouver une notion sans regarder le cours, puis vérifier.",
    exemples: ["Cours fermé, réécrire la formule du discriminant et un exemple, puis comparer avec « L'essentiel »."],
  },
  {
    titre: "Décomposer et demander une aide ciblée",
    quoi: "Découper un problème en sous-étapes, puis formuler une question précise.",
    exemples: [
      "« Je sais calculer $\\Delta$ mais je ne sais pas conclure quand $\\Delta < 0$ » est une question à laquelle on peut répondre.",
    ],
  },
];

/** Ce que l'élève fait à chaque étape, dans l'ordre : le fil conducteur de chaque chapitre. */
const SCHEMA = ["Cours", "Fiche", "Niveaux 1, 2, 3", "Niveaux 4 et 5", "Bilan"];

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
        <p className="accroche citation">Trois ingrédients pour apprendre : du temps, de la concentration, de la persévérance.</p>
      </section>

      <section className="carte" aria-labelledby="titre-etapes">
        <h2 id="titre-etapes">Les cinq étapes</h2>
        <ol className="schema-etapes" aria-label="Le fil d'un chapitre">
          {ETAPES.map((e, i) => (
            <li key={e.cle}>
              <span className="numero">{i + 1}</span>
              <strong>{e.titre}</strong>
              <span className="doux">{SCHEMA[i]}</span>
            </li>
          ))}
        </ol>
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
          Dans chaque leçon, ces étapes apparaissent en haut de page, avec ton avancement. Elles ne sont pas verrouillées :
          tu peux revenir à n'importe laquelle à tout moment, par exemple relire ta fiche après une erreur au niveau 4.
        </p>
      </section>

      <section className="carte" aria-labelledby="titre-gestes">
        <h2 id="titre-gestes">Les dix gestes mathématiques</h2>
        <p className="doux">Des réflexes à prendre devant chaque exercice, illustrés par un exemple.</p>
        <ol className="gestes">
          {GESTES.map((g, i) => (
            <li key={g.titre}>
              <strong>
                <span className="numero">{i + 1}</span> {g.titre}
              </strong>
              <p>{g.quoi}</p>
              {g.exemples.map((ex) => (
                <p key={ex} className="exemple-geste">
                  <Maths texte={ex} enLigne />
                </p>
              ))}
            </li>
          ))}
        </ol>
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
            méthode, et refais un exercice semblable deux jours plus tard sans regarder la correction. Le carnet intégré à PKP
            arrive bientôt ; en attendant, l'onglet « Mon historique » liste déjà toutes tes erreurs avec leur correction
            (case « Seulement mes erreurs ») : c'est le point de départ de ton carnet.
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
