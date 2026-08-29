#!/usr/bin/env bash
# Run after the user sends the VPS IPv4 (Hostinger, Hetzner, etc.).
# Password login: ./bootstrap.sh <IP> '<root-password>'
set -euo pipefail

IP="${1:-}"
PASSWORD="${2:-${SSH_PASSWORD:-}}"
if [ -z "$IP" ]; then
  echo "usage: ./bootstrap.sh <IPV4> [root-password]" >&2
  exit 2
fi

KEY="${SSH_KEY:-$HOME/.ssh/neurolab_hetzner}"
HERE="$(cd "$(dirname "$0")" && pwd)"

if [ ! -f "$KEY" ]; then
  echo "missing SSH private key: $KEY" >&2
  exit 1
fi

ssh_cmd() {
  ssh -i "$KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=8 "$@"
}

if [ -n "$PASSWORD" ]; then
  if ! command -v sshpass >/dev/null 2>&1; then
    sudo apt-get update -qq && sudo apt-get install -y -qq sshpass
  fi
  echo "==> Installing agent SSH key on $IP (password login)"
  PUB="$(cat "${KEY}.pub")"
  sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=accept-new \
    -o PreferredAuthentications=password -o PubkeyAuthentication=no \
    -o ConnectTimeout=15 "root@${IP}" \
    "mkdir -p ~/.ssh && chmod 700 ~/.ssh && touch ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && grep -qF '$PUB' ~/.ssh/authorized_keys || echo '$PUB' >> ~/.ssh/authorized_keys"
fi

echo "==> Waiting for SSH on $IP"
ok=0
for _ in $(seq 1 36); do
  if ssh_cmd -o BatchMode=yes "root@${IP}" 'echo ssh-ok' >/dev/null 2>&1; then
    ok=1
    break
  fi
  sleep 5
done
if [ "$ok" != 1 ]; then
  echo "cannot SSH as root@${IP}" >&2
  exit 1
fi

echo "==> Uploading deploy kit"
ssh_cmd "root@${IP}" 'rm -rf /tmp/neurolab-deploy && mkdir -p /tmp/neurolab-deploy'
tar czf - -C "$HERE" \
  --exclude './.env' \
  install.sh docker-compose.yml nginx.conf env.example overlay \
  | ssh_cmd "root@${IP}" 'tar xzf - -C /tmp/neurolab-deploy'
if [ -f "$HERE/.env" ]; then
  scp -i "$KEY" -o StrictHostKeyChecking=accept-new "$HERE/.env" "root@${IP}:/tmp/neurolab-deploy/.env"
fi

echo "==> Running install on the VPS (Docker build takes several minutes)"
ssh_cmd "root@${IP}" 'bash /tmp/neurolab-deploy/install.sh'
