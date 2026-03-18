"""POST /api/run-custom — Execute Trust Layer with user-provided input."""

import json
import sys
import os
import uuid
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import load_scoring_config
from core.fixtures import load_seed_profiles
from core.models import Task, Candidate
from core.scoring import ScoringEngine
from core.controller import TrustController
from core.store import RedisStore


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            store = RedisStore()

            # Auto-seed if empty
            if store.is_empty():
                seed = load_seed_profiles()
                store.reset(seed)

            # Parse required request body
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

            if not isinstance(body, dict):
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Request body must be a JSON object"}).encode())
                return

            # Validate required fields
            task_data = body.get("task")
            candidates_data = body.get("candidates")

            if not task_data or not isinstance(task_data, dict):
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing or invalid 'task' object"}).encode())
                return

            if not candidates_data or not isinstance(candidates_data, list):
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing or invalid 'candidates' array"}).encode())
                return

            prompt = task_data.get("prompt", "").strip()
            if not prompt:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Task prompt is required"}).encode())
                return

            if len(candidates_data) < 2:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "At least 2 candidates required"}).encode())
                return

            # Build models from custom input
            short_id = uuid.uuid4().hex[:8]
            task_id = f"custom_{short_id}"
            keywords = task_data.get("expected_keywords", [])

            task = Task(
                task_id=task_id,
                prompt=prompt,
                expected_keywords=keywords,
            )

            candidates = []
            for i, c in enumerate(candidates_data):
                agent_id = c.get("agent_id", "").strip()
                output_text = c.get("output_text", "").strip()

                if not agent_id:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "error": f"Candidate {i+1}: agent_id is required"
                    }).encode())
                    return

                if not output_text:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "error": f"Candidate {i+1}: output_text is required"
                    }).encode())
                    return

                candidates.append(Candidate(
                    output_id=f"out_{agent_id}_{short_id}",
                    task_id=task_id,
                    agent_id=agent_id,
                    output_text=output_text,
                ))

            explicit_outcome = body.get("outcome", None)

            # Snapshot profiles before
            profiles_before = [p.to_dict() for p in store.list_all()]

            # Run the full loop
            config = load_scoring_config()
            engine = ScoringEngine(config)
            controller = TrustController(store, engine, config)

            result = controller.run_task(task, candidates, outcome=explicit_outcome)
            logs = controller.get_logs()

            # Snapshot profiles after
            profiles_after = [p.to_dict() for p in store.list_all()]

            response = {
                "result": result.to_dict(),
                "profiles_before": profiles_before,
                "profiles_after": profiles_after,
                "logs": logs,
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

        except ValueError as e:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

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
