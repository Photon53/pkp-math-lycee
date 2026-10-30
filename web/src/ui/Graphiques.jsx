// Graphiques du tableau de bord, dessinés en SVG et CSS aux couleurs de la charte (EA6.12) :
// aucune bibliothèque tierce, lisibles dans les deux thèmes, doublés d'un tableau pour les lecteurs d'écran.

const L = 560;
const H = 180;
const MARGE = { haut: 12, droite: 12, bas: 24, gauche: 36 };

function jourCourt(iso) {
  const [, m, j] = iso.split("-");
  return `${Number(j)}/${Number(m)}`;
}

/** Courbe d'une série par jour ; `secondaire` ajoute une deuxième série en pointillés. */
export function Courbe({ points, libelle, secondaire, libelleSecondaire }) {
  if (!points.length) return <p className="doux">Aucune donnée sur la période.</p>;
  const max = Math.max(1, ...points.map((p) => p.y));
  const largeur = L - MARGE.gauche - MARGE.droite;
  const hauteur = H - MARGE.haut - MARGE.bas;
  const x = (i) => MARGE.gauche + (points.length === 1 ? largeur / 2 : (i / (points.length - 1)) * largeur);
  const y = (v) => MARGE.haut + hauteur - (v / max) * hauteur;
  const trace = (serie) => serie.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(p.y).toFixed(1)}`).join(" ");
  const graduations = [0, max / 2, max].map((v) => Math.round(v));
  const etiquettes = points.length <= 8 ? points.map((_, i) => i) : [0, Math.floor(points.length / 2), points.length - 1];

  return (
    <figure style={{ margin: 0 }}>
      <svg className="graphique" viewBox={`0 0 ${L} ${H}`} role="img" aria-label={`${libelle} par jour`}>
        {graduations.map((g) => (
          <g key={g}>
            <line className="grille" x1={MARGE.gauche} x2={L - MARGE.droite} y1={y(g)} y2={y(g)} />
            <text x={MARGE.gauche - 6} y={y(g) + 4} textAnchor="end">
              {g}
            </text>
          </g>
        ))}
        <path className="aire" d={`${trace(points)} L${x(points.length - 1)} ${y(0)} L${x(0)} ${y(0)} Z`} />
        <path className="serie" d={trace(points)} />
        {secondaire && <path className="serie" d={trace(secondaire)} style={{ stroke: "var(--ok)", strokeDasharray: "5 4" }} />}
        {points.length <= 31 && points.map((p, i) => <circle key={p.x} className="point" cx={x(i)} cy={y(p.y)} r="2.5" />)}
        {etiquettes.map((i) => (
          <text key={i} x={x(i)} y={H - 6} textAnchor="middle">
            {jourCourt(points[i].x)}
          </text>
        ))}
      </svg>
      {secondaire && (
        <figcaption className="legende">
          <span><i style={{ background: "var(--action)" }} />{libelle}</span>
          <span><i style={{ background: "var(--ok)" }} />{libelleSecondaire}</span>
        </figcaption>
      )}
      <table className="visuellement-cache">
        <caption>{libelle}</caption>
        <tbody>
          {points.map((p, i) => (
            <tr key={p.x}>
              <th scope="row">{p.x}</th>
              <td>{p.y}</td>
              {secondaire && <td>{secondaire[i]?.y}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}

/**
 * Barres horizontales triées par l'appelant. `elements` : [{ nom, valeur, texte, ton }] ;
 * en mode `empilees`, chaque élément porte `segments` : [{ valeur, ton }].
 */
export function Barres({ elements, max, empilees = false }) {
  const total = (e) => (empilees ? e.segments.reduce((s, x) => s + x.valeur, 0) : e.valeur);
  const plafond = max ?? Math.max(1, ...elements.map(total));
  return (
    <div className="barres">
      {elements.map((e) => (
        <div className="barre" key={e.nom}>
          <span className="nom" title={e.nom}>
            {e.nom}
          </span>
          <span className="piste" aria-hidden="true">
            {empilees ? (
              e.segments.map((s, i) => (
                <span key={i} className={`rempli ${s.ton}`} style={{ width: `${(s.valeur / plafond) * 100}%` }} />
              ))
            ) : (
              <span className={`rempli ${e.ton ?? ""}`} style={{ width: `${(e.valeur / plafond) * 100}%` }} />
            )}
          </span>
          <span className="val">{e.texte}</span>
        </div>
      ))}
    </div>
  );
}
