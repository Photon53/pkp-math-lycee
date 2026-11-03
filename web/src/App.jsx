import { Suspense, lazy } from "react";
import Accueil from "./Accueil.jsx";
import EspaceEleve from "./eleve/EspaceEleve.jsx";
import EspaceEnseignant from "./enseignant/EspaceEnseignant.jsx";
import Methode from "./Methode.jsx";
import { useChemin } from "./navigation.js";
import { Logo } from "./ui/Icone.jsx";

// L'espace administrateur n'est chargé que par ceux qui l'ouvrent : les élèves ne le téléchargent pas.
const EspaceAdmin = lazy(() => import("./admin/EspaceAdmin.jsx"));
// Même principe pour PKP Anglais : ni les élèves ni les professeurs de maths ne le téléchargent.
const EspaceAnglais = lazy(() => import("./anglais/EspaceAnglais.jsx"));
const EspaceEleveAnglais = lazy(() => import("./anglais/EspaceEleveAnglais.jsx"));

export default function App() {
  const chemin = useChemin();

  // Professeur et administrateur : application à navigation latérale.
  if (chemin === "/admin" || chemin.startsWith("/admin/")) {
    return (
      <Suspense fallback={<p className="doux page">Chargement…</p>}>
        <EspaceAdmin chemin={chemin} />
      </Suspense>
    );
  }
  if (chemin === "/enseignant" || chemin.startsWith("/enseignant/")) return <EspaceEnseignant chemin={chemin} />;
  // Élève d'anglais : avant l'espace professeur /anglais, dont il partage le préfixe.
  const eleveAnglais = chemin === "/anglais/eleve" || chemin.startsWith("/anglais/eleve/");
  if (!eleveAnglais && (chemin === "/anglais" || chemin.startsWith("/anglais/"))) {
    return (
      <Suspense fallback={<p className="doux page">Chargement…</p>}>
        <EspaceAnglais chemin={chemin} />
      </Suspense>
    );
  }

  // Élève et accueil public : colonne centrée, priorité au mobile.
  const eleve = chemin === "/eleve" || chemin.startsWith("/eleve/");
  const methode = chemin === "/methode";
  return (
    <div className="page">
      <header className="entete">
        <Logo />
        <nav aria-label="Espaces">
          {!methode && <a href="/methode">La méthode PKP</a>}
          {eleveAnglais ? (
            <a href="/anglais">Espace professeur</a>
          ) : eleve ? (
            <a href="/enseignant">Espace professeur</a>
          ) : (
            <a href="/eleve">Espace élève</a>
          )}
        </nav>
      </header>
      <main>
        {eleveAnglais ? (
          <Suspense fallback={<p className="doux">Chargement…</p>}>
            <EspaceEleveAnglais />
          </Suspense>
        ) : eleve ? (
          <EspaceEleve />
        ) : methode ? (
          <Methode />
        ) : (
          <Accueil />
        )}
      </main>
      <footer className="pied">
        <span>© {new Date().getFullYear()} PKP Math Lycée</span>
        <span>Aucun traceur publicitaire · Données des élèves réduites au prénom</span>
      </footer>
    </div>
  );
}
