// Habilitations d'un compte de l'équipe : professeur ou validateur, domaine par domaine (CDC V2, EX.6 et EX.9-bis).
// Un validateur est qualifié matière par matière ; un niveau précis peut restreindre sa validation.

const MATIERES = [
  ["maths", "Mathématiques"],
  ["anglais", "Anglais"],
  ["francais", "Français"],
];
const CYCLES = [
  ["college", "Collège"],
  ["lycee", "Lycée"],
];
const ROLES = [
  ["professeur", "Enseigne"],
  ["validateur", "Valide"],
];

// Avant la réponse de /admin/domaines (ou s'il échoue) : les deux domaines en service.
export const DOMAINES_PAR_DEFAUT = [
  { code: "maths-lycee", matiere: "maths", cycle: "lycee", libelle: "Maths lycée", niveaux: ["2nde", "1re", "Tle"], actif: true, public: true },
  { code: "anglais-college", matiere: "anglais", cycle: "college", libelle: "Anglais collège", niveaux: ["6e", "5e", "4e", "3e"], actif: true, public: true },
];

const cle = (role, domaine) => `${role}:${domaine}`;

/** [{ role, domaine, niveau }] → { "validateur:maths-lycee": [] (tout le domaine) | ["Tle", …] }. */
export function versGrille(habilitations) {
  const grille = {};
  for (const h of habilitations) {
    const k = cle(h.role, h.domaine);
    if (h.niveau == null) grille[k] = [];
    else if (grille[k]?.length !== 0) grille[k] = [...(grille[k] ?? []), h.niveau];
  }
  return grille;
}

export function depuisGrille(grille) {
  return Object.entries(grille).flatMap(([k, niveaux]) => {
    const [role, domaine] = k.split(":");
    return niveaux.length ? niveaux.map((niveau) => ({ role, domaine, niveau })) : [{ role, domaine, niveau: null }];
  });
}

export function BadgesHabilitations({ habilitations = [] }) {
  const parDomaine = {};
  for (const h of habilitations) {
    const k = cle(h.role, h.domaine);
    (parDomaine[k] ??= { ...h, niveaux: [] }).niveaux.push(h.niveau);
  }
  return Object.values(parDomaine).map((h) => (
    <span key={cle(h.role, h.domaine)} className={h.role === "validateur" ? "badge accent" : "badge neutre"}>
      {h.role === "validateur" ? "Valide" : "Enseigne"} {h.libelle}
      {h.niveaux.some(Boolean) && ` (${h.niveaux.filter(Boolean).join(", ")})`}
    </span>
  ));
}

/** Grille matières × cycles à cocher ; `valeur` et `onChange` au format de `versGrille`. */
export function GrilleQualifications({ domaines, valeur, onChange }) {
  const domaine = (matiere, cycle) => domaines.find((d) => d.matiere === matiere && d.cycle === cycle);

  function basculer(role, d, coche) {
    const suivante = { ...valeur };
    if (coche) suivante[cle(role, d.code)] = [];
    else delete suivante[cle(role, d.code)];
    onChange(suivante);
  }

  function touteLaMatiere(matiere) {
    const suivante = { ...valeur };
    for (const [cycle] of CYCLES) {
      const d = domaine(matiere, cycle);
      if (d?.actif) suivante[cle("validateur", d.code)] = [];
    }
    onChange(suivante);
  }

  function basculerNiveau(d, niveau) {
    const k = cle("validateur", d.code);
    const actuels = valeur[k] ?? [];
    const suivants = actuels.includes(niveau) ? actuels.filter((n) => n !== niveau) : [...actuels, niveau];
    // Tous les niveaux cochés un par un : c'est tout le domaine.
    onChange({ ...valeur, [k]: suivants.length === d.niveaux.length ? [] : d.niveaux.filter((n) => suivants.includes(n)) });
  }

  const validateurs = domaines.filter((d) => valeur[cle("validateur", d.code)]);

  return (
    <fieldset className="choix-chapitres">
      <legend>Qualifications</legend>
      <div className="tableau-defilant">
        <table className="grille-qualifications">
          <thead>
            <tr>
              <th>Matière</th>
              {ROLES.map(([role, libelle]) =>
                CYCLES.map(([cycle, nomCycle]) => (
                  <th key={`${role}-${cycle}`} className="centre">
                    {libelle}
                    <div className="aide">{nomCycle}</div>
                  </th>
                )),
              )}
              <th>
                <span className="visuellement-cache">Raccourci</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {MATIERES.map(([matiere, nomMatiere]) => (
              <tr key={matiere}>
                <th scope="row">{nomMatiere}</th>
                {ROLES.map(([role, libelle]) =>
                  CYCLES.map(([cycle]) => {
                    const d = domaine(matiere, cycle);
                    if (!d) return <td key={`${role}-${cycle}`} />;
                    return (
                      <td key={`${role}-${cycle}`} className="centre" title={d.actif ? undefined : "Domaine à activer dans la configuration"}>
                        <input
                          type="checkbox"
                          aria-label={`${libelle} — ${d.libelle}`}
                          disabled={!d.actif}
                          checked={!!valeur[cle(role, d.code)]}
                          onChange={(e) => basculer(role, d, e.target.checked)}
                        />
                      </td>
                    );
                  }),
                )}
                <td>
                  <button
                    type="button"
                    className="lien petit"
                    disabled={!CYCLES.some(([cycle]) => domaine(matiere, cycle)?.actif)}
                    onClick={() => touteLaMatiere(matiere)}
                  >
                    Valide toute la matière
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {validateurs.map((d) => (
        <div key={d.code} className="niveaux-valides" role="group" aria-label={`Niveaux validés en ${d.libelle}`}>
          <span className="aide">Valide en {d.libelle} :</span>
          {d.niveaux.map((n) => (
            <label key={n} className="case">
              <input
                type="checkbox"
                checked={valeur[cle("validateur", d.code)].includes(n)}
                onChange={() => basculerNiveau(d, n)}
              />
              {n}
            </label>
          ))}
          <span className="aide">{valeur[cle("validateur", d.code)].length ? "" : "(tous les niveaux)"}</span>
        </div>
      ))}
      <p className="aide">
        Un validateur ne valide que les matières cochées, et jamais son propre contenu. Le rôle d'administrateur ne donne pas le
        droit de valider.
      </p>
    </fieldset>
  );
}
