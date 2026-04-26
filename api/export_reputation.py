"""GET /api/export?agent_id=X — Export a portable reputation blob.

The blob is signed (sha256) so importers can detect tampering, and
includes the agent's full state plus its rated task history for
auditability.  See core/portability.py for the full schema.
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.store import RedisStore
from core.fixtures import seed_store
from core.portability import export_agent


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            store = RedisStore()
            seed_store(store)

            params = parse_qs(urlparse(self.path).query)
            agent_id = (params.get("agent_id", [""])[0] or "").strip()
            if not agent_id:
                self._error(400, "agent_id query parameter is required")
                return

            # Build the source URL from the request host so importers know
            # where the blob came from.
            host = self.headers.get("Host", "")
            scheme = "https" if host and "localhost" not in host else "http"
            source_url = f"{scheme}://{host}" if host else ""

            try:
                blob = export_agent(store, agent_id, source_url=source_url)
            except ValueError as e:
                self._error(404, str(e))
                return

            self._json(200, blob)

        except Exception as e:
            self._error(500, str(e))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _json(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _error(self, status, message):
        self._json(status, {"error": message})
