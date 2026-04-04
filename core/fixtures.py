"""Seed data loader for Agentic Reputation Infrastructure Layer."""

import json
import os

from core.models import Agent

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def load_seed_agents() -> list:
    """Load seed agents from data/seed_agents.json.

    Returns list of Agent objects with default trust scores.
    """
    path = os.path.join(DATA_DIR, "seed_agents.json")
    with open(path, "r") as f:
        raw = json.load(f)

    agents = []
    for entry in raw:
        agents.append(Agent(
            agent_id=entry["agent_id"],
            agent_name=entry["agent_name"],
            skill_md=entry["skill_md"],
            success_rate=entry.get("success_rate", 0.5),
            total_runs=entry.get("total_runs", 0),
            tasks_received=entry.get("tasks_received", 0),
            tasks_completed=entry.get("tasks_completed", 0),
            avg_latency_ms=entry.get("avg_latency_ms", 0.0),
        ))
    return agents


def seed_store(store) -> None:
    """Populate a store with seed agents if it's empty."""
    if store.is_empty():
        for agent in load_seed_agents():
            store.register(agent)
