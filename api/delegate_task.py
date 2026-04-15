"""POST /api/delegate-task — One agent sends a task to another."""

import json
import sys
import os
import uuid
from http.server import BaseHTTPRequestHandler
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.store import RedisStore
from core.models import Task
from core.controller import validate_delegation, DEFAULT_TRUST_THRESHOLD, submit_feedback


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
            payload = body.get("payload")

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

            # Validate delegation (self-delegation + trust gate)
            try:
                validate_delegation(store, requester_id, provider_id, DEFAULT_TRUST_THRESHOLD)
            except ValueError as e:
                self._error(400, str(e))
                return

            # Enforce mandatory feedback: auto-rate old unrated tasks, block only recent ones.
            # If a task is completed but unrated for >24h, auto-rate it with neutral 0.5.
            # This prevents permanent blocking while still enforcing rating discipline.
            all_tasks = store._all_tasks()
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(hours=24)

            unrated_recent = []
            for t in all_tasks:
                if (t.requester_id == requester_id
                    and t.provider_id == provider_id
                    and t.status == "completed"):

                    # Parse task's updated_at to check age
                    try:
                        task_time = datetime.fromisoformat(t.updated_at.replace('Z', '+00:00'))
                    except Exception:
                        task_time = now

                    if task_time < cutoff:
                        # Task is old (>24h) — auto-rate with neutral score
                        submit_feedback(store, provider_id, 0.5,
                                      task_id=t.task_id,
                                      rated_by=requester_id)
                    else:
                        # Task is recent — block if unrated
                        unrated_recent.append(t)

            if unrated_recent:
                self._error(400, (
                    f"Feedback required: you have {len(unrated_recent)} recently-completed task(s) "
                    f"with '{provider.agent_name}' that have not been rated. "
                    f"Submit feedback via POST /api/submit-feedback before delegating again. "
                    f"(Tasks older than 24h auto-rate with neutral score.)"
                ))
                return

            # Create the task and track on provider
            task_id = "task_" + uuid.uuid4().hex[:12]
            task = Task(
                task_id=task_id,
                requester_id=requester_id,
                provider_id=provider_id,
                description=description,
                payload=payload,
            )
            store.save_task(task)
            provider.tasks_received += 1
            store.upsert(provider)

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
