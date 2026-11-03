import { Suspense, lazy } from "react";
import Accueil from "./Accueil.jsx";
import { useChemin } from "./navigation.js";
import { Logo } from "./ui/Icone.jsx";

// Chaque espace n'est chargé que par ceux qui l'ouvrent : la page d'accueil reste légère sur téléphone,
// les élèves ne téléchargent ni l'espace professeur (QR codes) ni l'administration.
const EspaceEleve = lazy(() => import("./eleve/EspaceEleve.jsx"));
const Methode = lazy(() => import("./Methode.jsx"));
const EspaceEnseignant = lazy(() => import("./enseignant/EspaceEnseignant.jsx"));
const EspaceAdmin = lazy(() => import("./admin/EspaceAdmin.jsx"));
const EspaceParent = lazy(() => import("./parent/EspaceParent.jsx"));
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
  if (chemin === "/enseignant" || chemin.startsWith("/enseignant/")) {
    return (
      <Suspense fallback={<p className="doux page">Chargement…</p>}>
        <EspaceEnseignant chemin={chemin} />
      </Suspense>
    );
  }
  if (chemin === "/parent" || chemin.startsWith("/parent/")) {
    return (
      <Suspense fallback={<p className="doux page">Chargement…</p>}>
        <EspaceParent />
      </Suspense>
    );
  }
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
          <Suspense fallback={<p className="doux">Chargement…</p>}>
            <EspaceEleve />
          </Suspense>
        ) : methode ? (
          <Suspense fallback={<p className="doux">Chargement…</p>}>
            <Methode />
          </Suspense>
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
