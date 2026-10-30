import { useState } from "react";
import { envoyerPdf } from "../api.js";
import { Erreur } from "../composants.jsx";

const VIDE = {
  type: "lien", titre: "", description: "", url: "", source: "", licence: "", rattachement: "",
  public: "tous", classe_ids: [], droits_declares: false, ordre: 0,
};

const PUBLICS = [
  ["tous", "Élèves et professeurs"],
  ["eleves", "Élèves seulement"],
  ["enseignants", "Professeurs seulement"],
];

/**
 * Lien ou PDF rattaché à un chapitre ou à une compétence (module 3). Partagé entre le professeur
 * (portée « classe » : choix des classes, déclaration des droits) et l'administrateur (portée commune).
 * `chapitres` : [{ id, titre, niveau, competences: [{ id, libelle }] }].
 */
export default function FormulaireRessource({ initiale, chapitres, classes, appeler, jeton, base, onEnregistree }) {
  const [valeurs, setValeurs] = useState(() =>
    initiale
      ? {
          ...VIDE,
          ...initiale,
          url: initiale.url ?? "",
          source: initiale.source ?? "",
          licence: initiale.licence ?? "",
          rattachement: initiale.competence_id ? `c${initiale.competence_id}` : `h${initiale.chapitre_id}`,
          classe_ids: (classes ?? []).filter((c) => initiale.classes?.includes(c.code)).map((c) => c.id),
          droits_declares: true,
        }
      : VIDE,
  );
  const [fichier, setFichier] = useState(null);
  const [erreur, setErreur] = useState(null);
  const [envoi, setEnvoi] = useState(false);
  const pourClasses = classes != null;
  const champ = (cle) => ({ value: valeurs[cle], onChange: (e) => setValeurs({ ...valeurs, [cle]: e.target.value }) });

  async function soumettre(e) {
    e.preventDefault();
    setErreur(null);
    if (valeurs.type === "pdf" && !fichier && !initiale?.a_un_fichier) return setErreur("Choisissez le fichier PDF.");
    if (fichier && fichier.size > 10 * 1024 * 1024) return setErreur("Le PDF dépasse 10 Mo.");
    const [genre, id] = [valeurs.rattachement[0], Number(valeurs.rattachement.slice(1))];
    const corps = {
      type: valeurs.type,
      titre: valeurs.titre,
      description: valeurs.description,
      url: valeurs.type === "lien" ? valeurs.url.trim() : null,
      source: valeurs.source || null,
      licence: valeurs.licence || null,
      chapitre_id: genre === "h" ? id : null,
      competence_id: genre === "c" ? id : null,
      public: valeurs.public,
      classe_ids: valeurs.classe_ids,
      droits_declares: valeurs.droits_declares,
      ordre: Number(valeurs.ordre) || 0,
    };
    setEnvoi(true);
    try {
      let ressource = await appeler(initiale ? `${base}/${initiale.id}` : base, { methode: "POST", corps });
      if (fichier) ressource = await envoyerPdf(`${base}/${ressource.id}/fichier`, fichier, jeton);
      onEnregistree(ressource);
    } catch (err) {
      setErreur(err.message);
    } finally {
      setEnvoi(false);
    }
  }

  return (
    <form onSubmit={soumettre}>
      <fieldset className="choix-chapitres">
        <legend>Type</legend>
        <label className="case">
          <input type="radio" name="type" value="lien" checked={valeurs.type === "lien"} onChange={champ("type").onChange} /> Lien vers un site
        </label>
        <label className="case">
          <input type="radio" name="type" value="pdf" checked={valeurs.type === "pdf"} onChange={champ("type").onChange} /> Fichier PDF
        </label>
      </fieldset>

      <label htmlFor="r-titre">Titre</label>
      <input id="r-titre" maxLength={120} required {...champ("titre")} />
      <label htmlFor="r-description">Description (facultative)</label>
      <textarea id="r-description" rows={2} maxLength={300} {...champ("description")} />

      {valeurs.type === "lien" ? (
        <>
          <label htmlFor="r-url">Adresse</label>
          <input id="r-url" type="url" pattern="https://.*" placeholder="https://…" required {...champ("url")} />
          <p className="aide">Adresse https uniquement. Elle s'ouvrira dans un nouvel onglet, sans transmettre de donnée d'élève.</p>
        </>
      ) : (
        <>
          <label htmlFor="r-fichier">Fichier PDF (10 Mo au plus)</label>
          <input id="r-fichier" type="file" accept="application/pdf,.pdf" onChange={(e) => setFichier(e.target.files[0] ?? null)} />
          {initiale?.a_un_fichier && !fichier && <p className="aide">Un fichier est déjà enregistré ; en choisir un autre le remplace.</p>}
          <div className="ligne">
            <div>
              <label htmlFor="r-source">Source</label>
              <input id="r-source" maxLength={200} required placeholder="ex. Moi-même, Éduscol" {...champ("source")} />
            </div>
            <div>
              <label htmlFor="r-licence">Licence</label>
              <input id="r-licence" maxLength={100} required placeholder="ex. CC BY 4.0" {...champ("licence")} />
            </div>
          </div>
        </>
      )}

      <label htmlFor="r-rattachement">Rattachée à</label>
      <select id="r-rattachement" required {...champ("rattachement")}>
        <option value="">Choisir un chapitre ou une compétence…</option>
        {chapitres.map((ch) => (
          <optgroup key={ch.id} label={`${ch.niveau} · ${ch.titre}`}>
            <option value={`h${ch.id}`}>Tout le chapitre</option>
            {ch.competences.map((c) => (
              <option key={c.id} value={`c${c.id}`}>
                {c.libelle}
              </option>
            ))}
          </optgroup>
        ))}
      </select>

      <label htmlFor="r-public">Visible par</label>
      <select id="r-public" {...champ("public")}>
        {PUBLICS.map(([v, l]) => (
          <option key={v} value={v}>
            {l}
          </option>
        ))}
      </select>

      {pourClasses && (
        <fieldset className="choix-chapitres">
          <legend>Pour mes classes</legend>
          {classes.length === 0 && <p className="doux">Créez d'abord une classe.</p>}
          {classes.map((c) => (
            <label key={c.id} className="case">
              <input
                type="checkbox"
                checked={valeurs.classe_ids.includes(c.id)}
                onChange={(e) =>
                  setValeurs({
                    ...valeurs,
                    classe_ids: e.target.checked ? [...valeurs.classe_ids, c.id] : valeurs.classe_ids.filter((i) => i !== c.id),
                  })
                }
              />
              {c.code}
            </label>
          ))}
          <p className="aide">Les élèves ne la voient que si le chapitre est ouvert dans leur classe.</p>
        </fieldset>
      )}

      {pourClasses && valeurs.type === "pdf" && (
        <label className="case">
          <input
            type="checkbox"
            checked={valeurs.droits_declares}
            onChange={(e) => setValeurs({ ...valeurs, droits_declares: e.target.checked })}
          />
          Je détiens les droits de diffusion de ce document à mes élèves.
        </label>
      )}

      <Erreur message={erreur} />
      <div className="actions">
        <button type="submit" disabled={envoi}>
          {envoi ? "Enregistrement…" : "Enregistrer"}
        </button>
      </div>
    </form>
  );
}
