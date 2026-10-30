import { useEffect, useState } from "react";
import { Erreur } from "../composants.jsx";
import { useApi } from "../enseignant/useApi.js";
import { Lien } from "../navigation.js";
import { exporterCsv, formaterDate, pourcentage } from "../ui/Cadre.jsx";
import { Barres, Courbe } from "../ui/Graphiques.jsx";
import Icone from "../ui/Icone.jsx";

const PERIODES = [
  [7, "7 jours"],
  [30, "30 jours"],
  [365, "Année"],
];

const NOMS_NIVEAUX = { "2nde": "Seconde", "1re": "Première", Tle: "Terminale" };
const ORDRE_NIVEAUX = Object.keys(NOMS_NIVEAUX);

/** Statistiques globales du site, uniquement agrégées (EA3.20). */
export default function TableauDeBord({ jeton, onExpire }) {
  const { appeler, erreur } = useApi(jeton, onExpire);
  const [periode, setPeriode] = useState(30);
  const [stats, setStats] = useState(null);

  useEffect(() => {
    setStats(null);
    appeler(`/admin/statistiques?periode=${periode}`).then(setStats, () => {});
  }, [appeler, periode]);

  return (
    <>
      <div className="actions" style={{ marginTop: 0, marginBottom: 16, justifyContent: "space-between" }}>
        <div className="onglets" role="tablist" style={{ margin: 0, border: "none" }}>
          {PERIODES.map(([v, l]) => (
            <button
              key={v}
              role="tab"
              aria-selected={periode === v}
              className={periode === v ? "onglet actif" : "onglet"}
              onClick={() => setPeriode(v)}
            >
              {l}
            </button>
          ))}
        </div>
        {stats && <span className="doux petit">Calculé le {formaterDate(stats.calcule_le, { heure: true })} · mis à jour toutes les 10 min</span>}
      </div>
      <Erreur message={erreur} />
      {!stats && !erreur && <p className="doux">Chargement…</p>}
      {stats && <Contenu stats={stats} />}
    </>
  );
}

function Contenu({ stats }) {
  const chapitres = stats.reussite_par_chapitre.filter((c) => c.taux_reussite != null);
  const masques = stats.reussite_par_chapitre.length - chapitres.length;
  return (
    <>
      <div className="kpis">
        <Kpi icone="professeurs" libelle="Professeurs actifs" valeur={stats.professeurs_actifs} sous={`sur ${stats.professeurs_total}`} />
        <Kpi icone="eleve" libelle="Élèves actifs" valeur={stats.eleves_actifs} sous={`sur ${stats.eleves_total} inscrits`} />
        <Kpi icone="exercices" libelle="Réponses" valeur={stats.reponses.toLocaleString("fr-FR")} sous={`${stats.seances} séances`} />
        <Kpi icone="ok" libelle="Taux de réussite" valeur={pourcentage(stats.taux_reussite)} sous="toutes questions confondues" />
      </div>

      <div className="grille-2">
        <section className="carte">
          <TitreCarte titre="Séances par jour" csv={() => exporterCsv("seances-par-jour.csv", stats.seances_par_jour)} />
          <Courbe points={stats.seances_par_jour.map((p) => ({ x: p.jour, y: p.valeur }))} libelle="Séances" />
        </section>
        <section className="carte">
          <TitreCarte titre="Réponses et réussite par jour" csv={() => exporterCsv("reponses-par-jour.csv", stats.reponses_par_jour)} />
          <Courbe
            points={stats.reponses_par_jour.map((p) => ({ x: p.jour, y: p.reponses }))}
            libelle="Réponses"
            secondaire={stats.reponses_par_jour.map((p) => ({ x: p.jour, y: p.correctes }))}
            libelleSecondaire="Bonnes réponses"
          />
        </section>

        <section className="carte">
          <TitreCarte titre="Réussite par chapitre" csv={() => exporterCsv("reussite-par-chapitre.csv", stats.reussite_par_chapitre)} />
          {chapitres.length === 0 ? (
            <p className="doux">Pas encore assez d'élèves pour publier un taux (5 élèves au moins par chapitre).</p>
          ) : (
            <Barres
              elements={chapitres.map((c) => ({
                nom: `${c.niveau} · ${c.titre}`,
                valeur: c.taux_reussite,
                texte: pourcentage(c.taux_reussite),
                ton: c.taux_reussite < 0.4 ? "ko" : c.taux_reussite < 0.6 ? "alerte" : "ok",
              }))}
              max={1}
            />
          )}
          {masques > 0 && <p className="aide">{masques} chapitre(s) masqué(s) : moins de 5 élèves y ont répondu.</p>}
        </section>

        <section className="carte">
          <TitreCarte titre="Couverture du contenu" csv={() => exporterCsv("couverture.csv", stats.couverture)} />
          <Barres
            empilees
            elements={[...stats.couverture].sort((a, b) => ORDRE_NIVEAUX.indexOf(a.niveau) - ORDRE_NIVEAUX.indexOf(b.niveau)).map((c) => ({
              nom: NOMS_NIVEAUX[c.niveau] ?? c.niveau,
              segments: [
                { valeur: c.validees, ton: "ok" },
                { valeur: c.a_valider, ton: "" },
                { valeur: c.a_corriger, ton: "ko" },
              ],
              texte: String(c.validees + c.a_valider + c.a_corriger),
            }))}
          />
          <div className="legende">
            <span><i style={{ background: "var(--ok)" }} />Validées</span>
            <span><i style={{ background: "var(--action)" }} />À valider</span>
            <span><i style={{ background: "var(--ko)" }} />À corriger</span>
          </div>
          <p className="aide">
            {stats.competences_sans_cours} compétence(s) sans cours · {stats.chapitres_sans_question_validee.length} chapitre(s) sans
            question validée.
          </p>
        </section>

        <section className="carte">
          <TitreCarte titre="Questions les plus difficiles" csv={() => exporterCsv("questions-difficiles.csv", stats.questions_difficiles)} />
          {stats.questions_difficiles.length === 0 ? (
            <p className="doux">Aucune question n'a encore reçu 30 réponses sur la période.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Question</th>
                  <th className="nombre">Réponses</th>
                  <th className="nombre">Réussite</th>
                </tr>
              </thead>
              <tbody>
                {stats.questions_difficiles.map((q) => (
                  <tr key={q.question_id}>
                    <td>
                      <Lien vers={`/admin/exercices?q=${encodeURIComponent(q.code ?? q.enonce.slice(0, 30))}`}>{q.code ?? `#${q.question_id}`}</Lien>
                      <div className="aide">{q.chapitre}</div>
                    </td>
                    <td className="nombre">{q.reponses}</td>
                    <td className="nombre">{pourcentage(q.taux_reussite)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="carte">
          <TitreCarte titre="Classes et élèves par niveau" csv={() => exporterCsv("repartition.csv", stats.repartition)} />
          <table>
            <thead>
              <tr>
                <th>Niveau</th>
                <th>Parcours</th>
                <th className="nombre">Classes</th>
                <th className="nombre">Élèves</th>
              </tr>
            </thead>
            <tbody>
              {stats.repartition.map((r) => (
                <tr key={`${r.niveau}-${r.parcours}`}>
                  <td>{NOMS_NIVEAUX[r.niveau] ?? r.niveau}</td>
                  <td>{r.parcours}</td>
                  <td className="nombre">{r.classes}</td>
                  <td className="nombre">{r.eleves}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <h3>Ressources</h3>
          <p className="petit">
            {stats.ressources_liens} lien(s) · {stats.ressources_pdf} PDF
            {stats.ressources_consultees.length > 0 && " · les plus ouvertes :"}
          </p>
          {stats.ressources_consultees.length > 0 && (
            <Barres
              elements={stats.ressources_consultees.map((r) => ({ nom: r.titre, valeur: r.consultations, texte: String(r.consultations) }))}
            />
          )}
        </section>
      </div>
    </>
  );
}

function Kpi({ icone, libelle, valeur, sous }) {
  return (
    <div className="kpi">
      <div className="libelle">
        <Icone nom={icone} taille={16} /> {libelle}
      </div>
      <div className="valeur">{valeur}</div>
      <div className="sous">{sous}</div>
    </div>
  );
}

function TitreCarte({ titre, csv }) {
  return (
    <div className="carte-titre">
      <h2 style={{ fontSize: "1.05rem" }}>{titre}</h2>
      <button className="secondaire petit" onClick={csv}>
        CSV
      </button>
    </div>
  );
}
