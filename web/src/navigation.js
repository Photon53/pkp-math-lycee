// Routage minimal par l'historique du navigateur : quatre espaces et quelques sous-pages
// ne justifient pas une bibliothèque de routage.
import { createElement, useEffect, useState } from "react";

const EVENEMENT = "pkp:navigation";

export function naviguer(chemin) {
  if (chemin === window.location.pathname) return;
  window.history.pushState(null, "", chemin);
  window.dispatchEvent(new Event(EVENEMENT));
  window.scrollTo?.(0, 0);
}

export function useChemin() {
  const [chemin, setChemin] = useState(window.location.pathname);
  useEffect(() => {
    const suivre = () => setChemin(window.location.pathname);
    window.addEventListener("popstate", suivre);
    window.addEventListener(EVENEMENT, suivre);
    return () => {
      window.removeEventListener("popstate", suivre);
      window.removeEventListener(EVENEMENT, suivre);
    };
  }, []);
  return chemin;
}

/** Lien interne : navigation sans rechargement ; Ctrl/Cmd+clic ouvre toujours un nouvel onglet. */
export function Lien({ vers, actif, children, ...props }) {
  function cliquer(e) {
    if (e.ctrlKey || e.metaKey || e.shiftKey || e.button !== 0) return;
    e.preventDefault();
    naviguer(vers);
  }
  return createElement(
    "a",
    { href: vers, onClick: cliquer, "aria-current": actif ? "page" : undefined, ...props },
    children,
  );
}
