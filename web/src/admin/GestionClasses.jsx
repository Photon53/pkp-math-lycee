// Administrateur : gérer une classe de maths (élèves, chapitres ouverts, professeur, suppression) et retrouver
// les enfants des familles, y compris ceux qui ne sont encore inscrits nulle part.
import { useCallback, useEffect, useState } from "react";
import { Erreur, Onglets } from "../composants.jsx";
import { LIBELLES_PARCOURS, NIVEAUX, libelleNiveauParcours } from "../parcours.js";
import AjoutEnfants from "../ui/AjoutEnfants.jsx";
import { Modale, Vide, formaterDate } from "../ui/Cadre.jsx";
import { BarreSelection, CaseLigne, CaseTout, ConfirmationSuppression, useSelection } from "../ui/Selection.jsx";
import { nomComplet } from "./EnfantsFamille.jsx";

const NOM_NIVEAU = Object.fromEntries(NIVEAUX);
/** Libellé court du parcours, pour un tableau : « Excellence et olympiades », sans la précision entre parenthèses. */
export const parcoursCourt = (p) => (LIBELLES_PARCOURS[p] ?? p).split(" (")[0];

// --- Gérer une classe ----------------------------------------------------------------------------------

export function GererClasse({ classe, appeler, onFermer, onChange }) {
  const [vue, setVue] = useState("eleves");
  const [info, setInfo] = useState(classe);

  const recharger = useCallback(async () => {
    try {
      setInfo(await appeler(`/admin/classes/${classe.id}`));
    } catch {
      // erreur affichée par la vue
    }
    onChange();
  }, [appeler, classe.id, onChange]);

  return (
    <Modale titre={`Classe ${info.code}`} onFermer={onFermer} large>
      <p className="doux">
        {libelleNiveauParcours(info.niveau, info.parcours)} · {info.enseignant} · {info.nb_eleves} élève(s) ·{" "}
        {info.nb_chapitres_ouverts} chapitre(s) ouvert(s)
      </p>
      <Onglets
        valeur={vue}
        onChange={setVue}
        options={[
          ["eleves", "Élèves"],
          ["chapitres", "Chapitres ouverts"],
          ["professeur", "Professeur"],
          ["suppression", "Supprimer"],
        ]}
      />
      {vue === "eleves" && <ElevesDeLaClasse classe={info} appeler={appeler} onChange={recharger} />}
      {vue === "chapitres" && <ChapitresDeLaClasse classe={info} appeler={appeler} onChange={recharger} />}
      {vue === "professeur" && <ProfesseurDeLaClasse classe={info} appeler={appeler} onChange={recharger} />}
      {vue === "suppression" && (
        <SuppressionClasse
          classe={info}
          appeler={appeler}
          onSupprimee={() => {
            onChange(`Classe ${info.code} supprimée.`);
            onFermer();
          }}
        />
      )}
    </Modale>
  );
}

function ElevesDeLaClasse({ classe, appeler, onChange }) {
  const [eleves, setEleves] = useState(null);
  const [erreur, setErreur] = useState(null);
  const [message, setMessage] = useState(null);

  const charger = useCallback(
    () => appeler(`/admin/classes/${classe.id}/eleves`).then(setEleves, (err) => setErreur(err.message)),
    [appeler, classe.id],
  );
  useEffect(() => {
    charger();
  }, [charger]);

  const chercher = useCallback((q) => appeler(`/admin/classes/${classe.id}/enfants?q=${encodeURIComponent(q)}`), [appeler, classe.id]);
  const ajouter = (ids) => appeler(`/admin/classes/${classe.id}/enfants`, { methode: "POST", corps: { enfant_ids: ids } });

  async function retirer(e) {
    if (!window.confirm(`Retirer ${e.prenom} de ${classe.code} ? Son travail dans cette classe est effacé ; sa carte et ses autres matières restent.`)) return;
    setErreur(null);
    try {
      await appeler(`/admin/eleves/${e.id}`, { methode: "DELETE" });
      setMessage(`${e.prenom} a été retiré·e de la classe.`);
      await charger();
      onChange();
    } catch (err) {
      setErreur(err.message);
    }
  }

  return (
    <>
      <Erreur message={erreur} />
      {message && <p className="succes" role="status">{message}</p>}
      {eleves === null ? (
        <p className="doux">Chargement…</p>
      ) : eleves.length === 0 ? (
        <p className="doux">Aucun élève inscrit pour l'instant.</p>
      ) : (
        <div className="tableau-defilant">
          <table>
            <thead>
              <tr>
                <th>Élève</th>
                <th>Identifiant</th>
                <th className="nombre">Réponses</th>
                <th className="nombre">Réussite</th>
                <th>
                  <span className="visuellement-cache">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {eleves.map((e) => (
                <tr key={e.id}>
                  <td><strong>{e.prenom}</strong></td>
                  <td>{e.identifiant ? <code>{e.identifiant}</code> : <span className="doux">—</span>}</td>
                  <td className="nombre">{e.nb_reponses}</td>
                  <td className="nombre">{e.taux_reussite == null ? "—" : `${Math.round(e.taux_reussite * 100)} %`}</td>
                  <td className="nombre">
                    <button className="secondaire petit" onClick={() => retirer(e)} aria-label={`Retirer ${e.prenom}`}>
                      Retirer
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <AjoutEnfants
        chercher={chercher}
        ajouter={ajouter}
        onAjoutes={() => {
          charger();
          onChange();
        }}
      />
    </>
  );
}

function ChapitresDeLaClasse({ classe, appeler, onChange }) {
  const [chapitres, setChapitres] = useState(null);
  const [coches, setCoches] = useState(new Set());
  const [message, setMessage] = useState(null);
  const [erreur, setErreur] = useState(null);

  const appliquer = useCallback((liste) => {
    setChapitres(liste);
    setCoches(new Set(liste.filter((c) => c.propose).map((c) => c.id)));
  }, []);
  useEffect(() => {
    appeler(`/admin/classes/${classe.id}/chapitres`).then(appliquer, (err) => setErreur(err.message));
  }, [appeler, appliquer, classe.id]);

  function basculer(id) {
    setMessage(null);
    setCoches((avant) => {
      const apres = new Set(avant);
      apres.has(id) ? apres.delete(id) : apres.add(id);
      return apres;
    });
  }

  async function enregistrer() {
    setErreur(null);
    try {
      appliquer(await appeler(`/admin/classes/${classe.id}/chapitres`, { methode: "PUT", corps: { chapitre_ids: [...coches] } }));
      setMessage(`${coches.size} chapitre(s) ouvert(s) aux élèves de ${classe.code}.`);
      onChange();
    } catch (err) {
      setErreur(err.message);
    }
  }

  const modifie = chapitres !== null && chapitres.some((c) => c.propose !== coches.has(c.id));
  return (
    <>
      <Erreur message={erreur} />
      {chapitres === null ? (
        <p className="doux">Chargement…</p>
      ) : chapitres.length === 0 ? (
        <p className="doux">Aucun chapitre n'existe encore pour ce niveau et ce parcours.</p>
      ) : (
        <fieldset className="choix-chapitres">
          <legend>Programme de la classe</legend>
          {chapitres.map((c) => (
            <label key={c.id} className="case">
              <input type="checkbox" checked={coches.has(c.id)} onChange={() => basculer(c.id)} />
              {c.ordre}. {c.titre}
              <span className="doux">{c.nb_questions === 0 ? " — pas encore de questions" : ` — ${c.nb_questions} question(s)`}</span>
            </label>
          ))}
        </fieldset>
      )}
      <div className="actions">
        <button onClick={enregistrer} disabled={!modifie}>Enregistrer les chapitres</button>
      </div>
      {message && <p className="succes" role="status">{message}</p>}
    </>
  );
}

function ProfesseurDeLaClasse({ classe, appeler, onChange }) {
  const [professeurs, setProfesseurs] = useState([]);
  const [choix, setChoix] = useState(String(classe.enseignant_id));
  const [message, setMessage] = useState(null);
  const [erreur, setErreur] = useState(null);

  useEffect(() => {
    appeler("/admin/enseignants").then((liste) => setProfesseurs(liste.filter((p) => p.actif && p.enseigne_maths !== false)), () => {});
  }, [appeler]);

  async function enregistrer(e) {
    e.preventDefault();
    setErreur(null);
    try {
      const c = await appeler(`/admin/classes/${classe.id}`, { methode: "PATCH", corps: { enseignant_id: Number(choix) } });
      setMessage(`${c.code} est maintenant suivie par ${c.enseignant}.`);
      onChange();
    } catch (err) {
      setErreur(err.message);
    }
  }

  return (
    <form onSubmit={enregistrer}>
      <label htmlFor="gc-prof">Professeur de mathématiques</label>
      <select id="gc-prof" value={choix} onChange={(e) => setChoix(e.target.value)}>
        {professeurs.map((p) => (
          <option key={p.id} value={p.id}>{p.nom}</option>
        ))}
      </select>
      <p className="aide">Les élèves, leur travail et les chapitres ouverts restent dans la classe.</p>
      <Erreur message={erreur} />
      {message && <p className="succes" role="status">{message}</p>}
      <div className="actions">
        <button type="submit" disabled={choix === String(classe.enseignant_id)}>Changer de professeur</button>
      </div>
    </form>
  );
}

function SuppressionClasse({ classe, appeler, onSupprimee }) {
  const [saisie, setSaisie] = useState("");
  const [erreur, setErreur] = useState(null);

  async function supprimer(e) {
    e.preventDefault();
    setErreur(null);
    try {
      await appeler(`/admin/classes/${classe.id}?${new URLSearchParams({ confirmation: saisie })}`, { methode: "DELETE" });
      onSupprimee();
    } catch (err) {
      setErreur(err.message);
    }
  }

  return (
    <form onSubmit={supprimer}>
      <p>
        La classe, ses {classe.nb_eleves} inscription(s) et tout le travail fait dans cette classe (séances, réponses) seront
        effacés. Les enfants gardent leur carte, leur famille et leurs autres classes.
      </p>
      <label htmlFor="gc-confirmation">Pour confirmer, saisissez le code de la classe : {classe.code}</label>
      <input id="gc-confirmation" value={saisie} onChange={(e) => setSaisie(e.target.value)} autoComplete="off" />
      <Erreur message={erreur} />
      <div className="actions">
        <button type="submit" className="danger" disabled={saisie.trim().toUpperCase() !== classe.code}>
          Supprimer la classe
        </button>
      </div>
    </form>
  );
}

// --- Enfants des familles ----------------------------------------------------------------------------------

export function ListeEnfants({ appeler, erreur }) {
  const [q, setQ] = useState("");
  const [niveau, setNiveau] = useState("");
  const [sansClasse, setSansClasse] = useState(false);
  const [enfants, setEnfants] = useState(null);
  const [classes, setClasses] = useState([]);
  const [message, setMessage] = useState(null);
  const [echec, setEchec] = useState(null);
  const [suppression, setSuppression] = useState(false);
  const selection = useSelection();

  const charger = useCallback(() => {
    const params = new URLSearchParams();
    if (q.trim()) params.set("q", q.trim());
    if (niveau) params.set("niveau", niveau);
    if (sansClasse) params.set("sans_classe", "true");
    return appeler(`/admin/enfants?${params}`).then(setEnfants, () => {});
  }, [appeler, q, niveau, sansClasse]);

  useEffect(() => {
    const t = setTimeout(charger, 250);
    return () => clearTimeout(t);
  }, [charger]);
  useEffect(() => {
    appeler("/admin/classes").then(setClasses, () => {});
  }, [appeler]);

  async function inscrire(ids, classeId) {
    setMessage(null);
    setEchec(null);
    try {
      const r = await appeler(`/admin/classes/${classeId}/enfants`, { methode: "POST", corps: { enfant_ids: ids } });
      if (r.ajoutes.length) setMessage(`Inscription faite : ${r.ajoutes.join(", ")}.`);
      if (r.refus.length) setEchec(r.refus.join(" "));
      charger();
    } catch (err) {
      setEchec(err.message);
    }
  }

  async function bloquer(bloque) {
    setMessage(null);
    setEchec(null);
    try {
      const r = await appeler("/admin/enfants/blocage", { methode: "POST", corps: { ids: selection.ids, bloque } });
      setMessage(bloque ? `${r.traites} carte(s) bloquée(s) : connexion suspendue dans toutes les matières.` : `${r.traites} carte(s) débloquée(s).`);
      selection.vider();
      charger();
    } catch (err) {
      setEchec(err.message);
    }
  }

  const choisis = enfants?.filter((e) => selection.choisis.has(e.id)) ?? [];
  const niveauCommun = choisis.length && choisis.every((e) => e.niveau === choisis[0].niveau) ? choisis[0].niveau : null;

  return (
    <section className="carte">
      <div className="filtres">
        <div style={{ flexGrow: 3 }}>
          <label htmlFor="en-recherche">Rechercher (prénom, nom ou identifiant)</label>
          <input id="en-recherche" type="search" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <div>
          <label htmlFor="en-niveau">Niveau</label>
          <select id="en-niveau" value={niveau} onChange={(e) => setNiveau(e.target.value)}>
            <option value="">Tous</option>
            {NIVEAUX.map(([v, l]) => (
              <option key={v} value={v}>{l}</option>
            ))}
          </select>
        </div>
      </div>
      <label className="case">
        <input type="checkbox" checked={sansClasse} onChange={(e) => setSansClasse(e.target.checked)} /> Seulement les enfants
        inscrits nulle part (ni classe, ni groupe d'anglais)
      </label>
      <p className="aide">
        Les enfants sont créés avec leur famille (écran Familles, une par une ou par fichier Excel). Inscrivez-les ici dans une
        classe de leur niveau, ou laissez leur professeur les ajouter. Cochez plusieurs enfants pour les inscrire, les bloquer
        ou les supprimer ensemble.
      </p>
      <Erreur message={erreur || echec} />
      {message && <p className="succes" role="status">{message}</p>}
      {enfants === null && <p className="doux">Chargement…</p>}
      {enfants?.length === 0 && <Vide icone="eleve">Aucun enfant ne correspond.</Vide>}
      {enfants?.length > 0 && (
        <>
          <p className="doux petit">{enfants.length === 100 ? "Les 100 premiers résultats : affinez la recherche." : `${enfants.length} enfant(s)`}</p>
          <BarreSelection selection={selection} noms={["enfant", "enfants"]}>
            <select
              value=""
              aria-label="Inscrire la sélection dans une classe"
              disabled={!niveauCommun}
              title={niveauCommun ? undefined : "Sélectionnez des enfants du même niveau"}
              onChange={(ev) => ev.target.value && inscrire(selection.ids, ev.target.value).then(selection.vider)}
            >
              <option value="">{niveauCommun ? "Inscrire dans la classe…" : "Inscrire : même niveau requis"}</option>
              {classes
                .filter((c) => c.niveau === niveauCommun)
                .map((c) => (
                  <option key={c.id} value={c.id}>{c.code} · {parcoursCourt(c.parcours)} ({c.enseignant})</option>
                ))}
            </select>
            <button className="secondaire petit" onClick={() => bloquer(true)}>Bloquer</button>
            <button className="secondaire petit" onClick={() => bloquer(false)}>Débloquer</button>
            <button className="danger petit" onClick={() => setSuppression(true)}>Supprimer</button>
          </BarreSelection>
          <div className="tableau-defilant">
            <table>
              <thead>
                <tr>
                  <CaseTout selection={selection} ids={enfants.map((e) => e.id)} libelle="Sélectionner tous les enfants affichés" />
                  <th>Enfant</th>
                  <th>Niveau</th>
                  <th>Identifiant</th>
                  <th>Maths</th>
                  <th>Anglais</th>
                  <th>Dernière connexion</th>
                  <th>Inscrire en maths</th>
                </tr>
              </thead>
              <tbody>
                {enfants.map((e) => {
                  const possibles = classes.filter((c) => c.niveau === e.niveau && !e.maths.some((m) => m.code_classe === c.code));
                  return (
                    <tr key={e.id}>
                      <CaseLigne selection={selection} id={e.id} libelle={`Sélectionner ${nomComplet(e)}`} />
                      <td>
                        <strong>{nomComplet(e)}</strong> {e.bloque && <span className="badge alerte insecable">Bloqué</span>}
                      </td>
                      <td>{NOM_NIVEAU[e.niveau] ?? e.niveau}</td>
                      <td><code>{e.identifiant}</code></td>
                      <td>
                        {e.maths.length ? (
                          <div className="badges">
                            {e.maths.map((m) => <span key={m.eleve_id} className="badge neutre">{m.code_classe}</span>)}
                          </div>
                        ) : (
                          <span className="badge alerte">Sans classe</span>
                        )}
                      </td>
                      <td>{e.anglais.length ? e.anglais.map((a) => a.groupe).join(", ") : <span className="doux">—</span>}</td>
                      <td>{e.derniere_connexion ? formaterDate(e.derniere_connexion, { heure: true }) : <span className="doux">jamais</span>}</td>
                      <td>
                        <select
                          value=""
                          aria-label={`Inscrire ${nomComplet(e)} dans une classe`}
                          onChange={(ev) => ev.target.value && inscrire([e.id], ev.target.value)}
                          disabled={!possibles.length}
                        >
                          <option value="">{possibles.length ? "Choisir une classe…" : "Aucune autre classe de ce niveau"}</option>
                          {possibles.map((c) => (
                            <option key={c.id} value={c.id}>{c.code} · {parcoursCourt(c.parcours)} ({c.enseignant})</option>
                          ))}
                        </select>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
      {suppression && (
        <ConfirmationSuppression
          titre={`Supprimer ${selection.nombre} enfant(s)`}
          onFermer={() => setSuppression(false)}
          onConfirmer={async (confirmation) => {
            const r = await appeler("/admin/enfants/suppression", { methode: "POST", corps: { ids: selection.ids, confirmation } });
            setSuppression(false);
            setMessage(`${r.traites} enfant(s) supprimé(s), avec leurs inscriptions et leur travail.`);
            selection.vider();
            charger();
          }}
        >
          <p>
            Les enfants sélectionnés sont effacés avec toutes leurs inscriptions (maths et anglais), séances et réponses. Un compte
            parent qui n'a plus d'enfant est supprimé aussi.
          </p>
        </ConfirmationSuppression>
      )}
    </section>
  );
}
