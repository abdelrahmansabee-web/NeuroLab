FROM python:3.11.9-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev \
    libgomp1 wget curl gnupg \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:/usr/local/bin:/usr/bin:/bin"
ENV HOME=/home/user
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY --chown=user . .

RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Create specific directory structure
RUN mkdir -p frontend/build/static/js frontend/build/static/css models

# MediaPipe pose model (~30 MB) — required for video analysis
RUN curl -fsSL -o models/pose_landmarker_heavy.task \
      "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task" \
    && test -s models/pose_landmarker_heavy.task

# Explicitly copy files to ensure they land in the right place
RUN cp index.html manifest.json robots.txt favicon.ico logo192.png logo512.png bg.jpg frontend/build/ 2>/dev/null || true && \
    cp *.js frontend/build/static/js/ 2>/dev/null || true && \
    cp *.css frontend/build/static/css/ 2>/dev/null || true

EXPOSE 7860
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
