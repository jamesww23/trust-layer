#!/bin/bash
# ==============================================================
#  Trust Layer — Quick Update Script
#  Run this to pull latest code and restart services.
#
#  Usage: bash /opt/trust-layer-agents/update.sh
# ==============================================================

set -e

APP_DIR="/opt/trust-layer-agents"

echo "Pulling latest trust-layer code..."
cd "$APP_DIR/trust-layer" && git pull
cp "$APP_DIR/trust-layer/agent_worker.py" "$APP_DIR/agent_worker.py"

echo "Pulling latest weather-watch-agent code..."
cd "$APP_DIR/weather-watch-agent" && git pull

echo "Restarting services..."
systemctl restart trust-agent-workers
systemctl restart trust-weatherwatch

echo ""
echo "Done! Services restarted."
systemctl status trust-agent-workers --no-pager -l | head -5
echo ""
systemctl status trust-weatherwatch --no-pager -l | head -5
