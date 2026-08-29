#!/usr/bin/env bash
# Run from this Cloud Agent after the user sends the Hetzner IPv4 address.
set -euo pipefail

IP="${1:-}"
if [ -z "$IP" ]; then
  echo "usage: ./bootstrap.sh <HETZNER_IPV4>" >&2
  exit 2
fi

KEY="${SSH_KEY:-$HOME/.ssh/neurolab_hetzner}"
HERE="$(cd "$(dirname "$0")" && pwd)"

if [ ! -f "$KEY" ]; then
  echo "missing SSH private key: $KEY" >&2
  exit 1
fi

echo "==> Waiting for SSH on $IP"
ok=0
for _ in $(seq 1 36); do
  if ssh -i "$KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=8 \
      -o BatchMode=yes "root@${IP}" 'echo ssh-ok' >/dev/null 2>&1; then
    ok=1
    break
  fi
  sleep 5
done
if [ "$ok" != 1 ]; then
  echo "cannot SSH as root@${IP} with $KEY" >&2
  exit 1
fi

echo "==> Uploading deploy kit"
ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "root@${IP}" 'rm -rf /tmp/neurolab-deploy && mkdir -p /tmp/neurolab-deploy'
tar czf - -C "$HERE" \
  --exclude './.env' \
  install.sh docker-compose.yml nginx.conf env.example overlay \
  | ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "root@${IP}" 'tar xzf - -C /tmp/neurolab-deploy'
if [ -f "$HERE/.env" ]; then
  scp -i "$KEY" -o StrictHostKeyChecking=accept-new "$HERE/.env" "root@${IP}:/tmp/neurolab-deploy/.env"
fi

echo "==> Running install on the VPS (Docker build takes several minutes)"
ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "root@${IP}" 'bash /tmp/neurolab-deploy/install.sh'
