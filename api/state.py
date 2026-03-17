"""GET /api/state — Return current reputation state + fixture data."""

import json
import sys
import os
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import load_scoring_config
from core.fixtures import load_demo_task, load_seed_profiles
from core.store import RedisStore


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            store = RedisStore()

            # Auto-seed if empty
            if store.is_empty():
                seed = load_seed_profiles()
                store.reset(seed)

            profiles = store.list_all()
            task, candidates = load_demo_task()
            config = load_scoring_config()

            response = {
                "profiles": [p.to_dict() for p in profiles],
                "task": task.to_dict(),
                "candidates": [c.to_dict() for c in candidates],
                "config": config.to_dict(),
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
