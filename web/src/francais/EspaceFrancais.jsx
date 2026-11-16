// Issue #98 — Intégration du premier dossier Français 3e en DEV (Claude)
import { useCallback, useEffect, useState } from "react";
import { Erreur, Onglets } from "../composants.jsx";
import { AccesReserve, CLE_COMPTE, ConnexionEnseignant, NouveauMotDePasse, PageSimple } from "../enseignant/EspaceEnseignant.jsx";
import { useApi } from "../enseignant/useApi.js";
import { Decision, Historique, StatutSeance } from "../anglais/ValidationAnglais.jsx";
import { Maths } from "../maths.jsx";
import { ecrire, lire } from "../stockage.js";
import { CadreApplication, EntetePage, Vide } from "../ui/Cadre.jsx";
import Icone from "../ui/Icone.jsx";

const MARQUE = "Français";

/** Espace de préparation du français : adultes habilités seulement ; rien n'y est ouvert aux élèves (#98). */
export default function EspaceFrancais() {
  const [compte, setCompte] = useState(() => lire(CLE_COMPTE));

  function connecter(nouveau) {
    ecrire(CLE_COMPTE, nouveau);
    setCompte(nouveau);
  }

  function deconnecter() {
    ecrire(CLE_COMPTE, null);
    setCompte(null);
  }

  if (!compte) {
    return (
      <PageSimple marque={MARQUE}>
        <ConnexionEnseignant titre="Connexion — Français (préparation)" onConnexion={connecter} />
      </PageSimple>
    );
  }
  if (compte.mdp_provisoire) {
    return (
      <PageSimple marque={MARQUE}>
        <NouveauMotDePasse compte={compte} onChange={connecter} onAnnuler={deconnecter} retour="/francais" />
      </PageSimple>
    );
  }
  return <Dossiers compte={compte} onDeconnexion={deconnecter} />;
}

function Dossiers({ compte, onDeconnexion }) {
  const { appeler, erreur } = useApi(compte.jeton, onDeconnexion);
  const [dossiers, setDossiers] = useState(null);
  const [refus, setRefus] = useState(false);
  const [choisi, setChoisi] = useState(null);

  const charger = useCallback(async () => {
    try {
      setDossiers(await appeler("/francais/dossiers"));
    } catch (err) {
      if (err.status === 403) setRefus(true);
    }
  }, [appeler]);

  useEffect(() => {
    charger();
  }, [charger]);

  if (refus) {
    return (
      <PageSimple marque={MARQUE}>
        <AccesReserve titre="Espace réservé aux adultes habilités en français" compte={compte} onDeconnexion={onDeconnexion} />
      </PageSimple>
    );
  }

  return (
    <CadreApplication
      espace="Français — préparation"
      marque={MARQUE}
      liens={[{ vers: "/francais", libelle: "Dossiers", icone: "cours" }]}
      cheminActif="/francais"
      pied={
        <>
          <div className="compte">{compte.nom}</div>
          <button className="nav" onClick={onDeconnexion}>
            <Icone nom="sortie" /> Se déconnecter
          </button>
        </>
      }
    >
      <EntetePage titre="Dossiers de français" fil="Préparation par l'équipe" />
      <p className="carte" role="note">
        Contenus en préparation : <strong>non publiés aux élèves</strong>. Les réponses sont rédigées et relèvent d'un retour
        du professeur ; la plateforme ne les corrige pas, ne les note pas et ne calcule aucun taux de maîtrise.
      </p>
      <Erreur message={erreur} />
      {dossiers === null ? (
        <p className="doux">Chargement…</p>
      ) : dossiers.length === 0 ? (
        <Vide>Aucun dossier de français accessible avec vos habilitations.</Vide>
      ) : choisi ? (
        <Detail
          code={choisi}
          appeler={appeler}
          onRetour={() => {
            setChoisi(null);
            charger();
          }}
        />
      ) : (
        <ul className="liste-simple">
          {dossiers.map((d) => (
            <li key={d.code} className="carte">
              <h2>{d.titre}</h2>
              <p className="doux petit">
                {d.code} · {d.libelle_domaine} · {d.niveau} · {d.cible} · v{d.version} · {d.nb_questions} questions
              </p>
              <p>
                <StatutSeance statut={d.statut} /> <span className="doux petit">Non visible des élèves</span>
              </p>
              <p className="petit">
                Rédaction : {d.attribution.redaction} (#{d.attribution.redaction_issue}) · intégration :{" "}
                {d.attribution.integration} (#{d.attribution.integration_issue})
              </p>
              <button onClick={() => setChoisi(d.code)}>Ouvrir</button>
            </li>
          ))}
        </ul>
      )}
    </CadreApplication>
  );
}

function Detail({ code, appeler, onRetour }) {
  const [onglet, setOnglet] = useState("eleve");
  const [donnees, setDonnees] = useState({});

  useEffect(() => {
    const chemin = onglet === "historique" ? "historique" : onglet;
    appeler(`/francais/dossiers/${code}/${chemin}`).then(
      (r) => setDonnees((d) => ({ ...d, [onglet]: r })),
      () => {},
    );
  }, [appeler, code, onglet]);

  async function decider(action, motif) {
    const corps = motif ? { motif } : undefined;
    await appeler(`/francais/dossiers/${code}/${action}`, { methode: "POST", corps });
    onRetour();
  }

  const courant = donnees[onglet];
  const entete = donnees.eleve ?? donnees.professeur;
  return (
    <section>
      <button className="lien" onClick={onRetour}>
        ← Tous les dossiers
      </button>
      <Onglets
        valeur={onglet}
        onChange={setOnglet}
        options={[
          ["eleve", "Aperçu élève"],
          ["professeur", "Supports professeur (corrigés)"],
          ["historique", "Versions et validation"],
        ]}
      />
      {!courant ? (
        <p className="doux">Chargement…</p>
      ) : onglet === "eleve" ? (
        <ApercuEleve eleve={courant.eleve} />
      ) : onglet === "professeur" ? (
        <SupportsProfesseur professeur={courant.professeur} />
      ) : (
        <>
          <Historique versions={courant} />
          {entete && (
            <Decision
              interdit={
                entete.peut_valider
                  ? null
                  : "Validation réservée à un validateur habilité Français pour ce niveau, distinct de l'auteur, sur une version soumise."
              }
              onValider={() => decider("valider")}
              onRefuser={(motif) => decider("refuser", motif)}
            />
          )}
        </>
      )}
    </section>
  );
}

function ApercuEleve({ eleve }) {
  return (
    <article className="carte" aria-label="Aperçu de la partie élève">
      <p className="doux petit">Aperçu réservé aux adultes : aucun élève n'accède à ce dossier.</p>
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
            <p className="doux petit">Réponse rédigée : retour du professeur.</p>
          </li>
        ))}
      </ol>
      {eleve.je_verifie && (
        <section>
          <h3>5. Je vérifie</h3>
          <Maths texte={eleve.je_verifie} />
        </section>
      )}
    </article>
  );
}

function SupportsProfesseur({ professeur }) {
  const p = professeur;
  return (
    <article className="carte" aria-label="Supports professeur">
      {p.presentation.map((l) => (
        <p key={l} className="doux petit">
          {l}
        </p>
      ))}
      {p.deroulement && (
        <section>
          <h3>{p.deroulement.titre}</h3>
          <ul>
            {p.deroulement.etapes.map((e) => (
              <li key={e.activite}>
                <strong>{e.duree}</strong> — {e.activite} <span className="doux">({e.observation})</span>
              </li>
            ))}
          </ul>
          {p.deroulement.adaptations.map((l) => (
            <p key={l}>{l}</p>
          ))}
        </section>
      )}
      <h3>Corrigés expliqués</h3>
      {p.principes_correction && <p>{p.principes_correction}</p>}
      {p.questions.map((q) => (
        <section key={q.code}>
          <h4>
            {q.code}. {q.consigne}
          </h4>
          {q.corrige.intitule && <p className="petit">{q.corrige.intitule}</p>}
          {q.corrige.paragraphes.map((para) => (
            <Maths key={para} texte={para} />
          ))}
        </section>
      ))}
      {p.grille && (
        <section>
          <h3>{p.grille.titre}</h3>
          <ul>
            {p.grille.criteres.map((c) => (
              <li key={c.critere}>
                <strong>{c.critere}</strong> ({c.questions}) : {c.indice}
              </li>
            ))}
          </ul>
          {p.grille.consignes.map((l) => (
            <p key={l} className="petit">
              {l}
            </p>
          ))}
        </section>
      )}
      <h3>Contrôle avant utilisation</h3>
      <ul>
        {p.controle_avant_utilisation.map((l) => (
          <li key={l}>{l}</li>
        ))}
      </ul>
      {p.remarques.map((l) => (
        <p key={l} className="petit">
          {l}
        </p>
      ))}
      {p.retour_seance && (
        <section>
          <h3>Retour de séance</h3>
          <Maths texte={p.retour_seance} />
        </section>
      )}
    </article>
  );
}
