#!/usr/bin/env python3
"""Trust Layer MVP — CLI Entry Point.

Runs one complete demo task using pre-supplied fixture data.
No arguments required. No LLM API calls. No user input.

Inputs:   ./data/demo_task.json     — Task + hardcoded Candidates
Config:   ./config/scoring.json     — ScoringConfig weights (optional)
Storage:  ./data/reputation.json    — AgentProfiles (created on first run)

Exit 0 = success (TaskResult returned, state persisted)
Exit 1 = error   (logged to stderr, no state written)
"""

import json
import os
import sys

from trust_layer.schemas import (
    AgentProfile,
    Candidate,
    Task,
    ScoringConfig,
    ConfigError,
    DEFAULT_CONFIG,
)
from trust_layer.scoring_engine import ScoringEngine
from trust_layer.reputation_store import ReputationStore
from trust_layer.controller import TrustController


def load_config(path: str = "./config/scoring.json") -> ScoringConfig:
    if not os.path.exists(path):
        print(f"[CONFIG DEFAULT] {path} not found, using defaults", file=sys.stdout)
        return DEFAULT_CONFIG
    with open(path, "r") as f:
        data = json.load(f)
    return ScoringConfig.from_dict(data)


def load_demo_task(path: str = "./data/demo_task.json") -> tuple[Task, list[Candidate], dict]:
    with open(path, "r") as f:
        data = json.load(f)

    task = Task.from_dict(data["task"])
    candidates = [Candidate.from_dict(c) for c in data["candidates"]]
    initial_profiles = data.get("initial_profiles", {})
    return task, candidates, initial_profiles


def seed_profiles(store: ReputationStore, initial_profiles: dict):
    for agent_id, profile_data in initial_profiles.items():
        existing = store.get(agent_id)
        if existing is None:
            profile = AgentProfile(
                agent_id=profile_data["agent_id"],
                agent_name=profile_data["agent_name"],
                version=profile_data["version"],
                success_rate=profile_data["success_rate"],
                total_runs=profile_data["total_runs"],
            )
            store.upsert(profile)


def main():
    try:
        # Load config (fail fast if invalid)
        config = load_config()

        # Load demo task and candidates
        task, candidates, initial_profiles = load_demo_task()

        # Initialize store and seed initial profiles
        store = ReputationStore()
        seed_profiles(store, initial_profiles)

        # Initialize engine and controller
        engine = ScoringEngine()
        controller = TrustController(store, engine, config)

        # Run the task
        result = controller.run_task(task, candidates)

        # Print result summary
        print(f"\nTaskResult: {result.explanation}")
        print(f"Outcome: {result.outcome}")

        sys.exit(0)

    except ConfigError as e:
        print(f"ConfigError: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
