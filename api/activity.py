"""GET /api/activity — Recent task events enriched with agent names and trust deltas."""

import json
import sys
import os
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.store import RedisStore


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            store = RedisStore()

            # Collect all tasks from store
            all_tasks = []
            for agent in store.list_all():
                for task in store.get_tasks_for_agent(agent.agent_id):
                    all_tasks.append(task)

            # Deduplicate by task_id
            seen = set()
            unique = []
            for t in all_tasks:
                if t.task_id not in seen:
                    seen.add(t.task_id)
                    unique.append(t)

            # Sort by most recently updated
            unique.sort(key=lambda t: t.updated_at, reverse=True)

            # Enrich with agent names (limit to 20 most recent)
            events = []
            for t in unique[:20]:
                requester = store.get(t.requester_id)
                provider = store.get(t.provider_id)
                events.append({
                    **t.to_dict(),
                    "requester_name": requester.agent_name if requester else t.requester_id,
                    "provider_name": provider.agent_name if provider else t.provider_id,
                })

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "activity": events,
                "count": len(events),
            }).encode())

        except Exception as e:
            self._error(500, str(e))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _error(self, status, message):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())
