"""GET /api/runs — Fetch run history."""

import json
import sys
import os
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.store import RedisStore


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            store = RedisStore()

            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            limit = int(params.get("limit", ["50"])[0])
            offset = int(params.get("offset", ["0"])[0])

            runs = store.list_runs(limit=limit, offset=offset)

            response = {
                "runs": [r.to_dict() for r in runs],
                "count": len(runs),
                "limit": limit,
                "offset": offset,
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
