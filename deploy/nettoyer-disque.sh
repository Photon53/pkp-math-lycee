#!/usr/bin/env bash
# Libère de la place sur la VM de PKP Math Lycée (Google Cloud ou Oracle) sans toucher aux données.
# À lancer sur la VM, avec un utilisateur sudo :
#   bash nettoyer-disque.sh --simulation     # montre ce qui occupe le disque, ne supprime rien
#   bash nettoyer-disque.sh                  # nettoie (demande confirmation avant les sauvegardes)
#   bash nettoyer-disque.sh --oui            # nettoie sans rien demander
# Options : --garder-sauvegardes <n> (défaut 3 : les n sauvegardes de base les plus récentes sont gardées).
# Jamais supprimé : volumes Docker (base, PDF, certificats HTTPS), conteneurs en service et leurs images,
# fichiers .env et leurs copies, code du dépôt.
set -euo pipefail

SIMULATION=false
OUI=false
GARDER=3
SAUVEGARDES="$HOME/sauvegardes"

usage() { sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }
while [[ $# -gt 0 ]]; do
  case "$1" in
    --simulation)          SIMULATION=true; shift ;;
    --oui)                 OUI=true; shift ;;
    --garder-sauvegardes)  GARDER="$2"; shift 2 ;;
    -h|--help)             usage ;;
    *) echo "Option inconnue : $1"; usage 1 ;;
  esac
done
[[ "$GARDER" =~ ^[0-9]+$ ]] && (( GARDER >= 1 )) || { echo "--garder-sauvegardes : un nombre ≥ 1 (la dernière sauvegarde est toujours gardée)."; exit 1; }

etape() { printf '\n\033[1;36m==> %s\033[0m\n' "$1"; }
alerte() { printf '\033[1;33m[!] %s\033[0m\n' "$1"; }
echec() { printf '\033[1;31m[x] %s\033[0m\n' "$1"; exit 1; }
# Une étape qui échoue (outil absent, disque plein…) n'empêche pas les suivantes.
faire() { if $SIMULATION; then echo "   (simulation) $*"; else "$@" || alerte "Échec, on continue : $*"; fi; }
libre() { df -h --output=avail / | tail -1 | tr -d ' '; }
libre_mo() { df -BM --output=avail / | tail -1 | tr -dc '0-9'; }

sudo -n true 2>/dev/null || sudo -v || echec "Un utilisateur avec sudo est requis."
DOCKER=""
if command -v docker >/dev/null; then
  if docker info >/dev/null 2>&1; then DOCKER="docker"; else DOCKER="sudo docker"; fi
  # Disque plein : le service Docker a pu s'arrêter. On libère d'abord la place hors Docker, puis on le relance.
  $DOCKER info >/dev/null 2>&1 || { alerte "Docker ne répond pas (souvent à cause du disque plein) : il sera relancé après le nettoyage du système."; DOCKER_EN_PANNE=true; }
fi
DOCKER_EN_PANNE=${DOCKER_EN_PANNE:-false}

avant=$(libre_mo)
etape "Occupation du disque"
df -h / | sed 's/^/   /'
echo
sudo du -xh --max-depth=1 / 2>/dev/null | sort -rh | head -8 | sed 's/^/   /' || true
if [[ -n "$DOCKER" ]] && ! $DOCKER_EN_PANNE; then
  echo
  $DOCKER system df 2>/dev/null | sed 's/^/   /' || true
fi

# --- Système ------------------------------------------------------------------------------------
etape "Journaux système (journald : 100 Mo gardés ; anciens journaux compressés)"
command -v journalctl >/dev/null && faire sudo journalctl --vacuum-size=100M
faire sudo find /var/log -type f \( -name '*.gz' -o -name '*.[0-9]' -o -name '*.old' \) -delete

etape "Paquets : cache et dépendances devenues inutiles"
if command -v apt-get >/dev/null; then
  faire sudo apt-get clean
  faire sudo apt-get -y autoremove --purge
elif command -v dnf >/dev/null; then
  faire sudo dnf clean all
  faire sudo dnf -y autoremove
fi

if command -v snap >/dev/null; then
  etape "Snap : anciennes révisions (google-cloud-cli…)"
  anciennes=$(snap list --all 2>/dev/null | awk '/disabled/ {print $1, $3}' || true)
  if [[ -z "$anciennes" ]]; then
    echo "   Aucune."
  else
    while read -r nom revision; do faire sudo snap remove "$nom" --revision="$revision"; done <<< "$anciennes"
  fi
fi

etape "Fichiers temporaires de plus de 7 jours et caches utilisateur"
faire sudo find /tmp /var/tmp -xdev -type f -atime +7 -delete
faire rm -rf "$HOME/.cache/pip" "$HOME/.npm/_cacache"

# --- Docker -------------------------------------------------------------------------------------
if [[ -n "$DOCKER" ]] && $DOCKER_EN_PANNE && ! $SIMULATION; then
  etape "Redémarrage de Docker"
  sudo systemctl restart docker || alerte "Docker ne redémarre pas : sudo journalctl -u docker -n 50"
  if $DOCKER info >/dev/null 2>&1; then echo "   Docker répond."; DOCKER_EN_PANNE=false; fi
fi
PKP_RELANCE=true
# Après un disque plein, la base ou l'API ont pu s'arrêter : on relance PKP AVANT le nettoyage des images,
# sinon « image prune -a » supprimerait les images de conteneurs arrêtés et tout serait à recompiler.
if [[ -n "$DOCKER" ]] && ! $DOCKER_EN_PANNE && ! $SIMULATION; then
  compose=$(sudo find "$HOME" /opt /srv -maxdepth 4 -path '*/deploy/docker-compose.yml' 2>/dev/null | head -1 || true)
  if [[ -n "$compose" && -f "$(dirname "$compose")/.env" ]]; then
    en_service=$(cd "$(dirname "$compose")" && $DOCKER compose ps --services --status running 2>/dev/null | wc -l)
    if (( en_service < 4 )); then
      etape "Relance de PKP ($(dirname "$compose"))"
      (cd "$(dirname "$compose")" && $DOCKER compose up -d) || { PKP_RELANCE=false; alerte "Relance impossible : cd $(dirname "$compose") && $DOCKER compose logs"; }
    fi
    (cd "$(dirname "$compose")" && $DOCKER compose ps --format 'table {{.Service}}	{{.Status}}' 2>/dev/null | sed 's/^/   /') || true
  fi
fi
if [[ -n "$DOCKER" ]] && ! $DOCKER_EN_PANNE; then
  etape "Docker : conteneurs arrêtés, images inutilisées, cache de compilation"
  # Les images des conteneurs en service (pkp-api, web, postgres), relancés juste avant, ne sont pas touchées.
  # Pas de « volume prune » : si les conteneurs étaient arrêtés, il supprimerait la base.
  faire $DOCKER container prune -f
  if $PKP_RELANCE; then
    faire $DOCKER image prune -a -f
  else
    # PKP ne tourne pas : seules les images sans nom partent, celles de PKP restent pour la relance.
    faire $DOCKER image prune -f
  fi
  faire $DOCKER builder prune -a -f
  faire $DOCKER network prune -f

  etape "Docker : journaux des conteneurs de plus de 50 Mo"
  # Déjà bornés à 3 × 10 Mo par docker-compose.yml ; un conteneur créé avant cette règle peut avoir un journal énorme.
  journaux=$(sudo find /var/lib/docker/containers -name '*-json.log' -size +50M 2>/dev/null || true)
  if [[ -z "$journaux" ]]; then
    echo "   Aucun."
  else
    while IFS= read -r j; do
      echo "   $(sudo du -h "$j" | cut -f1)  $j"
      faire sudo truncate -s 0 "$j"
    done <<< "$journaux"
  fi

  orphelins=$($DOCKER volume ls -q -f dangling=true 2>/dev/null || true)
  if [[ -n "$orphelins" ]]; then
    alerte "Volumes Docker non utilisés (NON supprimés, ils peuvent contenir des données) :"
    echo "$orphelins" | sed 's/^/   /'
    echo "   À vérifier un par un avant tout « $DOCKER volume rm <nom> »."
  fi
elif [[ -z "$DOCKER" ]]; then
  alerte "Docker absent : étape ignorée."
else
  alerte "Docker ne répond toujours pas : nettoyage Docker impossible."
fi

# --- Sauvegardes de la base ---------------------------------------------------------------------
etape "Sauvegardes de la base ($SAUVEGARDES) : les $GARDER plus récentes sont gardées"
if [[ -d "$SAUVEGARDES" ]]; then
  mapfile -t toutes < <(ls -1t "$SAUVEGARDES"/pkp-*.sql.gz 2>/dev/null || true)
  if (( ${#toutes[@]} <= GARDER )); then
    echo "   ${#toutes[@]} sauvegarde(s) : rien à supprimer."
  else
    a_supprimer=("${toutes[@]:GARDER}")
    echo "   Gardées :"
    printf '     %s\n' "${toutes[@]:0:GARDER}"
    echo "   À supprimer ($(du -ch "${a_supprimer[@]}" | tail -1 | cut -f1)) :"
    printf '     %s\n' "${a_supprimer[@]}"
    if $SIMULATION; then
      echo "   (simulation) rien n'est supprimé."
    else
      reponse="oui"
      if ! $OUI; then
        alerte "Une sauvegarde supprimée ne se récupère pas. Copiez-les d'abord hors de la VM si besoin (gcloud compute scp)."
        read -r -p "   Supprimer ces anciennes sauvegardes ? (oui/non) : " reponse
      fi
      if [[ "$reponse" == "oui" ]]; then rm -f -- "${a_supprimer[@]}"; else echo "   Sauvegardes conservées."; fi
    fi
  fi
  # Les copies de .env (quelques octets, secrets nécessaires à une restauration) sont toujours gardées.
else
  echo "   Aucun dossier de sauvegardes."
fi

# --- Bilan --------------------------------------------------------------------------------------
etape "Bilan"
apres=$(libre_mo)
df -h / | sed 's/^/   /'
if $SIMULATION; then
  echo "   Simulation : rien n'a été supprimé. Relancer sans --simulation pour nettoyer."
else
  echo "   Espace libéré : $(( (apres - avant) )) Mo · libre maintenant : $(libre)"
fi
if (( apres < 3000 )); then
  alerte "Moins de 3 Go libres : la prochaine mise à jour (compilation des images) risque d'échouer."
  cat <<'FIN'
   Agrandir le disque de la VM (sans arrêt, sans perte de données), depuis votre poste :
     gcloud compute disks resize <nom-du-disque> --size=30GB --zone=<zone>
   puis sur la VM :
     sudo growpart /dev/sda 1 && sudo resize2fs /dev/sda1      (vérifier les noms avec : lsblk)
FIN
fi
