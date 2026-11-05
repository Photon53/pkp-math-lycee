import { useCallback, useEffect, useState } from "react";
import { Erreur, Onglets } from "../composants.jsx";
import { useApi } from "../enseignant/useApi.js";
import { Modale, Pagination, Vide, exporterCsv, formaterDate } from "../ui/Cadre.jsx";
import Icone from "../ui/Icone.jsx";
import { BarreSelection, CaseLigne, CaseTout, ConfirmationSuppression, useSelection } from "../ui/Selection.jsx";
import { avecDomaine, parametre } from "./BandeauAdmin.jsx";
import { LIBELLES_PARCOURS, NIVEAUX, PARCOURS_PAR_NIVEAU } from "../parcours.js";
import { GererClasse, ListeEnfants, parcoursCourt } from "./GestionClasses.jsx";

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
          ["enfants", "Enfants des familles"],
          ["inscriptions", "Inscriptions en classe"],
          ["classes", "Classes"],
        ]}
      />
      {onglet === "enfants" && <ListeEnfants appeler={appeler} erreur={erreur} />}
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

function ListeClasses({ jeton, onExpire, domaine }) {
  const { appeler, erreur } = useApi(jeton, onExpire);
  const [classes, setClasses] = useState(null);
  const [nouvelle, setNouvelle] = useState(false);
  const [geree, setGeree] = useState(null);
  const [message, setMessage] = useState(null);
  const [suppression, setSuppression] = useState(false);
  const selection = useSelection();
  const charger = useCallback(() => appeler(avecDomaine("/admin/classes", domaine)).then(setClasses, () => {}), [appeler, domaine]);
  const apresModification = useCallback(
    (texte) => {
      if (texte) setMessage(texte);
      charger();
    },
    [charger],
  );
  useEffect(() => {
    charger();
  }, [charger]);

  return (
    <section className="carte">
      <div className="actions" style={{ marginTop: 0 }}>
        <button onClick={() => setNouvelle(true)}>
          <Icone nom="plus" taille={18} /> Nouvelle classe
        </button>
      </div>
      {message && <p className="succes" role="status">{message}</p>}
      {nouvelle && (
        <NouvelleClasse
          appeler={appeler}
          onFermer={() => setNouvelle(false)}
          onCreee={(c) => {
            setNouvelle(false);
            setMessage(`Classe ${c.code} créée. Ajoutez-y les élèves avec « Gérer », ou laissez le professeur le faire.`);
            charger();
          }}
        />
      )}
      {geree && <GererClasse classe={geree} appeler={appeler} onFermer={() => setGeree(null)} onChange={apresModification} />}
      <Erreur message={erreur} />
      {classes === null && <p className="doux">Chargement…</p>}
      {classes?.length === 0 && <Vide icone="classes">Aucune classe.</Vide>}
      {suppression && (
        <ConfirmationSuppression
          titre={`Supprimer ${selection.nombre} classe(s)`}
          onFermer={() => setSuppression(false)}
          onConfirmer={async (confirmation) => {
            const r = await appeler("/admin/classes/suppression", { methode: "POST", corps: { ids: selection.ids, confirmation } });
            setSuppression(false);
            setMessage(`${r.traites} classe(s) supprimée(s). Les enfants des familles et leurs autres inscriptions sont conservés.`);
            selection.vider();
            charger();
          }}
        >
          <p>
            Classes : {classes.filter((c) => selection.choisis.has(c.id)).map((c) => c.code).join(", ")}. Leurs inscriptions,
            séances et réponses sont effacées ; les enfants des familles restent.
          </p>
        </ConfirmationSuppression>
      )}
      <BarreSelection selection={selection} noms={["classe", "classes"]}>
        <button className="danger petit" onClick={() => setSuppression(true)}>Supprimer</button>
      </BarreSelection>
      {classes?.length > 0 && (
        <div className="tableau-defilant">
          <table>
            <thead>
              <tr>
                <CaseTout selection={selection} ids={classes.map((c) => c.id)} libelle="Sélectionner toutes les classes" />
                <th>Code</th>
                <th>Niveau</th>
                <th>Parcours</th>
                <th>Professeur</th>
                <th className="nombre">Élèves</th>
                <th className="nombre">Chapitres ouverts</th>
                <th>
                  <span className="visuellement-cache">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {classes.map((c) => (
                <tr key={c.id}>
                  <CaseLigne selection={selection} id={c.id} libelle={`Sélectionner la classe ${c.code}`} />
                  <td>
                    <code>{c.code}</code>
                  </td>
                  <td>{c.niveau}</td>
                  <td>{parcoursCourt(c.parcours)}</td>
                  <td>{c.enseignant}</td>
                  <td className="nombre">{c.nb_eleves}</td>
                  <td className="nombre">{c.nb_chapitres_ouverts}</td>
                  <td className="nombre">
                    <button className="secondaire petit" onClick={() => setGeree(c)} aria-label={`Gérer la classe ${c.code}`}>
                      Gérer
                    </button>
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
