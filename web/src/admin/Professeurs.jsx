import { useCallback, useEffect, useState } from "react";
import { Erreur } from "../composants.jsx";
import { useApi } from "../enseignant/useApi.js";
import { Modale, exporterCsv, formaterDate } from "../ui/Cadre.jsx";
import Icone from "../ui/Icone.jsx";

/** Comptes professeurs : création, modification, désactivation, transfert, suppression (EA3.1 à EA3.6). */
export default function Professeurs({ jeton, onExpire }) {
  const { appeler, erreur } = useApi(jeton, onExpire);
  const [liste, setListe] = useState(null);
  const [recherche, setRecherche] = useState("");
  const [fenetre, setFenetre] = useState(null); // { genre: "edition" | "secret" | "transfert" | "suppression", prof, ... }
  const [message, setMessage] = useState(null);

  const charger = useCallback(
    () => appeler(`/admin/enseignants${recherche ? `?q=${encodeURIComponent(recherche)}` : ""}`).then(setListe, () => {}),
    [appeler, recherche],
  );

  useEffect(() => {
    const minuterie = setTimeout(charger, 250);
    return () => clearTimeout(minuterie);
  }, [charger]);

  async function action(promesse, texte) {
    setMessage(null);
    try {
      const resultat = await promesse;
      if (texte) setMessage(texte);
      charger();
      return resultat;
    } catch {
      return null;
    }
  }

  async function basculer(p) {
    const verbe = p.actif ? "Désactiver" : "Réactiver";
    if (p.actif && !window.confirm(`Désactiver ${p.nom} ? Ni lui ni ses élèves ne pourront plus se connecter. Aucune donnée n'est supprimée.`)) return;
    await action(appeler(`/admin/enseignants/${p.id}/activation`, { methode: "POST", corps: { actif: !p.actif } }), `${verbe} : ${p.nom}.`);
  }

  async function reinitialiser(p) {
    if (!window.confirm(`Donner un nouveau mot de passe provisoire à ${p.nom} ? Ses sessions ouvertes seront fermées.`)) return;
    const r = await action(appeler(`/admin/enseignants/${p.id}/reinitialiser`, { methode: "POST" }));
    if (r) setFenetre({ genre: "secret", prof: r.enseignant, secret: r.mot_de_passe_provisoire });
  }

  return (
    <>
      <section className="carte">
        <div className="filtres">
          <div style={{ flexGrow: 3 }}>
            <label htmlFor="p-recherche">Rechercher</label>
            <input id="p-recherche" type="search" placeholder="Nom ou e-mail" value={recherche} onChange={(e) => setRecherche(e.target.value)} />
          </div>
          <div className="actions" style={{ flexGrow: 0, marginTop: 0 }}>
            <button className="secondaire" onClick={() => exporterCsv("professeurs.csv", liste ?? [])} disabled={!liste?.length}>
              CSV
            </button>
            <button onClick={() => setFenetre({ genre: "edition", prof: null })}>
              <Icone nom="plus" taille={18} /> Nouveau professeur
            </button>
          </div>
        </div>
        {message && (
          <p className="succes" role="status">
            {message}
          </p>
        )}
        <Erreur message={erreur} />
        {liste === null ? (
          <p className="doux">Chargement…</p>
        ) : (
          <div className="tableau-defilant">
            <table>
              <thead>
                <tr>
                  <th>Professeur</th>
                  <th>Statut</th>
                  <th className="nombre">Classes</th>
                  <th className="nombre">Élèves</th>
                  <th>Dernière connexion</th>
                  <th>
                    <span className="visuellement-cache">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {liste.map((p) => (
                  <tr key={p.id} className={p.actif ? "" : "estompe"}>
                    <td>
                      <strong>{p.nom}</strong>
                      <div className="aide">{p.email}</div>
                    </td>
                    <td>
                      {p.role === "admin" && <span className="badge accent">Admin</span>}{" "}
                      {p.actif ? <span className="badge ok">Actif</span> : <span className="badge neutre">Désactivé</span>}{" "}
                      {p.mdp_provisoire && <span className="badge alerte">Mot de passe provisoire</span>}
                    </td>
                    <td className="nombre">{p.nb_classes}</td>
                    <td className="nombre">{p.nb_eleves}</td>
                    <td>{formaterDate(p.derniere_connexion, { heure: true })}</td>
                    <td className="nombre">
                      <div className="actions">
                        <button className="icone" onClick={() => setFenetre({ genre: "edition", prof: p })} aria-label={`Modifier ${p.nom}`} title="Modifier">
                          <Icone nom="crayon" />
                        </button>
                        <button className="icone" onClick={() => reinitialiser(p)} aria-label={`Réinitialiser le mot de passe de ${p.nom}`} title="Mot de passe provisoire">
                          <Icone nom="cle" />
                        </button>
                        <button className="icone" onClick={() => basculer(p)} aria-label={`${p.actif ? "Désactiver" : "Réactiver"} ${p.nom}`} title={p.actif ? "Désactiver" : "Réactiver"}>
                          <Icone nom={p.actif ? "oeilBarre" : "oeil"} />
                        </button>
                        {p.nb_classes > 0 ? (
                          <button className="secondaire petit" onClick={() => setFenetre({ genre: "transfert", prof: p })}>
                            Transférer
                          </button>
                        ) : (
                          <button className="icone" onClick={() => setFenetre({ genre: "suppression", prof: p })} aria-label={`Supprimer ${p.nom}`} title="Supprimer">
                            <Icone nom="poubelle" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {fenetre?.genre === "edition" && (
        <Edition
          prof={fenetre.prof}
          appeler={appeler}
          onFermer={() => setFenetre(null)}
          onCree={(r) => {
            charger();
            setFenetre({ genre: "secret", prof: r.enseignant, secret: r.mot_de_passe_provisoire });
          }}
          onModifie={() => {
            setFenetre(null);
            setMessage("Modifications enregistrées.");
            charger();
          }}
        />
      )}
      {fenetre?.genre === "secret" && (
        <Modale titre="Mot de passe provisoire" onFermer={() => setFenetre(null)}>
          <p>
            Transmettez ce mot de passe à <strong>{fenetre.prof.nom}</strong> ({fenetre.prof.email}) par un canal sûr. Il ne sera
            plus affiché. Il devra le changer à sa première connexion.
          </p>
          <p className="secret">{fenetre.secret}</p>
          <div className="actions">
            <button onClick={() => navigator.clipboard?.writeText(fenetre.secret)}>Copier</button>
            <button className="secondaire" onClick={() => setFenetre(null)}>
              J'ai noté le mot de passe
            </button>
          </div>
        </Modale>
      )}
      {fenetre?.genre === "transfert" && (
        <Transfert
          prof={fenetre.prof}
          autres={(liste ?? []).filter((p) => p.id !== fenetre.prof.id && p.actif)}
          onFermer={() => setFenetre(null)}
          onValider={async (versId) => {
            const ok = await action(
              appeler(`/admin/enseignants/${fenetre.prof.id}/transfert`, { methode: "POST", corps: { vers_enseignant_id: versId } }),
              `Classes de ${fenetre.prof.nom} transférées.`,
            );
            if (ok) setFenetre(null);
          }}
        />
      )}
      {fenetre?.genre === "suppression" && (
        <Suppression
          prof={fenetre.prof}
          onFermer={() => setFenetre(null)}
          onValider={async (confirmation) => {
            const ok = await action(
              appeler(`/admin/enseignants/${fenetre.prof.id}?confirmation=${encodeURIComponent(confirmation)}`, { methode: "DELETE" }).then(() => true),
              `Compte de ${fenetre.prof.nom} supprimé.`,
            );
            if (ok) setFenetre(null);
          }}
        />
      )}
    </>
  );
}

function Edition({ prof, appeler, onFermer, onCree, onModifie }) {
  const [nom, setNom] = useState(prof?.nom ?? "");
  const [email, setEmail] = useState(prof?.email ?? "");
  const [role, setRole] = useState(prof?.role ?? "enseignant");
  const [erreur, setErreur] = useState(null);

  async function soumettre(e) {
    e.preventDefault();
    setErreur(null);
    try {
      const corps = { nom, email, role };
      if (prof) {
        await appeler(`/admin/enseignants/${prof.id}`, { methode: "POST", corps });
        onModifie();
      } else {
        onCree(await appeler("/admin/enseignants", { methode: "POST", corps }));
      }
    } catch (err) {
      setErreur(err.message);
    }
  }

  return (
    <Modale titre={prof ? `Modifier ${prof.nom}` : "Nouveau professeur"} onFermer={onFermer}>
      <form onSubmit={soumettre}>
        <label htmlFor="e-nom">Nom affiché</label>
        <input id="e-nom" maxLength={100} required value={nom} onChange={(e) => setNom(e.target.value)} placeholder="ex. Mme Martin" />
        <label htmlFor="e-email">E-mail</label>
        <input id="e-email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        <label htmlFor="e-role">Rôle</label>
        <select id="e-role" value={role} onChange={(e) => setRole(e.target.value)}>
          <option value="enseignant">Professeur</option>
          <option value="admin">Administrateur (et professeur)</option>
        </select>
        {!prof && <p className="aide">Un mot de passe provisoire sera affiché une seule fois après la création.</p>}
        <Erreur message={erreur} />
        <div className="actions">
          <button type="submit">{prof ? "Enregistrer" : "Créer le compte"}</button>
        </div>
      </form>
    </Modale>
  );
}

function Transfert({ prof, autres, onFermer, onValider }) {
  const [vers, setVers] = useState(autres[0]?.id ?? "");
  return (
    <Modale titre={`Transférer les classes de ${prof.nom}`} onFermer={onFermer}>
      <p className="doux">
        Les {prof.nb_classes} classe(s) et leurs {prof.nb_eleves} élève(s) passent au professeur choisi, avec tout leur historique.
      </p>
      <label htmlFor="t-vers">Vers</label>
      <select id="t-vers" value={vers} onChange={(e) => setVers(Number(e.target.value))}>
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
    </Modale>
  );
}

function Suppression({ prof, onFermer, onValider }) {
  const [saisie, setSaisie] = useState("");
  return (
    <Modale titre={`Supprimer le compte de ${prof.nom}`} onFermer={onFermer}>
      <p>Cette action est définitive. Ses ressources sont supprimées avec le compte.</p>
      <label htmlFor="s-email">Pour confirmer, saisissez {prof.email}</label>
      <input id="s-email" value={saisie} onChange={(e) => setSaisie(e.target.value)} autoComplete="off" />
      <div className="actions">
        <button className="danger" disabled={saisie.trim().toLowerCase() !== prof.email} onClick={() => onValider(saisie)}>
          Supprimer définitivement
        </button>
      </div>
    </Modale>
  );
}
