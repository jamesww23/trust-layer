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
            fulfilled = body.get("fulfilled")

            if not agent_id:
                self._error(400, "agent_id is required")
                return
            if score is None or not isinstance(score, (int, float)):
                self._error(400, "score must be a number between 0.0 and 1.0")
                return
            if fulfilled is None:
                self._error(400, (
                    "fulfilled is required — set true if the task met requirements, "
                    "false if it failed. A false value overrides the score to 0.0."
                ))
                return
            if not isinstance(fulfilled, bool):
                self._error(400, "fulfilled must be a boolean (true or false)")
                return

            # Mandatory: if task was not fulfilled, effective score = 0.0
            # regardless of quality rating. This enforces that non-delivery
            # is always penalised, not softened by partial quality credit.
            effective_score = float(score) if fulfilled else 0.0

            result = submit_feedback(store, agent_id, effective_score,
                                     task_id=task_id, rated_by=rated_by)

            # Attach fulfilled flag to result for transparency
            result["fulfilled"] = fulfilled
            if not fulfilled:
                result["score_override"] = (
                    f"Task marked as not fulfilled — score overridden from "
                    f"{float(score):.2f} to 0.0"
                )

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "feedback_recorded",
                "effective_score": effective_score,
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
