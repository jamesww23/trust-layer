"""POST /api/run-demo — Execute full Trust Layer evaluation loop."""

import json
import sys
import os
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import load_scoring_config
from core.fixtures import load_demo_task, load_seed_profiles
from core.scoring import ScoringEngine
from core.controller import TrustController
from core.store import RedisStore


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            store = RedisStore()

            # Auto-seed if empty
            if store.is_empty():
                seed = load_seed_profiles()
                store.reset(seed)

            # Parse optional request body
            content_length = int(self.headers.get("Content-Length", 0))
            body = {}
            if content_length > 0:
                raw = self.rfile.read(content_length)
                try:
                    body = json.loads(raw.decode())
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": f"Malformed JSON: {e}"}).encode())
                    return

                if not isinstance(body, dict):
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Request body must be a JSON object"}).encode())
                    return

            explicit_outcome = body.get("outcome", None)

            # Snapshot profiles before
            profiles_before = [p.to_dict() for p in store.list_all()]

            # Load fixtures and config
            config = load_scoring_config()
            task, candidates = load_demo_task()
            engine = ScoringEngine(config)
            controller = TrustController(store, engine, config)

            # Run the full loop
            result = controller.run_task(task, candidates, outcome=explicit_outcome)
            logs = controller.get_logs()

            # Snapshot profiles after
            profiles_after = [p.to_dict() for p in store.list_all()]

            response = {
                "result": result.to_dict(),
                "profiles_before": profiles_before,
                "profiles_after": profiles_after,
                "logs": logs,
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

        except ValueError as e:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
