import { useCallback, useEffect, useState } from "react";
import { Erreur, Onglets } from "../composants.jsx";
import { useApi } from "../enseignant/useApi.js";
import { Modale, Pagination, Vide, exporterCsv, formaterDate } from "../ui/Cadre.jsx";
import Icone from "../ui/Icone.jsx";
import { BarreSelection, CaseLigne, CaseTout, ConfirmationSuppression, useSelection } from "../ui/Selection.jsx";
import { avecDomaine, parametre } from "./BandeauAdmin.jsx";
import { LIBELLES_PARCOURS, NIVEAUX, PARCOURS_PAR_NIVEAU } from "../parcours.js";
import { GererClasse, parcoursCourt } from "./GestionClasses.jsx";
import { NouveauGroupe } from "./AnglaisAdmin.jsx";
import { naviguer } from "../navigation.js";
import Repertoire from "./Repertoire.jsx";

/** Vue transverse des élèves et des classes (EA3.7 à EA3.10). Les élèves sont créés avec leur famille
 * (écran Familles) ; ici, l'administrateur crée des classes pour les professeurs. */
export default function Eleves({ jeton, onExpire, domaine = "" }) {
  // Un résultat de la recherche globale (`?q=prénom`) vise une inscription en classe.
  const [onglet, setOnglet] = useState(() =>
    ["classes", "inscriptions"].includes(parametre("onglet")) ? parametre("onglet") : parametre("q") ? "inscriptions" : "enfants",
  );
  const { appeler, erreur } = useApi(jeton, onExpire);
  return (
    <>
      <Onglets
        valeur={onglet}
        onChange={setOnglet}
        options={[
          ["enfants", "Tous les élèves"],
          ["inscriptions", "Inscriptions en classe"],
          ["classes", "Classes et groupes"],
        ]}
      />
      {onglet === "enfants" && <Repertoire appeler={appeler} erreur={erreur} domaine={domaine} jeton={jeton} onExpire={onExpire} />}
      {onglet === "inscriptions" && <ListeEleves jeton={jeton} onExpire={onExpire} domaine={domaine} />}
      {onglet === "classes" && <ListeClasses jeton={jeton} onExpire={onExpire} domaine={domaine} />}
    </>
  );
}

function ListeEleves({ jeton, onExpire, domaine }) {
  const { appeler, erreur } = useApi(jeton, onExpire);
  const [recherche, setRecherche] = useState(() => parametre("q"));
  const [page, setPage] = useState(1);
  const [donnees, setDonnees] = useState(null);
  const [classes, setClasses] = useState([]);
  const [code, setCode] = useState(null);
  const [deplacement, setDeplacement] = useState(null);
  const [message, setMessage] = useState(null);

  const charger = useCallback(() => {
    const params = new URLSearchParams({ page: String(page) });
    if (recherche.trim()) params.set("q", recherche.trim());
    if (domaine) params.set("domaine", domaine);
    return appeler(`/admin/eleves?${params}`).then(setDonnees, () => {});
  }, [appeler, page, recherche, domaine]);

  useEffect(() => {
    const minuterie = setTimeout(charger, 250);
    return () => clearTimeout(minuterie);
  }, [charger]);

  useEffect(() => {
    appeler(avecDomaine("/admin/classes", domaine)).then(setClasses, () => {});
  }, [appeler, domaine]);

  async function regenerer(e) {
    if (!window.confirm(`Nouveau code pour ${e.prenom} (${e.classe}) ? L'ancien cesse de fonctionner.`)) return;
    try {
      setCode(await appeler(`/admin/eleves/${e.id}/code`, { methode: "POST" }));
      charger();
    } catch {
      // erreur déjà affichée
    }
  }

  async function supprimer(e) {
    if (!window.confirm(`Supprimer ${e.prenom} (${e.classe}), ses séances et ses réponses ? Cette action est irréversible.`)) return;
    try {
      await appeler(`/admin/eleves/${e.id}`, { methode: "DELETE" });
      setMessage(`${e.prenom} a été supprimé·e.`);
      charger();
    } catch {
      // erreur déjà affichée
    }
  }

  async function exporter(e) {
    try {
      const donneesEleve = await appeler(`/admin/eleves/${e.id}/export`);
      const url = URL.createObjectURL(new Blob([JSON.stringify(donneesEleve, null, 2)], { type: "application/json" }));
      Object.assign(document.createElement("a"), { href: url, download: `pkp-${e.classe}-${e.prenom}.json` }).click();
      URL.revokeObjectURL(url);
    } catch {
      // erreur déjà affichée
    }
  }

  return (
    <section className="carte">
      <div className="filtres">
        <div style={{ flexGrow: 3 }}>
          <label htmlFor="el-recherche">Rechercher un prénom</label>
          <input
            id="el-recherche"
            type="search"
            value={recherche}
            onChange={(e) => {
              setRecherche(e.target.value);
              setPage(1);
            }}
          />
        </div>
        <div className="actions" style={{ flexGrow: 0, marginTop: 0 }}>
          <button className="secondaire" onClick={() => exporterCsv("eleves.csv", donnees?.elements ?? [])} disabled={!donnees?.elements.length}>
            CSV
          </button>
        </div>
      </div>
      <p className="aide">Les codes personnels ne sont jamais affichés : ils sont stockés hachés. On peut seulement en générer un nouveau.</p>
      {message && (
        <p className="succes" role="status">
          {message}
        </p>
      )}
      <Erreur message={erreur} />
      {donnees === null && <p className="doux">Chargement…</p>}
      {donnees?.total === 0 && <Vide icone="eleve">Aucun élève.</Vide>}
      {donnees?.total > 0 && (
        <>
          <p className="doux petit">{donnees.total} élève(s)</p>
          <div className="tableau-defilant">
            <table>
              <thead>
                <tr>
                  <th>Prénom</th>
                  <th>Classe</th>
                  <th>Professeur</th>
                  <th className="nombre">Séances</th>
                  <th>Dernière activité</th>
                  <th>Code</th>
                  <th>
                    <span className="visuellement-cache">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {donnees.elements.map((e) => (
                  <tr key={e.id}>
                    <td>
                      <strong>{e.prenom}</strong>
                    </td>
                    <td>
                      <code>{e.classe}</code>
                    </td>
                    <td>{e.enseignant}</td>
                    <td className="nombre">{e.nb_seances}</td>
                    <td>{formaterDate(e.derniere_activite)}</td>
                    <td>{e.a_un_code ? <span className="badge ok">Oui</span> : <span className="badge alerte">Sans code</span>}</td>
                    <td className="nombre">
                      <div className="actions">
                        <button className="icone" title="Nouveau code" aria-label={`Nouveau code pour ${e.prenom}`} onClick={() => regenerer(e)}>
                          <Icone nom="cle" />
                        </button>
                        <button className="secondaire petit" onClick={() => setDeplacement(e)}>
                          Déplacer
                        </button>
                        <button className="secondaire petit" onClick={() => exporter(e)}>
                          Exporter
                        </button>
                        <button className="icone" title="Supprimer" aria-label={`Supprimer ${e.prenom}`} onClick={() => supprimer(e)}>
                          <Icone nom="poubelle" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={page} total={donnees.total} onChange={setPage} />
        </>
      )}

      {code && (
        <Modale titre={`Nouveau code de ${code.prenom}`} onFermer={() => setCode(null)}>
          <p>Transmettez ce code à l'élève (ou à son professeur). Il ne sera plus affiché.</p>
          <p className="secret">{code.code}</p>
        </Modale>
      )}
      {deplacement && (
        <Deplacement
          eleve={deplacement}
          classes={classes.filter((c) => c.enseignant === deplacement.enseignant && c.id !== deplacement.classe_id)}
          onFermer={() => setDeplacement(null)}
          onValider={async (classeId) => {
            try {
              await appeler(`/admin/eleves/${deplacement.id}/deplacement`, { methode: "POST", corps: { classe_id: classeId } });
              setMessage(`${deplacement.prenom} a été déplacé·e.`);
              setDeplacement(null);
              charger();
            } catch {
              // erreur déjà affichée
            }
          }}
        />
      )}
    </section>
  );
}

function Deplacement({ eleve, classes, onFermer, onValider }) {
  const [classeId, setClasseId] = useState(classes[0]?.id ?? "");
  return (
    <Modale titre={`Déplacer ${eleve.prenom}`} onFermer={onFermer}>
      {classes.length === 0 ? (
        <p className="doux">Son professeur n'a pas d'autre classe.</p>
      ) : (
        <>
          <label htmlFor="d-classe">Vers la classe</label>
          <select id="d-classe" value={classeId} onChange={(e) => setClasseId(Number(e.target.value))}>
            {classes.map((c) => (
              <option key={c.id} value={c.id}>
                {c.code} ({c.niveau})
              </option>
            ))}
          </select>
          <p className="aide">Son historique le suit. Seules les classes du même professeur sont proposées.</p>
          <div className="actions">
            <button onClick={() => onValider(Number(classeId))}>Déplacer</button>
          </div>
        </>
      )}
    </Modale>
  );
}

const ETATS = [
  ["actives", "En cours"],
  ["archivees", "Archivées"],
  ["toutes", "Toutes"],
];
const NOM_DOMAINE = {
  "maths-college": "Maths collège",
  "maths-lycee": "Maths lycée",
  "anglais-college": "Anglais collège",
  "anglais-lycee": "Anglais lycée",
  "francais-college": "Français collège",
  "francais-lycee": "Français lycée",
};
const ORDRE_NIVEAU = Object.fromEntries(NIVEAUX.map(([v], i) => [v, i]));

/** Classes de maths et groupes d'anglais réunis, quel que soit le domaine (V3, Lot 3) : création, gestion,
 * archivage de fin d'année et rétablissement. Le travail des élèves d'une classe archivée est conservé. */
function ListeClasses({ jeton, onExpire, domaine }) {
  const { appeler, erreur } = useApi(jeton, onExpire);
  const [etat, setEtat] = useState("actives");
  const [lignes, setLignes] = useState(null);
  const [fenetre, setFenetre] = useState(null);
  const [message, setMessage] = useState(null);
  const [echec, setEchec] = useState(null);
  const [profs, setProfs] = useState([]);
  const selection = useSelection();

  const charger = useCallback(
    () =>
      Promise.all([
        appeler(avecDomaine(`/admin/classes?etat=${etat}`, domaine)),
        appeler(avecDomaine(`/admin/anglais/groupes?etat=${etat}`, domaine)),
      ]).then(([classes, groupes]) => {
        const toutes = [
          ...classes.map((c) => ({ ...c, cle: `c-${c.id}`, genre: "classe", nom: c.code, nb: c.nb_eleves })),
          ...groupes.map((g) => ({ ...g, cle: `g-${g.id}`, genre: "groupe", nb: g.eleves.length })),
        ];
        toutes.sort((a, b) => (ORDRE_NIVEAU[a.niveau] ?? 9) - (ORDRE_NIVEAU[b.niveau] ?? 9) || a.nom.localeCompare(b.nom));
        setLignes(toutes);
      }, () => {}),
    [appeler, domaine, etat],
  );
  useEffect(() => {
    charger();
  }, [charger]);
  useEffect(() => {
    appeler("/admin/enseignants").then(setProfs, () => {});
  }, [appeler]);

  const choisies = (lignes ?? []).filter((l) => selection.choisis.has(l.cle));
  const ids = (genre) => choisies.filter((l) => l.genre === genre).map((l) => l.id);

  async function regler(archiver, motif = "") {
    setMessage(null);
    setEchec(null);
    try {
      let n = 0;
      for (const [genre, chemin] of [["classe", "/admin/classes/archivage"], ["groupe", "/admin/anglais/groupes/archivage"]]) {
        if (ids(genre).length) n += (await appeler(chemin, { methode: "POST", corps: { ids: ids(genre), archiver, motif } })).traites;
      }
      setMessage(
        archiver
          ? `${n} classe(s) ou groupe(s) archivé(s) : hors des listes, le travail des élèves est conservé.`
          : `${n} classe(s) ou groupe(s) rétabli(s).`,
      );
      setFenetre(null);
      selection.vider();
      charger();
    } catch (err) {
      setEchec(err.message);
    }
  }

  return (
    <section className="carte">
      <div className="filtres">
        <div style={{ flexGrow: 0 }}>
          <label htmlFor="cg-etat">Afficher</label>
          <select
            id="cg-etat"
            value={etat}
            onChange={(e) => {
              setEtat(e.target.value);
              selection.vider();
            }}
          >
            {ETATS.map(([v, l]) => (
              <option key={v} value={v}>{l}</option>
            ))}
          </select>
        </div>
        <div className="actions" style={{ flexGrow: 0, marginTop: 0 }}>
          <button onClick={() => setFenetre({ genre: "classe" })}>
            <Icone nom="plus" taille={18} /> Classe de maths
          </button>
          <button className="secondaire" onClick={() => setFenetre({ genre: "groupe" })}>
            <Icone nom="plus" taille={18} /> Groupe d'anglais
          </button>
        </div>
      </div>
      <p className="aide">
        Toutes les classes et tous les groupes, quel que soit le domaine (choisissez-le dans le bandeau). En fin d'année,
        archivez-les : ils sortent des listes et n'ouvrent plus de séance, mais le travail des élèves reste consultable sur
        leur fiche et peut être rétabli.
      </p>
      {message && <p className="succes" role="status">{message}</p>}
      <Erreur message={erreur || echec} />
      {fenetre?.genre === "classe" && (
        <NouvelleClasse
          appeler={appeler}
          onFermer={() => setFenetre(null)}
          onCreee={(c) => {
            setFenetre(null);
            setMessage(`Classe ${c.code} créée. Ajoutez-y les élèves avec « Gérer », ou laissez le professeur le faire.`);
            charger();
          }}
        />
      )}
      {fenetre?.genre === "groupe" && (
        <NouveauGroupe
          profs={profs.filter((p) => p.actif && p.enseigne_anglais)}
          appeler={appeler}
          onFermer={() => setFenetre(null)}
          onCree={(g) => {
            setFenetre(null);
            setMessage(`Groupe « ${g.nom} » créé.`);
            charger();
          }}
        />
      )}
      {fenetre?.genre === "gerer" && (
        <GererClasse
          classe={fenetre.classe}
          appeler={appeler}
          onFermer={() => setFenetre(null)}
          onChange={(texte) => {
            if (texte) setMessage(texte);
            charger();
          }}
        />
      )}
      {fenetre?.genre === "archiver" && (
        <ArchivageFinAnnee nombre={choisies.length} onFermer={() => setFenetre(null)} onValider={(m) => regler(true, m)} />
      )}
      {fenetre?.genre === "suppression" && (
        <ConfirmationSuppression
          titre={`Supprimer ${ids("classe").length} classe(s)`}
          onFermer={() => setFenetre(null)}
          onConfirmer={async (confirmation) => {
            const r = await appeler("/admin/classes/suppression", { methode: "POST", corps: { ids: ids("classe"), confirmation } });
            setFenetre(null);
            setMessage(`${r.traites} classe(s) supprimée(s). Les enfants des familles gardent une copie archivée de leur travail.`);
            selection.vider();
            charger();
          }}
        >
          <p>
            Classes : {choisies.filter((l) => l.genre === "classe").map((l) => l.nom).join(", ")}. Préférez l'archivage en fin
            d'année : la suppression efface les inscriptions, séances et réponses (une copie est gardée pour les enfants des
            familles).
          </p>
        </ConfirmationSuppression>
      )}
      <BarreSelection selection={selection} noms={["classe ou groupe", "classes ou groupes"]}>
        {choisies.some((l) => !l.archivee_le) && (
          <button className="secondaire petit" onClick={() => setFenetre({ genre: "archiver" })}>Archiver (fin d'année)</button>
        )}
        {choisies.some((l) => l.archivee_le) && (
          <button className="secondaire petit" onClick={() => regler(false)}>Rétablir</button>
        )}
        <button
          className="danger petit"
          disabled={!ids("classe").length || ids("groupe").length > 0}
          title={ids("groupe").length ? "Les groupes d'anglais se suppriment un par un, dans Boussole Anglais" : undefined}
          onClick={() => setFenetre({ genre: "suppression" })}
        >
          Supprimer
        </button>
      </BarreSelection>
      {lignes === null && <p className="doux">Chargement…</p>}
      {lignes?.length === 0 && (
        <Vide icone="classes">{etat === "archivees" ? "Aucune classe archivée." : "Aucune classe ni aucun groupe."}</Vide>
      )}
      {lignes?.length > 0 && (
        <div className="tableau-defilant">
          <table>
            <thead>
              <tr>
                <CaseTout selection={selection} ids={lignes.map((l) => l.cle)} libelle="Sélectionner toutes les classes et tous les groupes" />
                <th>Classe ou groupe</th>
                <th>Domaine</th>
                <th>Niveau</th>
                <th>Parcours</th>
                <th>Professeur</th>
                <th className="nombre">Élèves</th>
                <th>État</th>
                <th>
                  <span className="visuellement-cache">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {lignes.map((l) => (
                <tr key={l.cle}>
                  <CaseLigne selection={selection} id={l.cle} libelle={`Sélectionner ${l.nom}`} />
                  <td>{l.genre === "classe" ? <code>{l.nom}</code> : l.nom}</td>
                  <td>{NOM_DOMAINE[l.domaine_code] ?? l.domaine_code}</td>
                  <td>{l.niveau}</td>
                  <td>{l.genre === "classe" ? parcoursCourt(l.parcours) : <span className="doux">—</span>}</td>
                  <td>{l.enseignant}</td>
                  <td className="nombre">{l.nb}</td>
                  <td>
                    {l.archivee_le ? (
                      <span className="badge neutre" title={[l.motif_archivage, l.archivee_par].filter(Boolean).join(" · ")}>
                        Archivée le {formaterDate(l.archivee_le)}
                      </span>
                    ) : (
                      <span className="badge ok">En cours</span>
                    )}
                  </td>
                  <td className="nombre">
                    {l.genre === "classe" ? (
                      <button className="secondaire petit" onClick={() => setFenetre({ genre: "gerer", classe: l })} aria-label={`Gérer ${l.nom}`}>
                        Gérer
                      </button>
                    ) : (
                      <a
                        className="lien petit"
                        href="/admin/anglais"
                        onClick={(e) => {
                          e.preventDefault();
                          naviguer("/admin/anglais");
                        }}
                      >
                        Dans Boussole Anglais
                      </a>
                    )}
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

function ArchivageFinAnnee({ nombre, onFermer, onValider }) {
  const [motif, setMotif] = useState("Fin d'année scolaire");
  return (
    <Modale titre={`Archiver ${nombre} classe(s) ou groupe(s)`} onFermer={onFermer}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onValider(motif);
        }}
      >
        <label htmlFor="arch-motif">Motif (visible dans l'historique)</label>
        <input id="arch-motif" value={motif} maxLength={200} onChange={(e) => setMotif(e.target.value)} />
        <p className="aide">
          Les élèves et leur professeur n'y ont plus accès ; inscriptions, séances et réponses restent en base. Vous pourrez
          les rétablir.
        </p>
        <div className="actions">
          <button type="button" className="secondaire" onClick={onFermer}>Annuler</button>
          <button type="submit">Archiver</button>
        </div>
      </form>
    </Modale>
  );
}

function NouvelleClasse({ appeler, onFermer, onCreee }) {
  const [professeurs, setProfesseurs] = useState([]);
  const [enseignantId, setEnseignantId] = useState("");
  const [niveau, setNiveau] = useState("6e");
  const [parcours, setParcours] = useState("tronc-commun");
  const [erreur, setErreur] = useState(null);

  useEffect(() => {
    appeler("/admin/enseignants").then((liste) => setProfesseurs(liste.filter((p) => p.actif && p.enseigne_maths !== false)), () => {});
  }, [appeler]);

  async function soumettre(e) {
    e.preventDefault();
    setErreur(null);
    try {
      onCreee(await appeler("/admin/classes", { methode: "POST", corps: { niveau, parcours, enseignant_id: Number(enseignantId) } }));
    } catch (err) {
      setErreur(err.message);
    }
  }

  return (
    <Modale titre="Nouvelle classe" onFermer={onFermer}>
      <form onSubmit={soumettre}>
        <label htmlFor="nc-prof">Professeur de mathématiques</label>
        <select id="nc-prof" required value={enseignantId} onChange={(e) => setEnseignantId(e.target.value)}>
          <option value="">Choisir…</option>
          {professeurs.map((p) => (
            <option key={p.id} value={p.id}>{p.nom}</option>
          ))}
        </select>
        <label htmlFor="nc-niveau">Niveau</label>
        <select
          id="nc-niveau"
          value={niveau}
          onChange={(e) => {
            setNiveau(e.target.value);
            setParcours(PARCOURS_PAR_NIVEAU[e.target.value][0]);
          }}
        >
          {NIVEAUX.map(([v, l]) => (
            <option key={v} value={v}>{l}</option>
          ))}
        </select>
        <label htmlFor="nc-parcours">Parcours</label>
        <select id="nc-parcours" value={parcours} onChange={(e) => setParcours(e.target.value)}>
          {PARCOURS_PAR_NIVEAU[niveau].map((v) => (
            <option key={v} value={v}>{LIBELLES_PARCOURS[v]}</option>
          ))}
        </select>
        <p className="aide">
          Un même élève peut suivre plusieurs parcours de son niveau (tronc commun, excellence, mise à niveau) : créez une
          classe par parcours et inscrivez-le dans chacune.
        </p>
        <Erreur message={erreur} />
        <div className="actions">
          <button type="submit" disabled={!enseignantId}>Créer la classe</button>
        </div>
      </form>
    </Modale>
  );
}
