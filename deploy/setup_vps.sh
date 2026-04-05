#!/bin/bash
# ==============================================================
#  Trust Layer Agent Workers — Hostinger VPS Setup Script
#  Run this ONCE on your VPS to set everything up.
#
#  Usage:
#    scp -r deploy/ root@YOUR_VPS_IP:/root/
#    ssh root@YOUR_VPS_IP
#    chmod +x /root/deploy/setup_vps.sh
#    bash /root/deploy/setup_vps.sh
# ==============================================================

set -e

echo ""
echo "=========================================="
echo "  Trust Layer — VPS Setup"
echo "=========================================="
echo ""

# --- 1. System packages ---
echo "[1/6] Installing system packages..."
apt update -y
apt install -y python3 python3-pip python3-venv git

# --- 2. Create app directory ---
APP_DIR="/opt/trust-layer-agents"
echo "[2/6] Creating app directory: $APP_DIR"
mkdir -p "$APP_DIR"
mkdir -p "$APP_DIR/weather-watch-agent"
mkdir -p "$APP_DIR/logs"

# --- 3. Clone repos ---
echo "[3/6] Cloning repositories..."

# Main trust-layer repo (has agent_worker.py)
if [ -d "$APP_DIR/trust-layer" ]; then
    cd "$APP_DIR/trust-layer" && git pull
else
    git clone https://github.com/jamesww23/trust-layer.git "$APP_DIR/trust-layer"
fi

# Weather watch agent repo
if [ -d "$APP_DIR/weather-watch-agent" ]; then
    cd "$APP_DIR/weather-watch-agent" && git pull
else
    git clone https://github.com/jamesww23/weather-watch-agent.git "$APP_DIR/weather-watch-agent"
fi

# Copy agent_worker.py to app root
cp "$APP_DIR/trust-layer/agent_worker.py" "$APP_DIR/agent_worker.py"

# --- 4. Python virtual environment ---
echo "[4/6] Setting up Python virtual environment..."
python3 -m venv "$APP_DIR/venv"
source "$APP_DIR/venv/bin/activate"
pip install --upgrade pip
pip install requests

# --- 5. Install systemd services ---
echo "[5/6] Installing systemd services..."

# Service 1: All seed agent workers (simulated responses)
cat > /etc/systemd/system/trust-agent-workers.service << 'UNIT'
[Unit]
Description=Trust Layer Agent Workers (All Agents)
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/trust-layer-agents
ExecStart=/opt/trust-layer-agents/venv/bin/python3 /opt/trust-layer-agents/agent_worker.py --all --loop https://trust-layer-topaz.vercel.app
Restart=always
RestartSec=30
StandardOutput=append:/opt/trust-layer-agents/logs/workers.log
StandardError=append:/opt/trust-layer-agents/logs/workers.log
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
UNIT

# Service 2: WeatherWatch agent (real weather data)
cat > /etc/systemd/system/trust-weatherwatch.service << 'UNIT'
[Unit]
Description=Trust Layer WeatherWatch Agent (Real Weather Data)
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/trust-layer-agents/weather-watch-agent
ExecStart=/opt/trust-layer-agents/venv/bin/python3 /opt/trust-layer-agents/weather-watch-agent/agent.py --worker
Restart=always
RestartSec=30
StandardOutput=append:/opt/trust-layer-agents/logs/weatherwatch.log
StandardError=append:/opt/trust-layer-agents/logs/weatherwatch.log
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
UNIT

# Reload systemd
systemctl daemon-reload

# --- 6. Enable and start ---
echo "[6/6] Starting services..."
systemctl enable trust-agent-workers
systemctl enable trust-weatherwatch
systemctl start trust-agent-workers
systemctl start trust-weatherwatch

echo ""
echo "=========================================="
echo "  Setup Complete!"
echo "=========================================="
echo ""
echo "  Services running:"
echo "    - trust-agent-workers  (all 13 seed agents)"
echo "    - trust-weatherwatch   (real weather data)"
echo ""
echo "  Useful commands:"
echo "    systemctl status trust-agent-workers"
echo "    systemctl status trust-weatherwatch"
echo "    journalctl -u trust-agent-workers -f"
echo "    journalctl -u trust-weatherwatch -f"
echo "    tail -f /opt/trust-layer-agents/logs/workers.log"
echo "    tail -f /opt/trust-layer-agents/logs/weatherwatch.log"
echo ""
echo "  To stop:"
echo "    systemctl stop trust-agent-workers"
echo "    systemctl stop trust-weatherwatch"
echo ""
echo "  To restart after code updates:"
echo "    bash /opt/trust-layer-agents/update.sh"
echo ""
