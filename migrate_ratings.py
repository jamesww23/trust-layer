#!/usr/bin/env python3
"""
migrate_ratings.py — One-time backfill: rebuild agent ratings lists from stored tasks.

Before our fix, to_dict() didn't save the `ratings` or `rating_weights` lists,
so every Redis reload lost them. This script reconstructs them from rated tasks.

Usage:
    UPSTASH_REDIS_REST_URL=... UPSTASH_REDIS_REST_TOKEN=... python3 migrate_ratings.py

Or if you have a .env file:
    export $(cat .env | xargs) && python3 migrate_ratings.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.store import RedisStore


def migrate():
    store = RedisStore()

    print("Loading all agents...")
    agents = store.list_all()
    print(f"  Found {len(agents)} agents")

    print("Loading all tasks...")
    all_tasks = store._all_tasks()
    rated_tasks = [t for t in all_tasks if t.status == "rated" and t.rating is not None]
    print(f"  Found {len(rated_tasks)} rated tasks")

    # Build a map: provider_id → list of (rating, requester_trust)
    # Use requester's current trust as the weight (best approximation we have)
    agent_map = {a.agent_id: a for a in agents}

    provider_ratings = {}  # agent_id → [(rating, weight)]
    for task in sorted(rated_tasks, key=lambda t: t.rated_at or t.updated_at):
        pid = task.provider_id
        rid = task.requester_id
        if pid not in provider_ratings:
            provider_ratings[pid] = []
        # Use requester's current trust as weight
        requester = agent_map.get(rid)
        weight = requester.trust_score if requester else 0.2
        provider_ratings[pid].append((task.rating, weight))

    # Update each agent
    updated = 0
    skipped = 0
    for agent in agents:
        new_ratings = provider_ratings.get(agent.agent_id, [])
        if not new_ratings:
            print(f"  {agent.agent_name:25} ({agent.agent_id}) — no rated tasks, skip")
            skipped += 1
            continue

        # Keep only last 20 (matches scoring.py convention)
        new_ratings = new_ratings[-20:]
        old_count = len(agent.ratings)
        new_count = len(new_ratings)

        agent.ratings = [r for r, _ in new_ratings]
        agent.rating_weights = [w for _, w in new_ratings]

        store.save(agent)
        print(f"  {agent.agent_name:25} ({agent.agent_id}) — "
              f"ratings: {old_count} → {new_count}  "
              f"trust: {agent.trust_score:.0%}")
        updated += 1

    print()
    print(f"Done. Updated {updated} agents, skipped {skipped}.")


if __name__ == "__main__":
    migrate()
