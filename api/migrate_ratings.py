"""POST /api/migrate-ratings — One-time backfill: rebuild ratings lists from stored tasks.

Reconstructs each agent's ratings + rating_weights from rated tasks in Redis.
Safe to run multiple times (idempotent — uses task history as source of truth).
"""

import json
import sys
import os
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.store import RedisStore


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            store = RedisStore()

            agents = store.list_all()
            agent_map = {a.agent_id: a for a in agents}

            all_tasks = store._all_tasks()
            rated_tasks = [t for t in all_tasks if t.status == "rated" and t.rating is not None]

            # Build per-provider rating history sorted by time
            provider_ratings = {}
            for task in sorted(rated_tasks, key=lambda t: t.rated_at or t.updated_at or ""):
                pid = task.provider_id
                if pid not in provider_ratings:
                    provider_ratings[pid] = []
                requester = agent_map.get(task.requester_id)
                weight = requester.trust_score if requester else 0.2
                provider_ratings[pid].append((task.rating, weight))

            results = []
            for agent in agents:
                new_pairs = provider_ratings.get(agent.agent_id, [])
                if not new_pairs:
                    results.append({"agent_id": agent.agent_id, "agent_name": agent.agent_name,
                                    "ratings_before": 0, "ratings_after": 0, "status": "skipped"})
                    continue

                new_pairs = new_pairs[-20:]  # keep last 20
                before = len(agent.ratings)
                agent.ratings = [r for r, _ in new_pairs]
                agent.rating_weights = [w for _, w in new_pairs]
                store.save(agent)
                results.append({
                    "agent_id": agent.agent_id,
                    "agent_name": agent.agent_name,
                    "ratings_before": before,
                    "ratings_after": len(agent.ratings),
                    "trust_score": round(agent.trust_score, 4),
                    "status": "updated",
                })

            updated = sum(1 for r in results if r["status"] == "updated")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "ok": True,
                "agents_updated": updated,
                "agents_total": len(agents),
                "rated_tasks_found": len(rated_tasks),
                "results": results,
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
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
