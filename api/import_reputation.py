"""POST /api/import — Import a reputation blob produced by /api/export.

Body
----
    {
        "blob":       <export blob from another instance>,
        "overwrite":  false   # optional — replace if agent_id already exists
    }

Anti-poisoning: imported rating weights are halved by default so the
imported trust score immediately starts at roughly half its reported
value and rebuilds via local activity.  Pass `"apply_decay": false` to
disable (intended for migrations between instances you control, not for
accepting blobs from untrusted sources).
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.store import RedisStore
from core.fixtures import seed_store
from core.portability import import_agent


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            store = RedisStore()
            seed_store(store)

            length = int(self.headers.get("Content-Length", 0))
            if length == 0:
                self._error(400, "Request body required")
                return

            try:
                body = json.loads(self.rfile.read(length).decode())
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                self._error(400, f"Malformed JSON: {e}")
                return

            if not isinstance(body, dict):
                self._error(400, "Request body must be a JSON object")
                return

            blob = body.get("blob")
            if blob is None:
                self._error(400, "Field 'blob' is required (the export payload)")
                return

            overwrite = bool(body.get("overwrite", False))
            apply_decay = bool(body.get("apply_decay", True))

            try:
                result = import_agent(
                    store,
                    blob,
                    overwrite=overwrite,
                    apply_decay=apply_decay,
                )
            except ValueError as e:
                # Distinguish duplicate (409) from other validation errors (400)
                msg = str(e)
                status = 409 if "already exists" in msg else 400
                self._error(status, msg)
                return

            self._json(200, result)

        except Exception as e:
            self._error(500, str(e))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
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
