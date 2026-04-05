#!/bin/bash
# ==============================================================
#  Trust Layer — Quick Update Script
#  Run this to pull latest code and restart services.
#
#  Usage: bash /opt/trust-layer-agents/update.sh
# ==============================================================

set -e

APP_DIR="/opt/trust-layer-agents"

echo "Pulling latest code..."
cd "$APP_DIR/repo" && git pull

echo "Copying updated files..."
cp "$APP_DIR/repo/agent_worker.py" "$APP_DIR/agent_worker.py"

if [ -d "$APP_DIR/repo/weather-watch-agent" ]; then
    cp "$APP_DIR/repo/weather-watch-agent/"*.py "$APP_DIR/weather-watch-agent/"
fi

echo "Restarting services..."
systemctl restart trust-agent-workers
systemctl restart trust-weatherwatch

echo "Done! Services restarted."
systemctl status trust-agent-workers --no-pager -l | head -5
systemctl status trust-weatherwatch --no-pager -l | head -5
