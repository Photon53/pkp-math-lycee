// Espace de l'enfant d'une famille : une seule carte, puis le choix de la matière.
// PKP Math : s'entraîner dans l'un de ses parcours (tronc commun, excellence, mise à niveau…) ou lire les
// fiches de son niveau ; PKP Anglais : ouvre son groupe d'anglais ; PKP Français : bientôt disponible.
import { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";
import { Erreur } from "../composants.jsx";
import { NIVEAUX } from "../parcours.js";
import PkpMath from "../pkpmath/PkpMath.jsx";
import { ecrire } from "../stockage.js";

export const CLE_ENFANT = "pkp.enfant";
const CLE_ANGLAIS = "pkp.eleve.anglais";
const NOM_NIVEAU = Object.fromEntries(NIVEAUX);

export default function EspaceEnfant({ session, onOuvrirMaths, onDeconnexion }) {
  const [espace, setEspace] = useState(session.enfant);
  const [matiere, setMatiere] = useState(null);
  const [erreur, setErreur] = useState(null);
  const expire = useCallback(() => onDeconnexion(), [onDeconnexion]);

  // Inscriptions à jour (le professeur a pu ajouter une classe depuis la connexion).
  useEffect(() => {
    api("/enfants/moi", { jeton: session.jeton }).then(setEspace, (err) => (err.status === 401 ? expire() : null));
  }, [session.jeton, expire]);

  async function ouvrirMaths(eleveId) {
    setErreur(null);
    try {
      onOuvrirMaths(await api(`/enfants/moi/maths/${eleveId}`, { methode: "POST", jeton: session.jeton }));
    } catch (err) {
      if (err.status === 401) return expire();
      setErreur(err.message);
    }
  }

  async function ouvrirAnglais(eleveId) {
    setErreur(null);
    try {
      const compte = await api(`/enfants/moi/anglais/${eleveId}`, { methode: "POST", jeton: session.jeton });
      ecrire(CLE_ANGLAIS, compte, { durable: session.durable });
      window.location.assign("/anglais/eleve");
    } catch (err) {
      if (err.status === 401) return expire();
      setErreur(err.message);
    }
  }

  const niveau = NOM_NIVEAU[espace.niveau] ?? espace.niveau;
  return (
    <>
      <div className="barre-session">
        <p>
          Bonjour <strong>{espace.prenom}</strong> <span className="doux">· {niveau}</span>
        </p>
        {matiere && (
          <button className="lien" onClick={() => setMatiere(null)}>
            ← Mes matières
          </button>
        )}
        <button className="lien" onClick={onDeconnexion}>
          Ce n'est pas moi
        </button>
      </div>
      <Erreur message={erreur} />

      {!matiere && (
        <section className="carte" aria-labelledby="titre-matieres">
          <h1 id="titre-matieres">Que veux-tu travailler ?</h1>
          <div className="grille-matieres">
            {espace.matieres.map((m) => (
              <button key={m.code} className="matiere" disabled={!m.disponible} onClick={() => setMatiere(m.code)}>
                <span className="matiere-nom">{m.libelle}</span>
                <span className="doux">{resumeMatiere(m, espace, niveau)}</span>
                {!m.disponible && <span className="badge neutre">Bientôt disponible</span>}
              </button>
            ))}
          </div>
        </section>
      )}

      {matiere === "maths" && (
        <>
          <section className="carte" aria-labelledby="titre-exercices">
            <h2 id="titre-exercices">S'entraîner en maths</h2>
            {espace.maths.length === 0 ? (
              <p className="doux">
                Ton professeur ne t'a pas encore ajouté à une classe. En attendant, tu peux lire les cours et les fiches de ton
                niveau ci-dessous.
              </p>
            ) : (
              <ul className="liste-inscriptions">
                {espace.maths.map((i) => (
                  <li key={i.eleve_id}>
                    <span>
                      <strong>{i.libelle_parcours}</strong> <span className="doux">· {i.code_classe} · {i.enseignant}</span>
                    </span>
                    <button onClick={() => ouvrirMaths(i.eleve_id)}>S'entraîner</button>
                  </li>
                ))}
              </ul>
            )}
          </section>
          <section className="carte">
            <PkpMath
              jeton={session.jeton}
              onExpire={expire}
              niveauParDefaut={espace.niveau}
              intro={`Les cours de ${niveau} : résumé, cours complet, fiche d'exercices et corrigé, à lire ici ou à exporter en PDF.`}
            />
          </section>
        </>
      )}

      {matiere === "anglais" && (
        <section className="carte" aria-labelledby="titre-anglais">
          <h2 id="titre-anglais">Boussole Anglais</h2>
          {espace.anglais.length === 0 ? (
            <p className="doux">Ton professeur d'anglais ne t'a pas encore ajouté à un groupe.</p>
          ) : (
            <ul className="liste-inscriptions">
              {espace.anglais.map((i) => (
                <li key={i.eleve_id}>
                  <span>
                    <strong>{i.groupe}</strong> <span className="doux">· {i.niveau} · {i.enseignant}</span>
                  </span>
                  <button onClick={() => ouvrirAnglais(i.eleve_id)}>Ouvrir mes séances</button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </>
  );
}

function resumeMatiere(m, espace, niveau) {
  if (!m.disponible) return "Le français arrive bientôt sur Boussole.";
  if (m.code === "maths") {
    const n = espace.maths.length;
    return n ? `${n} parcours · cours et fiches de ${niveau}` : `Cours et fiches de ${niveau}`;
  }
  if (m.code === "anglais") return espace.anglais.length ? espace.anglais.map((a) => a.groupe).join(", ") : "Pas encore de groupe";
  return "";
}
