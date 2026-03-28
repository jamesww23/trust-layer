"""Agent registry store for Agentic Reputation Infrastructure Layer.

Provides an abstract interface and two implementations:
- MemoryStore: dict-backed, for tests and local dev
- RedisStore: Upstash Redis, for Vercel KV deployment
"""

import json
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from core.models import Agent


class AgentStore(ABC):
    """Abstract base for agent registry persistence."""

    @abstractmethod
    def register(self, agent: Agent) -> None:
        """Register a new agent. Raises ValueError if agent_id already exists."""
        ...

    @abstractmethod
    def get(self, agent_id: str) -> Agent:
        """Get agent by ID. Returns None if not found."""
        ...

    @abstractmethod
    def upsert(self, agent: Agent) -> None:
        """Create or update an agent."""
        ...

    @abstractmethod
    def list_all(self) -> list:
        """Return all registered agents."""
        ...

    @abstractmethod
    def discover(self, keyword: str, min_trust: float = None) -> list:
        """Find agents whose skill_md contains keyword (case-insensitive).
        Results are sorted by keyword relevance (occurrence count) first,
        then by trust score.  Optionally filter by minimum trust score."""
        ...

    @abstractmethod
    def reset(self) -> None:
        """Wipe all agents."""
        ...

    @abstractmethod
    def is_empty(self) -> bool:
        """Check if store has any agents."""
        ...


class MemoryStore(AgentStore):
    """In-memory store for tests and local development."""

    def __init__(self, initial: dict = None):
        self._agents: dict = {}
        if initial:
            for agent_id, agent in initial.items():
                self._agents[agent_id] = agent

    def register(self, agent: Agent) -> None:
        if agent.agent_id in self._agents:
            raise ValueError(f"Agent '{agent.agent_id}' already registered")
        self._agents[agent.agent_id] = agent

    def get(self, agent_id: str) -> Agent:
        return self._agents.get(agent_id)

    def upsert(self, agent: Agent) -> None:
        agent.updated_at = datetime.now(timezone.utc).isoformat()
        self._agents[agent.agent_id] = agent

    def list_all(self) -> list:
        return list(self._agents.values())

    def discover(self, keyword: str, min_trust: float = None) -> list:
        keyword_lower = keyword.lower()
        scored = []
        for agent in self._agents.values():
            skill_lower = agent.skill_md.lower()
            if keyword_lower in skill_lower:
                if min_trust is not None and agent.success_rate < min_trust:
                    continue
                relevance = skill_lower.count(keyword_lower)
                scored.append((agent, relevance))
        scored.sort(key=lambda x: (-x[1], -x[0].success_rate))
        return [agent for agent, _ in scored]

    def reset(self) -> None:
        self._agents.clear()

    def is_empty(self) -> bool:
        return len(self._agents) == 0


class RedisStore(AgentStore):
    """Upstash Redis store for Vercel KV deployment."""

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

    def register(self, agent: Agent) -> None:
        existing = self._redis.get(self._key(agent.agent_id))
        if existing is not None:
            raise ValueError(f"Agent '{agent.agent_id}' already registered")
        self._redis.set(self._key(agent.agent_id), json.dumps(agent.to_dict()))

    def get(self, agent_id: str) -> Agent:
        raw = self._redis.get(self._key(agent_id))
        if raw is None:
            return None
        data = raw if isinstance(raw, dict) else json.loads(raw)
        return Agent.from_dict(data)

    def upsert(self, agent: Agent) -> None:
        agent.updated_at = datetime.now(timezone.utc).isoformat()
        self._redis.set(self._key(agent.agent_id), json.dumps(agent.to_dict()))

    def list_all(self) -> list:
        keys = self._redis.keys(f"{self.KEY_PREFIX}*")
        agents = []
        for key in keys:
            raw = self._redis.get(key)
            if raw is not None:
                data = raw if isinstance(raw, dict) else json.loads(raw)
                agents.append(Agent.from_dict(data))
        return agents

    def discover(self, keyword: str, min_trust: float = None) -> list:
        all_agents = self.list_all()
        keyword_lower = keyword.lower()
        scored = []
        for agent in all_agents:
            skill_lower = agent.skill_md.lower()
            if keyword_lower in skill_lower:
                if min_trust is not None and agent.success_rate < min_trust:
                    continue
                relevance = skill_lower.count(keyword_lower)
                scored.append((agent, relevance))
        scored.sort(key=lambda x: (-x[1], -x[0].success_rate))
        return [agent for agent, _ in scored]

    def reset(self) -> None:
        keys = self._redis.keys(f"{self.KEY_PREFIX}*")
        for key in keys:
            self._redis.delete(key)

    def is_empty(self) -> bool:
        keys = self._redis.keys(f"{self.KEY_PREFIX}*")
        return len(keys) == 0
