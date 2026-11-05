import { useState } from "react";
import { Maths } from "./maths.jsx";

// Question d'essai de la page d'accueil : tout se passe dans le navigateur, rien n'est envoyé ni enregistré.
const QUESTION = {
  niveau: "Seconde",
  enonce: "Développe l'expression $(x + 3)^2$.",
  choix: ["$x^2 + 9$", "$x^2 + 6x + 9$", "$x^2 + 3x + 9$", "$2x + 6$"],
  bonne: 1,
  correction:
    "On applique l'identité remarquable $(a + b)^2 = a^2 + 2ab + b^2$ avec $a = x$ et $b = 3$ :\n\n" +
    "$$(x + 3)^2 = x^2 + 2 \\times x \\times 3 + 3^2 = x^2 + 6x + 9$$\n\n" +
    "Piège classique : $x^2 + 9$ oublie le double produit $2ab$",
};

export default function ExempleQuestion() {
  const [choix, setChoix] = useState(null);
  const [verifie, setVerifie] = useState(false);
  const juste = choix === QUESTION.bonne;

  function verifier(e) {
    e.preventDefault();
    if (choix !== null) setVerifie(true);
  }

  function recommencer() {
    setChoix(null);
    setVerifie(false);
  }

  return (
    <form className="carte exemple-question" onSubmit={verifier}>
      <fieldset>
        <legend>
          <span className="badge">{QUESTION.niveau}</span> <Maths texte={QUESTION.enonce} enLigne />
        </legend>
        <div className="exemple-choix">
          {QUESTION.choix.map((texte, i) => (
            <label key={texte} className={verifie && i === QUESTION.bonne ? "exemple-bonne" : undefined}>
              <input
                type="radio"
                name="exemple"
                value={i}
                checked={choix === i}
                disabled={verifie}
                onChange={() => setChoix(i)}
              />
              <Maths texte={texte} enLigne />
            </label>
          ))}
        </div>
      </fieldset>

      <div aria-live="polite">
        {verifie && (
          <div className={`exemple-retour ${juste ? "juste" : "faux"}`}>
            <p>
              <strong>{juste ? "Bravo, c'est juste !" : "Pas tout à fait."}</strong>{" "}
              {juste ? "Voici la correction détaillée :" : "Regarde la correction pas à pas :"}
            </p>
            <Maths texte={QUESTION.correction} />
          </div>
        )}
      </div>

      <div className="actions">
        {verifie ? (
          <button type="button" className="secondaire" onClick={recommencer}>
            Réessayer
          </button>
        ) : (
          <button type="submit" disabled={choix === null}>
            Vérifier ma réponse
          </button>
        )}
      </div>
    </form>
  );
}
