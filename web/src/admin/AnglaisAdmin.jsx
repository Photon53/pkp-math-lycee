import { Fragment, useCallback, useEffect, useState } from "react";
import { Erreur, Onglets } from "../composants.jsx";
import { FicheCodes } from "../enseignant/Classes.jsx";
import { useApi } from "../enseignant/useApi.js";
import AjoutEnfants from "../ui/AjoutEnfants.jsx";
import { Modale, Vide } from "../ui/Cadre.jsx";
import Icone from "../ui/Icone.jsx";
import { BarreSelection, CaseLigne, CaseTout, ConfirmationSuppression, useSelection } from "../ui/Selection.jsx";
import SeancesAnglaisAdmin from "./SeancesAnglaisAdmin.jsx";
import { avecDomaine, parametre } from "./BandeauAdmin.jsx";

const pluriel = (n) => `${n} élève${n > 1 ? "s" : ""}`;

/** PKP Anglais côté administrateur : groupes 4e/3e de tous les professeurs d'anglais, édition et validation des séances. */
export default function AnglaisAdmin({ jeton, onExpire, domaine = "" }) {
  const [onglet, setOnglet] = useState(() => (parametre("onglet") === "seances" ? "seances" : "groupes"));
  return (
    <>
      <Onglets
        valeur={onglet}
        onChange={setOnglet}
        options={[
          ["groupes", "Groupes et élèves"],
          ["seances", "Séances et validation"],
        ]}
      />
      {onglet === "groupes" ? (
        <Groupes jeton={jeton} onExpire={onExpire} domaine={domaine} />
      ) : (
        <SeancesAnglaisAdmin jeton={jeton} onExpire={onExpire} domaine={domaine} />
      )}
    </>
  );
}

function Groupes({ jeton, onExpire, domaine }) {
  const { appeler, erreur } = useApi(jeton, onExpire);
  const [groupes, setGroupes] = useState(null);
  const [profs, setProfs] = useState([]);
  const [gere, setGere] = useState(null); // id du groupe ouvert dans « Gérer »
  const [creation, setCreation] = useState(false);
  const [transfert, setTransfert] = useState(null);
  const [message, setMessage] = useState(null);
  const [suppression, setSuppression] = useState(false);
  const selection = useSelection();

  const charger = useCallback(
    () => appeler(avecDomaine("/admin/anglais/groupes", domaine)).then(setGroupes, () => {}),
    [appeler, domaine],
  );

  useEffect(() => {
    charger();
    appeler("/admin/enseignants").then(setProfs, () => {});
  }, [appeler, charger]);

  async function action(promesse, texte) {
    setMessage(null);
    try {
      await promesse;
      setMessage(texte);
      await charger();
      return true;
    } catch {
      return false; // erreur déjà affichée
    }
  }

  function supprimerGroupe(g) {
    if (!window.confirm(`Supprimer le groupe « ${g.nom} » de ${g.enseignant} ?\n\nSes ${pluriel(g.eleves.length)} seront supprimés définitivement.`)) return;
    action(appeler(`/admin/anglais/groupes/${g.id}`, { methode: "DELETE" }), `Groupe ${g.nom} supprimé.`);
  }

  return (
    <section className="carte">
      <div className="barre-session">
        <p className="doux">
          Groupes d'anglais (4e, 3e), gérés comme les classes de maths : élèves, cartes, professeur, suppression.
        </p>
        <button onClick={() => setCreation(true)}>
          <Icone nom="plus" taille={18} /> Nouveau groupe
        </button>
      </div>
      {message && (
        <p className="succes" role="status">
          {message}
        </p>
      )}
      <Erreur message={erreur} />
      {groupes === null && <p className="doux">Chargement…</p>}
      {groupes?.length === 0 && <Vide icone="classes">Aucun groupe d'anglais.</Vide>}
      {suppression && (
        <ConfirmationSuppression
          titre={`Supprimer ${selection.nombre} groupe(s) d'anglais`}
          onFermer={() => setSuppression(false)}
          onConfirmer={async (confirmation) => {
            const r = await appeler("/admin/anglais/groupes/suppression", { methode: "POST", corps: { ids: selection.ids, confirmation } });
            setSuppression(false);
            setMessage(`${r.traites} groupe(s) supprimé(s). Les enfants des familles et leurs autres inscriptions sont conservés.`);
            selection.vider();
            charger();
          }}
        >
          <p>
            Groupes : {groupes.filter((g) => selection.choisis.has(g.id)).map((g) => g.nom).join(", ")}. Le travail d'anglais de
            leurs élèves est effacé ; les enfants des familles restent.
          </p>
        </ConfirmationSuppression>
      )}
      <BarreSelection selection={selection} noms={["groupe", "groupes"]}>
        <button className="danger petit" onClick={() => setSuppression(true)}>Supprimer</button>
      </BarreSelection>
      {groupes?.length > 0 && (
        <div className="tableau-defilant">
          <table>
            <thead>
              <tr>
                <CaseTout selection={selection} ids={groupes.map((g) => g.id)} libelle="Sélectionner tous les groupes" />
                <th>Groupe</th>
                <th>Niveau</th>
                <th>Professeur</th>
                <th className="nombre">Élèves</th>
                <th className="nombre">Actions</th>
              </tr>
            </thead>
            <tbody>
              {groupes.map((g) => (
                <Fragment key={g.id}>
                  <tr>
                    <CaseLigne selection={selection} id={g.id} libelle={`Sélectionner le groupe ${g.nom}`} />
                    <td>{g.nom}</td>
                    <td>{g.niveau}</td>
                    <td>{g.enseignant}</td>
                    <td className="nombre">{pluriel(g.eleves.length)}</td>
                    <td className="nombre">
                      <div className="actions">
                        <button className="petit" onClick={() => setGere(g.id)} aria-label={`Gérer le groupe ${g.nom}`}>
                          Gérer
                        </button>
                        <button className="secondaire petit" onClick={() => setTransfert(g)}>
                          Transférer
                        </button>
                        <button className="danger petit" onClick={() => supprimerGroupe(g)} aria-label={`Supprimer le groupe ${g.nom}`}>
                          Supprimer
                        </button>
                      </div>
                    </td>
                  </tr>
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {creation && (
        <NouveauGroupe
          profs={profs.filter((p) => p.actif && p.enseigne_anglais)}
          appeler={appeler}
          onFermer={() => setCreation(false)}
          onCree={(g) => {
            setCreation(false);
            setMessage(`Groupe ${g.nom} créé pour ${g.enseignant}.`);
            charger().then(() => setGere(g.id));
          }}
        />
      )}
      {gere && groupes?.some((g) => g.id === gere) && (
        <GererGroupe
          groupe={groupes.find((g) => g.id === gere)}
          appeler={appeler}
          onFermer={() => setGere(null)}
          onChange={charger}
          onTransferer={(g) => setTransfert(g)}
          onSupprimer={(g) => {
            setGere(null);
            supprimerGroupe(g);
          }}
        />
      )}
      {transfert && (
        <TransfertGroupe
          groupe={transfert}
          autres={profs.filter((p) => p.id !== transfert.enseignant_id && p.actif && p.enseigne_anglais)}
          onFermer={() => setTransfert(null)}
          onValider={async (versId) => {
            const ok = await action(
              appeler(`/admin/anglais/groupes/${transfert.id}/transfert`, { methode: "POST", corps: { vers_enseignant_id: versId } }),
              `Groupe ${transfert.nom} transféré.`,
            );
            if (ok) setTransfert(null);
          }}
        />
      )}
    </section>
  );
}

function TransfertGroupe({ groupe, autres, onFermer, onValider }) {
  const [vers, setVers] = useState(autres[0]?.id ?? "");
  return (
    <Modale titre={`Transférer le groupe ${groupe.nom}`} onFermer={onFermer}>
      {autres.length === 0 ? (
        <p className="doux">Aucun autre professeur d'anglais actif. Cochez la discipline Anglais d'un professeur dans « Professeurs ».</p>
      ) : (
        <>
          <p className="doux">Le groupe et ses {pluriel(groupe.eleves.length)} passent au professeur d'anglais choisi.</p>
          <label htmlFor="ta-vers">Vers</label>
          <select id="ta-vers" value={vers} onChange={(e) => setVers(Number(e.target.value))}>
            {autres.map((p) => (
              <option key={p.id} value={p.id}>
                {p.nom} ({p.email})
              </option>
            ))}
          </select>
          <div className="actions">
            <button disabled={!vers} onClick={() => onValider(Number(vers))}>
              Transférer
            </button>
          </div>
        </>
      )}
    </Modale>
  );
}

function NouveauGroupe({ profs, appeler, onFermer, onCree }) {
  const [nom, setNom] = useState("");
  const [niveau, setNiveau] = useState("4e");
  const [prof, setProf] = useState(profs[0]?.id ?? "");
  const [erreur, setErreur] = useState(null);

  async function creer(e) {
    e.preventDefault();
    setErreur(null);
    try {
      onCree(await appeler("/admin/anglais/groupes", { methode: "POST", corps: { nom, niveau, enseignant_id: Number(prof) } }));
    } catch (err) {
      setErreur(err.message);
    }
  }

  return (
    <Modale titre="Nouveau groupe d'anglais" onFermer={onFermer}>
      {profs.length === 0 ? (
        <p className="doux">Aucun professeur d'anglais actif. Cochez la discipline Anglais d'un professeur dans « Équipe ».</p>
      ) : (
        <form onSubmit={creer}>
          <label htmlFor="ng-nom">Nom du groupe</label>
          <input id="ng-nom" required maxLength={60} value={nom} onChange={(e) => setNom(e.target.value)} placeholder="Ex. : 4e B - mardi" />
          <label htmlFor="ng-niveau">Niveau</label>
          <select id="ng-niveau" value={niveau} onChange={(e) => setNiveau(e.target.value)}>
            <option value="4e">4e</option>
            <option value="3e">3e</option>
          </select>
          <label htmlFor="ng-prof">Professeur</label>
          <select id="ng-prof" value={prof} onChange={(e) => setProf(e.target.value)}>
            {profs.map((p) => (
              <option key={p.id} value={p.id}>
                {p.nom} ({p.email})
              </option>
            ))}
          </select>
          <Erreur message={erreur} />
          <div className="actions">
            <button type="submit" disabled={!nom.trim() || !prof}>
              Créer le groupe
            </button>
          </div>
        </form>
      )}
    </Modale>
  );
}

/** Même gestion qu'une classe de maths : élèves (ajout, carte, retrait), nom, professeur, suppression. */
function GererGroupe({ groupe, appeler, onFermer, onChange, onTransferer, onSupprimer }) {
  const [cartes, setCartes] = useState(null);
  const [message, setMessage] = useState(null);
  const [erreur, setErreur] = useState(null);

  async function agir(promesse, texte) {
    setErreur(null);
    setMessage(null);
    try {
      const r = await promesse;
      if (texte) setMessage(texte);
      await onChange();
      return r;
    } catch (err) {
      setErreur(err.message);
      return undefined;
    }
  }

  async function nouvelleCarte(e) {
    if (!window.confirm(`Nouvelle carte pour ${e.prenom} ? L'ancien code cessera de fonctionner, dans toutes ses matières.`)) return;
    const carte = await agir(appeler(`/admin/anglais/eleves/${e.id}/code`, { methode: "POST" }));
    if (carte) setCartes([carte]);
  }

  function retirer(e) {
    if (!window.confirm(`Retirer ${e.prenom} du groupe « ${groupe.nom} » ? Son travail d'anglais est effacé ; sa carte et ses autres matières restent.`)) return;
    agir(appeler(`/admin/anglais/eleves/${e.id}`, { methode: "DELETE" }), `${e.prenom} a été retiré·e du groupe.`);
  }

  function renommer() {
    const nom = window.prompt("Nouveau nom du groupe :", groupe.nom);
    if (!nom?.trim() || nom.trim() === groupe.nom) return;
    agir(appeler(`/admin/anglais/groupes/${groupe.id}`, { methode: "PATCH", corps: { nom: nom.trim() } }), "Groupe renommé.");
  }

  const chercher = useCallback((q) => appeler(`/admin/anglais/groupes/${groupe.id}/enfants?q=${encodeURIComponent(q)}`), [appeler, groupe.id]);
  const ajouter = (ids) => appeler(`/admin/anglais/groupes/${groupe.id}/enfants`, { methode: "POST", corps: { enfant_ids: ids } });

  return (
    <Modale titre={`Groupe ${groupe.nom}`} onFermer={onFermer} large>
      <p className="doux">
        Anglais {groupe.niveau} · {groupe.enseignant} · {pluriel(groupe.eleves.length)}
      </p>
      <div className="actions">
        <button className="secondaire petit" onClick={renommer}>Renommer</button>
        <button className="secondaire petit" onClick={() => onTransferer(groupe)}>Changer de professeur</button>
        <button className="danger petit" onClick={() => onSupprimer(groupe)}>Supprimer le groupe</button>
      </div>
      <Erreur message={erreur} />
      {message && <p className="succes" role="status">{message}</p>}
      {cartes && (
        <FicheCodes
          classe={groupe.nom}
          intitule={`Anglais ${groupe.niveau} · ${groupe.nom}`}
          chemin="/anglais/eleve"
          codes={cartes}
          onFermer={() => setCartes(null)}
        />
      )}
      {groupe.eleves.length === 0 ? (
        <p className="doux">Aucun élève inscrit pour l'instant.</p>
      ) : (
        <div className="tableau-defilant">
          <table>
            <thead>
              <tr>
                <th>Élève</th>
                <th>Identifiant</th>
                <th>
                  <span className="visuellement-cache">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {groupe.eleves.map((e) => (
                <tr key={e.id}>
                  <td><strong>{e.prenom}</strong></td>
                  <td>{e.identifiant ? <code>{e.identifiant}</code> : <span className="doux">—</span>}</td>
                  <td className="nombre">
                    <button className="lien petit" onClick={() => nouvelleCarte(e)} aria-label={`Nouvelle carte pour ${e.prenom}`}>
                      Nouvelle carte
                    </button>
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
      <AjoutEnfants key={groupe.id} chercher={chercher} ajouter={ajouter} onAjoutes={onChange} />
    </Modale>
  );
}
