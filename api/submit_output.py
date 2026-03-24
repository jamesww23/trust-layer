"""POST /api/submit-output — External agent submits output for a task."""

import json
import sys
import os
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.store import RedisStore


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            store = RedisStore()

            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Request body required"}).encode())
                return

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

            task_id = body.get("task_id", "").strip()
            agent_id = body.get("agent_id", "").strip()
            agent_name = body.get("agent_name", "").strip() or agent_id
            output_text = body.get("output_text", "").strip()

            if not task_id:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "task_id is required"}).encode())
                return

            if not agent_id:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "agent_id is required"}).encode())
                return

            if not output_text:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "output_text is required"}).encode())
                return

            # Verify task exists
            task_data = store.get_task(task_id)
            if task_data is None:
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"Task {task_id} not found"}).encode())
                return

            output_id = f"out_{agent_id}_{uuid.uuid4().hex[:6]}"
            submission = {
                "output_id": output_id,
                "task_id": task_id,
                "agent_id": agent_id,
                "agent_name": agent_name,
                "output_text": output_text,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            store.queue_submission(task_id, submission)

            # Get current submission count
            submissions = store.get_submissions(task_id)

            response = {
                "output_id": output_id,
                "task_id": task_id,
                "agent_id": agent_id,
                "status": "queued",
                "submissions_count": len(submissions),
                "message": f"Output queued. {len(submissions)} submission(s) for this task.",
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

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
