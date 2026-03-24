"""Reputation store for Trust Layer MVP.

Provides an abstract interface and two implementations:
- MemoryStore: dict-backed, for tests and local dev
- RedisStore: Upstash Redis, for Vercel KV deployment
"""

import json
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from core.models import AgentProfile, RunRecord


class ReputationStore(ABC):
    """Abstract base for agent reputation persistence."""

    @abstractmethod
    def get(self, agent_id: str) -> AgentProfile:
        """Get agent profile by ID. Returns default profile if not found.

        NOTE: This method persists a default on cache miss. Use lookup()
        when you need a read-only path that does not mutate state.
        """
        ...

    @abstractmethod
    def lookup(self, agent_id: str) -> AgentProfile:
        """Read-only lookup. Returns profile or default WITHOUT persisting.

        Use this in scoring/ranking paths where side-effect-free reads
        are required (e.g., the controller INIT phase).
        """
        ...

    @abstractmethod
    def upsert(self, profile: AgentProfile) -> None:
        """Create or update an agent profile."""
        ...

    @abstractmethod
    def list_all(self) -> list:
        """Return all stored agent profiles."""
        ...

    @abstractmethod
    def reset(self, seed_profiles: dict) -> None:
        """Wipe all profiles and re-seed from provided dict."""
        ...

    @abstractmethod
    def save_run(self, record: RunRecord) -> None:
        """Persist a run record."""
        ...

    @abstractmethod
    def get_run(self, run_id: str) -> RunRecord:
        """Retrieve a run record by ID. Returns None if not found."""
        ...

    @abstractmethod
    def list_runs(self, limit: int = 50, offset: int = 0) -> list:
        """Fetch recent runs, newest first."""
        ...

    @abstractmethod
    def update_run(self, record: RunRecord) -> None:
        """Overwrite an existing run record."""
        ...

    @abstractmethod
    def clear_runs(self) -> None:
        """Wipe all run history."""
        ...

    @abstractmethod
    def store_task(self, task_id: str, task_data: dict) -> None:
        """Store a pending task for external agent submission."""
        ...

    @abstractmethod
    def get_task(self, task_id: str) -> dict:
        """Retrieve a pending task. Returns None if not found."""
        ...

    @abstractmethod
    def queue_submission(self, task_id: str, submission: dict) -> None:
        """Queue an external agent submission for a task."""
        ...

    @abstractmethod
    def get_submissions(self, task_id: str) -> list:
        """Get all queued submissions for a task."""
        ...

    @abstractmethod
    def clear_submissions(self, task_id: str) -> None:
        """Clear queued submissions for a task."""
        ...

    def _default_profile(self, agent_id: str) -> AgentProfile:
        """Create a default profile for an unknown agent."""
        now = datetime.now(timezone.utc).isoformat()
        return AgentProfile(
            agent_id=agent_id,
            agent_name=agent_id,
            version="1.0",
            success_rate=0.5,
            total_runs=0,
            created_at=now,
            updated_at=now,
        )


class MemoryStore(ReputationStore):
    """In-memory store for tests and local development."""

    def __init__(self, initial: dict = None):
        self._data: dict[str, AgentProfile] = {}
        self._runs: dict = {}
        self._run_index: list = []
        self._tasks: dict = {}
        self._queues: dict = {}
        if initial:
            for agent_id, profile in initial.items():
                self._data[agent_id] = profile

    def get(self, agent_id: str) -> AgentProfile:
        if agent_id not in self._data:
            default = self._default_profile(agent_id)
            self._data[agent_id] = default
        return self._data[agent_id]

    def lookup(self, agent_id: str) -> AgentProfile:
        if agent_id in self._data:
            return self._data[agent_id]
        return self._default_profile(agent_id)

    def upsert(self, profile: AgentProfile) -> None:
        profile.updated_at = datetime.now(timezone.utc).isoformat()
        self._data[profile.agent_id] = profile

    def list_all(self) -> list:
        return list(self._data.values())

    def reset(self, seed_profiles: dict) -> None:
        self._data.clear()
        for agent_id, profile in seed_profiles.items():
            self._data[agent_id] = profile

    def save_run(self, record: RunRecord) -> None:
        self._runs[record.run_id] = record
        self._run_index.insert(0, record.run_id)

    def get_run(self, run_id: str) -> RunRecord:
        return self._runs.get(run_id)

    def list_runs(self, limit: int = 50, offset: int = 0) -> list:
        ids = self._run_index[offset:offset + limit]
        return [self._runs[rid] for rid in ids if rid in self._runs]

    def update_run(self, record: RunRecord) -> None:
        self._runs[record.run_id] = record

    def clear_runs(self) -> None:
        self._runs.clear()
        self._run_index.clear()

    def store_task(self, task_id: str, task_data: dict) -> None:
        self._tasks[task_id] = task_data

    def get_task(self, task_id: str) -> dict:
        return self._tasks.get(task_id)

    def queue_submission(self, task_id: str, submission: dict) -> None:
        if task_id not in self._queues:
            self._queues[task_id] = []
        self._queues[task_id].append(submission)

    def get_submissions(self, task_id: str) -> list:
        return self._queues.get(task_id, [])

    def clear_submissions(self, task_id: str) -> None:
        self._queues.pop(task_id, None)

    def is_empty(self) -> bool:
        return len(self._data) == 0


class RedisStore(ReputationStore):
    """Upstash Redis store for deployed use with Vercel KV.

    Environment variables (checked in order):
      Primary:   UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN
      Fallback:  KV_REST_API_URL, KV_REST_API_TOKEN
    """

    KEY_PREFIX = "agent:"

    def __init__(self):
        from upstash_redis import Redis

        url = os.environ.get("UPSTASH_REDIS_REST_URL") or os.environ.get("KV_REST_API_URL")
        token = os.environ.get("UPSTASH_REDIS_REST_TOKEN") or os.environ.get("KV_REST_API_TOKEN")

        if not url or not token:
            raise EnvironmentError(
                "Redis credentials not found. Set UPSTASH_REDIS_REST_URL and "
                "UPSTASH_REDIS_REST_TOKEN (or KV_REST_API_URL and KV_REST_API_TOKEN)."
            )

        self._redis = Redis(url=url, token=token)

    def _key(self, agent_id: str) -> str:
        return f"{self.KEY_PREFIX}{agent_id}"

    def get(self, agent_id: str) -> AgentProfile:
        raw = self._redis.get(self._key(agent_id))
        if raw is None:
            default = self._default_profile(agent_id)
            self.upsert(default)
            return default
        data = raw if isinstance(raw, dict) else json.loads(raw)
        return AgentProfile.from_dict(data)

    def lookup(self, agent_id: str) -> AgentProfile:
        raw = self._redis.get(self._key(agent_id))
        if raw is None:
            return self._default_profile(agent_id)
        data = raw if isinstance(raw, dict) else json.loads(raw)
        return AgentProfile.from_dict(data)

    def upsert(self, profile: AgentProfile) -> None:
        profile.updated_at = datetime.now(timezone.utc).isoformat()
        self._redis.set(self._key(profile.agent_id), json.dumps(profile.to_dict()))

    def list_all(self) -> list:
        keys = self._redis.keys(f"{self.KEY_PREFIX}*")
        profiles = []
        for key in keys:
            raw = self._redis.get(key)
            if raw is not None:
                data = raw if isinstance(raw, dict) else json.loads(raw)
                profiles.append(AgentProfile.from_dict(data))
        return profiles

    def reset(self, seed_profiles: dict) -> None:
        keys = self._redis.keys(f"{self.KEY_PREFIX}*")
        for key in keys:
            self._redis.delete(key)
        for agent_id, profile in seed_profiles.items():
            self.upsert(profile)

    def save_run(self, record: RunRecord) -> None:
        self._redis.set(f"run:{record.run_id}", json.dumps(record.to_dict()))
        self._redis.lpush("runs:index", record.run_id)

    def get_run(self, run_id: str) -> RunRecord:
        raw = self._redis.get(f"run:{run_id}")
        if raw is None:
            return None
        data = raw if isinstance(raw, dict) else json.loads(raw)
        return RunRecord.from_dict(data)

    def list_runs(self, limit: int = 50, offset: int = 0) -> list:
        ids = self._redis.lrange("runs:index", offset, offset + limit - 1)
        if not ids:
            return []
        runs = []
        for run_id in ids:
            raw = self._redis.get(f"run:{run_id}")
            if raw is not None:
                data = raw if isinstance(raw, dict) else json.loads(raw)
                runs.append(RunRecord.from_dict(data))
        return runs

    def update_run(self, record: RunRecord) -> None:
        self._redis.set(f"run:{record.run_id}", json.dumps(record.to_dict()))

    def clear_runs(self) -> None:
        ids = self._redis.lrange("runs:index", 0, -1)
        for run_id in (ids or []):
            self._redis.delete(f"run:{run_id}")
        self._redis.delete("runs:index")

    def store_task(self, task_id: str, task_data: dict) -> None:
        self._redis.set(f"task:{task_id}", json.dumps(task_data))

    def get_task(self, task_id: str) -> dict:
        raw = self._redis.get(f"task:{task_id}")
        if raw is None:
            return None
        return raw if isinstance(raw, dict) else json.loads(raw)

    def queue_submission(self, task_id: str, submission: dict) -> None:
        self._redis.lpush(f"queue:{task_id}", json.dumps(submission))

    def get_submissions(self, task_id: str) -> list:
        items = self._redis.lrange(f"queue:{task_id}", 0, -1)
        if not items:
            return []
        return [
            (item if isinstance(item, dict) else json.loads(item))
            for item in items
        ]

    def clear_submissions(self, task_id: str) -> None:
        self._redis.delete(f"queue:{task_id}")

    def is_empty(self) -> bool:
        keys = self._redis.keys(f"{self.KEY_PREFIX}*")
        return len(keys) == 0
