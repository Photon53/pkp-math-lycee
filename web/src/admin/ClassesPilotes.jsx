// Issue #176 — Accès au français réservé aux classes pilotes (Claude)
//
// Classes pilotes (décision SEC-D6) : seul moyen d'ouvrir un domaine actif mais fermé au public à quelques
// classes. Le contrôle est fait par l'API sur chaque route élève ; cet écran tient seulement la liste.
import { useCallback, useEffect, useState } from "react";
import { Erreur } from "../composants.jsx";
import { useApi } from "../enseignant/useApi.js";

export default function ClassesPilotes({ jeton, onExpire, domaines }) {
  const { appeler, erreur } = useApi(jeton, onExpire);
  const [pilotes, setPilotes] = useState(null);
  const [message, setMessage] = useState(null);
  const fermes = domaines.filter((d) => d.actif && !d.public);
  const [domaine, setDomaine] = useState("");
  const [niveau, setNiveau] = useState("");
  const [professeurs, setProfesseurs] = useState([]);
  const [professeur, setProfesseur] = useState("");
  const [motif, setMotif] = useState("");

  const charger = useCallback(() => appeler("/admin/classes-pilotes").then(setPilotes, () => {}), [appeler]);
  useEffect(() => {
    charger();
  }, [charger]);

  const choisi = fermes.find((d) => d.code === domaine);
  useEffect(() => {
    setNiveau("");
    setProfesseur("");
    setProfesseurs([]);
    if (domaine) appeler(`/admin/enseignants?domaine=${encodeURIComponent(domaine)}`).then((l) => setProfesseurs(l.filter((p) => p.actif)), () => {});
  }, [appeler, domaine]);

  async function creer(e) {
    e.preventDefault();
    setMessage(null);
    try {
      const p = await appeler("/admin/classes-pilotes", {
        methode: "POST",
        corps: { matiere: choisi.matiere, niveau, enseignant_id: Number(professeur), motif },
      });
      setMessage(`Classe pilote ${p.code} créée pour ${p.enseignant}.`);
      setMotif("");
      charger();
    } catch {
      // erreur déjà affichée
    }
  }

  async function revoquer(p) {
    if (!window.confirm(`Retirer ${p.code} des classes pilotes ? Ses élèves n'auront plus accès au contenu, séance en cours comprise ; rien n'est supprimé.`)) return;
    setMessage(null);
    try {
      await appeler(`/admin/classes-pilotes/${p.classe_id}`, { methode: "DELETE" });
      setMessage(`${p.code} n'est plus une classe pilote.`);
      charger();
    } catch {
      // erreur déjà affichée
    }
  }

  return (
    <section className="carte" aria-labelledby="titre-classes-pilotes">
      <h2 id="titre-classes-pilotes">Classes pilotes</h2>
      <p className="doux">
        Un domaine activé mais fermé aux élèves peut être ouvert à quelques classes seulement. Les élèves des autres classes,
        les familles et les visiteurs n'y ont pas accès.
      </p>
      {message && <p className="succes" role="status">{message}</p>}
      <Erreur message={erreur} />
      {pilotes === null ? (
        <p className="doux">Chargement…</p>
      ) : pilotes.length === 0 ? (
        <p className="doux">Aucune classe pilote.</p>
      ) : (
        <div className="tableau-defilant">
          <table>
            <thead>
              <tr>
                <th>Classe</th>
                <th>Domaine</th>
                <th>Professeur</th>
                <th className="nombre">Élèves</th>
                <th>Motif</th>
                <th>Accordée</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {pilotes.map((p) => (
                <tr key={p.classe_id}>
                  <td><strong>{p.code}</strong></td>
                  <td>{p.domaine}</td>
                  <td>{p.enseignant}</td>
                  <td className="nombre">{p.nb_eleves}</td>
                  <td>{p.motif}</td>
                  <td>
                    {new Date(p.accordee_le).toLocaleDateString("fr-FR")}
                    {p.accordee_par && <div className="doux">{p.accordee_par}</div>}
                  </td>
                  <td>
                    <button className="secondaire" onClick={() => revoquer(p)}>Retirer</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {fermes.length === 0 ? (
        <p className="aide">Pour créer une classe pilote, activez d'abord un domaine sans l'ouvrir aux élèves.</p>
      ) : (
        <form onSubmit={creer} className="ligne-champs">
          <label>
            Domaine
            <select value={domaine} onChange={(e) => setDomaine(e.target.value)} required>
              <option value="">Choisir…</option>
              {fermes.map((d) => <option key={d.code} value={d.code}>{d.libelle}</option>)}
            </select>
          </label>
          <label>
            Niveau
            <select value={niveau} onChange={(e) => setNiveau(e.target.value)} required disabled={!choisi}>
              <option value="">Choisir…</option>
              {(choisi?.niveaux ?? []).map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </label>
          <label>
            Professeur
            <select value={professeur} onChange={(e) => setProfesseur(e.target.value)} required disabled={!choisi}>
              <option value="">Choisir…</option>
              {professeurs.map((p) => <option key={p.id} value={p.id}>{p.nom}</option>)}
            </select>
          </label>
          <label>
            Motif
            <input
              value={motif}
              onChange={(e) => setMotif(e.target.value)}
              required
              minLength={3}
              maxLength={200}
              placeholder="Ex. : pilote de janvier, sans nom d'élève"
            />
          </label>
          <button type="submit" disabled={!choisi || !niveau || !professeur || motif.trim().length < 3}>Créer la classe pilote</button>
        </form>
      )}
    </section>
  );
}
