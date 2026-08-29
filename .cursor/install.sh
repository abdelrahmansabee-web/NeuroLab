#!/usr/bin/env bash
# Cloud Agent bootstrap for NeuroLab (FastAPI backend + React frontend).
# Idempotent: safe to re-run. Sets up the Python venv, installs backend and
# frontend dependencies, downloads the MediaPipe pose model, and builds the
# frontend so the backend can serve it from a single origin on port 8000.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"
FRONTEND_DIR="$REPO_ROOT/frontend"
POSE_MODEL_URL="https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task"

echo "[1/5] Installing system packages (OpenCV / MediaPipe / ffmpeg runtime libs)..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
  python3-venv ffmpeg libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 curl

echo "[2/5] Creating Python virtual environment + installing backend deps..."
cd "$BACKEND_DIR"
if [ ! -x "venv/bin/python" ]; then
  python3 -m venv venv
fi
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

echo "[3/5] Downloading MediaPipe Pose Landmarker model (if missing)..."
mkdir -p "$BACKEND_DIR/models" "$BACKEND_DIR/uploads" "$BACKEND_DIR/outputs"
MODEL_FILE="$BACKEND_DIR/models/pose_landmarker_heavy.task"
if [ ! -s "$MODEL_FILE" ]; then
  curl -fsSL -o "$MODEL_FILE" "$POSE_MODEL_URL"
fi

echo "[4/5] Installing frontend dependencies..."
cd "$FRONTEND_DIR"
npm install

echo "[5/5] Building the frontend (served by the backend at / )..."
NODE_OPTIONS="--max-old-space-size=8192" GENERATE_SOURCEMAP=false CI=false npm run build

echo "NeuroLab environment ready. Start the server with:"
echo "  cd backend && ./venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000"
