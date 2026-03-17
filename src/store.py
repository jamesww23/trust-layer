"""ReputationStore — JSON file backend for agent profiles.

Storage file: ./data/reputation.json
Format: top-level object keyed by agent_id.
Behavior: read full file -> update matching key -> write full file.
"""

import json
import os
from typing import Optional, List

from models import AgentProfile, StorageError


class ReputationStore:
    def __init__(self, path: str = "./data/reputation.json"):
        self.path = path

    def _read(self) -> dict:
        if not os.path.exists(self.path):
            return {}
        with open(self.path, "r") as f:
            return json.load(f)

    def _write(self, data: dict) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        try:
            with open(self.path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            raise StorageError(f"Failed to write {self.path}: {e}")

    def get(self, agent_id: str) -> Optional[AgentProfile]:
        """Return profile for agent_id, or None if not found."""
        data = self._read()
        if agent_id in data:
            return AgentProfile.from_dict(data[agent_id])
        return None

    def upsert(self, profile: AgentProfile) -> None:
        """Insert or update an agent profile. Atomic read-modify-write."""
        data = self._read()
        data[profile.agent_id] = profile.to_dict()
        self._write(data)

    def list_all(self) -> List[AgentProfile]:
        """Return all stored profiles."""
        data = self._read()
        return [AgentProfile.from_dict(v) for v in data.values()]
