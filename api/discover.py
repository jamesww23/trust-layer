"""GET /api/discover — Find agents by skill keyword and optional min trust."""

import json
import sys
import os
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.store import RedisStore
from core.fixtures import seed_store


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            store = RedisStore()
            seed_store(store)

            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)

            keyword = params.get("keyword", [""])[0].strip()
            if not keyword:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "keyword parameter required"}).encode())
                return

            min_trust = None
            min_trust_raw = params.get("min_trust", [None])[0]
            if min_trust_raw is not None:
                try:
                    min_trust = float(min_trust_raw)
                except ValueError:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "min_trust must be a number"}).encode())
                    return

            results = store.discover(keyword, min_trust)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "results": [
                    {
                        "agent_id": a.agent_id,
                        "agent_name": a.agent_name,
                        "skill_md": a.skill_md,
                        "trust_score": a.success_rate,
                    }
                    for a in results
                ],
            }).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
