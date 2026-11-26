import "@fontsource-variable/inter";
// Titres (#149) : Space Grotesk, licence SIL OFL 1.1, servie par le site comme Inter.
import "@fontsource-variable/space-grotesk";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./theme.css";
import "./styles.css";
import { MARQUE } from "./marque.js";
import { rechargerApresMiseAJour } from "./miseAJour.js";

// Nom de l'onglet selon la variante construite (Boussole Maîtrise+ ou PKP Éducation, voir marque.js).
document.title = MARQUE.titreDocument;

window.addEventListener("vite:preloadError", rechargerApresMiseAJour);

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
