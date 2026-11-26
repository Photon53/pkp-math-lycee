#!/usr/bin/env bash
# Prépare un environnement de développement aligné sur la CI (.github/workflows/ci.yml). Linux.
#   bash scripts/preparer-environnement.sh                    # tout
#   bash scripts/preparer-environnement.sh --sans-terraform   # sans installer Terraform
#   bash scripts/preparer-environnement.sh --sans-dependances # outils seulement (ni pip ni npm)
#
# Ce que fait le script, dans cet ordre :
#   1. Python : version lue dans .python-version, environnement .venv (le même que scripts/tests.sh),
#      dépendances installées par la même commande que la CI. .venv est recréé s'il a été créé avec une
#      autre version de Python.
#   2. Node : version majeure lue dans .nvmrc ; un Node de cette version déjà présent dans le PATH est
#      utilisé, sinon la version épinglée ci-dessous est téléchargée. Puis « npm ci » dans web/.
#   3. ShellCheck et Terraform : versions épinglées, empreinte SHA-256 vérifiée avant installation.
#
# Le script peut être relancé : ce qui est déjà en place à la bonne version n'est ni retéléchargé ni
# réinstallé. Les outils vont dans $BOUSSOLE_OUTILS (par défaut ~/.local/share/boussole-outils), jamais
# dans le système. Le script ne crée pas la base de démo (voir scripts/installer-dev.sh), n'exécute
# aucun « terraform init » et n'utilise aucun identifiant cloud.
set -euo pipefail
cd "$(dirname "$0")/.."

# --- Versions épinglées -------------------------------------------------------------------------
# Terraform : la CI installe « latest » (hashicorp/setup-terraform@v3 sans version) ; au 12/11/2026,
# « latest » désignait la 1.17.2 (publiée le 11/11/2026). Compatible avec required_version >= 1.7.0
# (infrastructure/terraform/dev/main.tf). Empreintes tirées de terraform_1.17.2_SHA256SUMS, dont la
# signature a été vérifiée avec la clé HashiCorp Security C874 011F 0AB4 0511 0D02 1055 3436 5D94 72D7 468F.
TERRAFORM_VERSION=1.17.2
declare -A TERRAFORM_SHA256=(
  [amd64]=e6f16b2f0b137ee5729caa8c4e79a3bae4ee261acd198a1fcfa8584a6296605b
  [arm64]=858e08c181a76b6b223e8c767a8e983922eebe2d062db949a2de66ce040c368c
)
# Node : dernière 20.x (la CI demande « 20 »). Empreintes tirées de nodejs.org/dist/v20.20.2/SHASUMS256.txt.
NODE_VERSION=20.20.2
declare -A NODE_SHA256=(
  [x64]=df770b2a6f130ed8627c9782c988fda9669fa23898329a61a871e32f965e007d
  [arm64]=73093db209e4e9e09dd7d15a47aeaab1b74833830df03efa5f942a1122c5fa71
)
# ShellCheck : la CI ne l'exécute pas (elle vérifie seulement « bash -n ») ; outil local. Le projet ne
# publie pas d'empreinte : celles-ci ont été calculées sur les archives de la release GitHub v0.11.0,
# et le binaire x86_64 a été comparé, identique, à celui du paquet PyPI shellcheck-py 0.11.0.1.
SHELLCHECK_VERSION=0.11.0
declare -A SHELLCHECK_SHA256=(
  [x86_64]=8c3be12b05d5c177a04c29e3c78ce89ac86f1595681cab149b65b97c4e227198
  [aarch64]=12b331c1d2db6b9eb13cfca64306b1b157a86eb69db83023e261eaa7e7c14588
)

# --- Options ------------------------------------------------------------------------------------
avec_terraform=1
avec_dependances=1
for option in "$@"; do
  case "$option" in
    --sans-terraform) avec_terraform=0 ;;
    --sans-dependances) avec_dependances=0 ;;
    -h|--help) sed -n '2,5p' "$0"; exit 0 ;;
    *) echo "Option inconnue : $option" >&2; exit 2 ;;
  esac
done

OUTILS="${BOUSSOLE_OUTILS:-${XDG_DATA_HOME:-$HOME/.local/share}/boussole-outils}"
BIN="$OUTILS/bin"
mkdir -p "$BIN"
export PATH="$BIN:$PATH"
TEMP="$(mktemp -d)"
trap 'rm -rf "$TEMP"' EXIT

etape() { printf '\n==> %s\n' "$1"; }
info() { printf '    %s\n' "$1"; }
erreur() { printf 'ERREUR : %s\n' "$1" >&2; exit 1; }

[[ "$(uname -s)" == Linux ]] || erreur "ce script ne prend en charge que Linux (voir scripts/installer-dev.ps1 sous Windows)"
case "$(uname -m)" in
  x86_64) arch_tf=amd64; arch_node=x64; arch_sc=x86_64 ;;
  aarch64|arm64) arch_tf=arm64; arch_node=arm64; arch_sc=aarch64 ;;
  *) erreur "architecture non prise en charge : $(uname -m)" ;;
esac
for commande in curl sha256sum tar; do
  command -v "$commande" >/dev/null || erreur "commande requise introuvable : $commande"
done

# Télécharge $1 vers $2 et vérifie l'empreinte $3 ; le fichier est supprimé si elle ne correspond pas.
telecharger_verifie() {
  local url="$1" destination="$2" attendu="$3"
  curl -fsSL --retry 3 --proto '=https' -o "$destination" "$url" || erreur "téléchargement impossible : $url"
  if ! printf '%s  %s\n' "$attendu" "$destination" | sha256sum --check --status; then
    rm -f "$destination"
    erreur "empreinte SHA-256 inattendue pour $url (fichier supprimé, rien installé)"
  fi
  info "empreinte vérifiée : $(basename "$destination")"
}

# --- 1. Python ----------------------------------------------------------------------------------
etape "Python"
version_python="$(tr -d '[:space:]' < .python-version)"
version_de() { "$1" -c 'import sys; print("%d.%d" % sys.version_info[:2])'; }
python_ok=""
if command -v "python$version_python" >/dev/null; then
  python_ok="$(command -v "python$version_python")"
elif command -v uv >/dev/null; then
  python_ok="$(uv python find "$version_python" 2>/dev/null || true)"
  if [[ -z "$python_ok" ]]; then
    uv python install "$version_python"
    python_ok="$(uv python find "$version_python")"
  fi
fi
[[ -n "$python_ok" && "$(version_de "$python_ok")" == "$version_python" ]] \
  || erreur "Python $version_python introuvable (installer python$version_python, ou uv)"
info "Python $version_python : $python_ok"

if [[ -x .venv/bin/python ]] && [[ "$(version_de .venv/bin/python)" != "$version_python" ]]; then
  info ".venv a été créé avec Python $(version_de .venv/bin/python) : recréé avec $version_python"
  rm -rf .venv
fi
if [[ -x .venv/bin/python ]]; then
  info ".venv déjà en Python $version_python"
else
  "$python_ok" -m venv .venv
  info ".venv créé"
fi
if ((avec_dependances)); then
  # Même commande que la CI (job « Moteur, API et contenu »).
  .venv/bin/python -m pip install --quiet --disable-pip-version-check -e "./engine[dev]" -e "./api[dev]"
  info "dépendances Python installées (engine[dev], api[dev])"
fi

# --- 2. Node ------------------------------------------------------------------------------------
etape "Node"
majeure_node="$(tr -d '[:space:]' < .nvmrc)"
[[ "${NODE_VERSION%%.*}" == "$majeure_node" ]] \
  || erreur "NODE_VERSION ($NODE_VERSION) ne correspond pas à .nvmrc ($majeure_node)"
majeure_de() { "$1" --version 2>/dev/null | sed -E 's/^v([0-9]+).*/\1/'; }
dossier_node="$OUTILS/node-v$NODE_VERSION-linux-$arch_node"
if [[ -x "$dossier_node/bin/node" ]]; then
  info "Node $NODE_VERSION déjà installé : $dossier_node"
elif command -v node >/dev/null && [[ "$(majeure_de node)" == "$majeure_node" ]] \
     && [[ "$(command -v node)" != "$BIN/node" ]]; then
  dossier_node=""
  info "Node $(node --version) du PATH utilisé : $(command -v node)"
else
  archive="$TEMP/node.tar.xz"
  telecharger_verifie "https://nodejs.org/dist/v$NODE_VERSION/node-v$NODE_VERSION-linux-$arch_node.tar.xz" \
    "$archive" "${NODE_SHA256[$arch_node]}"
  tar -xJf "$archive" -C "$OUTILS"
  info "Node $NODE_VERSION installé : $dossier_node"
fi
if [[ -n "$dossier_node" ]]; then
  for outil in node npm npx; do ln -sfn "$dossier_node/bin/$outil" "$BIN/$outil"; done
fi
[[ "$(majeure_de node)" == "$majeure_node" ]] || erreur "Node $majeure_node attendu, $(node --version) trouvé"
if ((avec_dependances)); then
  (cd web && npm ci --no-audit --no-fund --loglevel=error)
  info "dépendances du front installées (npm ci)"
fi

# --- 3. ShellCheck ------------------------------------------------------------------------------
etape "ShellCheck"
dossier_sc="$OUTILS/shellcheck-v$SHELLCHECK_VERSION"
if [[ -x "$dossier_sc/shellcheck" ]]; then
  info "ShellCheck $SHELLCHECK_VERSION déjà installé"
else
  archive="$TEMP/shellcheck.tar.xz"
  telecharger_verifie \
    "https://github.com/koalaman/shellcheck/releases/download/v$SHELLCHECK_VERSION/shellcheck-v$SHELLCHECK_VERSION.linux.$arch_sc.tar.xz" \
    "$archive" "${SHELLCHECK_SHA256[$arch_sc]}"
  tar -xJf "$archive" -C "$OUTILS"
  info "ShellCheck $SHELLCHECK_VERSION installé"
fi
ln -sfn "$dossier_sc/shellcheck" "$BIN/shellcheck"

# --- 4. Terraform -------------------------------------------------------------------------------
etape "Terraform"
if ((avec_terraform)); then
  dossier_tf="$OUTILS/terraform-$TERRAFORM_VERSION"
  if [[ -x "$dossier_tf/terraform" ]]; then
    info "Terraform $TERRAFORM_VERSION déjà installé"
  else
    archive="$TEMP/terraform.zip"
    telecharger_verifie \
      "https://releases.hashicorp.com/terraform/$TERRAFORM_VERSION/terraform_${TERRAFORM_VERSION}_linux_$arch_tf.zip" \
      "$archive" "${TERRAFORM_SHA256[$arch_tf]}"
    mkdir -p "$dossier_tf"
    # Extraction par Python pour ne pas exiger « unzip ».
    .venv/bin/python -I -m zipfile -e "$archive" "$dossier_tf"
    chmod 0755 "$dossier_tf/terraform"
    info "Terraform $TERRAFORM_VERSION installé"
  fi
  ln -sfn "$dossier_tf/terraform" "$BIN/terraform"
else
  info "ignoré (--sans-terraform)"
fi

# --- Bilan --------------------------------------------------------------------------------------
etape "Bilan"
info "Python     : $(.venv/bin/python --version | cut -d' ' -f2) (.venv)"
info "Node       : $(node --version | tr -d v), npm $(npm --version)"
info "ShellCheck : $("$BIN/shellcheck" --version | sed -n 's/^version: //p')"
if ((avec_terraform)); then
  info "Terraform  : $("$BIN/terraform" version | head -1 | sed 's/^Terraform v//')"
fi
# Le PATH reçu au lancement contient-il déjà $BIN ? (le script l'a ajouté en tête pour lui-même)
if [[ ":${PATH#"$BIN:"}:" != *":$BIN:"* ]]; then
  # shellcheck disable=SC2016 # « $PATH » doit être affiché tel quel.
  printf '\nPour utiliser ces outils dans votre terminal :\n  export PATH="%s:$PATH"\n' "$BIN"
fi
printf '\nPrêt. Tests : bash scripts/tests.sh\n'
