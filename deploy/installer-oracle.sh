#!/usr/bin/env bash
# Installe (ou met à jour) PKP Math Lycée sur une VM Oracle Cloud sous Oracle Linux 9 ou 10.
# À lancer sur la VM, en tant qu'utilisateur opc (sudo sans mot de passe) :
#   bash installer-oracle.sh                                   # domaine sslip.io déduit de l'IP publique
#   bash installer-oracle.sh --domaine maths.mon-lycee.fr
#   bash installer-oracle.sh --email prof@lycee.fr --nom "Mme Martin"   # crée aussi le compte enseignant
# Relançable sans risque : les secrets et la base existants sont conservés.
#
# Prérequis côté console Oracle (impossible à faire depuis la VM) : dans la « Security List »
# du sous-réseau, des règles entrantes TCP 80 et TCP 443 depuis 0.0.0.0/0.
set -euo pipefail

DEPOT="https://github.com/Photon53/pkp-math-lycee.git"
BRANCHE="main"
DOSSIER="$HOME/pkp-math-lycee"
DOMAINE=""
EMAIL=""
NOM=""

usage() { sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }
while [[ $# -gt 0 ]]; do
  case "$1" in
    --domaine) DOMAINE="$2"; shift 2 ;;
    --email)   EMAIL="$2"; shift 2 ;;
    --nom)     NOM="$2"; shift 2 ;;
    --depot)   DEPOT="$2"; shift 2 ;;
    --branche) BRANCHE="$2"; shift 2 ;;
    --dossier) DOSSIER="$2"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "Option inconnue : $1"; usage 1 ;;
  esac
done
if [[ -n "$EMAIL" && -z "$NOM" ]]; then echo "--email demande aussi --nom."; exit 1; fi

etape() { printf '\n\033[1;36m==> %s\033[0m\n' "$1"; }
alerte() { printf '\033[1;33m[!] %s\033[0m\n' "$1"; }
echec() { printf '\033[1;31m[x] %s\033[0m\n' "$1"; exit 1; }

etape "Vérification du système"
# shellcheck disable=SC1091
. /etc/os-release
case "$ID" in
  ol|rhel|rocky|almalinux|centos) echo "$PRETTY_NAME ($(uname -m))" ;;
  *) echec "Ce script vise Oracle Linux (trouvé : $PRETTY_NAME). Sous Ubuntu, suivre docs/DEPLOIEMENT.md." ;;
esac
sudo -n true 2>/dev/null || echec "sudo sans mot de passe est requis (utilisateur opc)."

# Avec moins de 4 Go de RAM, la compilation du front et le hachage scrypt (128 Mo par connexion
# enseignant) peuvent manquer de mémoire : un fichier d'échange de 2 Go évite les arrêts brutaux.
ram_mo=$(awk '/MemTotal/ {print int($2 / 1024)}' /proc/meminfo)
echo "Mémoire : ${ram_mo} Mo"
if (( ram_mo < 4000 )) && ! swapon --show | grep -q .; then
  etape "Fichier d'échange de 2 Go (mémoire < 4 Go)"
  sudo dd if=/dev/zero of=/swapfile bs=1M count=2048 status=none
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile >/dev/null
  sudo swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap defaults 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

etape "Paquets de base"
sudo dnf install -y -q git curl openssl
# podman, buildah et runc (préinstallés sur certaines images) entrent en conflit avec containerd.io.
for paquet in podman buildah runc; do
  if rpm -q "$paquet" >/dev/null 2>&1; then sudo dnf remove -y -q "$paquet"; fi
done

etape "Docker"
if ! command -v docker >/dev/null; then
  sudo curl -fsSL https://download.docker.com/linux/rhel/docker-ce.repo -o /etc/yum.repos.d/docker-ce.repo
  sudo dnf install -y -q docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin \
    || echec "Installation de Docker impossible (version d'Oracle Linux non prise en charge par le dépôt Docker ?)."
fi
sudo systemctl enable --now docker
# Pour lancer docker sans sudo aux prochaines connexions SSH ; ce script, lui, utilise sudo.
sudo usermod -aG docker "$USER"
sudo docker compose version

etape "Pare-feu de la VM (firewalld)"
if systemctl is-active --quiet firewalld; then
  # Deux appels : firewall-cmd (OL 9) refuse --add-service et --add-port dans la même commande.
  sudo firewall-cmd --quiet --permanent --add-service=http --add-service=https
  sudo firewall-cmd --quiet --permanent --add-port=443/udp
  sudo firewall-cmd --quiet --reload
  echo "Ports ouverts : $(sudo firewall-cmd --list-services) $(sudo firewall-cmd --list-ports)"
else
  echo "firewalld inactif : rien à ouvrir sur la VM."
fi

etape "Code de l'application ($DOSSIER)"
if [[ -d "$DOSSIER/.git" ]]; then
  git -C "$DOSSIER" fetch --quiet origin "$BRANCHE"
  git -C "$DOSSIER" checkout --quiet "$BRANCHE"
  git -C "$DOSSIER" pull --quiet --ff-only origin "$BRANCHE"
else
  git clone --quiet --branch "$BRANCHE" "$DEPOT" "$DOSSIER"
fi
git -C "$DOSSIER" log --oneline -1
cd "$DOSSIER/deploy"

etape "Configuration (.env)"
if [[ -z "$DOMAINE" ]]; then
  ip=$(curl -fsS --max-time 10 https://api.ipify.org || curl -fsS --max-time 10 https://ifconfig.me) \
    || echec "IP publique introuvable : relancer avec --domaine."
  DOMAINE="${ip//./-}.sslip.io"
  alerte "Pas de --domaine : utilisation de $DOMAINE (provisoire, prendre un vrai domaine avant la mise en service)."
fi
if [[ ! -f .env ]]; then
  cp .env.example .env
  # Hexadécimal : aucun caractère à échapper dans l'URL de connexion PostgreSQL.
  sed -i "s|^PKP_SECRET_KEY=.*|PKP_SECRET_KEY=$(openssl rand -hex 48)|" .env
  sed -i "s|^PKP_DB_MOT_DE_PASSE=.*|PKP_DB_MOT_DE_PASSE=$(openssl rand -hex 32)|" .env
  echo "Secrets générés."
else
  # Ne jamais régénérer : le mot de passe de la base doit rester celui du volume existant.
  echo "Fichier .env existant conservé (secrets inchangés)."
fi
sed -i "s|^PKP_DOMAINE=.*|PKP_DOMAINE=$DOMAINE|" .env
chmod 600 .env
echo "Domaine : $DOMAINE"

etape "Construction et démarrage (plusieurs minutes la première fois)"
sudo docker compose up -d --build

etape "Attente de l'API"
for _ in $(seq 60); do
  if sudo docker compose exec -T api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" 2>/dev/null; then
    echo "API prête."; break
  fi
  sleep 3
done || true
sudo docker compose exec -T api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" 2>/dev/null \
  || echec "L'API ne répond pas. Journaux : cd $DOSSIER/deploy && sudo docker compose logs api"

etape "Certificat HTTPS (Let's Encrypt)"
https_ok=false
for _ in $(seq 36); do
  # --resolve : on teste Caddy sur cette machine, avec le vrai nom de domaine (et donc le vrai certificat).
  if curl -fsS --max-time 5 --resolve "$DOMAINE:443:127.0.0.1" "https://$DOMAINE/api/health" >/dev/null 2>&1; then
    https_ok=true; break
  fi
  sleep 5
done
if $https_ok; then
  echo "HTTPS opérationnel."
else
  alerte "Pas encore de certificat après 3 minutes. Causes habituelles :"
  echo "  - Security List Oracle : règles entrantes TCP 80 et 443 depuis 0.0.0.0/0 manquantes ;"
  echo "  - le domaine ne pointe pas vers l'IP publique de cette VM ;"
  echo "  - limite de demandes Let's Encrypt (Caddy réessaie seul)."
  echo "  Suivre : cd $DOSSIER/deploy && sudo docker compose logs -f web"
fi

if [[ -n "$EMAIL" ]]; then
  etape "Compte enseignant $EMAIL"
  sudo docker compose exec api python -m app.admin creer --email "$EMAIL" --nom "$NOM" \
    || alerte "Compte non créé (déjà existant ?)."
fi

etape "Terminé"
cat <<FIN
  Site        : https://$DOMAINE
  Enseignant  : https://$DOMAINE/enseignant
  Santé       : https://$DOMAINE/api/health
  Dossier     : $DOSSIER/deploy   (secrets dans .env, à sauvegarder hors de la VM)

  Créer un compte enseignant :
    cd $DOSSIER/deploy && sudo docker compose exec api python -m app.admin creer --email prof@lycee.fr --nom "Mme Martin"
  Mettre à jour plus tard : relancer ce script.
FIN
