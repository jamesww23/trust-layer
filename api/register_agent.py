"""POST /api/register-agent — Register a new agent in the reputation layer."""

import json
import sys
import os
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import Agent
from core.store import RedisStore
from core.fixtures import seed_store


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            store = RedisStore()
            seed_store(store)

            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                self._error(400, "Request body required")
                return

            raw = self.rfile.read(content_length)
            try:
                body = json.loads(raw.decode())
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                self._error(400, f"Malformed JSON: {e}")
                return

            if not isinstance(body, dict):
                self._error(400, "Request body must be a JSON object")
                return

            agent_id = body.get("agent_id", "").strip()
            agent_name = body.get("agent_name", "").strip()
            skill_md = body.get("skill_md", "").strip()

            if not agent_id:
                self._error(400, "agent_id is required")
                return
            if not agent_name:
                self._error(400, "agent_name is required")
                return
            if not skill_md:
                self._error(400, "skill_md is required")
                return

            agent = Agent(
                agent_id=agent_id,
                agent_name=agent_name,
                skill_md=skill_md,
            )
            store.register(agent)

            self._json(200, {
                "status": "registered",
                "agent": agent.to_dict(),
            })

        except ValueError as e:
            self._error(400, str(e))
        except Exception as e:
            self._error(500, str(e))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _json(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _error(self, status, message):
        self._json(status, {"error": message})
