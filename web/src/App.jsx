import { Suspense, lazy } from "react";
import Accueil from "./Accueil.jsx";
import EspaceEleve from "./eleve/EspaceEleve.jsx";
import EspaceEnseignant from "./enseignant/EspaceEnseignant.jsx";
import { useChemin } from "./navigation.js";
import { Logo } from "./ui/Icone.jsx";

// L'espace administrateur n'est chargé que par ceux qui l'ouvrent : les élèves ne le téléchargent pas.
const EspaceAdmin = lazy(() => import("./admin/EspaceAdmin.jsx"));

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

  // Élève et accueil public : colonne centrée, priorité au mobile.
  const eleve = chemin === "/eleve" || chemin.startsWith("/eleve/");
  return (
    <div className="page">
      <header className="entete">
        <Logo />
        <nav aria-label="Espaces">
          {eleve ? <a href="/enseignant">Espace professeur</a> : <a href="/eleve">Espace élève</a>}
        </nav>
      </header>
      <main>{eleve ? <EspaceEleve /> : <Accueil />}</main>
      <footer className="pied">
        <span>© {new Date().getFullYear()} PKP Math Lycée</span>
        <span>Aucun traceur publicitaire · Données des élèves réduites au prénom</span>
      </footer>
    </div>
  );
}
