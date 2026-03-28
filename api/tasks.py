"""GET /api/tasks — Check tasks assigned to an agent."""

import json
import sys
import os
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.store import RedisStore


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            store = RedisStore()

            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            agent_id = params.get("agent_id", [None])[0]
            status_filter = params.get("status", [None])[0]
            role = params.get("role", ["provider"])[0]  # provider or requester

            if not agent_id:
                self._error(400, "agent_id query parameter is required")
                return

            agent = store.get(agent_id)
            if not agent:
                self._error(404, f"Agent '{agent_id}' not found")
                return

            if role == "requester":
                tasks = store.get_tasks_by_requester(agent_id)
            else:
                tasks = store.get_tasks_for_agent(agent_id, status=status_filter)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "agent_id": agent_id,
                "role": role,
                "tasks": [t.to_dict() for t in tasks],
                "count": len(tasks),
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
