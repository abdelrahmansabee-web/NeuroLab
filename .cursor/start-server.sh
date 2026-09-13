#!/usr/bin/env bash
# Launches the NeuroLab FastAPI server (serves the web UI + analysis API).
set -euo pipefail

cd "$(dirname "$0")/.."

VENV="$HOME/neurolab-venv"

# The app requires JWT_SECRET (used to sign auth tokens and to encrypt the local
# SQLCipher databases). If one is not injected via environment secrets, generate
# a persistent per-machine development key. This is a throwaway dev value, never
# a production credential, and it is never committed.
if [ -z "${JWT_SECRET:-}" ]; then
  SECRET_FILE="$HOME/.neurolab/jwt_secret"
  mkdir -p "$(dirname "$SECRET_FILE")"
  if [ ! -s "$SECRET_FILE" ]; then
    (openssl rand -hex 32 2>/dev/null \
      || head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n') > "$SECRET_FILE"
  fi
  export JWT_SECRET="$(cat "$SECRET_FILE")"
fi

# Keep runtime data (encrypted DBs, uploads, outputs) outside the repo checkout.
export NEUROLAB_DATA_DIR="${NEUROLAB_DATA_DIR:-$HOME/neurolab-data}"
mkdir -p "$NEUROLAB_DATA_DIR"

exec "$VENV/bin/uvicorn" main:app --host 0.0.0.0 --port 7860
