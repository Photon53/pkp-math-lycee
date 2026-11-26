// Issue #212 — Circuit du français aligné sur l'anglais (Claude) ; activité de l'élève : #217
//
// Dossiers de français ouverts à la classe par la professeure, dans leur version validée seulement. L'API applique
// les règles d'accès (classes pilotes, SEC-D6) et ne renvoie ni corrigé ni support professeur (ARCH-4).
import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Erreur } from "../composants.jsx";
import PartieEleve from "../francais/PartieEleve.jsx";
import { AutoEvaluation, QuizFrancais, ReponsesRedigees } from "./ActiviteFrancais.jsx";

export default function DossiersFrancais({ jeton, onExpire }) {
  const [dossiers, setDossiers] = useState(null);
  const [ouvert, setOuvert] = useState(null);
  const [erreur, setErreur] = useState(null);

  useEffect(() => {
    api("/francais/eleve/dossiers", { jeton }).then(setDossiers, (err) =>
      err.status === 401 && onExpire ? onExpire() : setDossiers([]),
    );
  }, [jeton, onExpire]);

  async function lire(code) {
    setErreur(null);
    try {
      setOuvert(await api(`/francais/eleve/dossiers/${encodeURIComponent(code)}`, { jeton }));
    } catch (err) {
      if (err.status === 401 && onExpire) onExpire();
      else setErreur(err.message);
    }
  }

  if (!dossiers || dossiers.length === 0) return null;
  if (ouvert) {
    return (
      <section aria-labelledby="titre-dossier-francais">
        <button className="lien" onClick={() => setOuvert(null)}>
          ← Mes dossiers
        </button>
        <h2 id="titre-dossier-francais">{ouvert.titre}</h2>
        <PartieEleve eleve={ouvert.eleve} />
        <QuizFrancais key={`quiz-${ouvert.code}`} dossier={ouvert} jeton={jeton} onExpire={onExpire} />
        <ReponsesRedigees key={`reponses-${ouvert.code}`} dossier={ouvert} jeton={jeton} onExpire={onExpire} />
        <AutoEvaluation key={`je-sais-${ouvert.code}`} dossier={ouvert} jeton={jeton} onExpire={onExpire} />
      </section>
    );
  }
  return (
    <section className="carte" aria-labelledby="titre-dossiers-francais">
      <h2 id="titre-dossiers-francais">Mes dossiers</h2>
      <p className="doux">Les dossiers que ta professeure a ouverts à ta classe : leçon, textes, quiz et questions à rédiger.</p>
      <Erreur message={erreur} />
      <ul className="liste-simple">
        {dossiers.map((d) => (
          <li key={d.code}>
            <button className="lien" onClick={() => lire(d.code)}>
              {d.titre}
            </button>
            {d.score !== null && d.score !== undefined && (
              <span className="doux petit">
                {" "}
                · meilleur score {d.score}/{d.total}
              </span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
