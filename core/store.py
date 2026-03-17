"""Reputation store for Trust Layer MVP.

Provides an abstract interface and two implementations:
- MemoryStore: dict-backed, for tests and local dev
- RedisStore: Upstash Redis, for Vercel KV deployment
"""

import json
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from core.models import AgentProfile


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

    def is_empty(self) -> bool:
        keys = self._redis.keys(f"{self.KEY_PREFIX}*")
        return len(keys) == 0
