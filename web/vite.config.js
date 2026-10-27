import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// En dev, /api/* est relayé vers FastAPI : le front n'a pas d'URL d'API en dur.
// PKP_API_URL permet de viser un autre port si 8000 est déjà pris.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: process.env.PKP_API_URL ?? "http://localhost:8000",
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/tests/setup.js",
  },
});
