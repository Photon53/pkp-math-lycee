import { useCallback, useEffect, useState } from "react";
import { telecharger } from "../anglais/SeancesAnglais.jsx";
import { Decision, Historique, StatutSeance } from "../anglais/ValidationAnglais.jsx";
import { Erreur } from "../composants.jsx";
import { useApi } from "../enseignant/useApi.js";

const lignes = (texte) => texte.split("\n").map((l) => l.trim()).filter(Boolean);
const QCM_VIDE = { question: "", choix: ["", "", ""], reponse: 0, explication: "" };

/** Catalogue des séances PKP Anglais : statut, version publiée, édition et circuit de validation. */
export default function SeancesAnglaisAdmin({ jeton, onExpire }) {
  const { appeler, erreur, setErreur } = useApi(jeton, onExpire);
  const [seances, setSeances] = useState(null);
  const [code, setCode] = useState(null);
  const [encours, setEncours] = useState("");

  const charger = useCallback(() => appeler("/admin/anglais/seances").then(setSeances, () => {}), [appeler]);

  useEffect(() => {
    charger();
  }, [charger]);

  async function pdf(c, publicCible) {
    setErreur(null);
    setEncours(`${c}-${publicCible}`);
    try {
      await telecharger(c, publicCible, jeton, "/admin/anglais/seances");
    } catch (err) {
      setErreur(err.message);
    } finally {
      setEncours("");
    }
  }

  if (code) {
    return (
      <EditeurSeance
        code={code}
        appeler={appeler}
        erreur={erreur}
        onPdf={(publicCible) => pdf(code, publicCible)}
        onRetour={() => {
          setCode(null);
          charger();
        }}
      />
    );
  }

  const enAttente = seances?.filter((s) => s.statut === "soumis").length ?? 0;
  return (
    <section className="carte">
      <p className="doux">
        Chaque séance a une version courante et, une fois validée par un validateur, une version publiée : seule celle-ci est ouverte
        aux élèves. Modifier une séance validée crée une nouvelle version en brouillon ; l'ancienne reste publiée jusqu'à la
        validation de la nouvelle. L'auteur d'une version ne peut pas la valider.
      </p>
      {seances && <p>{enAttente} séance(s) en attente de validation.</p>}
      <Erreur message={erreur} />
      {seances === null && <p className="doux">Chargement…</p>}
      {seances?.length > 0 && (
        <div className="tableau-defilant">
          <table>
            <thead>
              <tr>
                <th>Code</th>
                <th>Titre</th>
                <th>Version courante</th>
                <th>Publiée</th>
                <th className="nombre">Actions</th>
              </tr>
            </thead>
            <tbody>
              {seances.map((s) => (
                <tr key={s.code}>
                  <td>
                    <code>{s.code}</code>
                  </td>
                  <td>{s.titre}</td>
                  <td>
                    v{s.version} <StatutSeance statut={s.statut} />
                    {s.motif_refus && <p className="petit">Motif : {s.motif_refus}</p>}
                  </td>
                  <td>{s.version_publiee ? `v${s.version_publiee}` : <span className="doux">non</span>}</td>
                  <td className="nombre">
                    <div className="actions">
                      <button className="petit" onClick={() => setCode(s.code)} aria-label={`Modifier ${s.code}`}>
                        Modifier
                      </button>
                      {[["eleve", "Élève"], ["animateur", "Animateur"]].map(([publicCible, libelle]) => (
                        <button
                          key={publicCible}
                          className="secondaire petit"
                          disabled={!!encours}
                          onClick={() => pdf(s.code, publicCible)}
                          aria-label={`PDF ${libelle.toLowerCase()} ${s.code}`}
                        >
                          {encours === `${s.code}-${publicCible}` ? "…" : libelle}
                        </button>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function Champ({ id, libelle, valeur, onChange, multiligne = false, rows = 3 }) {
  return (
    <>
      <label htmlFor={id}>{libelle}</label>
      {multiligne ? (
        <textarea id={id} rows={rows} value={valeur ?? ""} onChange={(e) => onChange(e.target.value)} />
      ) : (
        <input id={id} value={valeur ?? ""} onChange={(e) => onChange(e.target.value)} />
      )}
    </>
  );
}

function EditeurSeance({ code, appeler, erreur, onPdf, onRetour }) {
  const [seance, setSeance] = useState(null);
  const [v, setV] = useState(null); // { contenu, cahier, quiz } en cours d'édition
  const [modifie, setModifie] = useState(false);
  const [message, setMessage] = useState(null);

  const recevoir = useCallback((s) => {
    setSeance(s);
    setV(structuredClone({ contenu: s.contenu, cahier: s.cahier, quiz: s.quiz }));
    setModifie(false);
  }, []);

  useEffect(() => {
    appeler(`/admin/anglais/seances/${encodeURIComponent(code)}`).then(recevoir, () => {});
  }, [appeler, code, recevoir]);

  if (!v) return <p className="doux">Chargement…</p>;

  /** Modifie une valeur à un chemin (ex. ["cahier", "grammar", "rule"]) sur une copie. */
  function maj(chemin, valeur) {
    setV((ancien) => {
      const copie = structuredClone(ancien);
      let o = copie;
      for (const cle of chemin.slice(0, -1)) o = o[cle];
      o[chemin.at(-1)] = valeur;
      return copie;
    });
    setModifie(true);
    setMessage(null);
  }

  async function enregistrer() {
    try {
      recevoir(await appeler(`/admin/anglais/seances/${code}`, { methode: "PUT", corps: v }));
      setMessage("Enregistré en brouillon. Soumettez-le pour validation quand il est prêt.");
    } catch {
      // erreur déjà affichée (contenu incomplet, par exemple)
    }
  }

  async function action(chemin, corps, texte) {
    try {
      await appeler(`/admin/anglais/seances/${code}/${chemin}`, { methode: "POST", corps });
      recevoir(await appeler(`/admin/anglais/seances/${code}`));
      setMessage(texte);
    } catch {
      // erreur déjà affichée
    }
  }

  const { contenu, cahier, quiz } = v;
  const total = contenu.steps.reduce((t, e) => t + (Number(e.duration_minutes) || 0), 0);
  const etape = (i, cle, valeur) =>
    maj(["contenu", "steps"], contenu.steps.map((e, k) => (k === i ? { ...e, [cle]: valeur } : e)));

  return (
    <section className="editeur-anglais">
      <div className="actions">
        <button className="secondaire" onClick={() => (!modifie || window.confirm("Abandonner les modifications ?")) && onRetour()}>
          ← Toutes les séances
        </button>
      </div>
      <div className="carte">
        <h2>
          {code} · v{seance.version} <StatutSeance statut={seance.statut} />
        </h2>
        <p className="doux">
          {seance.version_publiee
            ? `Version publiée : v${seance.version_publiee}. Enregistrer une séance validée crée une nouvelle version.`
            : "Aucune version publiée : les élèves ne voient pas encore cette séance."}
          {seance.motif_refus && ` Refusée : ${seance.motif_refus}`}
        </p>
        {message && (
          <p className="succes" role="status">
            {message}
          </p>
        )}
        <Erreur message={erreur} />
        <div className="actions">
          <button onClick={enregistrer} disabled={!modifie}>
            Enregistrer
          </button>
          {["brouillon", "refuse"].includes(seance.statut) && (
            <button className="secondaire" disabled={modifie} onClick={() => action("soumettre", undefined, "Soumise aux validateurs.")}>
              Soumettre pour validation
            </button>
          )}
          <button className="secondaire" disabled={modifie} onClick={() => onPdf("eleve")}>
            PDF élève
          </button>
          <button className="secondaire" disabled={modifie} onClick={() => onPdf("animateur")}>
            PDF animateur
          </button>
        </div>
        {seance.statut === "soumis" && !modifie && (
          <>
            <h3>Décision</h3>
            <Decision
              onValider={() => action("valider", undefined, "Version validée : elle est ouverte aux élèves.")}
              onRefuser={(motif) => action("refuser", { motif }, "Version refusée.")}
            />
          </>
        )}
      </div>

      <div className="carte">
        <fieldset>
          <legend>Séance</legend>
          <Champ id="ed-titre" libelle="Titre" valeur={contenu.title} onChange={(x) => maj(["contenu", "title"], x)} />
          <Champ id="ed-objectif" libelle="Objectif" valeur={contenu.objective} onChange={(x) => maj(["contenu", "objective"], x)} multiligne rows={2} />
          <Champ id="ed-accroche" libelle="Accroche (hook)" valeur={cahier.hook} onChange={(x) => maj(["cahier", "hook"], x)} />
        </fieldset>

        <fieldset>
          <legend>Déroulé : {total} minutes sur 90</legend>
          {contenu.steps.map((e, i) => (
            <div key={i} className="carte">
              <div className="ligne-edition">
                <Champ id={`ed-etape-${i}`} libelle={`Étape ${i + 1}`} valeur={e.title} onChange={(x) => etape(i, "title", x)} />
                <div>
                  <label htmlFor={`ed-duree-${i}`}>Durée (min)</label>
                  <input
                    id={`ed-duree-${i}`}
                    type="number"
                    min={1}
                    max={90}
                    value={e.duration_minutes}
                    onChange={(ev) => etape(i, "duration_minutes", Number(ev.target.value))}
                  />
                </div>
              </div>
              <Champ id={`ed-eleve-${i}`} libelle="Consigne élève" valeur={e.student_instruction} onChange={(x) => etape(i, "student_instruction", x)} multiligne rows={2} />
              <Champ id={`ed-anim-${i}`} libelle="Consigne animateur" valeur={e.facilitator_instruction} onChange={(x) => etape(i, "facilitator_instruction", x)} multiligne rows={2} />
            </div>
          ))}
        </fieldset>

        <fieldset>
          <legend>Fiches A / B / C</legend>
          {contenu.sheets.map((f, i) => (
            <div key={f.track}>
              <Champ
                id={`ed-fiche-${f.track}`}
                libelle={`Fiche ${f.track} : énoncé`}
                valeur={f.student_content}
                onChange={(x) => maj(["contenu", "sheets", i, "student_content"], x)}
                multiligne
              />
              <Champ
                id={`ed-corrige-${f.track}`}
                libelle={`Fiche ${f.track} : corrigé`}
                valeur={f.facilitator_correction}
                onChange={(x) => maj(["contenu", "sheets", i, "facilitator_correction"], x)}
                multiligne
              />
            </div>
          ))}
        </fieldset>

        <fieldset>
          <legend>Vocabulaire (les 6 premiers mots donnent les QCM de vocabulaire)</legend>
          {cahier.vocab.map((mot, i) => (
            <div key={i} className="ligne-edition">
              {["English", "Français", "Exemple"].map((libelle, k) => (
                <input
                  key={libelle}
                  aria-label={`${libelle} ${i + 1}`}
                  placeholder={libelle}
                  value={mot[k] ?? ""}
                  onChange={(e) => maj(["cahier", "vocab", i, k], e.target.value)}
                />
              ))}
              <button className="lien" onClick={() => maj(["cahier", "vocab"], cahier.vocab.filter((_, k) => k !== i))}>
                Retirer
              </button>
            </div>
          ))}
          <button className="secondaire petit" onClick={() => maj(["cahier", "vocab"], [...cahier.vocab, ["", "", ""]])}>
            Ajouter un mot
          </button>
        </fieldset>

        <fieldset>
          <legend>Grammaire et prononciation</legend>
          <Champ id="ed-gram-titre" libelle="Titre" valeur={cahier.grammar.title} onChange={(x) => maj(["cahier", "grammar", "title"], x)} />
          <Champ id="ed-gram-regle" libelle="Règle" valeur={cahier.grammar.rule} onChange={(x) => maj(["cahier", "grammar", "rule"], x)} multiligne />
          <Champ
            id="ed-gram-ex"
            libelle="Exemples (un par ligne)"
            valeur={cahier.grammar.examples.join("\n")}
            onChange={(x) => maj(["cahier", "grammar", "examples"], lignes(x))}
            multiligne
          />
          <Champ id="ed-prononciation" libelle="Say it right!" valeur={cahier.pronunciation} onChange={(x) => maj(["cahier", "pronunciation"], x)} multiligne rows={2} />
          <Champ id="ed-culture" libelle="Did you know?" valeur={cahier.did_you_know} onChange={(x) => maj(["cahier", "did_you_know"], x)} multiligne rows={2} />
          <Champ id="ed-modele" libelle="Texte modèle (Nom: réplique, une par ligne)" valeur={cahier.model} onChange={(x) => maj(["cahier", "model"], x)} multiligne rows={5} />
        </fieldset>

        <fieldset>
          <legend>Écoute</legend>
          <Champ id="ed-ecoute-titre" libelle="Titre" valeur={cahier.listening.title} onChange={(x) => maj(["cahier", "listening", "title"], x)} />
          <Champ id="ed-ecoute-url" libelle="Lien (https)" valeur={cahier.listening.url} onChange={(x) => maj(["cahier", "listening", "url"], x)} />
          <Champ id="ed-ecoute-date" libelle="Lien vérifié le" valeur={cahier.listening.verified_on} onChange={(x) => maj(["cahier", "listening", "verified_on"], x)} />
          {cahier.listening.questions.map((q, i) => (
            <div key={i} className="ligne-edition">
              <input aria-label={`Question d'écoute ${i + 1}`} value={q} onChange={(e) => maj(["cahier", "listening", "questions", i], e.target.value)} />
              <input
                aria-label={`Réponse d'écoute ${i + 1}`}
                value={cahier.listening.answers[i] ?? ""}
                onChange={(e) => maj(["cahier", "listening", "answers", i], e.target.value)}
              />
            </div>
          ))}
          <Champ id="ed-secours" libelle="Script de secours" valeur={cahier.listening.fallback} onChange={(x) => maj(["cahier", "listening", "fallback"], x)} multiligne rows={4} />
        </fieldset>

        <fieldset>
          <legend>Exercices et corrigés</legend>
          {cahier.practice.map((q, i) => (
            <div key={i} className="ligne-edition">
              <input aria-label={`Exercice ${i + 1}`} value={q} onChange={(e) => maj(["cahier", "practice", i], e.target.value)} />
              <input aria-label={`Corrigé ${i + 1}`} value={cahier.practice_answers[i] ?? ""} onChange={(e) => maj(["cahier", "practice_answers", i], e.target.value)} />
            </div>
          ))}
          <Champ id="ed-mission" libelle="Mission finale" valeur={cahier.mission} onChange={(x) => maj(["cahier", "mission"], x)} multiligne rows={2} />
          <Champ
            id="ed-can-do"
            libelle="I can… (une phrase par ligne)"
            valeur={cahier.can_do.join("\n")}
            onChange={(x) => maj(["cahier", "can_do"], lignes(x))}
            multiligne
          />
          <Champ id="ed-memoire" libelle="Remember for next time" valeur={cahier.memory} onChange={(x) => maj(["cahier", "memory"], x)} multiligne rows={2} />
        </fieldset>

        <fieldset>
          <legend>QCM de grammaire (corrigés automatiquement)</legend>
          {quiz.map((q, i) => (
            <div key={i} className="carte">
              <Champ id={`ed-qcm-${i}`} libelle={`QCM ${i + 1} : question`} valeur={q.question} onChange={(x) => maj(["quiz", i, "question"], x)} />
              {q.choix.map((c, j) => (
                <div key={j} className="ligne-edition">
                  <input aria-label={`QCM ${i + 1} choix ${j + 1}`} value={c} onChange={(e) => maj(["quiz", i, "choix", j], e.target.value)} />
                  <label className="case">
                    <input type="radio" name={`bonne-${i}`} checked={q.reponse === j} onChange={() => maj(["quiz", i, "reponse"], j)} />
                    Bonne réponse
                  </label>
                </div>
              ))}
              <Champ id={`ed-qcm-expl-${i}`} libelle="Explication" valeur={q.explication} onChange={(x) => maj(["quiz", i, "explication"], x)} />
              <button className="lien" onClick={() => maj(["quiz"], quiz.filter((_, k) => k !== i))}>
                Retirer ce QCM
              </button>
            </div>
          ))}
          <button className="secondaire petit" onClick={() => maj(["quiz"], [...quiz, structuredClone(QCM_VIDE)])}>
            Ajouter un QCM
          </button>
          <p className="aide">
            S'y ajoutent {seance.quiz_vocabulaire.length} QCM de vocabulaire tirés du tableau de mots, par exemple :{" "}
            {seance.quiz_vocabulaire[0]?.question}
          </p>
        </fieldset>
        <div className="actions">
          <button onClick={enregistrer} disabled={!modifie}>
            Enregistrer
          </button>
        </div>
      </div>

      <div className="carte">
        <h3>Historique des versions</h3>
        <Historique versions={seance.historique} />
      </div>
    </section>
  );
}
