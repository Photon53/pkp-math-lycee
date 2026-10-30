#!/usr/bin/env bash
# Passe une installation V1 de PKP Math Lycée à la V2, sur une VM Oracle Cloud (Oracle Linux 9 ou 10).
# À lancer sur la VM, en tant qu'utilisateur opc, dans une session SSH interactive :
#   bash mettre-a-jour-v2-oracle.sh --admin-email moi@lycee.fr              # compte V1 existant → administrateur
#   bash mettre-a-jour-v2-oracle.sh --admin-email admin@pkp.fr --admin-nom "Équipe PKP"   # nouveau compte admin
#   bash mettre-a-jour-v2-oracle.sh                                         # mise à jour seule
#   bash mettre-a-jour-v2-oracle.sh --retour                                # revenir à la V1 (perd les données V2)
# Options : --dossier <chemin> (défaut : détecté automatiquement), --branche <nom> (défaut main).
# Avant tout changement : sauvegarde de la base et de .env dans ~/sauvegardes. Relançable sans risque.
set -euo pipefail

DOSSIER=""   # vide : détecté (conteneurs en service, puis ~/pkp-math-lycee, puis recherche)
BRANCHE="main"
ADMIN_EMAIL=""
ADMIN_NOM=""
RETOUR=false
SAUVEGARDES="$HOME/sauvegardes"
COMMIT_V1="$SAUVEGARDES/pkp-commit-avant-v2.txt"

usage() { sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dossier)     DOSSIER="$2"; shift 2 ;;
    --branche)     BRANCHE="$2"; shift 2 ;;
    --admin-email) ADMIN_EMAIL="$2"; shift 2 ;;
    --admin-nom)   ADMIN_NOM="$2"; shift 2 ;;
    --retour)      RETOUR=true; shift ;;
    -h|--help)     usage ;;
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
  ol|rhel|rocky|almalinux|centos) echo "$PRETTY_NAME ($(uname -m))" ;;
  *) alerte "Script prévu pour Oracle Linux (trouvé : $PRETTY_NAME). Sur Google Cloud : mettre-a-jour-v2-gcp.sh." ;;
esac
command -v docker >/dev/null || echec "Docker n'est pas installé : utiliser installer-oracle.sh pour une première installation."
# Le script d'installation V1 lance Docker avec sudo ; après reconnexion, opc peut s'en passer.
if docker info >/dev/null 2>&1; then DOCKER="docker"; else DOCKER="sudo docker"; fi

# Dossier de l'installation : celui que Docker Compose a utilisé pour lancer la base,
# sinon l'emplacement par défaut, sinon une recherche dans les dossiers habituels.
installation() { [[ -f "$1/deploy/docker-compose.yml" && -f "$1/deploy/.env" ]]; }
if [[ -z "$DOSSIER" ]]; then
  compose=$($DOCKER ps --filter label=com.docker.compose.service=db     --format '{{.Label "com.docker.compose.project.working_dir"}}' 2>/dev/null | head -1 || true)
  for candidat in "${compose%/}/.." "$HOME/pkp-math-lycee"; do
    if [[ -n "$candidat" ]] && installation "$candidat"; then DOSSIER=$(cd "$candidat" && pwd); break; fi
  done
fi
if [[ -z "$DOSSIER" ]]; then
  trouve=$(sudo find /home /opt /srv /mnt /root -maxdepth 5 -path '*/deploy/docker-compose.yml' 2>/dev/null | head -1 || true)
  [[ -n "$trouve" ]] && DOSSIER=$(dirname "$(dirname "$trouve")")
fi
[[ -n "$DOSSIER" ]] || echec "Installation introuvable : relancer avec --dossier <dossier contenant deploy/>."
installation "$DOSSIER" || echec "$DOSSIER ne contient pas deploy/docker-compose.yml et deploy/.env (option --dossier)."
git -C "$DOSSIER" rev-parse --git-dir >/dev/null 2>&1   || echec "$DOSSIER n'est pas un dépôt Git : la mise à jour se fait par git pull. Cloner le dépôt et y recopier deploy/.env."
cd "$DOSSIER/deploy"
dc() { $DOCKER compose "$@"; }
dc ps --services --status running | grep -qx db || echec "Le service db ne tourne pas : démarrer la V1 (dc up -d) avant la mise à jour."
DOMAINE=$(grep -E '^PKP_DOMAINE=' .env | cut -d= -f2-)
echo "Dossier : $DOSSIER · domaine : ${DOMAINE:-?} · docker : $DOCKER"

attendre_api() {
  for _ in $(seq 60); do
    if dc exec -T api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" 2>/dev/null; then
      echo "API prête."; return 0
    fi
    sleep 3
  done
  echec "L'API ne répond pas. Journaux : cd $DOSSIER/deploy && $DOCKER compose logs api"
}

sauvegarder() {
  etape "Sauvegarde de la base et de .env ($SAUVEGARDES)"
  mkdir -p "$SAUVEGARDES" && chmod 700 "$SAUVEGARDES"
  local horodatage fichier
  horodatage=$(date +%F-%H%M%S)
  fichier="$SAUVEGARDES/pkp-$1-$horodatage.sql.gz"
  dc exec -T db pg_dump -U pkp pkp | gzip > "$fichier"
  [[ $(gzip -cd "$fichier" | head -c 100000 | wc -c) -gt 1000 ]] || echec "Sauvegarde vide ou incomplète : $fichier. Arrêt sans rien changer."
  cp .env "$SAUVEGARDES/env-$horodatage" && chmod 600 "$SAUVEGARDES/env-$horodatage"
  echo "Base : $fichier ($(du -h "$fichier" | cut -f1))"
  echo "Copiez ce dossier hors de la VM (scp) : c'est la seule façon de revenir en arrière en cas de panne du disque."
}

# --- Retour à la V1 -------------------------------------------------------------------------------
if $RETOUR; then
  [[ -f "$COMMIT_V1" ]] || echec "Commit V1 inconnu ($COMMIT_V1 absent) : la mise à jour n'a pas été faite par ce script."
  ancien=$(cat "$COMMIT_V1")
  alerte "Retour au commit V1 $ancien. Les données propres à la V2 (ressources, PDF, journal, versions de leçons,"
  alerte "rôles administrateur) seront supprimées. Classes, élèves et réponses sont conservés."
  read -r -p "Taper OUI pour continuer : " confirmation
  [[ "$confirmation" == "OUI" ]] || echec "Abandon."
  sauvegarder "avant-retour-v1"
  etape "Retour du schéma de base à la V1 (migration 0007)"
  dc exec -T api alembic downgrade 0007
  etape "Code V1"
  git -C "$DOSSIER" checkout --quiet "$ancien"
  etape "Reconstruction et redémarrage"
  dc up -d --build --remove-orphans
  attendre_api
  printf '\nRetour à la V1 terminé. Pour repasser en V2 : relancer ce script sans --retour.\n'
  exit 0
fi

# --- Mise à jour vers la V2 ---------------------------------------------------------------------
ram_mo=$(awk '/MemTotal/ {print int($2 / 1024)}' /proc/meminfo)
if (( ram_mo < 4000 )) && ! swapon --show | grep -q .; then
  etape "Fichier d'échange de 2 Go (mémoire : ${ram_mo} Mo)"
  sudo dd if=/dev/zero of=/swapfile bs=1M count=2048 status=none
  sudo chmod 600 /swapfile && sudo mkswap /swapfile >/dev/null && sudo swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap defaults 0 0' | sudo tee -a /etc/fstab >/dev/null
fi
libre_go=$(df -BG --output=avail / | tail -1 | tr -dc '0-9')
(( libre_go >= 3 )) || echec "Moins de 3 Go libres sur le disque : libérer de la place (sudo docker system prune) puis relancer."

sauvegarder "avant-v2"

etape "Code de la V2 (branche $BRANCHE)"
if [[ -n "$(git -C "$DOSSIER" status --porcelain --untracked-files=no)" ]]; then
  git -C "$DOSSIER" status --short --untracked-files=no
  echec "Des fichiers suivis ont été modifiés sur la VM : les mettre de côté (git stash) puis relancer."
fi
# Mémorise la version V1 une seule fois : une relance après la V2 ne doit pas l'écraser.
[[ -f "$COMMIT_V1" ]] || git -C "$DOSSIER" rev-parse HEAD > "$COMMIT_V1"
echo "Version actuelle : $(git -C "$DOSSIER" log --oneline -1)"
git -C "$DOSSIER" fetch --quiet origin "$BRANCHE"
git -C "$DOSSIER" checkout --quiet "$BRANCHE"
git -C "$DOSSIER" pull --quiet --ff-only origin "$BRANCHE"
echo "Nouvelle version : $(git -C "$DOSSIER" log --oneline -1)"
ls "$DOSSIER"/api/migrations/versions/0008_*.py >/dev/null 2>&1 \
  || echec "La branche $BRANCHE ne contient pas la V2 (migration 0008 absente) : pousser la V2 sur GitHub."

etape "Reconstruction et redémarrage (plusieurs minutes : compilation du front et tests)"
dc up -d --build --remove-orphans

etape "Migration de la base (appliquée au démarrage de l'API)"
attendre_api
version=$(dc exec -T api alembic current 2>/dev/null | tail -1)
echo "Schéma : $version"
[[ "$version" == 0008* ]] || echec "La base n'est pas en 0008. Journaux : $DOCKER compose logs api"

etape "HTTPS"
if [[ -n "$DOMAINE" ]] && curl -fsS --max-time 10 --resolve "$DOMAINE:443:127.0.0.1" "https://$DOMAINE/api/health" >/dev/null; then
  echo "https://$DOMAINE répond."
else
  alerte "https://$DOMAINE ne répond pas encore : $DOCKER compose logs -f web"
fi

if [[ -n "$ADMIN_EMAIL" ]]; then
  etape "Administrateur $ADMIN_EMAIL"
  if dc exec -T api python -m app.admin promouvoir --email "$ADMIN_EMAIL" 2>/dev/null; then
    echo "Compte existant promu administrateur (mot de passe inchangé)."
  else
    [[ -n "$ADMIN_NOM" ]] || echec "Aucun compte $ADMIN_EMAIL : relancer avec --admin-nom pour le créer."
    echo "Choisissez le mot de passe de l'administrateur (12 caractères au moins) :"
    dc exec api python -m app.admin creer --email "$ADMIN_EMAIL" --nom "$ADMIN_NOM" --admin
  fi
  etape "Second facteur (obligatoire en production)"
  dc exec -T api python -m app.admin totp --email "$ADMIN_EMAIL"
  alerte "Ajoutez maintenant le secret ci-dessus dans votre application d'authentification : il ne sera plus affiché."
fi

etape "Terminé"
cat <<FIN
  Accueil         : https://$DOMAINE/
  Élèves          : https://$DOMAINE/eleve      (nouvelle adresse : prévenir les professeurs)
  Professeurs     : https://$DOMAINE/enseignant
  Administration  : https://$DOMAINE/admin      (e-mail, mot de passe, code à 6 chiffres)
  Sauvegardes     : $SAUVEGARDES

  Les comptes professeurs, classes, élèves et réponses de la V1 sont conservés.
  Revenir à la V1 : bash $0 --retour
FIN
