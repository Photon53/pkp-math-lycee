import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// En dev, /api/* est relayé vers FastAPI : le front n'a pas d'URL d'API en dur.
// PKP_API_URL permet de viser un autre port si 8000 est déjà pris.
// 127.0.0.1 et non « localhost » : Node résout localhost en IPv6 (::1), alors qu'uvicorn n'écoute par
// défaut qu'en IPv4 ; chaque appel échouait alors en « Le serveur a rencontré un problème ».
const versIPv4 = (url) => url.replace("//localhost:", "//127.0.0.1:");

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: versIPv4(process.env.PKP_API_URL ?? "http://127.0.0.1:8000"),
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/tests/setup.js",
    // Les tests tournent aussi pendant la construction de l'image Docker, sur des VM à vCPU partagé
    // (GCP e2-small, Oracle E2.1.Micro) bien plus lentes qu'un poste : 5 s par défaut ne suffisent pas.
    testTimeout: 30_000,
    hookTimeout: 30_000,
  },
});
