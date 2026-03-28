"""POST /api/run-simulation — Run multi-round agent interaction simulation."""

import json
import sys
import os
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.store import RedisStore
from core.fixtures import seed_store
from core.controller import run_simulation


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            store = RedisStore()
            seed_store(store)

            content_length = int(self.headers.get("Content-Length", 0))
            body = {}
            if content_length > 0:
                raw = self.rfile.read(content_length)
                try:
                    body = json.loads(raw.decode())
                except (json.JSONDecodeError, UnicodeDecodeError):
                    body = {}

            if not isinstance(body, dict):
                body = {}

            rounds_raw = body.get("rounds", 5)
            if not isinstance(rounds_raw, int) or isinstance(rounds_raw, bool):
                self._error(400, "rounds must be an integer")
                return
            if rounds_raw < 1:
                self._error(400, "rounds must be at least 1")
                return
            rounds = min(rounds_raw, 50)

            result = run_simulation(store, rounds)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())

        except ValueError as e:
            self._error(400, str(e))
        except Exception as e:
            self._error(500, str(e))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _error(self, status, message):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())
