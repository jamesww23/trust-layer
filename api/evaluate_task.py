"""POST /api/evaluate-task — Evaluate queued external agent submissions."""

import json
import sys
import os
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import load_scoring_config
from core.fixtures import load_seed_profiles
from core.models import Task, Candidate
from core.scoring import ScoringEngine
from core.controller import TrustController, build_run_record
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

            if not isinstance(body, dict):
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Request body must be a JSON object"}).encode())
                return

            task_id = body.get("task_id", "").strip()
            if not task_id:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "task_id is required"}).encode())
                return

            # Load task
            task_data = store.get_task(task_id)
            if task_data is None:
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"Task {task_id} not found"}).encode())
                return

            # Get queued submissions
            submissions = store.get_submissions(task_id)
            if len(submissions) < 2:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "error": f"At least 2 submissions required, got {len(submissions)}",
                    "submissions_count": len(submissions),
                }).encode())
                return

            # Check for duplicate agent_ids
            agent_ids = [s["agent_id"] for s in submissions]
            if len(agent_ids) != len(set(agent_ids)):
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "error": "Duplicate agent_id in submissions"
                }).encode())
                return

            # Build Task and Candidate objects
            task = Task(
                task_id=task_data["task_id"],
                prompt=task_data["prompt"],
                expected_keywords=task_data.get("expected_keywords", []),
            )

            candidates = []
            for s in submissions:
                candidates.append(Candidate(
                    output_id=s["output_id"],
                    task_id=task_id,
                    agent_id=s["agent_id"],
                    output_text=s["output_text"],
                    timestamp=s.get("timestamp"),
                ))

            # Snapshot profiles before
            profiles_before = [p.to_dict() for p in store.list_all()]

            # Run Trust Layer evaluation
            config = load_scoring_config()
            engine = ScoringEngine(config)
            controller = TrustController(store, engine, config)

            result = controller.run_task(task, candidates)
            logs = controller.get_logs()

            # Snapshot profiles after
            profiles_after = [p.to_dict() for p in store.list_all()]

            # Persist run record
            record = build_run_record(
                task, candidates, result, logs,
                profiles_before, profiles_after, source="external")
            store.save_run(record)

            # Clear the submission queue
            store.clear_submissions(task_id)

            response = {
                "run_id": record.run_id,
                "result": result.to_dict(),
                "candidates": [c.to_dict() for c in candidates],
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
