"""POST /api/run-llm — Generate real LLM outputs and evaluate with Trust Layer."""

import json
import sys
import os
import uuid
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import load_scoring_config
from core.fixtures import load_seed_profiles
from core.models import Task
from core.scoring import ScoringEngine
from core.controller import TrustController, build_run_record
from core.store import RedisStore
from core.llm import generate_candidates


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            store = RedisStore()

            # Auto-seed if empty
            if store.is_empty():
                seed = load_seed_profiles()
                store.reset(seed)

            # Parse required body
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

            prompt = body.get("prompt", "").strip()
            if not prompt:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "prompt is required"}).encode())
                return

            keywords = body.get("expected_keywords", [])
            model = body.get("model", "gpt-4o-mini")

            # Build task
            task_id = f"llm_{uuid.uuid4().hex[:8]}"
            task = Task(task_id=task_id, prompt=prompt, expected_keywords=keywords)

            # Generate real LLM outputs
            candidates = generate_candidates(prompt, task_id, model=model)

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
                profiles_before, profiles_after, source="llm")
            store.save_run(record)

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

        except EnvironmentError as e:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

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
