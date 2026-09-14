#!/usr/bin/env bash
# Run as root on a fresh Hetzner Ubuntu 22.04/24.04 CX33.
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="${APP_DIR:-/opt/neurolab}"
DATA_DIR="${DATA_DIR:-/var/lib/neurolab/data}"
HF_REPO="${HF_REPO:-https://huggingface.co/spaces/AbdelrahmanSabee/neurolab}"

export DEBIAN_FRONTEND=noninteractive

echo "==> Installing packages"
apt-get update -qq
apt-get install -y -qq git curl ca-certificates nginx ufw python3 openssl

if ! command -v docker >/dev/null 2>&1; then
  apt-get install -y -qq docker.io || true
fi
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi
apt-get install -y -qq docker-compose-v2 || apt-get install -y -qq docker-compose || true
systemctl enable --now docker
if ! docker compose version >/dev/null 2>&1 && ! command -v docker-compose >/dev/null 2>&1; then
  mkdir -p /usr/local/lib/docker/cli-plugins
  curl -fsSL "https://github.com/docker/compose/releases/download/v2.32.4/docker-compose-linux-x86_64" \
    -o /usr/local/lib/docker/cli-plugins/docker-compose
  chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
fi

compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
  else
    echo "docker compose is not installed" >&2
    exit 1
  fi
}

if [ ! -f /swapfile ]; then
  echo "==> Creating 8G swap"
  fallocate -l 8G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "==> Fetching NeuroLab (Hugging Face production app)"
mkdir -p "$APP_DIR" "$DATA_DIR"
if [ ! -d "$APP_DIR/.git" ]; then
  rm -rf "$APP_DIR"
  git clone --depth 1 "$HF_REPO" "$APP_DIR"
else
  git -C "$APP_DIR" fetch --depth 1 origin
  git -C "$APP_DIR" reset --hard FETCH_HEAD
fi

echo "==> Applying Hetzner overlay (/sync-ipad)"
python3 "$DEPLOY_DIR/overlay/apply_overlay.py" "$APP_DIR"
cp "$DEPLOY_DIR/docker-compose.yml" "$APP_DIR/docker-compose.yml"

if [ ! -f "$APP_DIR/.env" ]; then
  if [ -f "$DEPLOY_DIR/.env" ]; then
    cp "$DEPLOY_DIR/.env" "$APP_DIR/.env"
    echo "==> Using secrets from deploy folder"
  else
    SECRET="$(openssl rand -hex 32)"
    cat > "$APP_DIR/.env" <<EOF
JWT_SECRET=$SECRET
MFA_ENCRYPTION_KEY=$SECRET
DB_ENCRYPTION_KEY=$SECRET
EOF
    chmod 600 "$APP_DIR/.env"
    echo "==> WARNING: generated new JWT_SECRET. Paste Hugging Face secrets later or existing logins will not work."
  fi
fi
chmod 600 "$APP_DIR/.env" 2>/dev/null || true

echo "==> Building and starting Docker image (first build downloads PyTorch — several minutes)"
cd "$APP_DIR"
compose up -d --build

echo "==> Nginx reverse proxy"
mkdir -p /etc/nginx/snippets
cp "$DEPLOY_DIR/nginx-gzip.conf" /etc/nginx/conf.d/neurolab-gzip.conf
cp "$DEPLOY_DIR/nginx-static-cache.conf" /etc/nginx/snippets/neurolab-static-cache.conf
cp "$DEPLOY_DIR/nginx-static-cache-locations.conf" /etc/nginx/snippets/neurolab-static-cache-locations.conf
if [ -f /etc/letsencrypt/live/medlabai.duckdns.org/fullchain.pem ] && [ -f "$DEPLOY_DIR/nginx-https.example.conf" ]; then
  echo "==> Keeping HTTPS vhost (Let's Encrypt certs present)"
else
  cp "$DEPLOY_DIR/nginx.conf" /etc/nginx/sites-available/neurolab
fi
ln -sfn /etc/nginx/sites-available/neurolab /etc/nginx/sites-enabled/neurolab
rm -f /etc/nginx/sites-enabled/default
python3 "$DEPLOY_DIR/overlay/patch_nginx_server_max.py" /etc/nginx/sites-available/neurolab
nginx -t
systemctl enable --now nginx
systemctl reload nginx

echo "==> Firewall (SSH + HTTP + HTTPS)"
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo "==> Waiting for /health"
ok=0
for _ in $(seq 1 60); do
  if curl -fsS http://127.0.0.1/health >/dev/null 2>&1; then
    ok=1
    break
  fi
  sleep 3
done

PUBLIC_IP="$(curl -4 -fsS https://ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')"
echo ""
echo "=== NeuroLab Hetzner deploy ==="
if [ "$ok" = 1 ]; then
  curl -fsS http://127.0.0.1/health || true
  echo "App:    http://${PUBLIC_IP}/"
  echo "Health: http://${PUBLIC_IP}/health"
  echo "iPad:   http://${PUBLIC_IP}/sync-ipad"
else
  echo "App container is still starting. Check: docker logs neurolab-neurolab-1"
  echo "IP: http://${PUBLIC_IP}/"
  exit 1
fi
