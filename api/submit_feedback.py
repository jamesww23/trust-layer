"""POST /api/submit-feedback — Submit explicit feedback for an agent."""

import json
import sys
import os
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.store import RedisStore
from core.controller import submit_feedback


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            store = RedisStore()

            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                self._error(400, "Request body required")
                return

            raw = self.rfile.read(content_length)
            try:
                body = json.loads(raw.decode())
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._error(400, "Invalid JSON")
                return

            if not isinstance(body, dict):
                self._error(400, "Request body must be a JSON object")
                return

            agent_id = body.get("agent_id")
            score = body.get("score")
            task_id = body.get("task_id")
            rated_by = body.get("rated_by")

            if not agent_id:
                self._error(400, "agent_id is required")
                return
            if score is None or not isinstance(score, (int, float)):
                self._error(400, "score must be a number between 0.0 and 1.0")
                return

            result = submit_feedback(store, agent_id, float(score),
                                     task_id=task_id, rated_by=rated_by)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "feedback_recorded",
                **result,
            }).encode())

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
