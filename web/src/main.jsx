import "@fontsource-variable/inter";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./theme.css";
import "./styles.css";
import { rechargerApresMiseAJour } from "./miseAJour.js";

window.addEventListener("vite:preloadError", rechargerApresMiseAJour);

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
