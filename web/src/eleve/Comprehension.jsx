import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Erreur } from "../composants.jsx";

/**
 * Ticket #28 : l'élève dit s'il a compris le cours, sans devoir échouer à un exercice. Il peut changer d'avis ;
 * son professeur voit « Je n'ai pas compris » pendant la séance. Ce n'est pas une note : la maîtrise ne change pas.
 */
export function AvisCours({ competenceId, jeton }) {
  const [compris, setCompris] = useState(undefined); // undefined : chargement ; null : rien indiqué
  const [erreur, setErreur] = useState(null);

  useEffect(() => {
    let actif = true;
    api(`/eleves/moi/comprehension/${competenceId}`, { jeton }).then(
      (a) => actif && setCompris(a.compris),
      () => actif && setCompris(null),
    );
    return () => {
      actif = false;
    };
  }, [competenceId, jeton]);

  async function choisir(valeur) {
    setErreur(null);
    try {
      const a = await api("/eleves/moi/comprehension", { methode: "POST", corps: { competence_id: competenceId, compris: valeur }, jeton });
      setCompris(a.compris);
    } catch (err) {
      setErreur(err.message);
    }
  }

  if (compris === undefined) return null;
  return (
    <section className="carte avis-cours" aria-labelledby="titre-avis">
      <h3 id="titre-avis" style={{ marginTop: 0 }}>
        As-tu compris ce cours ?
      </h3>
      <div className="actions" role="group" aria-label="As-tu compris ce cours ?">
        <button className={compris === true ? "" : "secondaire"} aria-pressed={compris === true} onClick={() => choisir(true)}>
          J'ai compris
        </button>
        <button className={compris === false ? "" : "secondaire"} aria-pressed={compris === false} onClick={() => choisir(false)}>
          Je n'ai pas compris
        </button>
      </div>
      {compris === false && (
        <p className="doux petit" role="status">
          Ton professeur est prévenu. Tu peux changer d'avis quand tu veux.
        </p>
      )}
      <Erreur message={erreur} />
    </section>
  );
}

/** Après une réponse : « Je n'ai pas compris » l'exercice ou sa correction ; le professeur le voit en direct. */
export function AideExercice({ seanceId, questionId, jeton, avecCorrection }) {
  const [envoyees, setEnvoyees] = useState({});
  const [erreur, setErreur] = useState(null);

  async function demander(objet) {
    setErreur(null);
    try {
      await api(`/seances/${seanceId}/aide`, { methode: "POST", corps: { question_id: questionId, objet }, jeton });
      setEnvoyees((e) => ({ ...e, [objet]: true }));
    } catch (err) {
      setErreur(err.message);
    }
  }

  return (
    <div className="aide-exercice">
      <div className="actions">
        {[
          ["exercice", "Je n'ai pas compris l'exercice"],
          ...(avecCorrection ? [["corrige", "Je n'ai pas compris la correction"]] : []),
        ].map(([objet, libelle]) => (
          <button key={objet} className="secondaire petit" disabled={envoyees[objet]} onClick={() => demander(objet)}>
            {envoyees[objet] ? "Demande envoyée à ton professeur" : libelle}
          </button>
        ))}
      </div>
      <Erreur message={erreur} />
    </div>
  );
}
