#!/usr/bin/env bash
set -e

echo "=== NeuroLab - Server Deployment ==="
echo ""

# Detect project root (script location)
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$APP_DIR/backend"
FRONTEND_DIR="$APP_DIR/frontend"
PORT=8000
DOMAIN="${DOMAIN:-}"

# ─── System packages ─────────────────────────────────────────────────────
echo "[1/6] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3-pip python3-venv ffmpeg libsm6 libxext6 curl nginx
sudo apt-get autoremove -y -qq

# ─── Create required directories ─────────────────────────────────────────
echo "[2/6] Setting up directories..."
mkdir -p "$BACKEND_DIR/uploads"
mkdir -p "$BACKEND_DIR/outputs"
mkdir -p "$BACKEND_DIR/models"

# ─── Python environment ──────────────────────────────────────────────────
echo "[3/6] Creating Python venv..."
cd "$BACKEND_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

# ─── Download MediaPipe model ────────────────────────────────────────────
echo "[4/6] Downloading MediaPipe Pose Landmarker model..."
if [ ! -f "$BACKEND_DIR/models/pose_landmarker_heavy.task" ]; then
    curl -L -o "$BACKEND_DIR/models/pose_landmarker_heavy.task" \
        "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task"
    echo "  Model downloaded."
else
    echo "  Model already exists."
fi

# ─── Systemd service ─────────────────────────────────────────────────────
echo "[5/6] Creating systemd service..."
USER_NAME=$(whoami)
cat > /tmp/neurolab.service << SERVICEEOF
[Unit]
Description=NeuroLab Stroke Rehab Backend
After=network.target

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$BACKEND_DIR
ExecStart=$BACKEND_DIR/venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port $PORT
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
SERVICEEOF

sudo mv /tmp/neurolab.service /etc/systemd/system/neurolab.service
sudo systemctl daemon-reload
sudo systemctl enable neurolab.service
sudo systemctl start neurolab.service

# ─── Nginx (optional, if DOMAIN is set) ──────────────────────────────────
echo "[6/6] Configuring Nginx..."
if [ -n "$DOMAIN" ]; then
    cat > /tmp/neurolab_nginx << 'NGINXEOF'
server {
    listen 80;
    server_name _;
    client_max_body_size 500M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
    }
}
NGINXEOF

    sudo mv /tmp/neurolab_nginx /etc/nginx/sites-available/neurolab
    sudo ln -sf /etc/nginx/sites-available/neurolab /etc/nginx/sites-enabled/
    sudo rm -f /etc/nginx/sites-enabled/default
    sudo nginx -t && sudo systemctl restart nginx
    echo "  Nginx Reverse Proxy configured."
else
    echo "  Skipping Nginx (set DOMAIN for reverse proxy)."
fi

# ─── Open firewall port ──────────────────────────────────────────────────
echo ""
echo "  IMPORTANT: Open port $PORT in Oracle Cloud firewall:"
echo "  -> Networking -> Security List -> Add Ingress Rule: TCP/$PORT"

echo ""
echo "=== Deployment Complete ==="
echo "  App:   http://$(curl -4 -s ifconfig.me):$PORT"
echo "  Ctrl:  sudo systemctl status neurolab"
echo "  Logs:  journalctl -u neurolab -f"
echo ""
