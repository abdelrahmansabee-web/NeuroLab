#!/usr/bin/env bash
# Idempotent dependency setup for the NeuroLab Cloud Agent environment.
# Safe to run repeatedly: apt/pip skip already-satisfied packages and the
# generated assets are recreated deterministically.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Installing system libraries"
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq
# OpenCV / MediaPipe (libGL, glib, X libs, OpenMP), Tesseract OCR + language
# packs, Poppler (PDF), SQLCipher (encrypted-at-rest SQLite) and ffmpeg (video).
sudo apt-get install -y --no-install-recommends \
  libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 libgomp1 \
  tesseract-ocr tesseract-ocr-eng tesseract-ocr-tur tesseract-ocr-ara \
  poppler-utils \
  sqlcipher libsqlcipher-dev libsqlcipher1 \
  build-essential python3-dev python3-venv \
  ffmpeg

VENV="$HOME/neurolab-venv"
echo "==> Creating/refreshing Python virtualenv at $VENV"
if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV"
fi
"$VENV/bin/python" -m pip install --upgrade pip wheel setuptools
"$VENV/bin/pip" install --no-cache-dir -r requirements.txt

echo "==> Generating skeleton overlay assets"
# PNGs are gitignored and generated at build time in production too.
"$VENV/bin/python" generate_skeleton_assets_v4.py

echo "==> Prefetching MediaPipe pose model"
mkdir -p models
if [ ! -s models/pose_landmarker_heavy.task ]; then
  curl -fsSL --max-time 180 -o models/pose_landmarker_heavy.task \
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task" \
    || echo "Pose model prefetch failed; the app will retry at runtime."
fi

echo "==> Install complete"
