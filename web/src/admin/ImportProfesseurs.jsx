import { useState } from "react";
import { ApiError, envoyerFichier, telechargerFichier } from "../api.js";
import { Erreur } from "../composants.jsx";
import { Modale, exporterCsv } from "../ui/Cadre.jsx";
import Icone from "../ui/Icone.jsx";

const MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

/** Création en masse des comptes professeurs : modèle Excel (une ligne par professeur), vérification sans
 * rien écrire, puis import (tout ou rien) ; les mots de passe provisoires ne sont donnés qu'une fois. */
export default function ImportProfesseurs({ jeton, onExpire, onFermer, onImporte }) {
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

  const modele = () =>
    executer(telechargerFichier("/admin/import/professeurs/modele", jeton, "boussole-modele-professeurs.xlsx"));

  async function verifier(e) {
    e.preventDefault();
    const r = await executer(envoyerFichier("/admin/import/professeurs?simulation=true", fichier, jeton, MIME_XLSX));
    if (r) setRapport(r);
  }

  async function importer() {
    const r = await executer(envoyerFichier("/admin/import/professeurs?simulation=false", fichier, jeton, MIME_XLSX));
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
          {resultat.comptes.length} compte(s) professeur créé(s)
          {resultat.nb_deja_presents ? `, ${resultat.nb_deja_presents} déjà inscrit(s) ignoré(s)` : ""}.
        </p>
        {resultat.comptes.length > 0 && (
          <>
            <h3>Mots de passe provisoires</h3>
            <p className="aide">
              Ils ne seront plus affichés : téléchargez la liste (CSV) ou notez-les, puis transmettez-les par un canal sûr.
              Chaque professeur changera le sien à la première connexion.
            </p>
            <div className="tableau-defilant">
              <table>
                <thead>
                  <tr>
                    <th>Nom</th>
                    <th>E-mail</th>
                    <th>Mot de passe provisoire</th>
                  </tr>
                </thead>
                <tbody>
                  {resultat.comptes.map((c) => (
                    <tr key={c.email}>
                      <td>{c.nom}</td>
                      <td>{c.email}</td>
                      <td>
                        <code>{c.mot_de_passe_provisoire}</code>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
        <div className="actions">
          {resultat.comptes.length > 0 && (
            <button
              className="secondaire"
              onClick={() =>
                exporterCsv(
                  "boussole-comptes-professeurs.csv",
                  resultat.comptes.map(({ nom, email, mot_de_passe_provisoire }) => ({ nom, email, mot_de_passe_provisoire })),
                )
              }
            >
              Télécharger la liste (CSV)
            </button>
          )}
          <button onClick={onFermer}>J'ai noté les mots de passe</button>
        </div>
      </Modale>
    );

  const pret = rapport && !rapport.nb_erreurs && rapport.nb_professeurs > 0;
  return (
    <Modale titre="Importer des professeurs (Excel)" onFermer={onFermer} large>
      <ol className="etapes-import">
        <li>
          Téléchargez le modèle : une ligne par professeur (nom affiché, e-mail, maths, anglais, référent anglais).{" "}
          <button type="button" className="secondaire petit" onClick={modele} disabled={envoi}>
            <Icone nom="telecharger" taille={16} /> Télécharger le modèle Excel
          </button>
        </li>
        <li>Remplissez-le dans Excel (ou LibreOffice), enregistrez au format .xlsx.</li>
        <li>Choisissez le fichier : Boussole vérifie chaque ligne sans rien enregistrer, puis vous lancez l'import.</li>
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
              : `Fichier prêt : ${rapport.nb_professeurs} compte(s) professeur à créer.`}
            {rapport.nb_deja_presents ? ` ${rapport.nb_deja_presents} adresse(s) déjà inscrite(s) seront ignorée(s).` : ""}
          </p>
          <div className="tableau-defilant">
            <table>
              <thead>
                <tr>
                  <th className="nombre">Ligne</th>
                  <th>Nom</th>
                  <th>E-mail</th>
                  <th>Matières</th>
                  <th>État</th>
                </tr>
              </thead>
              <tbody>
                {rapport.lignes.map((l) => (
                  <tr key={l.ligne} className={l.erreurs.length ? "ligne-erreur" : undefined}>
                    <td className="nombre">{l.ligne}</td>
                    <td>{l.nom}</td>
                    <td>{l.email || "—"}</td>
                    <td>{l.matieres.join(", ") || "—"}</td>
                    <td>
                      {l.erreurs.length ? (
                        <ul className="liste-simple">
                          {l.erreurs.map((m) => (
                            <li key={m}>{m}</li>
                          ))}
                        </ul>
                      ) : l.deja_present ? (
                        <span className="badge neutre">Déjà inscrit</span>
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
              {envoi ? "Import en cours…" : `Créer ${rapport.nb_professeurs} compte(s)`}
            </button>
          </div>
        </>
      )}
    </Modale>
  );
}
