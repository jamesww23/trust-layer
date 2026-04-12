"""GET /api/agents — Return all registered agents."""

import json
import sys
import os
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.store import RedisStore
from core.fixtures import seed_store


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            store = RedisStore()
            seed_store(store)

            agents = store.list_all()

            # Auto-backfill: if any agent has empty ratings but rated tasks exist,
            # reconstruct from task history (one-time self-healing migration)
            needs_backfill = [a for a in agents if len(a.ratings) == 0 and a.tasks_completed > 0]
            if needs_backfill:
                all_tasks = store._all_tasks()
                rated_tasks = [t for t in all_tasks if t.status == "rated" and t.rating is not None]
                agent_map = {a.agent_id: a for a in agents}
                provider_ratings = {}
                for task in sorted(rated_tasks, key=lambda t: t.rated_at or t.updated_at or ""):
                    pid = task.provider_id
                    if pid not in provider_ratings:
                        provider_ratings[pid] = []
                    requester = agent_map.get(task.requester_id)
                    weight = requester.trust_score if requester else 0.2
                    provider_ratings[pid].append((task.rating, weight))
                for agent in needs_backfill:
                    pairs = provider_ratings.get(agent.agent_id, [])[-20:]
                    if pairs:
                        agent.ratings = [r for r, _ in pairs]
                        agent.rating_weights = [w for _, w in pairs]
                        store.register(agent)

            agents.sort(key=lambda a: -a.trust_score)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "public, s-maxage=30, stale-while-revalidate=60")
            self.end_headers()
            self.wfile.write(json.dumps({
                "agents": [a.to_dict() for a in agents],
            }).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
