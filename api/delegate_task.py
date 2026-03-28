"""POST /api/delegate-task — One agent sends a task to another."""

import json
import sys
import os
import uuid
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.store import RedisStore
from core.models import Task


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

            requester_id = body.get("requester_id")
            provider_id = body.get("provider_id")
            description = body.get("description")

            if not requester_id:
                self._error(400, "requester_id is required")
                return
            if not provider_id:
                self._error(400, "provider_id is required")
                return
            if not description:
                self._error(400, "description is required — tell the provider what you need")
                return

            # Verify both agents exist
            requester = store.get(requester_id)
            if not requester:
                self._error(404, f"Requester agent '{requester_id}' not found. Register first.")
                return

            provider = store.get(provider_id)
            if not provider:
                self._error(404, f"Provider agent '{provider_id}' not found")
                return

            # Create the task
            task_id = "task_" + uuid.uuid4().hex[:12]
            task = Task(
                task_id=task_id,
                requester_id=requester_id,
                provider_id=provider_id,
                description=description,
            )
            store.save_task(task)

            self.send_response(201)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "task_delegated",
                "task": task.to_dict(),
                "message": f"Task sent to {provider.agent_name}. They can see it at GET /api/tasks?agent_id={provider_id}",
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
