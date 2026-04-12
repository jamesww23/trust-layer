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

            # Fetch all tasks in one pass (avoids N×M Redis calls)
            all_tasks = store._all_tasks()

            # Sort by most recently updated, take top 20
            all_tasks.sort(key=lambda t: t.updated_at, reverse=True)
            top20 = all_tasks[:20]

            # Batch-resolve unique agent names (at most 40 lookups, never N×M)
            agent_ids_needed = set()
            for t in top20:
                agent_ids_needed.add(t.requester_id)
                agent_ids_needed.add(t.provider_id)
            agent_name_map = {}
            for aid in agent_ids_needed:
                ag = store.get(aid)
                agent_name_map[aid] = ag.agent_name if ag else aid

            # Enrich with agent names
            events = []
            for t in top20:
                events.append({
                    **t.to_dict(),
                    "requester_name": agent_name_map.get(t.requester_id, t.requester_id),
                    "provider_name": agent_name_map.get(t.provider_id, t.provider_id),
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
