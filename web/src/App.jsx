import EspaceEleve from "./eleve/EspaceEleve.jsx";
import EspaceEnseignant from "./enseignant/EspaceEnseignant.jsx";

export default function App() {
  const enseignant = window.location.pathname.startsWith("/enseignant");
  return (
    <div className="page">
      <header className="entete">
        <a className="logo" href="/">
          PKP <span>Math</span> Lycée
        </a>
        <a href={enseignant ? "/" : "/enseignant"}>{enseignant ? "Espace élève" : "Espace enseignant"}</a>
      </header>
      <main>{enseignant ? <EspaceEnseignant /> : <EspaceEleve />}</main>
    </div>
  );
}
