#!/usr/bin/env bash
# Lance toutes les suites de tests (moteur, API, front). Mac/Linux.
set -uo pipefail
cd "$(dirname "$0")/.."
PYTHON="$PWD/.venv/bin/python"
echecs=()

suite() {
  local nom="$1" dossier="$2"; shift 2
  printf '\n==> %s\n' "$nom"
  (cd "$dossier" && "$@") || echecs+=("$nom")
}

suite "Moteur" engine "$PYTHON" -m pytest -q
suite "API" api "$PYTHON" -m pytest -q -W ignore::DeprecationWarning
suite "Front" web npm test

if ((${#echecs[@]})); then printf '\nÉchec : %s\n' "${echecs[*]}"; exit 1; fi
printf '\nTous les tests passent.\n'
