// Issue #98 — Intégration du premier dossier Français 3e en DEV (Claude)
import { useCallback, useEffect, useState } from "react";
import { api, telechargerFichier } from "../api.js";
import { Erreur, Onglets } from "../composants.jsx";
import { AccesReserve, CLE_COMPTE, ConnexionEnseignant, NouveauMotDePasse, PageSimple } from "../enseignant/EspaceEnseignant.jsx";
import { useApi } from "../enseignant/useApi.js";
import { Decision, Historique as HistoriqueAnglais, STATUTS, StatutSeance as StatutAnglais } from "../anglais/ValidationAnglais.jsx";
import { Maths } from "../maths.jsx";
import EditionDossier from "./EditionDossier.jsx";
import PartieEleve from "./PartieEleve.jsx";
import SuiviFrancais from "./SuiviFrancais.jsx";
import { ecrire, lire } from "../stockage.js";
import { CadreApplication, EntetePage, Vide } from "../ui/Cadre.jsx";
import Icone from "../ui/Icone.jsx";

const MARQUE = "Français";

// Issue #217 : une version refusée s'affiche « À corriger » ; la version validée déjà diffusée reste servie.
export const STATUTS_FRANCAIS = { ...STATUTS, refuse: "À corriger" };

function StatutSeance({ statut }) {
  return <StatutAnglais statut={statut} libelle={STATUTS_FRANCAIS[statut]} />;
}

function Historique({ versions }) {
  return <HistoriqueAnglais versions={versions} libelles={STATUTS_FRANCAIS} />;
}
const SANS_DOSSIER = "Aucun dossier de français accessible avec vos habilitations.";

/**
 * Issue #212 : cause réelle d'une liste vide ou d'un refus, d'après l'état de l'instance (administrateurs seuls).
 * Renvoie une liste de phrases, vide si l'état n'explique rien.
 */
export function causesAbsence(etat) {
  if (!etat) return [];
  const causes = [];
  const actifs = etat.domaines.filter((d) => d.actif);
  const enAttente = etat.domaines.filter((d) => !d.actif && d.dossiers > 0);
  if (etat.dossiers === 0) {
    causes.push(
      "Aucun dossier de français n'est importé dans la base de cette instance. L'import est une opération d'exploitation " +
        "(docs/francais/INTEGRATION-DEV.md, étape 3) : il n'est fait ni au démarrage, ni au déploiement.",
    );
  }
  for (const d of enAttente) {
    causes.push(
      `${d.dossiers} dossier(s) rangé(s) dans « ${d.libelle} », qui n'est pas activé pour la préparation. ` +
        "L'activer dans Administration → Configuration → Domaines, sans l'ouvrir au public.",
    );
  }
  if (actifs.length === 0 && enAttente.length === 0) {
    causes.push("Aucun domaine de français n'est activé pour la préparation (Administration → Configuration → Domaines).");
  }
  return causes;
}

function Causes({ causes }) {
  if (causes.length === 0) return null;
  return (
    <div className="carte" role="status">
      <p>
        <strong>Diagnostic administrateur</strong>
      </p>
      <ul>
        {causes.map((c) => (
          <li key={c}>{c}</li>
        ))}
      </ul>
    </div>
  );
}

// Issue #217 : session d'administration (30 min, second facteur) ouverte dans le même onglet, acceptée par l'API.
const CLE_ADMIN = "pkp.admin";

export function sessionAdmin() {
  const a = lire(CLE_ADMIN);
  return a?.jeton && a.expire_le >= Date.now() ? { jeton: a.jeton, nom: a.nom, mdp_provisoire: false, admin: true } : null;
}

/** Espace adulte du français : préparation, validation et ouverture aux classes (#98, #212, même circuit que l'anglais). */
export default function EspaceFrancais() {
  // La session professeur d'abord ; sinon celle de l'administration, sans nouvelle connexion (#217).
  const [compte, setCompte] = useState(() => lire(CLE_COMPTE) ?? sessionAdmin());

  function connecter(nouveau) {
    ecrire(CLE_COMPTE, nouveau);
    setCompte(nouveau);
  }

  function deconnecter() {
    ecrire(compte?.admin ? CLE_ADMIN : CLE_COMPTE, null);
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
  const [causes, setCauses] = useState([]);
  const [page, setPage] = useState("dossiers");
  // File de validation (#212, comme l'anglais) : visible des seuls validateurs ; l'API le revérifie.
  const [validateur, setValidateur] = useState(false);

  // Lu sans passer par `appeler` : un refus (professeur) est attendu ici et ne doit afficher aucune erreur.
  const expliquer = useCallback(async () => {
    try {
      setCauses(causesAbsence(await api("/francais/etat", { jeton: compte.jeton })));
    } catch {
      setCauses([]);
    }
  }, [compte.jeton]);

  const charger = useCallback(async () => {
    try {
      const liste = await appeler("/francais/dossiers");
      setDossiers(liste);
      if (liste.length === 0) expliquer();
    } catch (err) {
      if (err.status === 403) {
        setRefus(true);
        expliquer();
      }
    }
  }, [appeler, expliquer]);

  useEffect(() => {
    charger();
  }, [charger]);

  useEffect(() => {
    api("/francais/validation", { jeton: compte.jeton }).then(
      () => setValidateur(true),
      () => setValidateur(false),
    );
  }, [compte.jeton]);

  if (refus) {
    return (
      <PageSimple marque={MARQUE}>
        <AccesReserve titre="Espace réservé aux adultes habilités en français" compte={compte} onDeconnexion={onDeconnexion} />
        <Causes causes={causes} />
      </PageSimple>
    );
  }

  return (
    <CadreApplication
      espace="Français"
      marque={MARQUE}
      liens={[
        { vers: "/francais", libelle: "Dossiers et validation", icone: "cours" },
        ...(compte.admin ? [{ vers: "/admin", libelle: "Retour à l'administration", icone: "bouclier" }] : []),
      ]}
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
      <EntetePage titre="Dossiers de français" fil="Préparation, validation et ouverture aux classes" />
      <p className="carte" role="note">
        Seule la <strong>version validée</strong> d'un dossier est lue par les élèves, et seulement dans les classes auxquelles
        vous l'ouvrez. Une révision soumise ou refusée ne la remplace pas. Seul le quiz est corrigé par la plateforme ; les
        réponses rédigées relèvent d'un retour du professeur, sans note ni taux de maîtrise.
      </p>
      <Onglets
        valeur={page}
        onChange={(p) => {
          setPage(p);
          setChoisi(null);
          if (p === "dossiers") charger();
        }}
        options={[
          ["dossiers", "Dossiers"],
          ["suivi", "Suivi des classes"],
          ...(validateur ? [["validation", "Validation"]] : []),
        ]}
      />
      <Erreur message={erreur} />
      {page === "validation" ? (
        <ValidationFrancais appeler={appeler} />
      ) : page === "suivi" ? (
        <SuiviFrancais appeler={appeler} jeton={compte.jeton} />
      ) : dossiers === null ? (
        <p className="doux">Chargement…</p>
      ) : dossiers.length === 0 ? (
        <>
          <Vide>{SANS_DOSSIER}</Vide>
          <Causes causes={causes} />
        </>
      ) : choisi ? (
        <Detail
          code={choisi}
          admin={Boolean(compte.admin || compte.role === "admin")}
          jeton={compte.jeton}
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
                <StatutSeance statut={d.statut} />{" "}
                <span className="doux petit">
                  {d.version_validee ? `Version validée : v${d.version_validee}` : "Jamais validé"} ·{" "}
                  {d.visible_eleves ? `ouvert à ${d.classes_ouvertes} classe(s)` : "Non visible des élèves"}
                </span>
              </p>
              {d.statut === "refuse" && d.motif_refus && <p className="petit">Motif : {d.motif_refus}</p>}
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

/** Version affichée : la validée (celle des élèves), sinon la courante, NON VALIDÉE, comme en anglais. */
function VersionAffichee({ donnees }) {
  if (!donnees) return null;
  return donnees.validee ? (
    <p className="doux petit" role="status">
      Version validée v{donnees.version_affichee} : celle que lisent les élèves des classes ouvertes.
      {donnees.version !== donnees.version_affichee && ` La v${donnees.version} est en relecture (${donnees.statut}).`}
    </p>
  ) : (
    <p className="avertissement petit" role="status">
      NON VALIDÉ — version v{donnees.version_affichee}, jamais servie aux élèves tant qu'un validateur ne l'a pas validée.
    </p>
  );
}

/** Issue #217 : export PDF de la version affichée ; la version élève ne contient aucun corrigé (contrôlé par l'API). */
function ExportPdf({ code, jeton }) {
  const [erreur, setErreur] = useState(null);
  async function exporter(public_) {
    setErreur(null);
    try {
      await telechargerFichier(`/francais/dossiers/${encodeURIComponent(code)}/pdf/${public_}`, jeton, `${code}-${public_}.pdf`);
    } catch (err) {
      setErreur(err.message);
    }
  }
  return (
    <div className="actions">
      <button className="secondaire" onClick={() => exporter("eleve")}>
        PDF élève (sans corrigé)
      </button>
      <button className="secondaire" onClick={() => exporter("professeur")}>
        PDF professeur (avec corrigés)
      </button>
      <Erreur message={erreur} />
    </div>
  );
}

function Detail({ code, admin, jeton, appeler, onRetour }) {
  const [onglet, setOnglet] = useState("eleve");
  const [donnees, setDonnees] = useState({});

  useEffect(() => {
    if (onglet === "modifier") return;
    appeler(`/francais/dossiers/${code}/${onglet}`).then(
      (r) => setDonnees((d) => ({ ...d, [onglet]: r })),
      () => {},
    );
  }, [appeler, code, onglet]);

  const courant = donnees[onglet];
  const entete = donnees.eleve ?? donnees.professeur;
  return (
    <section>
      <button className="lien" onClick={onRetour}>
        ← Tous les dossiers
      </button>
      <ExportPdf code={code} jeton={jeton} />
      <Onglets
        valeur={onglet}
        onChange={setOnglet}
        options={[
          ["eleve", "Aperçu élève"],
          ["professeur", "Supports professeur (corrigés)"],
          ["classes", "Mes classes"],
          ["historique", "Versions et validation"],
          ...(admin ? [["modifier", "Modifier"]] : []),
        ]}
      />
      {onglet === "modifier" ? (
        <EditionDossier code={code} appeler={appeler} onEnregistre={() => setDonnees({})} />
      ) : !courant ? (
        <p className="doux">Chargement…</p>
      ) : onglet === "eleve" ? (
        <>
          <VersionAffichee donnees={courant} />
          <PartieEleve eleve={courant.eleve} apercu />
        </>
      ) : onglet === "professeur" ? (
        <>
          <VersionAffichee donnees={courant} />
          <SupportsProfesseur professeur={courant.professeur} />
        </>
      ) : onglet === "classes" ? (
        <OuvertureClasses
          code={code}
          classes={courant}
          validee={entete ? entete.version_validee !== null : true}
          appeler={appeler}
          onChange={(r) => setDonnees((d) => ({ ...d, classes: r }))}
        />
      ) : (
        <>
          <Historique versions={courant} />
          <p className="doux petit">
            La relecture et la décision (valider, ou refuser avec motif) se font dans l'onglet « Validation », réservé aux
            validateurs habilités, jamais par l'auteur de la version.
          </p>
        </>
      )}
    </section>
  );
}

/** Ouvrir le dossier à ses classes du même niveau : seule la version validée est servie aux élèves (#212). */
function OuvertureClasses({ code, classes, validee, appeler, onChange }) {
  async function basculer(c) {
    try {
      onChange(await appeler(`/francais/dossiers/${code}/classes/${c.id}`, { methode: c.ouvert ? "DELETE" : "PUT" }));
    } catch {
      // erreur déjà affichée
    }
  }
  if (classes.length === 0) {
    return <Vide>Vous n'avez aucune classe de français de ce niveau.</Vide>;
  }
  return (
    <div className="carte">
      {!validee && (
        <p className="doux">Aucune version de ce dossier n'est validée : il ne peut pas encore être ouvert aux élèves.</p>
      )}
      <ul className="liste-simple">
        {classes.map((c) => (
          <li key={c.id}>
            <strong>{c.code}</strong> · {c.niveau} ·{" "}
            {c.ouvert ? <span className="succes">Ouvert</span> : <span className="doux">Fermé</span>}
            {!c.acces_eleves && <p className="doux petit">Élèves sans accès pour l'instant : {c.motif_acces}</p>}
            <div className="actions">
              <button className={c.ouvert ? "secondaire" : undefined} disabled={!c.ouvert && !validee} onClick={() => basculer(c)}>
                {c.ouvert ? "Retirer à cette classe" : "Ouvrir à cette classe"}
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** File de validation, comme l'anglais : versions soumises, relues en entier, validées ou refusées avec motif. */
function ValidationFrancais({ appeler }) {
  const [liste, setListe] = useState(null);
  const [code, setCode] = useState(null);
  const [dossier, setDossier] = useState(null);
  const [message, setMessage] = useState(null);

  const charger = useCallback(() => appeler("/francais/validation").then(setListe, () => {}), [appeler]);

  useEffect(() => {
    charger();
  }, [charger]);

  useEffect(() => {
    setDossier(null);
    if (code) appeler(`/francais/validation/${encodeURIComponent(code)}`).then(setDossier, () => {});
  }, [appeler, code]);

  async function decider(chemin, corps, texte) {
    setMessage(null);
    try {
      await appeler(`/francais/validation/${code}/${chemin}`, { methode: "POST", corps });
      setMessage(texte);
      setCode(null);
      await charger();
    } catch {
      // erreur déjà affichée
    }
  }

  const choisi = liste?.find((d) => d.code === code);
  return (
    <section>
      <div className="carte">
        <p className="doux">
          Dossiers soumis à relecture. Une fois validée, la version devient celle que lisent les élèves des classes auxquelles le
          dossier est ouvert. Vous ne pouvez pas valider un contenu dont vous êtes l'auteur.
        </p>
        {message && (
          <p className="succes" role="status">
            {message}
          </p>
        )}
        {liste === null && <p className="doux">Chargement…</p>}
        {liste?.length === 0 && <p className="doux">Aucun dossier en attente de validation.</p>}
        {liste?.length > 0 && (
          <>
            <label htmlFor="dossier-a-valider">Dossier à relire ({liste.length} en attente)</label>
            <select id="dossier-a-valider" value={code ?? ""} onChange={(e) => setCode(e.target.value || null)}>
              <option value="">Choisir…</option>
              {liste.map((d) => (
                <option key={d.code} value={d.code}>
                  {d.code} · {d.titre} · v{d.version}
                  {d.est_auteur ? " (vous en êtes l'auteur)" : ""}
                </option>
              ))}
            </select>
          </>
        )}
      </div>
      {dossier && choisi && (
        <>
          <div className="carte">
            <h2>
              {dossier.code} · {dossier.titre} <StatutSeance statut={dossier.statut} />
            </h2>
            <p className="doux">
              Version {dossier.version_affichee} · auteur : {dossier.auteur ?? "import du dépôt"}
              {dossier.version_validee ? ` · version diffusée actuellement : v${dossier.version_validee}` : " · jamais validée"}
            </p>
            <Decision
              interdit={choisi.est_auteur && "Vous êtes l'auteur de cette version : un autre validateur doit la valider."}
              onValider={() => decider("valider", undefined, `${dossier.code} validé : les classes ouvertes lisent cette version.`)}
              onRefuser={(motif) => decider("refuser", { motif }, `${dossier.code} refusé, motif enregistré.`)}
            />
          </div>
          <PartieEleve eleve={dossier.eleve} apercu />
          <SupportsProfesseur professeur={dossier.professeur} />
          <div className="carte">
            <h3>Historique</h3>
            <Historique versions={dossier.historique} />
          </div>
        </>
      )}
    </section>
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
      {(p.quiz ?? []).length > 0 && (
        <section>
          <h3>Quiz : réponses</h3>
          <ol>
            {p.quiz.map((q, i) => (
              <li key={i}>
                {q.question} <strong>→ {q.choix[q.reponse]}</strong> <span className="doux">{q.explication}</span>
              </li>
            ))}
          </ol>
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
