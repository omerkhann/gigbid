#!/usr/bin/env bash
# One-shot deploy of GigBid on a fresh Ubuntu 22.04/24.04 VM (x86_64 or ARM), as root or with sudo:
#
#   curl -fsSL https://raw.githubusercontent.com/omerkhann/gigbid/main/infra/deploy/setup_vm.sh -o setup_vm.sh
#   sudo GROQ_API_KEY=... bash setup_vm.sh
#
# Installs Docker, clones the repo, writes .env (generated APP_SECRET_KEY; GROQ_API_KEY from the
# environment), starts the full stack (profile app) and puts Caddy in front with automatic HTTPS on
# https://<ip-with-dashes>.sslip.io (a free wildcard DNS name, so no domain is needed).
set -euo pipefail

REPO=${REPO:-https://github.com/omerkhann/gigbid.git}
DIR=${DIR:-/opt/gigbid}
: "${GROQ_API_KEY:?set GROQ_API_KEY in the environment}"

apt-get update -y
apt-get install -y ca-certificates curl git ufw
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi

# Small VMs: 4 GB swap so image builds and model downloads don't get OOM-killed.
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo "/swapfile none swap sw 0 0" >> /etc/fstab
fi

ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw --force enable

if [ -d "$DIR/.git" ]; then git -C "$DIR" pull --ff-only; else git clone "$REPO" "$DIR"; fi
cd "$DIR"

IP=$(curl -fsS https://api.ipify.org)
HOST="${IP//./-}.sslip.io"
if [ ! -f .env ]; then
  cat > .env <<EOF
APP_ENV=production
APP_SECRET_KEY=$(openssl rand -hex 32)
GROQ_API_KEY=$GROQ_API_KEY
MODEL_PROFILE=open_hosted
MAX_NEW_JOBS_PER_SCOUT=2
WEB_ORIGINS=https://$HOST
PHOENIX_UI_URL=https://$HOST/phoenix
EOF
  chmod 600 .env
fi

cat > infra/deploy/Caddyfile <<EOF
$HOST {
  encode gzip
  reverse_proxy web:3000
}
EOF

docker compose -f infra/docker-compose.yml -f infra/deploy/compose.prod.yml --profile app up -d --build
echo
echo "GigBid is starting at https://$HOST  (reviewer@gigbid.dev / gigbid-review)"
echo "First start builds images and downloads the embedding model: allow ~10 minutes."
