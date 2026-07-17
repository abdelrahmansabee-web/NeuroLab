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

# Install Python deps before copying the full repo so Docker caches this layer.
# A hard wall-clock timeout prevents the build from hanging if pip gets stuck.
COPY requirements.txt .
RUN timeout 600 pip install --no-cache-dir --timeout 60 --retries 3 --upgrade -r requirements.txt

# Copy all code and assets.
COPY . .

# Create specific directory structure
RUN mkdir -p frontend/build/static/js frontend/build/static/css models

# Background image for glass UI (decode from embedded base64 to avoid broken external URLs).
RUN if [ ! -f frontend/build/bg.jpg ] && [ -f frontend/build/bg.b64.txt ]; then \
      base64 -d frontend/build/bg.b64.txt > frontend/build/bg.jpg; \
    fi

EXPOSE 7860
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
