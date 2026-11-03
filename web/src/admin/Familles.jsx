import { useCallback, useEffect, useState } from "react";
import { Erreur } from "../composants.jsx";
import { useApi } from "../enseignant/useApi.js";
import { Modale, Pagination, Vide, formaterDate } from "../ui/Cadre.jsx";
import Icone from "../ui/Icone.jsx";

const nomEnfant = (e) => `${e.prenom} (${e.classe})`;

/** Familles (CDC V2, EA.8 à EA.12) : recherche par e-mail ou par classe — jamais de liste complète —,
 * création, rattachement et détachement des enfants, historique, mot de passe oublié, suppression. */
export default function Familles({ jeton, onExpire }) {
  const { appeler, erreur } = useApi(jeton, onExpire);
  const [recherche, setRecherche] = useState("");
  const [classeId, setClasseId] = useState("");
  const [classes, setClasses] = useState([]);
  const [page, setPage] = useState(1);
  const [resultats, setResultats] = useState(null);
  const [fenetre, setFenetre] = useState(null); // { genre: "nouveau" | "famille" | "secret", ... }
  const [message, setMessage] = useState(null);

  useEffect(() => {
    appeler("/admin/classes").then(setClasses, () => {});
  }, [appeler]);

  const filtre = recherche.trim().length >= 3 || classeId !== "";
  const charger = useCallback(() => {
    if (!filtre) return Promise.resolve(setResultats(null));
    const params = new URLSearchParams({ page: String(page) });
    if (recherche.trim()) params.set("q", recherche.trim());
    if (classeId !== "") params.set("classe_id", classeId);
    return appeler(`/admin/parents?${params}`).then(setResultats, () => {});
  }, [appeler, filtre, page, recherche, classeId]);

  useEffect(() => {
    const minuterie = setTimeout(charger, 250);
    return () => clearTimeout(minuterie);
  }, [charger]);

  function montrerSecret(email, secret) {
    setFenetre({ genre: "secret", email, secret });
  }

  return (
    <>
      <section className="carte">
        <div className="filtres">
          <div style={{ flexGrow: 3 }}>
            <label htmlFor="f-recherche">E-mail du parent (au moins 3 caractères)</label>
            <input
              id="f-recherche"
              type="search"
              value={recherche}
              onChange={(e) => {
                setRecherche(e.target.value);
                setPage(1);
              }}
            />
          </div>
          <div>
            <label htmlFor="f-classe">ou classe d'un enfant</label>
            <select
              id="f-classe"
              value={classeId}
              onChange={(e) => {
                setClasseId(e.target.value);
                setPage(1);
              }}
            >
              <option value="">—</option>
              {classes.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.code} ({c.enseignant})
                </option>
              ))}
            </select>
          </div>
          <div className="actions" style={{ flexGrow: 0, marginTop: 0 }}>
            <button onClick={() => setFenetre({ genre: "nouveau" })}>
              <Icone nom="plus" taille={18} /> Nouveau parent
            </button>
          </div>
        </div>
        <p className="aide">Pas de liste complète des familles : cherchez un parent par son e-mail, ou par la classe d'un enfant.</p>
        {message && (
          <p className="succes" role="status">
            {message}
          </p>
        )}
        <Erreur message={erreur} />
        {resultats?.total === 0 && <Vide>Aucun compte parent trouvé.</Vide>}
        {resultats?.total > 0 && (
          <>
            <p className="doux petit">{resultats.total} compte(s) parent</p>
            <div className="tableau-defilant">
              <table>
                <thead>
                  <tr>
                    <th>E-mail</th>
                    <th>Enfants suivis</th>
                    <th>Dernière connexion</th>
                    <th>
                      <span className="visuellement-cache">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {resultats.elements.map((p) => (
                    <tr key={p.id}>
                      <td>{p.email}</td>
                      <td>{p.enfants.map(nomEnfant).join(", ")}</td>
                      <td>{p.mdp_provisoire ? <span className="badge alerte">Mot de passe provisoire</span> : formaterDate(p.derniere_connexion)}</td>
                      <td className="nombre">
                        <button className="secondaire petit" onClick={() => setFenetre({ genre: "famille", id: p.id })}>
                          Gérer
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={page} total={resultats.total} onChange={setPage} />
          </>
        )}
      </section>

      {fenetre?.genre === "nouveau" && (
        <NouveauParent
          appeler={appeler}
          onFermer={() => setFenetre(null)}
          onCree={(r) => {
            charger();
            if (r.mot_de_passe_provisoire) montrerSecret(r.famille.email, r.mot_de_passe_provisoire);
            else {
              setFenetre(null);
              setMessage(`Enfant rattaché au compte existant de ${r.famille.email}.`);
            }
          }}
        />
      )}
      {fenetre?.genre === "famille" && (
        <Famille
          id={fenetre.id}
          appeler={appeler}
          onFermer={() => {
            setFenetre(null);
            charger();
          }}
          onSecret={montrerSecret}
          onSupprime={(texte) => {
            setFenetre(null);
            setMessage(texte);
            charger();
          }}
        />
      )}
      {fenetre?.genre === "secret" && (
        <Modale titre="Mot de passe provisoire" onFermer={() => setFenetre(null)}>
          <p>
            Transmettez ce mot de passe à <strong>{fenetre.email}</strong> par un canal sûr. Il ne sera plus affiché ; le parent le
            changera à sa première connexion.
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
    </>
  );
}

/** Choix d'un élève par son prénom, parmi toutes les classes. */
function ChoixEleve({ appeler, id, onChoisir, exclus = [] }) {
  const [prenom, setPrenom] = useState("");
  const [trouves, setTrouves] = useState([]);

  useEffect(() => {
    if (prenom.trim().length < 2) {
      setTrouves([]);
      return undefined;
    }
    const minuterie = setTimeout(
      () => appeler(`/admin/eleves?${new URLSearchParams({ q: prenom.trim() })}`).then((r) => setTrouves(r.elements.slice(0, 8)), () => {}),
      250,
    );
    return () => clearTimeout(minuterie);
  }, [appeler, prenom]);

  return (
    <>
      <label htmlFor={id}>Prénom de l'enfant</label>
      <input id={id} type="search" value={prenom} onChange={(e) => setPrenom(e.target.value)} autoComplete="off" />
      {trouves.length > 0 && (
        <ul className="liste-choix">
          {trouves
            .filter((e) => !exclus.includes(e.id))
            .map((e) => (
              <li key={e.id}>
                <button type="button" className="lien" onClick={() => onChoisir(e)}>
                  {e.prenom} — {e.classe} ({e.enseignant})
                </button>
              </li>
            ))}
        </ul>
      )}
    </>
  );
}

function NouveauParent({ appeler, onFermer, onCree }) {
  const [email, setEmail] = useState("");
  const [enfant, setEnfant] = useState(null);
  const [erreur, setErreur] = useState(null);

  async function soumettre(e) {
    e.preventDefault();
    setErreur(null);
    try {
      onCree(await appeler("/admin/parents", { methode: "POST", corps: { email, eleve_id: enfant.id } }));
    } catch (err) {
      setErreur(err.message);
    }
  }

  return (
    <Modale titre="Nouveau parent" onFermer={onFermer}>
      <form onSubmit={soumettre}>
        <label htmlFor="n-email">E-mail du parent</label>
        <input id="n-email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        {enfant ? (
          <p>
            Enfant : <strong>{nomEnfant(enfant)}</strong>{" "}
            <button type="button" className="lien petit" onClick={() => setEnfant(null)}>
              changer
            </button>
          </p>
        ) : (
          <ChoixEleve appeler={appeler} id="n-enfant" onChoisir={setEnfant} />
        )}
        <p className="aide">Si un compte existe déjà pour cet e-mail, l'enfant y est rattaché et le mot de passe ne change pas.</p>
        <Erreur message={erreur} />
        <div className="actions">
          <button type="submit" disabled={!enfant}>
            Créer et rattacher
          </button>
        </div>
      </form>
    </Modale>
  );
}

function Famille({ id, appeler, onFermer, onSecret, onSupprime }) {
  const [famille, setFamille] = useState(null);
  const [ajout, setAjout] = useState(false);
  const [confirmation, setConfirmation] = useState("");
  const [erreur, setErreur] = useState(null);

  useEffect(() => {
    appeler(`/admin/parents/${id}`).then(setFamille, (err) => setErreur(err.message));
  }, [appeler, id]);

  async function agir(promesse) {
    setErreur(null);
    try {
      return await promesse;
    } catch (err) {
      setErreur(err.message);
      return undefined;
    }
  }

  async function rattacher(eleve) {
    const r = await agir(appeler(`/admin/parents/${id}/enfants`, { methode: "POST", corps: { eleve_id: eleve.id } }));
    if (r) {
      setFamille(r);
      setAjout(false);
    }
  }

  async function detacher(enfant) {
    const dernier = famille.enfants.length === 1;
    const texte = dernier
      ? `Détacher ${nomEnfant(enfant)} ? C'est son dernier enfant : le compte de ${famille.email} sera supprimé.`
      : `Détacher ${nomEnfant(enfant)} ? Le parent n'aura plus accès à son suivi, immédiatement.`;
    if (!window.confirm(texte)) return;
    const r = await agir(appeler(`/admin/parents/${id}/enfants/${enfant.id}`, { methode: "DELETE" }));
    if (r === null) onSupprime(`Compte de ${famille.email} supprimé : il ne suivait plus aucun enfant.`);
    else if (r) setFamille(r);
  }

  async function reinitialiser() {
    if (!window.confirm(`Donner un nouveau mot de passe provisoire à ${famille.email} ? Ses sessions ouvertes seront fermées.`)) return;
    const r = await agir(appeler(`/admin/parents/${id}/reinitialiser`, { methode: "POST" }));
    if (r) onSecret(famille.email, r.mot_de_passe_provisoire);
  }

  async function supprimer() {
    const r = await agir(
      appeler(`/admin/parents/${id}?${new URLSearchParams({ confirmation })}`, { methode: "DELETE" }).then(() => true),
    );
    if (r) onSupprime(`Compte de ${famille.email} supprimé. Les enfants et leur travail sont conservés.`);
  }

  return (
    <Modale titre={famille ? famille.email : "Famille"} onFermer={onFermer} large>
      <Erreur message={erreur} />
      {famille === null ? (
        <p className="doux">Chargement…</p>
      ) : (
        <>
          <p className="doux">
            Compte créé le {formaterDate(famille.cree_le)} ·{" "}
            {famille.mdp_provisoire ? "mot de passe provisoire" : `dernière connexion : ${formaterDate(famille.derniere_connexion, { heure: true })}`}
          </p>
          <h3>Enfants suivis</h3>
          <ul className="liste-simple">
            {famille.enfants.map((e) => (
              <li key={e.id}>
                <strong>{e.prenom}</strong> — {e.classe}, {e.niveau} ({e.enseignant}){" "}
                <button className="lien petit" onClick={() => detacher(e)} aria-label={`Détacher ${nomEnfant(e)}`}>
                  Détacher
                </button>
              </li>
            ))}
          </ul>
          {ajout ? (
            <ChoixEleve appeler={appeler} id="r-enfant" onChoisir={rattacher} exclus={famille.enfants.map((e) => e.id)} />
          ) : (
            <button className="secondaire petit" onClick={() => setAjout(true)}>
              <Icone nom="plus" taille={16} /> Rattacher un enfant
            </button>
          )}

          <h3>Historique des rattachements</h3>
          <div className="tableau-defilant">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Action</th>
                  <th>Enfant</th>
                  <th>Par</th>
                </tr>
              </thead>
              <tbody>
                {famille.historique.map((h, i) => (
                  <tr key={i}>
                    <td>{formaterDate(h.le, { heure: true })}</td>
                    <td>{h.action === "ajout" ? <span className="badge ok">Rattaché</span> : <span className="badge neutre">Détaché</span>}</td>
                    <td>{h.enfant}</td>
                    <td>{h.par}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="actions">
            <button className="secondaire" onClick={reinitialiser}>
              <Icone nom="cle" taille={16} /> Nouveau mot de passe
            </button>
          </div>
          <details>
            <summary>Supprimer le compte (demande du parent)</summary>
            <label htmlFor="f-confirmation">Pour confirmer, saisissez {famille.email}</label>
            <input id="f-confirmation" value={confirmation} onChange={(e) => setConfirmation(e.target.value)} autoComplete="off" />
            <div className="actions">
              <button className="danger" disabled={confirmation.trim().toLowerCase() !== famille.email} onClick={supprimer}>
                Supprimer définitivement
              </button>
            </div>
          </details>
        </>
      )}
    </Modale>
  );
}
