"""GET /api/state — Return current reputation state + fixture data."""

import json
import sys
import os
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import load_scoring_config
from urllib.parse import urlparse, parse_qs
from core.fixtures import load_demo_task, load_seed_profiles, list_scenarios, load_scenario
from core.store import RedisStore
from core.llm import get_available_providers


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            store = RedisStore()

            # Auto-seed if empty
            if store.is_empty():
                seed = load_seed_profiles()
                store.reset(seed)

            profiles = store.list_all()
            config = load_scoring_config()
            scenarios = list_scenarios()

            # Support ?task_id= query param for scenario selection
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            task_id = params.get("task_id", [None])[0]

            if task_id:
                task, candidates = load_scenario(task_id)
            else:
                task, candidates = load_demo_task()

            available_providers = [
                {"agent_id": p["agent_id"], "agent_name": p["agent_name"], "provider": p["provider"]}
                for p in get_available_providers()
            ]

            response = {
                "profiles": [p.to_dict() for p in profiles],
                "task": task.to_dict(),
                "candidates": [c.to_dict() for c in candidates],
                "config": config.to_dict(),
                "scenarios": scenarios,
                "available_providers": available_providers,
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
