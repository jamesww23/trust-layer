"""Fixture loader for demo task and seed profiles."""

import json
import os

from core.models import AgentProfile, Task, Candidate

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEMO_TASK_PATH = os.path.join(_PROJECT_ROOT, "data", "demo_task.json")
_SEED_PROFILES_PATH = os.path.join(_PROJECT_ROOT, "data", "seed_profiles.json")


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
