import { useState } from "react";
import { ApiError, envoyerFichier, telechargerFichier } from "../api.js";
import { Erreur } from "../composants.jsx";
import { FicheCodes } from "../enseignant/Classes.jsx";
import { Modale, exporterCsv } from "../ui/Cadre.jsx";
import Icone from "../ui/Icone.jsx";
import { cartesAImprimer } from "./EnfantsFamille.jsx";

const MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

/** Inscription en masse : modèle Excel à remplir (une ligne par enfant), vérification sans rien écrire,
 * puis import (tout ou rien) ; cartes et mots de passe provisoires donnés une seule fois. */
export default function ImportFamilles({ jeton, onExpire, onFermer, onImporte }) {
  const [fichier, setFichier] = useState(null);
  const [rapport, setRapport] = useState(null);
  const [resultat, setResultat] = useState(null);
  const [erreur, setErreur] = useState(null);
  const [envoi, setEnvoi] = useState(false);

  async function executer(promesse) {
    setErreur(null);
    setEnvoi(true);
    try {
      return await promesse;
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) onExpire();
      else setErreur(err.message);
      return undefined;
    } finally {
      setEnvoi(false);
    }
  }

  const modele = () => executer(telechargerFichier("/admin/import/modele", jeton, "pkp-modele-inscriptions.xlsx"));

  async function verifier(e) {
    e.preventDefault();
    const r = await executer(envoyerFichier("/admin/import?simulation=true", fichier, jeton, MIME_XLSX));
    if (r) setRapport(r);
  }

  async function importer() {
    const r = await executer(envoyerFichier("/admin/import?simulation=false", fichier, jeton, MIME_XLSX));
    if (!r) return;
    if (r.nb_erreurs) setRapport(r);
    else {
      setResultat(r);
      onImporte(r);
    }
  }

  if (resultat)
    return (
      <Modale titre="Import terminé" onFermer={onFermer} large>
        <p className="succes" role="status">
          {resultat.nb_enfants} enfant(s) créé(s), {resultat.comptes.length} compte(s) parent créé(s)
          {resultat.nb_deja_presents ? `, ${resultat.nb_deja_presents} déjà présent(s) ignoré(s)` : ""}.
        </p>
        {resultat.comptes.length > 0 && (
          <>
            <h3>Mots de passe provisoires des nouveaux parents</h3>
            <p className="aide">
              Ils ne seront plus affichés : téléchargez la liste (CSV) ou notez-les, puis transmettez-les par un canal sûr. Chaque
              parent changera le sien à la première connexion.
            </p>
            <div className="tableau-defilant">
              <table>
                <thead>
                  <tr>
                    <th>E-mail</th>
                    <th>Mot de passe provisoire</th>
                  </tr>
                </thead>
                <tbody>
                  {resultat.comptes.map((c) => (
                    <tr key={c.email}>
                      <td>{c.email}</td>
                      <td>
                        <code>{c.mot_de_passe_provisoire}</code>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="actions">
              <button className="secondaire" onClick={() => exporterCsv("pkp-comptes-parents.csv", resultat.comptes)}>
                Télécharger la liste (CSV)
              </button>
            </div>
          </>
        )}
        <FicheCodes classe="Import" intitule="Inscription en masse" codes={cartesAImprimer(resultat.cartes)} onFermer={onFermer} />
      </Modale>
    );

  const pret = rapport && !rapport.nb_erreurs && rapport.nb_enfants > 0;
  return (
    <Modale titre="Importer des élèves (Excel)" onFermer={onFermer} large>
      <ol className="etapes-import">
        <li>
          Téléchargez le modèle : une ligne par enfant (prénom, nom, niveau, e-mail du parent 1, et si besoin parent 2, classe de
          maths, groupe d'anglais). Les classes et groupes existants sont proposés en liste déroulante.{" "}
          <button type="button" className="secondaire petit" onClick={modele} disabled={envoi}>
            <Icone nom="telecharger" taille={16} /> Télécharger le modèle Excel
          </button>
        </li>
        <li>Remplissez-le dans Excel (ou LibreOffice), enregistrez au format .xlsx.</li>
        <li>Choisissez le fichier : PKP vérifie chaque ligne sans rien enregistrer, puis vous lancez l'import.</li>
      </ol>
      <form onSubmit={verifier} className="ligne-champs">
        <label>
          Fichier rempli (.xlsx)
          <input
            type="file"
            accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            onChange={(e) => {
              setFichier(e.target.files?.[0] ?? null);
              setRapport(null);
            }}
          />
        </label>
        <div className="actions">
          <button type="submit" disabled={!fichier || envoi}>
            {envoi && !rapport ? "Vérification…" : "Vérifier le fichier"}
          </button>
        </div>
      </form>
      <Erreur message={erreur} />
      {rapport && (
        <>
          <p role="status" className={rapport.nb_erreurs ? "alerte-texte" : "succes"}>
            {rapport.nb_erreurs
              ? `${rapport.nb_erreurs} ligne(s) à corriger dans le fichier : rien n'a été enregistré.`
              : `Fichier prêt : ${rapport.nb_enfants} enfant(s) à créer, ${rapport.nb_comptes_nouveaux} nouveau(x) compte(s) parent.`}
            {rapport.nb_deja_presents ? ` ${rapport.nb_deja_presents} enfant(s) déjà présent(s) seront ignoré(s).` : ""}
          </p>
          {pret && rapport.nb_comptes_nouveaux > 20 && (
            <p className="aide">
              Comptez environ une seconde par nouveau compte parent (mots de passe protégés) : gardez la fenêtre ouverte pendant
              l'import.
            </p>
          )}
          <div className="tableau-defilant">
            <table>
              <thead>
                <tr>
                  <th className="nombre">Ligne</th>
                  <th>Enfant</th>
                  <th>Niveau</th>
                  <th>Parents</th>
                  <th>Inscriptions</th>
                  <th>État</th>
                </tr>
              </thead>
              <tbody>
                {rapport.lignes.map((l) => (
                  <tr key={l.ligne} className={l.erreurs.length ? "ligne-erreur" : undefined}>
                    <td className="nombre">{l.ligne}</td>
                    <td>{l.enfant}</td>
                    <td>{l.niveau ?? "—"}</td>
                    <td>{l.parents.join(", ") || "—"}</td>
                    <td>{l.inscriptions.join(", ") || "—"}</td>
                    <td>
                      {l.erreurs.length ? (
                        <ul className="liste-simple">
                          {l.erreurs.map((m) => (
                            <li key={m}>{m}</li>
                          ))}
                        </ul>
                      ) : l.deja_present ? (
                        <span className="badge neutre">Déjà présent</span>
                      ) : (
                        <span className="badge ok">Prêt</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="actions">
            <button onClick={importer} disabled={!pret || envoi}>
              {envoi ? "Import en cours…" : `Importer ${rapport.nb_enfants} élève(s)`}
            </button>
          </div>
        </>
      )}
    </Modale>
  );
}
