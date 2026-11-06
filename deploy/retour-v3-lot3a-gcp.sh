#!/usr/bin/env bash
# Retour arrière du Lot 3a de la V3 (archivage des classes et des groupes, migration 0031), sur une VM Google Cloud (Ubuntu ou Debian).
# À lancer sur la VM (gcloud compute ssh <vm>), avec un utilisateur sudo, dans une session interactive :
#   bash retour-v3-lot3a-gcp.sh                       # revient à la version d'avant le Lot 3a
#   bash retour-v3-lot3a-gcp.sh --version <commit>    # revient à un commit précis (antérieur au Lot 3a)
#   bash retour-v3-lot3a-gcp.sh --simulation          # affiche ce qui serait fait, sans rien changer
# Options : --dossier <chemin> (défaut : détecté automatiquement).
# Avant tout changement : sauvegarde complète de la base, de la liste des classes et groupes archivés et de .env.
# Perdu au retour : l'état « archivé » des classes et des groupes, qui redeviennent actifs (liste sauvegardée à part).
# Conservé : comptes, familles, classes, inscriptions, séances, réponses. Revenir à la V3 : mettre-a-jour-v2-gcp.sh.

# Tout le script est dans une fonction appelée à la dernière ligne : bash le lit en entier avant de l'exécuter,
# ce qui le protège du `git checkout` qui retire ce fichier du dossier pendant le retour.
retour() {
set -euo pipefail

local DOSSIER="" VERSION="" SIMULATION=false
local SAUVEGARDES="$HOME/sauvegardes"
local MIGRATION="api/migrations/versions/0031_archivage_des_classes_et_groupes.py"
local REVISION_CIBLE="0030"

usage() { sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dossier)    DOSSIER="$2"; shift 2 ;;
    --version)    VERSION="$2"; shift 2 ;;
    --simulation) SIMULATION=true; shift ;;
    -h|--help)    usage ;;
    *) echo "Option inconnue : $1"; usage 1 ;;
  esac
done

etape() { printf '\n\033[1;36m==> %s\033[0m\n' "$1"; }
alerte() { printf '\033[1;33m[!] %s\033[0m\n' "$1"; }
echec() { printf '\033[1;31m[x] %s\033[0m\n' "$1"; exit 1; }

etape "Vérifications"
# shellcheck disable=SC1091
. /etc/os-release
case "$ID" in
  ubuntu|debian) echo "$PRETTY_NAME ($(uname -m))" ;;
  *) alerte "Script prévu pour Ubuntu ou Debian (trouvé : $PRETTY_NAME). Sur Oracle Linux : retour-v3-lot3a-oracle.sh." ;;
esac
sudo -n true 2>/dev/null || sudo -v || echec "Un utilisateur avec sudo est requis."
command -v docker >/dev/null || echec "Docker n'est pas installé."
local DOCKER
if docker info >/dev/null 2>&1; then DOCKER="docker"; else DOCKER="sudo docker"; fi

# Dossier de l'installation : celui que Docker Compose a utilisé pour lancer la base, sinon ~/pkp-math-lycee.
installation() { [[ -f "$1/deploy/docker-compose.yml" && -f "$1/deploy/.env" ]]; }
if [[ -z "$DOSSIER" ]]; then
  local compose candidat
  compose=$($DOCKER ps --filter label=com.docker.compose.service=db --format '{{.Label "com.docker.compose.project.working_dir"}}' 2>/dev/null | head -1 || true)
  for candidat in "${compose%/}/.." "$HOME/pkp-math-lycee"; do
    if [[ -n "$candidat" ]] && installation "$candidat"; then DOSSIER=$(cd "$candidat" && pwd); break; fi
  done
fi
[[ -n "$DOSSIER" ]] || echec "Installation introuvable : relancer avec --dossier <dossier contenant deploy/>."
installation "$DOSSIER" || echec "$DOSSIER ne contient pas deploy/docker-compose.yml et deploy/.env (option --dossier)."
git -C "$DOSSIER" rev-parse --git-dir >/dev/null 2>&1 || echec "$DOSSIER n'est pas un dépôt Git."
cd "$DOSSIER/deploy"
dc() { $DOCKER compose "$@"; }
dc ps --services --status running | grep -qx db || echec "Le service db ne tourne pas : cd $DOSSIER/deploy && $DOCKER compose up -d db"
local DOMAINE
DOMAINE=$(grep -E '^PKP_DOMAINE=' .env | cut -d= -f2- || true)
echo "Dossier : $DOSSIER · domaine : ${DOMAINE:-?} · docker : $DOCKER"

if [[ -n "$(git -C "$DOSSIER" status --porcelain --untracked-files=no)" ]]; then
  git -C "$DOSSIER" status --short --untracked-files=no
  echec "Des fichiers suivis ont été modifiés sur la VM : les mettre de côté (git stash) puis relancer."
fi

# Version visée : celle qui précède le commit ayant ajouté la migration 0031 (sauf --version).
local actuel ajout
actuel=$(git -C "$DOSSIER" rev-parse HEAD)
if [[ -z "$VERSION" ]]; then
  [[ -f "$DOSSIER/$MIGRATION" ]] || echec "Le code en place ne contient pas le Lot 3a ($MIGRATION absent) : rien à défaire."
  ajout=$(git -C "$DOSSIER" log --format=%H --diff-filter=A -- "$MIGRATION" | tail -1)
  [[ -n "$ajout" ]] || echec "Commit du Lot 3a introuvable dans l'historique : relancer avec --version <commit>."
  VERSION=$(git -C "$DOSSIER" rev-parse "$ajout^")
else
  VERSION=$(git -C "$DOSSIER" rev-parse --verify "$VERSION^{commit}") || echec "Commit $VERSION inconnu (git fetch ?)."
  if git -C "$DOSSIER" cat-file -e "$VERSION:$MIGRATION" 2>/dev/null; then
    echec "Le commit $VERSION contient encore la migration 0031 : ce n'est pas un retour avant le Lot 3a."
  fi
fi

# Révision actuelle de la base, lue par l'API en service (sinon par un conteneur ponctuel).
local revision
if dc ps --services --status running | grep -qx api; then
  revision=$(dc exec -T api alembic current 2>/dev/null | tail -1 || true)
else
  revision=$(dc run --rm -T api alembic current 2>/dev/null | tail -1 || true)
fi
echo "Code actuel      : $(git -C "$DOSSIER" log --oneline -1 "$actuel")"
echo "Code visé        : $(git -C "$DOSSIER" log --oneline -1 "$VERSION")"
echo "Schéma de base   : ${revision:-inconnu} → $REVISION_CIBLE"
local nb_archives
nb_archives=$(dc exec -T db psql -U pkp -d pkp -tAc \
  "SELECT (SELECT count(*) FROM classe WHERE archivee_le IS NOT NULL) + (SELECT count(*) FROM groupe_anglais WHERE archivee_le IS NOT NULL)" \
  2>/dev/null || echo 0)
echo "Classes et groupes archivés : ${nb_archives:-0}"
if [[ "${nb_archives:-0}" != "0" ]]; then
  alerte "Après le retour, ils redeviennent actifs : visibles des élèves et des professeurs. Préférez les supprimer"
  alerte "ou les rétablir à la main avant, ou réarchivez-les après le retour à la V3 (liste sauvegardée)."
fi

if $SIMULATION; then
  printf "\nSimulation : rien n'a été changé.\n"
  exit 0
fi

alerte "Retour au code ${VERSION:0:7} et au schéma $REVISION_CIBLE. L'application sera indisponible quelques minutes."
read -r -p "Taper OUI pour continuer : " confirmation
[[ "$confirmation" == "OUI" ]] || echec "Abandon."

etape "Sauvegarde de la base, des classes archivées et de .env ($SAUVEGARDES)"
mkdir -p "$SAUVEGARDES" && chmod 700 "$SAUVEGARDES"
local horodatage fichier
horodatage=$(date +%F-%H%M%S)
fichier="$SAUVEGARDES/pkp-avant-retour-v3-lot3a-$horodatage.sql.gz"
dc exec -T db pg_dump -U pkp pkp | gzip > "$fichier"
[[ $(gzip -cd "$fichier" | head -c 100000 | wc -c) -gt 1000 ]] || echec "Sauvegarde vide ou incomplète : $fichier. Arrêt sans rien changer."
if [[ "${nb_archives:-0}" != "0" ]]; then
  dc exec -T db psql -U pkp -d pkp -c "\\copy (SELECT 'classe' AS genre, id, code AS nom, archivee_le, archivee_par, motif_archivage FROM classe WHERE archivee_le IS NOT NULL UNION ALL SELECT 'groupe', id, nom, archivee_le, archivee_par, motif_archivage FROM groupe_anglais WHERE archivee_le IS NOT NULL) TO STDOUT WITH CSV HEADER" \
    > "$SAUVEGARDES/classes-archivees-$horodatage.csv"
  echo "Classes et groupes archivés : $SAUVEGARDES/classes-archivees-$horodatage.csv"
fi
cp .env "$SAUVEGARDES/env-$horodatage" && chmod 600 "$SAUVEGARDES/env-$horodatage"
echo "$actuel" > "$SAUVEGARDES/pkp-commit-avant-retour-v3-lot3a.txt"
echo "Base : $fichier ($(du -h "$fichier" | cut -f1))"
echo "Copiez ce dossier hors de la VM (gcloud compute scp) avant d'aller plus loin si possible."

# D'abord la base, avec le code actuel (lui seul connaît la migration 0031) ; l'ancien code, qui applique
# « alembic upgrade head » à son démarrage, refuserait sinon une base à une révision qu'il ne connaît pas.
etape "Retour du schéma de base à la révision $REVISION_CIBLE"
if [[ "$revision" == "$REVISION_CIBLE"* ]]; then
  echo "Déjà à $REVISION_CIBLE."
elif dc ps --services --status running | grep -qx api; then
  dc exec -T api alembic downgrade "$REVISION_CIBLE"
else
  dc run --rm -T api alembic downgrade "$REVISION_CIBLE"
fi

etape "Code d'avant le Lot 3a (${VERSION:0:7})"
git -C "$DOSSIER" checkout --quiet "$VERSION"
echo "Version en place : $(git -C "$DOSSIER" log --oneline -1)"

etape "Reconstruction et redémarrage (plusieurs minutes)"
dc up -d --build --remove-orphans
local ok=false
for _ in $(seq 60); do
  if dc exec -T api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" 2>/dev/null; then
    ok=true; break
  fi
  sleep 3
done
$ok || echec "L'API ne répond pas. Journaux : cd $DOSSIER/deploy && $DOCKER compose logs api"
revision=$(dc exec -T api alembic current 2>/dev/null | tail -1)
echo "Schéma : $revision"
[[ "$revision" == "$REVISION_CIBLE"* ]] || echec "La base n'est pas à $REVISION_CIBLE ($revision). Journaux : $DOCKER compose logs api"

etape "HTTPS"
if [[ -n "$DOMAINE" ]] && curl -fsS --max-time 10 --resolve "$DOMAINE:443:127.0.0.1" "https://$DOMAINE/api/health" >/dev/null; then
  echo "https://$DOMAINE répond."
else
  alerte "https://$DOMAINE ne répond pas encore : $DOCKER compose logs -f web"
fi

etape "Terminé"
cat <<FIN
  Version en place : $(git -C "$DOSSIER" log --oneline -1)
  Sauvegardes      : $SAUVEGARDES
  Revenir à la V3  : bash $DOSSIER/deploy/mettre-a-jour-v2-gcp.sh
                     (les classes et groupes reviennent tous actifs ; les réarchiver depuis
                      « Classes et groupes », à l'aide de $SAUVEGARDES/classes-archivees-<date>.csv)
FIN
}

retour "$@"
