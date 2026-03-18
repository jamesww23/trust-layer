"""Fixture loader for demo task, seed profiles, and scenario management."""

import json
import os

from core.models import AgentProfile, Task, Candidate

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR = os.path.join(_PROJECT_ROOT, "data")
_DEMO_TASK_PATH = os.path.join(_DATA_DIR, "demo_task.json")
_SEED_PROFILES_PATH = os.path.join(_DATA_DIR, "seed_profiles.json")
_SCENARIOS_PATH = os.path.join(_DATA_DIR, "scenarios.json")


def load_demo_task(path: str = None) -> tuple:
    """Load demo task and candidates from fixture JSON.

    Returns:
        (Task, list[Candidate])
    """
    task_path = path or _DEMO_TASK_PATH

    with open(task_path, "r") as f:
        data = json.load(f)

    task = Task.from_dict(data["task"])
    candidates = [Candidate.from_dict(c) for c in data["candidates"]]

    return task, candidates


def load_seed_profiles(path: str = None) -> dict:
    """Load seed agent profiles from fixture JSON.

    Returns:
        dict[str, AgentProfile] keyed by agent_id
    """
    profiles_path = path or _SEED_PROFILES_PATH

    with open(profiles_path, "r") as f:
        data = json.load(f)

    return {
        agent_id: AgentProfile.from_dict(profile_data)
        for agent_id, profile_data in data.items()
    }


def list_scenarios() -> list:
    """Return list of available scenario metadata dicts.

    Each dict has: task_id, title, domain, file.
    """
    with open(_SCENARIOS_PATH, "r") as f:
        return json.load(f)


def load_scenario(task_id: str) -> tuple:
    """Load a specific scenario by task_id from the manifest.

    Returns:
        (Task, list[Candidate])

    Raises:
        ValueError: If task_id not found in scenarios manifest.
    """
    scenarios = list_scenarios()
    match = None
    for s in scenarios:
        if s["task_id"] == task_id:
            match = s
            break

    if match is None:
        valid_ids = [s["task_id"] for s in scenarios]
        raise ValueError(
            f"Unknown task_id: {task_id}. Valid options: {valid_ids}"
        )

    path = os.path.join(_DATA_DIR, match["file"])
    return load_demo_task(path=path)
