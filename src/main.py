#!/usr/bin/env python3
"""Trust Layer MVP — CLI Entry Point.

Usage:  python src/main.py

Runs one complete demo task using pre-supplied fixture data.
No arguments. No LLM API calls. No user input.

Inputs:   ./data/demo_task.json     — Task + hardcoded Candidates
Config:   ./config/scoring.json     — ScoringConfig weights (optional)
Storage:  ./data/reputation.json    — AgentProfiles (created on first run)

Exit 0 = success  |  Exit 1 = error
"""

import json
import sys
import os

# Ensure src/ is on the path when run from project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import (
    AgentProfile,
    Candidate,
    Task,
    ScoringConfig,
    ConfigError,
    DEFAULT_CONFIG,
)
from scoring import ScoringEngine
from store import ReputationStore
from controller import TrustController
from utils import load_config


def load_demo_task(path: str = "./data/demo_task.json"):
    """Load task, candidates, and optional seed profiles from fixture JSON."""
    with open(path, "r") as f:
        data = json.load(f)
    task = Task.from_dict(data["task"])
    candidates = [Candidate.from_dict(c) for c in data["candidates"]]
    initial_profiles = data.get("initial_profiles", {})
    return task, candidates, initial_profiles


def seed_profiles(store: ReputationStore, initial_profiles: dict):
    """Write seed profiles into the store if they don't already exist."""
    for agent_id, pdata in initial_profiles.items():
        if store.get(agent_id) is None:
            profile = AgentProfile(
                agent_id=pdata["agent_id"],
                agent_name=pdata["agent_name"],
                version=pdata["version"],
                success_rate=pdata["success_rate"],
                total_runs=pdata["total_runs"],
            )
            store.upsert(profile)


def main():
    try:
        # 1. Load config (fail fast if weights invalid)
        config = load_config()

        # 2. Load task + candidates from fixture
        task, candidates, initial_profiles = load_demo_task()

        # 3. Initialize store, seed profiles on first run
        store = ReputationStore()
        seed_profiles(store, initial_profiles)

        # 4. Build engine + controller
        engine = ScoringEngine()
        controller = TrustController(store, engine, config)

        # 5. Run the full Trust Layer loop
        result = controller.run_task(task, candidates)

        # 6. Print final TaskResult as JSON
        print("\n--- TaskResult (JSON) ---")
        print(json.dumps(result.to_dict(), indent=2))

        sys.exit(0)

    except ConfigError as e:
        print(f"[FATAL] ConfigError: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[FATAL] {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
