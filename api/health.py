"""GET /api/health — Liveness check."""

import json
import sys
import os
from http.server import BaseHTTPRequestHandler

# Add project root to path for core imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        response = {
            "status": "ok",
            "engine": "trust-layer",
            "version": "1.0",
        }
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())
