"""POST /api/create-task — Create a task for external agents to respond to."""

import json
import sys
import os
import uuid
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.fixtures import load_seed_profiles
from core.store import RedisStore


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            store = RedisStore()

            if store.is_empty():
                seed = load_seed_profiles()
                store.reset(seed)

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

            prompt = body.get("prompt", "").strip()
            if not prompt:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "prompt is required"}).encode())
                return

            keywords = body.get("expected_keywords", [])
            task_id = f"ext_{uuid.uuid4().hex[:8]}"

            task_data = {
                "task_id": task_id,
                "prompt": prompt,
                "expected_keywords": keywords,
                "status": "open",
            }
            store.store_task(task_id, task_data)

            response = {
                "task_id": task_id,
                "prompt": prompt,
                "expected_keywords": keywords,
                "status": "open",
                "message": "Task created. Agents can now submit outputs via POST /api/submit-output",
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
