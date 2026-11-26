#!/usr/bin/env bash
# Issue #217 — Recette Français multi-rôles sur une pile locale jetable (Claude)
#
# Base SQLite temporaire (jamais api/pkp.db), migrations, démo, import du contenu (chapitres et dossiers de
# français, comme au déploiement), API et front locaux, puis scripts/recette/recette-francais.mjs en mode complet.
# Aucun accès cloud. Prérequis : bash scripts/preparer-environnement.sh (ou .venv et web/node_modules), Playwright.
#
#   bash scripts/recette/pile-locale.sh [dossier-du-rapport]
set -euo pipefail
cd "$(dirname "$0")/../.."
RACINE="$PWD"
PYTHON="$RACINE/.venv/bin/python"
TRAVAIL="$(mktemp -d)"
SORTIE="${1:-$RACINE/recette-francais-locale}"
PORT_API="${PORT_API:-8765}"
PORT_WEB="${PORT_WEB:-5765}"
export PKP_DATABASE_URL="sqlite:///$TRAVAIL/recette.db"

arreter() { kill "${PID_API:-}" "${PID_WEB:-}" 2>/dev/null || true; wait 2>/dev/null || true; rm -rf "$TRAVAIL"; }
trap arreter EXIT

echo "==> Base jetable ($TRAVAIL), migrations, démo et import du contenu"
(cd api && "$PYTHON" -m alembic upgrade head >"$TRAVAIL/migration.log" 2>&1 \
  && "$PYTHON" -m app.db.seed && "$PYTHON" -m app.contenu importer | tail -3)

echo "==> API (port $PORT_API) et front (port $PORT_WEB)"
# Un serveur resté d'une exécution précédente répondrait avec une autre base : refuser plutôt que tester à côté.
if curl -s -o /dev/null "http://127.0.0.1:$PORT_API/health" || curl -s -o /dev/null "http://127.0.0.1:$PORT_WEB/"; then
  echo "Port $PORT_API ou $PORT_WEB déjà utilisé : arrêter l'ancien serveur ou choisir PORT_API / PORT_WEB." >&2; exit 1
fi
(cd api && exec "$PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT_API" >"$TRAVAIL/api.log" 2>&1) &
PID_API=$!
(cd web && PKP_API_URL="http://127.0.0.1:$PORT_API" exec ./node_modules/.bin/vite --host 127.0.0.1 --port "$PORT_WEB" --strictPort >"$TRAVAIL/web.log" 2>&1) &
PID_WEB=$!
for _ in $(seq 1 60); do
  curl -sf "http://127.0.0.1:$PORT_WEB/api/health" >/dev/null && break
  sleep 1
done
curl -sf "http://127.0.0.1:$PORT_WEB/api/health" >/dev/null || { cat "$TRAVAIL/api.log" "$TRAVAIL/web.log"; exit 1; }

echo "==> Recette (mode complet, base jetable)"
VERSION="${VERSION:-$(git rev-parse HEAD) (pile locale)}" BASE_URL="http://127.0.0.1:$PORT_WEB" \
  ADMIN_EMAIL=admin@pkp.test ADMIN_MDP=demo-pkp-2026 MODE=complet SORTIE="$SORTIE" \
  node scripts/recette/recette-francais.mjs
