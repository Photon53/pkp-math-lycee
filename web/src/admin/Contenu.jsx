import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { Erreur } from "../composants.jsx";
import { NIVEAUX } from "../enseignant/CoursEnseignant.jsx";
import { useApi } from "../enseignant/useApi.js";
import { Maths, formulesInvalides } from "../maths.jsx";
import { naviguer } from "../navigation.js";
import { Modale, formaterDate } from "../ui/Cadre.jsx";
import { LIBELLES_PARCOURS, PARCOURS_PAR_NIVEAU, libelleNiveauParcours, trierChapitres } from "../parcours.js";
import Icone from "../ui/Icone.jsx";

/**
 * Arborescence niveau › chapitre › compétence et éditeur de leçon (EA3.11 à EA3.14).
 * L'adresse /admin/cours/<id de compétence> ouvre l'éditeur.
 */
export default function Contenu({ jeton, onExpire, chemin }) {
  const competenceId = Number(chemin.split("/")[3]) || null;
  return competenceId ? (
    <EditeurLecon jeton={jeton} onExpire={onExpire} competenceId={competenceId} />
  ) : (
    <Arbre jeton={jeton} onExpire={onExpire} />
  );
}

function Arbre({ jeton, onExpire }) {
  const { appeler, erreur } = useApi(jeton, onExpire);
  const [niveau, setNiveau] = useState("2nde");
  const [parcours, setParcours] = useState("");
  const [chapitres, setChapitres] = useState(null);
  const [fenetre, setFenetre] = useState(null);
  const [glisse, setGlisse] = useState(null);

  const charger = useCallback(() => appeler(`/admin/contenu?niveau=${niveau}`).then(setChapitres, () => {}), [appeler, niveau]);
  useEffect(() => {
    setChapitres(null);
    charger();
  }, [charger]);

  async function ecrire(chemin, corps) {
    try {
      await appeler(chemin, { methode: "POST", corps });
      charger();
      return true;
    } catch {
      return false;
    }
  }

  // Glisser-déposer : une compétence ne change d'ordre qu'à l'intérieur de son chapitre.
  function deposer(chapitre, cibleId) {
    if (!glisse || glisse.chapitreId !== chapitre.id || glisse.id === cibleId) return setGlisse(null);
    const ids = chapitre.competences.map((c) => c.id).filter((i) => i !== glisse.id);
    ids.splice(ids.indexOf(cibleId), 0, glisse.id);
    setGlisse(null);
    ecrire(`/admin/chapitres/${chapitre.id}/competences/ordre`, { ids });
  }

  // Rangés par parcours (voie générale, technologique, soutien, approfondissement), puis par ordre dans l'année.
  const visibles = useMemo(
    () => (chapitres ? trierChapitres(chapitres).filter((c) => !parcours || c.parcours === parcours) : null),
    [chapitres, parcours],
  );

  function deplacerChapitre(chapitre, sens) {
    const parParcours = chapitres.filter((c) => c.parcours === chapitre.parcours);
    const position = parParcours.indexOf(chapitre);
    const voisin = parParcours[position + sens];
    if (!voisin) return;
    const ids = parParcours.map((c) => c.id);
    [ids[position], ids[position + sens]] = [ids[position + sens], ids[position]];
    ecrire(`/admin/chapitres/ordre/${niveau}/${chapitre.parcours}`, { ids });
  }

  return (
    <>
      <div className="carte filtres">
        <div style={{ maxWidth: 240 }}>
          <label htmlFor="ct-niveau">Niveau</label>
          <select
            id="ct-niveau"
            value={niveau}
            onChange={(e) => {
              setNiveau(e.target.value);
              setParcours("");
            }}
          >
            {NIVEAUX.map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </div>
        <div style={{ maxWidth: 360 }}>
          <label htmlFor="ct-parcours">Parcours</label>
          <select id="ct-parcours" value={parcours} onChange={(e) => setParcours(e.target.value)}>
            <option value="">Tous</option>
            {PARCOURS_PAR_NIVEAU[niveau].map((p) => (
              <option key={p} value={p}>
                {LIBELLES_PARCOURS[p]}
              </option>
            ))}
          </select>
        </div>
        <div className="actions" style={{ flexGrow: 0, marginTop: 0 }}>
          <button onClick={() => setFenetre({ genre: "chapitre" })}>
            <Icone nom="plus" taille={18} /> Nouveau chapitre
          </button>
        </div>
      </div>
      <Erreur message={erreur} />
      {chapitres === null && <p className="doux">Chargement…</p>}
      <ul className="arbre">
        {visibles?.map((ch, index) => (
          <Fragment key={ch.id}>
            {(index === 0 || visibles[index - 1].parcours !== ch.parcours) && (
              <li className="groupe-parcours">
                <h2 className="titre-parcours">{libelleNiveauParcours(ch.niveau ?? niveau, ch.parcours)}</h2>
              </li>
            )}
          <li className={ch.masque ? "estompe" : ""}>
            <div className="noeud">
              <span className="titre">
                {ch.titre} <span className="doux petit">{ch.code}</span>
              </span>
              {ch.masque && <span className="badge neutre">Masqué</span>}
              <button className="icone" aria-label={`Monter ${ch.titre}`} title="Monter" onClick={() => deplacerChapitre(ch, -1)}>
                ↑
              </button>
              <button className="icone" aria-label={`Descendre ${ch.titre}`} title="Descendre" onClick={() => deplacerChapitre(ch, 1)}>
                ↓
              </button>
              <button
                className="icone"
                title="Renommer"
                aria-label={`Renommer ${ch.titre}`}
                onClick={() => setFenetre({ genre: "renommer-chapitre", chapitre: ch })}
              >
                <Icone nom="crayon" />
              </button>
              <button
                className="icone"
                title={ch.masque ? "Réafficher" : "Masquer"}
                aria-label={`${ch.masque ? "Réafficher" : "Masquer"} ${ch.titre}`}
                onClick={() => ecrire(`/admin/chapitres/${ch.id}`, { titre: ch.titre, masque: !ch.masque })}
              >
                <Icone nom={ch.masque ? "oeil" : "oeilBarre"} />
              </button>
              <button className="secondaire petit" onClick={() => setFenetre({ genre: "competence", chapitre: ch })}>
                <Icone nom="plus" taille={16} /> Compétence
              </button>
            </div>
            {ch.competences.length > 0 && (
              <ul>
                {ch.competences.map((c) => (
                  <li
                    key={c.id}
                    draggable
                    onDragStart={() => setGlisse({ id: c.id, chapitreId: ch.id })}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={() => deposer(ch, c.id)}
                    className={glisse?.id === c.id ? "glisse" : ""}
                  >
                    <span className="poignee" title="Glisser pour réordonner">
                      <Icone nom="poignee" taille={16} />
                    </span>
                    <span className="libelle">
                      {c.libelle} <span className="doux petit">{c.code}</span>
                    </span>
                    {c.masque && <span className="badge neutre">Masquée</span>}
                    {c.a_une_lecon ? (
                      <span className="badge ok" title={`Mise à jour le ${formaterDate(c.lecon_maj_le)}`}>
                        Cours
                      </span>
                    ) : (
                      <span className="badge alerte">Sans cours</span>
                    )}
                    <span className="doux petit chiffres">{c.nb_questions} question(s)</span>
                    <button className="secondaire petit" onClick={() => naviguer(`/admin/cours/${c.id}`)}>
                      Éditer la leçon
                    </button>
                    <button
                      className="icone"
                      title="Renommer"
                      aria-label={`Renommer ${c.libelle}`}
                      onClick={() => setFenetre({ genre: "renommer-competence", competence: c })}
                    >
                      <Icone nom="crayon" />
                    </button>
                    <button
                      className="icone"
                      title={c.masque ? "Réafficher" : "Masquer"}
                      aria-label={`${c.masque ? "Réafficher" : "Masquer"} ${c.libelle}`}
                      onClick={() => ecrire(`/admin/competences/${c.id}`, { libelle: c.libelle, masque: !c.masque })}
                    >
                      <Icone nom={c.masque ? "oeil" : "oeilBarre"} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </li>
          </Fragment>
        ))}
      </ul>

      {fenetre && (
        <FenetreArbre
          fenetre={fenetre}
          niveau={niveau}
          appeler={appeler}
          onFermer={() => setFenetre(null)}
          onFait={() => {
            setFenetre(null);
            charger();
          }}
        />
      )}
    </>
  );
}

function FenetreArbre({ fenetre, niveau, appeler, onFermer, onFait }) {
  const { genre, chapitre, competence } = fenetre;
  const [texte, setTexte] = useState(chapitre && genre === "renommer-chapitre" ? chapitre.titre : competence?.libelle ?? "");
  const [code, setCode] = useState("");
  const [parcours, setParcours] = useState(PARCOURS_PAR_NIVEAU[niveau][0]);
  const [erreur, setErreur] = useState(null);
  const creation = genre === "chapitre" || genre === "competence";
  const titres = {
    chapitre: "Nouveau chapitre",
    competence: `Nouvelle compétence — ${chapitre?.titre}`,
    "renommer-chapitre": "Renommer le chapitre",
    "renommer-competence": "Renommer la compétence",
  };

  async function soumettre(e) {
    e.preventDefault();
    setErreur(null);
    const requetes = {
      chapitre: ["/admin/chapitres", { code, niveau, parcours, titre: texte }],
      competence: ["/admin/competences", { chapitre_id: chapitre?.id, code, libelle: texte }],
      "renommer-chapitre": [`/admin/chapitres/${chapitre?.id}`, { titre: texte, masque: chapitre?.masque }],
      "renommer-competence": [`/admin/competences/${competence?.id}`, { libelle: texte, masque: competence?.masque }],
    };
    const [chemin, corps] = requetes[genre];
    try {
      await appeler(chemin, { methode: "POST", corps });
      onFait();
    } catch (err) {
      setErreur(err.message);
    }
  }

  return (
    <Modale titre={titres[genre]} onFermer={onFermer}>
      <form onSubmit={soumettre}>
        {creation && (
          <>
            <label htmlFor="f-code">Code (majuscules, chiffres, tirets)</label>
            <input
              id="f-code"
              required
              pattern="[A-Z0-9-]{2,40}"
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase())}
              placeholder={genre === "chapitre" ? "ex. 1RE-PROBA-COND" : "ex. 1RE-PROBA-COND-ARBRE"}
            />
          </>
        )}
        {genre === "chapitre" && (
          <>
            <label htmlFor="f-parcours">Parcours</label>
            <select id="f-parcours" value={parcours} onChange={(e) => setParcours(e.target.value)}>
              {PARCOURS_PAR_NIVEAU[niveau].map((v) => (
                <option key={v} value={v}>
                  {LIBELLES_PARCOURS[v]}
                </option>
              ))}
            </select>
          </>
        )}
        <label htmlFor="f-texte">{genre.includes("chapitre") ? "Titre" : "Libellé"}</label>
        <input id="f-texte" required maxLength={200} value={texte} onChange={(e) => setTexte(e.target.value)} />
        <Erreur message={erreur} />
        <div className="actions">
          <button type="submit">Enregistrer</button>
        </div>
      </form>
    </Modale>
  );
}

function EditeurLecon({ jeton, onExpire, competenceId }) {
  const { appeler, erreur } = useApi(jeton, onExpire);
  const [lecon, setLecon] = useState(null);
  const [cours, setCours] = useState("");
  const [resume, setResume] = useState("");
  const [volet, setVolet] = useState("cours");
  const [message, setMessage] = useState(null);
  const [version, setVersion] = useState(null);

  const appliquer = useCallback((l) => {
    setLecon(l);
    setCours(l.cours);
    setResume(l.resume);
  }, []);

  useEffect(() => {
    appeler(`/admin/lecons/${competenceId}`).then(appliquer, () => {});
  }, [appeler, competenceId, appliquer]);

  const invalides = useMemo(() => [...formulesInvalides(cours), ...formulesInvalides(resume)], [cours, resume]);
  const modifie = lecon && (cours !== lecon.cours || resume !== lecon.resume);

  async function enregistrer() {
    setMessage(null);
    try {
      appliquer(await appeler(`/admin/lecons/${competenceId}`, { methode: "POST", corps: { cours, resume } }));
      setMessage("Leçon enregistrée. La version précédente est conservée.");
    } catch {
      // erreur déjà affichée
    }
  }

  async function voirVersion(id) {
    try {
      setVersion(await appeler(`/admin/lecons/versions/${id}`));
    } catch {
      // erreur déjà affichée
    }
  }

  async function restaurer() {
    if (!window.confirm("Restaurer cette version ? L'état actuel sera conservé dans l'historique.")) return;
    try {
      appliquer(await appeler(`/admin/lecons/versions/${version.id}/restaurer`, { methode: "POST" }));
      setVersion(null);
      setMessage("Version restaurée.");
    } catch {
      // erreur déjà affichée
    }
  }

  return (
    <>
      <button className="lien" style={{ paddingLeft: 0 }} onClick={() => naviguer("/admin/cours")}>
        ← Arborescence
      </button>
      <Erreur message={erreur} />
      {!lecon && !erreur && <p className="doux">Chargement…</p>}
      {lecon && (
        <>
          <div className="carte">
            <div className="carte-titre">
              <div>
                <div className="fil">{lecon.chapitre}</div>
                <h2 style={{ margin: 0 }}>{lecon.libelle}</h2>
                <span className="doux petit">
                  {lecon.code}
                  {lecon.maj_le && ` · mise à jour le ${formaterDate(lecon.maj_le, { heure: true })}`}
                  {lecon.modifiee_admin_le && " · modifiée dans l'administration (l'import YAML ne l'écrase plus)"}
                </span>
              </div>
              <div className="actions" style={{ marginTop: 0 }}>
                <button disabled={!modifie || invalides.length > 0 || !cours.trim() || !resume.trim()} onClick={enregistrer}>
                  Enregistrer
                </button>
                <button className="secondaire" disabled={!modifie} onClick={() => appliquer(lecon)}>
                  Annuler les modifications
                </button>
              </div>
            </div>
            {message && (
              <p className="succes" role="status">
                {message}
              </p>
            )}
            {invalides.length > 0 && (
              <div className="erreur" role="alert">
                <div>
                  <strong>Formule(s) à corriger avant d'enregistrer :</strong>
                  <ul style={{ margin: "4px 0 0", paddingLeft: 20 }}>
                    {invalides.map((e) => (
                      <li key={e}>
                        <code>{e}</code>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            )}
            <div className="onglets" role="tablist">
              {[
                ["cours", "Cours"],
                ["resume", "L'essentiel (résumé)"],
              ].map(([v, l]) => (
                <button key={v} role="tab" aria-selected={volet === v} className={volet === v ? "onglet actif" : "onglet"} onClick={() => setVolet(v)}>
                  {l}
                </button>
              ))}
            </div>
            <div className="deux-volets">
              <div>
                <label htmlFor="ed-texte" className="visuellement-cache">
                  Texte Markdown et LaTeX
                </label>
                <textarea
                  id="ed-texte"
                  value={volet === "cours" ? cours : resume}
                  onChange={(e) => (volet === "cours" ? setCours : setResume)(e.target.value)}
                  spellCheck
                />
                <p className="aide">Markdown ; formules entre $…$ (en ligne) ou $$…$$ (centrées).</p>
              </div>
              <div className="apercu" aria-label="Aperçu tel que le voit l'élève">
                {volet === "resume" ? (
                  <section className="resume">
                    <h3>L'essentiel</h3>
                    <Maths texte={resume} />
                  </section>
                ) : (
                  <Maths texte={cours} />
                )}
              </div>
            </div>
          </div>

          <section className="carte">
            <h2>Versions précédentes</h2>
            {lecon.versions.length === 0 ? (
              <p className="doux">Aucune modification depuis l'import.</p>
            ) : (
              <table>
                <tbody>
                  {lecon.versions.map((v) => (
                    <tr key={v.id}>
                      <td className="chiffres">{formaterDate(v.le, { heure: true })}</td>
                      <td>{v.auteur ?? "—"}</td>
                      <td className="nombre">
                        <button className="secondaire petit" onClick={() => voirVersion(v.id)}>
                          Comparer
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </>
      )}

      {version && (
        <Modale titre={`Version du ${formaterDate(version.le, { heure: true })}`} large onFermer={() => setVersion(null)}>
          <div className="deux-volets">
            <div>
              <h3>Cette version</h3>
              <div className="apercu" style={{ minHeight: 0 }}>
                <Maths texte={version.cours} />
              </div>
            </div>
            <div>
              <h3>Actuelle</h3>
              <div className="apercu" style={{ minHeight: 0 }}>
                <Maths texte={lecon.cours} />
              </div>
            </div>
          </div>
          <div className="actions">
            <button onClick={restaurer}>Restaurer cette version</button>
          </div>
        </Modale>
      )}
    </>
  );
}
