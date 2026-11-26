// Issue #212 — Circuit du français aligné sur l'anglais (Claude)
//
// Partie élève d'un dossier de français : leçon, textes et consignes, jamais de corrigé (ARCH-4). Sert à l'aperçu des
// adultes et à la lecture par l'élève d'un dossier validé et ouvert à sa classe.
import { Maths } from "../maths.jsx";

export default function PartieEleve({ eleve, apercu = false }) {
  return (
    <article className="carte" aria-label={apercu ? "Aperçu de la partie élève" : "Dossier de français"}>
      {apercu && <p className="doux petit">Aperçu réservé aux adultes : partie que lisent les élèves des classes ouvertes.</p>}
      {eleve.presentation.map((l) => (
        <p key={l} className="doux petit">
          {l}
        </p>
      ))}
      <h3>Objectifs</h3>
      {eleve.objectifs.map((l) => (
        <p key={l}>{l}</p>
      ))}
      {eleve.lecon.map((s) => (
        <section key={s.titre}>
          <h3>{s.titre}</h3>
          <Maths texte={s.markdown} />
        </section>
      ))}
      {eleve.textes.map((t) => (
        <section key={t.code}>
          <h3>{t.titre}</h3>
          <ol className="texte-lignes">
            {t.lignes.map((ligne, i) => (
              <li key={i} value={i + 1}>
                {ligne}
              </li>
            ))}
          </ol>
          {t.mention && <p className="doux petit">{t.mention}</p>}
        </section>
      ))}
      <h3>Questions</h3>
      {eleve.consignes_questions.map((l) => (
        <p key={l} className="petit">
          {l}
        </p>
      ))}
      <ol className="liste-simple">
        {eleve.questions.map((q) => (
          <li key={q.code}>
            <strong>{q.code}.</strong> {q.consigne}{" "}
            {q.difficulte_proposee && <span className="doux petit">(difficulté proposée {q.difficulte_proposee})</span>}
            {q.coup_de_pouce && <p className="doux petit">Coup de pouce : {q.coup_de_pouce}</p>}
            <p className="doux petit">
              {apercu ? "Réponse rédigée : retour du professeur." : "Rédige ta réponse : ton professeur la relira."}
            </p>
          </li>
        ))}
      </ol>
      {eleve.je_verifie && (
        <section>
          <h3>5. Je vérifie</h3>
          <Maths texte={eleve.je_verifie} />
        </section>
      )}
      {apercu && (eleve.quiz ?? []).length > 0 && (
        <section>
          <h3>Quiz ({eleve.quiz.length} questions, corrigé après réponse)</h3>
          <ol>
            {eleve.quiz.map((q, i) => (
              <li key={i}>
                {q.question} <span className="doux petit">({q.choix.join(" / ")})</span>
              </li>
            ))}
          </ol>
        </section>
      )}
      {apercu && (eleve.je_sais ?? []).length > 0 && (
        <section>
          <h3>Je fais le point</h3>
          <ul>
            {eleve.je_sais.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </section>
      )}
    </article>
  );
}
