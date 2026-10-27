#!/usr/bin/env bash
# Installe l'environnement de développement (Mac/Linux).
#   bash scripts/installer-dev.sh
#   bash scripts/installer-dev.sh --base-seulement   # recrée seulement la base SQLite de démo
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON=".venv/bin/python"
etape() { printf '\n==> %s\n' "$1"; }

if [[ "${1:-}" != "--base-seulement" ]]; then
  etape "Vérification des prérequis"
  command -v python3 >/dev/null || { echo "Python 3.11+ introuvable"; exit 1; }
  python3 -c "import sys; assert sys.version_info >= (3, 11), 'Python 3.11 ou plus requis'"
  command -v npm >/dev/null || { echo "Node.js 20+ introuvable"; exit 1; }

  etape "Environnement Python (.venv)"
  [[ -x "$PYTHON" ]] || python3 -m venv .venv
  "$PYTHON" -m pip install --quiet --upgrade pip
  "$PYTHON" -m pip install --quiet -e "./engine[dev]" -e "./api[dev]"

  etape "Dépendances du front (npm ci)"
  (cd web && npm ci --no-audit --no-fund)
fi

etape "Base de démo SQLite (api/pkp.db)"
(cd api && rm -f pkp.db && "../$PYTHON" -m alembic upgrade head && "../$PYTHON" -m app.db.seed)

printf '\nPrêt. Dans VS Code : ouvrir pkp-math-lycee.code-workspace, puis « ▶ API + Front ».\n'
printf 'Sous Mac/Linux, remplacer .venv/Scripts/python.exe par .venv/bin/python dans\n'
printf 'pkp-math-lycee.code-workspace, engine/.vscode et api/.vscode.\n'
