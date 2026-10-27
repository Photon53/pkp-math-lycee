import { useCallback, useRef, useState } from "react";
import { api } from "../api.js";

/**
 * Appels API authentifiés de l'espace enseignant : mémorise la dernière erreur
 * et déconnecte si le jeton a expiré.
 */
export function useApi(jeton, onExpire) {
  const [erreur, setErreur] = useState(null);
  const expire = useRef(onExpire);
  expire.current = onExpire;

  const appeler = useCallback(
    async (chemin, options = {}) => {
      setErreur(null);
      try {
        return await api(chemin, { ...options, jeton });
      } catch (err) {
        if (err.status === 401) expire.current();
        else setErreur(err.message);
        throw err;
      }
    },
    [jeton],
  );

  return { appeler, erreur, setErreur };
}
