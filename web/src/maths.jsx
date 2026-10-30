// Rendu Markdown + formules LaTeX ($…$ en ligne, $$…$$ centré) pour les cours et énoncés.
import DOMPurify from "dompurify";
import katex from "katex";
import "katex/dist/katex.min.css";
import { marked } from "marked";

// $$…$$ d'abord, puis $…$ ; « \$ » est un dollar littéral.
const FORMULE = /\$\$([\s\S]+?)\$\$|(?<!\\)\$((?:\\\$|[^$])+?)\$/g;

function rendreFormule(tex, centree) {
  return katex.renderToString(tex, { displayMode: centree, throwOnError: false, output: "htmlAndMathml" });
}

export function versHtml(texte, { enLigne = false } = {}) {
  const formules = [];
  // Les formules sont mises de côté avant Markdown : sinon « _ » et « * » y seraient interprétés.
  const sansFormules = texte.replace(FORMULE, (_, bloc, ligne) => {
    formules.push(rendreFormule(bloc ?? ligne, bloc !== undefined));
    return `@@F${formules.length - 1}@@`;
  });
  const html = enLigne ? marked.parseInline(sansFormules) : marked.parse(sansFormules);
  const complet = html.replace(/@@F(\d+)@@/g, (_, i) => formules[Number(i)]);
  // Contenu relu avant import, mais on nettoie quand même : jamais de script ni d'attribut on*.
  return DOMPurify.sanitize(complet, { ADD_TAGS: ["semantics", "annotation"], ADD_ATTR: ["encoding"] });
}

/** Formules que KaTeX ne sait pas afficher : l'éditeur refuse d'enregistrer tant qu'il en reste (EA3.12). */
export function formulesInvalides(texte) {
  const erreurs = [];
  for (const [, bloc, ligne] of texte.matchAll(FORMULE)) {
    try {
      katex.renderToString(bloc ?? ligne, { displayMode: bloc !== undefined, throwOnError: true });
    } catch (err) {
      erreurs.push(`$${bloc ?? ligne}$ : ${err.message.replace(/^KaTeX parse error: /, "")}`);
    }
  }
  return erreurs;
}

export function Maths({ texte, enLigne = false, className }) {
  const Balise = enLigne ? "span" : "div";
  return <Balise className={className ?? "maths"} dangerouslySetInnerHTML={{ __html: versHtml(texte, { enLigne }) }} />;
}
