import { useCallback, useEffect, useState } from "react";
import { Erreur, Onglets } from "../composants.jsx";
import { useApi } from "../enseignant/useApi.js";
import { Modale, Pagination, Vide, exporterCsv, formaterDate } from "../ui/Cadre.jsx";
import Icone from "../ui/Icone.jsx";

/** Vue transverse des élèves et des classes (EA3.7 à EA3.10). L'administrateur ne crée pas d'élève. */
export default function Eleves({ jeton, onExpire }) {
  const [onglet, setOnglet] = useState("eleves");
  return (
    <>
      <Onglets
        valeur={onglet}
        onChange={setOnglet}
        options={[
          ["eleves", "Élèves"],
          ["classes", "Classes"],
        ]}
      />
      {onglet === "eleves" ? <ListeEleves jeton={jeton} onExpire={onExpire} /> : <ListeClasses jeton={jeton} onExpire={onExpire} />}
    </>
  );
}

function ListeEleves({ jeton, onExpire }) {
  const { appeler, erreur } = useApi(jeton, onExpire);
  const [recherche, setRecherche] = useState("");
  const [page, setPage] = useState(1);
  const [donnees, setDonnees] = useState(null);
  const [classes, setClasses] = useState([]);
  const [code, setCode] = useState(null);
  const [deplacement, setDeplacement] = useState(null);
  const [message, setMessage] = useState(null);

  const charger = useCallback(() => {
    const params = new URLSearchParams({ page: String(page) });
    if (recherche.trim()) params.set("q", recherche.trim());
    return appeler(`/admin/eleves?${params}`).then(setDonnees, () => {});
  }, [appeler, page, recherche]);

  useEffect(() => {
    const minuterie = setTimeout(charger, 250);
    return () => clearTimeout(minuterie);
  }, [charger]);

  useEffect(() => {
    appeler("/admin/classes").then(setClasses, () => {});
  }, [appeler]);

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

function ListeClasses({ jeton, onExpire }) {
  const { appeler, erreur } = useApi(jeton, onExpire);
  const [classes, setClasses] = useState(null);
  useEffect(() => {
    appeler("/admin/classes").then(setClasses, () => {});
  }, [appeler]);

  return (
    <section className="carte">
      <Erreur message={erreur} />
      {classes === null && <p className="doux">Chargement…</p>}
      {classes?.length === 0 && <Vide icone="classes">Aucune classe.</Vide>}
      {classes?.length > 0 && (
        <div className="tableau-defilant">
          <table>
            <thead>
              <tr>
                <th>Code</th>
                <th>Niveau</th>
                <th>Parcours</th>
                <th>Professeur</th>
                <th className="nombre">Élèves</th>
                <th className="nombre">Chapitres ouverts</th>
              </tr>
            </thead>
            <tbody>
              {classes.map((c) => (
                <tr key={c.id}>
                  <td>
                    <code>{c.code}</code>
                  </td>
                  <td>{c.niveau}</td>
                  <td>{c.parcours}</td>
                  <td>{c.enseignant}</td>
                  <td className="nombre">{c.nb_eleves}</td>
                  <td className="nombre">{c.nb_chapitres_ouverts}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
