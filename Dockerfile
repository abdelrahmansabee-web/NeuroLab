FROM python:3.11.9-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev \
    libgomp1 wget curl gnupg \
    libgl1-mesa-dev libegl1-mesa-dev libgles2-mesa-dev \
    libosmesa6-dev \
    tesseract-ocr tesseract-ocr-eng tesseract-ocr-tur tesseract-ocr-ara poppler-utils \
    sqlcipher libsqlcipher-dev libsqlcipher0 \
    build-essential python3-dev \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Install Python deps before copying the full repo so Docker caches this layer
# unless requirements.txt changes.  A hard wall-clock timeout prevents the build
# from hanging if pip gets stuck resolving or downloading.
COPY requirements.txt .
RUN timeout 600 pip install --no-cache-dir --timeout 60 --retries 3 --upgrade -r requirements.txt

# Copy all code and assets.
COPY . .

# Generate high-quality skeleton bone assets at build time (PNG files are too
# large for HF git and are rejected by pre-receive hook).
RUN python generate_skeleton_assets_v4.py

# Create specific directory structure
RUN mkdir -p frontend/build/static/js frontend/build/static/css models

# MediaPipe pose model (~30 MB) — required for video analysis.  Cap the download
# at 120 seconds; if it fails the app will retry at runtime via ensure_pose_model().
RUN curl -fsSL --max-time 120 -o models/pose_landmarker_heavy.task \
      "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task" \
    && test -s models/pose_landmarker_heavy.task \
    || echo "Pose model download failed; will retry at runtime"

# Background image for glass UI (decode from embedded base64 to avoid broken external URLs).
RUN if [ ! -f frontend/build/bg.jpg ] && [ -f frontend/build/bg.b64.txt ]; then \
      base64 -d frontend/build/bg.b64.txt > frontend/build/bg.jpg; \
    fi

EXPOSE 7860
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
