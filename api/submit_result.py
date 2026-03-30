"""POST /api/submit-result — Provider submits result for a delegated task."""

import json
import sys
import os
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.store import RedisStore
from core.controller import update_agent_latency


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

            task_id = body.get("task_id")
            result = body.get("result")

            if not task_id:
                self._error(400, "task_id is required")
                return
            if not result:
                self._error(400, "result is required — provide your work output")
                return

            task = store.get_task(task_id)
            if not task:
                self._error(404, f"Task '{task_id}' not found")
                return

            if task.status in ("completed", "rated"):
                self._error(400, "Task already completed")
                return

            # Update the task with the result
            from datetime import datetime, timezone
            task.status = "completed"
            task.result = result
            task.completed_at = datetime.now(timezone.utc).isoformat()
            # Compute real latency from delegation to completion
            created = datetime.fromisoformat(task.created_at)
            completed = datetime.fromisoformat(task.completed_at)
            task.latency_ms = round((completed - created).total_seconds() * 1000, 1)
            store.save_task(task)

            # Track completion and latency on the provider agent
            provider = store.get(task.provider_id)
            if provider:
                update_agent_latency(provider, task.latency_ms)
                provider.tasks_completed += 1
                store.upsert(provider)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "result_submitted",
                "task": task.to_dict(),
                "message": f"Result submitted. The requester ({task.requester_id}) can now rate your work at POST /api/submit-feedback",
            }).encode())

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
