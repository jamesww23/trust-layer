"""POST /api/run-batch — Run multiple evaluations and track reputation changes."""

import json
import sys
import os
import uuid
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import load_scoring_config
from core.fixtures import load_seed_profiles, list_scenarios, load_scenario
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
            body = {}
            if content_length > 0:
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

            mode = body.get("mode", "scenarios")
            config = load_scoring_config()
            engine = ScoringEngine(config)

            # Build list of (task, candidates) to evaluate
            tasks_and_candidates = []

            if mode == "scenarios":
                scenarios = list_scenarios()
                for s in scenarios:
                    task, candidates = load_scenario(s["task_id"])
                    tasks_and_candidates.append((task, candidates))

            elif mode == "repeat":
                task_id = body.get("task_id")
                count = min(body.get("count", 3), 10)  # cap at 10
                if not task_id:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "task_id required for repeat mode"}).encode())
                    return
                for _ in range(count):
                    task, candidates = load_scenario(task_id)
                    tasks_and_candidates.append((task, candidates))

            elif mode == "llm":
                prompts = body.get("prompts", [])
                if not prompts or len(prompts) < 1:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "prompts array required for llm mode"}).encode())
                    return
                if len(prompts) > 5:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Maximum 5 prompts per batch (Vercel timeout)"}).encode())
                    return

                from core.llm import generate_candidates
                model = body.get("model", "gpt-4o-mini")
                for p in prompts:
                    prompt = p.get("prompt", "").strip()
                    keywords = p.get("expected_keywords", [])
                    if not prompt:
                        continue
                    task_id = f"llm_{uuid.uuid4().hex[:8]}"
                    task = Task(task_id=task_id, prompt=prompt, expected_keywords=keywords)
                    candidates = generate_candidates(prompt, task_id, model=model)
                    tasks_and_candidates.append((task, candidates))
            else:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"Unknown mode: {mode}"}).encode())
                return

            if not tasks_and_candidates:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "No tasks to evaluate"}).encode())
                return

            # Run each evaluation sequentially
            profiles_start = [p.to_dict() for p in store.list_all()]
            run_ids = []
            results = []
            reputation_timeline = []
            win_counts = {}

            for task, candidates in tasks_and_candidates:
                profiles_before = [p.to_dict() for p in store.list_all()]

                controller = TrustController(store, engine, config)
                result = controller.run_task(task, candidates)
                logs = controller.get_logs()

                profiles_after = [p.to_dict() for p in store.list_all()]

                record = build_run_record(
                    task, candidates, result, logs,
                    profiles_before, profiles_after, source="batch")
                store.save_run(record)

                run_ids.append(record.run_id)
                results.append(result.to_dict())
                reputation_timeline.append(profiles_after)

                winner = result.winner_agent_id
                win_counts[winner] = win_counts.get(winner, 0) + 1

            profiles_end = [p.to_dict() for p in store.list_all()]

            # Build aggregate stats
            aggregate_stats = {}
            for r in results:
                aid = r["winner_agent_id"]
                if aid not in aggregate_stats:
                    aggregate_stats[aid] = {"wins": 0, "total_score": 0.0}
                aggregate_stats[aid]["wins"] += 1
                aggregate_stats[aid]["total_score"] += r["winner_score"]
            for aid in aggregate_stats:
                stats = aggregate_stats[aid]
                stats["avg_score"] = round(stats["total_score"] / stats["wins"], 4)
                del stats["total_score"]

            response = {
                "run_ids": run_ids,
                "results": results,
                "reputation_timeline": reputation_timeline,
                "aggregate_stats": aggregate_stats,
                "profiles_before": profiles_start,
                "profiles_after": profiles_end,
                "total_runs": len(results),
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
