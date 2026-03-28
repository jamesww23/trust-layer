"""Local development server — serves static files + API with in-memory store."""

import json
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.store import MemoryStore
from core.fixtures import seed_store
from core.controller import run_simulation, submit_feedback, validate_delegation, DEFAULT_TRUST_THRESHOLD

# Global in-memory store seeded with demo agents
store = MemoryStore()
seed_store(store)


class DevHandler(SimpleHTTPRequestHandler):
    """Handle both API routes and static file serving."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory="public", **kwargs)

    # --- API Routing ---

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/agents":
            self._api_agents()
        elif parsed.path == "/api/discover":
            params = parse_qs(parsed.query)
            keyword = params.get("keyword", [""])[0]
            min_trust = params.get("min_trust", [None])[0]
            if min_trust:
                min_trust = float(min_trust)
            self._api_discover(keyword, min_trust)
        elif parsed.path == "/api/tasks":
            params = parse_qs(parsed.query)
            self._api_tasks(params)
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        body, parse_error = self._read_body()
        if parse_error:
            self._json_error(400, parse_error)
            return

        if parsed.path == "/api/run-simulation":
            self._api_run_simulation(body)
        elif parsed.path == "/api/submit-feedback":
            self._api_submit_feedback(body)
        elif parsed.path == "/api/reset":
            self._api_reset()
        elif parsed.path == "/api/register-agent":
            self._api_register_agent(body)
        elif parsed.path == "/api/delegate-task":
            self._api_delegate_task(body)
        elif parsed.path == "/api/submit-result":
            self._api_submit_result(body)
        else:
            self._json_error(404, "Not found")

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    # --- API Handlers ---

    def _api_agents(self):
        agents = store.list_all()
        agents.sort(key=lambda a: -a.trust_score)
        self._json_response({"agents": [a.to_dict() for a in agents]})

    def _api_discover(self, keyword, min_trust):
        if not keyword:
            self._json_error(400, "keyword parameter required")
            return
        results = store.discover(keyword, min_trust)
        self._json_response({"agents": [a.to_dict() for a in results]})

    def _api_run_simulation(self, body):
        try:
            rounds = body.get("rounds", 10)
            if not isinstance(rounds, int) or isinstance(rounds, bool):
                rounds = 10
            rounds = max(1, min(50, rounds))

            threshold = body.get("trust_threshold", 0.3)
            if not isinstance(threshold, (int, float)):
                threshold = 0.3
            threshold = max(0.0, min(1.0, float(threshold)))

            result = run_simulation(store, rounds, trust_threshold=threshold)
            self._json_response(result)
        except ValueError as e:
            self._json_error(400, str(e))

    def _api_submit_feedback(self, body):
        try:
            agent_id = body.get("agent_id")
            score = body.get("score")
            if not agent_id:
                self._json_error(400, "agent_id is required")
                return
            if score is None or not isinstance(score, (int, float)):
                self._json_error(400, "score must be a number between 0.0 and 1.0")
                return
            result = submit_feedback(store, agent_id, float(score))
            self._json_response({"status": "feedback_recorded", "agent": result})
        except ValueError as e:
            self._json_error(400, str(e))

    def _api_reset(self):
        store.reset()
        seed_store(store)
        agents = store.list_all()
        self._json_response({"status": "reset", "agents": [a.to_dict() for a in agents]})

    def _api_register_agent(self, body):
        from core.models import Agent
        try:
            agent = Agent(
                agent_id=body.get("agent_id", ""),
                agent_name=body.get("agent_name", ""),
                skill_md=body.get("skill_md", ""),
            )
            store.register(agent)
            self._json_response({"status": "registered", "agent": agent.to_dict()})
        except ValueError as e:
            self._json_error(400, str(e))

    def _api_delegate_task(self, body):
        import uuid
        from core.models import Task
        requester_id = body.get("requester_id")
        provider_id = body.get("provider_id")
        description = body.get("description")
        if not requester_id:
            self._json_error(400, "requester_id is required"); return
        if not provider_id:
            self._json_error(400, "provider_id is required"); return
        if not description:
            self._json_error(400, "description is required"); return
        requester = store.get(requester_id)
        if not requester:
            self._json_error(404, f"Requester agent '{requester_id}' not found"); return
        provider = store.get(provider_id)
        if not provider:
            self._json_error(404, f"Provider agent '{provider_id}' not found"); return
        try:
            validate_delegation(store, requester_id, provider_id, DEFAULT_TRUST_THRESHOLD)
        except ValueError as e:
            self._json_error(400, str(e)); return
        task_id = "task_" + uuid.uuid4().hex[:12]
        task = Task(task_id=task_id, requester_id=requester_id,
                    provider_id=provider_id, description=description)
        store.save_task(task)
        provider.tasks_received += 1
        store.upsert(provider)
        self._json_response({
            "status": "task_delegated",
            "task": task.to_dict(),
            "message": f"Task sent to {provider.agent_name}. They can see it at GET /api/tasks?agent_id={provider_id}",
        }, 201)

    def _api_tasks(self, params):
        agent_id = params.get("agent_id", [None])[0]
        status_filter = params.get("status", [None])[0]
        role = params.get("role", ["provider"])[0]
        if not agent_id:
            self._json_error(400, "agent_id query parameter is required"); return
        agent = store.get(agent_id)
        if not agent:
            self._json_error(404, f"Agent '{agent_id}' not found"); return
        if role == "requester":
            tasks = store.get_tasks_by_requester(agent_id)
        else:
            tasks = store.get_tasks_for_agent(agent_id, status=status_filter)
        self._json_response({
            "agent_id": agent_id, "role": role,
            "tasks": [t.to_dict() for t in tasks], "count": len(tasks),
        })

    def _api_submit_result(self, body):
        task_id = body.get("task_id")
        result = body.get("result")
        if not task_id:
            self._json_error(400, "task_id is required"); return
        if not result:
            self._json_error(400, "result is required"); return
        task = store.get_task(task_id)
        if not task:
            self._json_error(404, f"Task '{task_id}' not found"); return
        if task.status == "completed":
            self._json_error(400, "Task already completed"); return
        task.status = "completed"
        task.result = result
        store.save_task(task)
        provider = store.get(task.provider_id)
        if provider:
            provider.tasks_completed += 1
            store.upsert(provider)
        self._json_response({
            "status": "result_submitted",
            "task": task.to_dict(),
            "message": f"Result submitted. The requester ({task.requester_id}) can now rate your work at POST /api/submit-feedback",
        })

    # --- Helpers ---

    def _read_body(self):
        """Parse JSON body.  Returns (body_dict, error_string)."""
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}, None
        try:
            parsed = json.loads(self.rfile.read(length).decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None, "Malformed JSON in request body"
        if not isinstance(parsed, dict):
            return None, "Request body must be a JSON object"
        return parsed, None

    def _json_response(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self._cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _json_error(self, status, message):
        self._json_response({"error": message}, status)

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, format, *args):
        # Cleaner logging
        if args and len(args) >= 2:
            method_path = args[0] if args else ""
            status = args[1] if len(args) > 1 else ""
            print(f"  {method_path} → {status}")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    server = HTTPServer(("", port), DevHandler)
    print(f"\n  Agentic Reputation Layer — Local Dev Server")
    print(f"  http://localhost:{port}")
    print(f"  5 seed agents loaded. Ready.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")
