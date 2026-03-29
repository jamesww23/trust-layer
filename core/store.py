"""Agent registry store for Agentic Reputation Infrastructure Layer.

Provides an abstract interface and two implementations:
- MemoryStore: dict-backed, for tests and local dev
- RedisStore: Upstash Redis, for Vercel KV deployment
"""

import json
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from core.models import Agent, Task


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
        """Find agents by multi-keyword search across skill_md and agent_name.
        Query is split into words; an agent matches if ANY word appears.
        Results sorted by total keyword hits then trust score."""
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
        self._tasks: dict = {}  # task_id -> Task
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
        words = [w.lower() for w in keyword.strip().split() if len(w) >= 2]
        if not words:
            words = [keyword.strip().lower()]
        scored = []
        for agent in self._agents.values():
            searchable = (agent.skill_md + " " + agent.agent_name).lower()
            relevance = sum(searchable.count(w) for w in words)
            if relevance == 0:
                continue
            if min_trust is not None and agent.trust_score < min_trust:
                continue
            scored.append((agent, relevance))
        scored.sort(key=lambda x: (-x[1], -x[0].trust_score))
        return [agent for agent, _ in scored]

    def reset(self) -> None:
        self._agents.clear()
        self._tasks.clear()

    def is_empty(self) -> bool:
        return len(self._agents) == 0

    # --- Task methods ---

    def save_task(self, task: Task) -> None:
        task.updated_at = datetime.now(timezone.utc).isoformat()
        self._tasks[task.task_id] = task

    def get_task(self, task_id: str) -> Task:
        return self._tasks.get(task_id)

    def get_tasks_for_agent(self, agent_id: str, status: str = None) -> list:
        results = []
        for task in self._tasks.values():
            if task.provider_id == agent_id:
                if status is None or task.status == status:
                    results.append(task)
        results.sort(key=lambda t: t.created_at, reverse=True)
        return results

    def get_tasks_by_requester(self, agent_id: str) -> list:
        results = []
        for task in self._tasks.values():
            if task.requester_id == agent_id:
                results.append(task)
        results.sort(key=lambda t: t.created_at, reverse=True)
        return results


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
        words = [w.lower() for w in keyword.strip().split() if len(w) >= 2]
        if not words:
            words = [keyword.strip().lower()]
        scored = []
        for agent in all_agents:
            searchable = (agent.skill_md + " " + agent.agent_name).lower()
            relevance = sum(searchable.count(w) for w in words)
            if relevance == 0:
                continue
            if min_trust is not None and agent.trust_score < min_trust:
                continue
            scored.append((agent, relevance))
        scored.sort(key=lambda x: (-x[1], -x[0].trust_score))
        return [agent for agent, _ in scored]

    def reset(self) -> None:
        for prefix in [self.KEY_PREFIX, self.TASK_PREFIX]:
            keys = self._redis.keys(f"{prefix}*")
            for key in keys:
                self._redis.delete(key)

    def is_empty(self) -> bool:
        keys = self._redis.keys(f"{self.KEY_PREFIX}*")
        return len(keys) == 0

    # --- Task methods ---

    TASK_PREFIX = "task:"

    def _task_key(self, task_id: str) -> str:
        return f"{self.TASK_PREFIX}{task_id}"

    def save_task(self, task: Task) -> None:
        task.updated_at = datetime.now(timezone.utc).isoformat()
        self._redis.set(self._task_key(task.task_id), json.dumps(task.to_dict()))

    def get_task(self, task_id: str) -> Task:
        raw = self._redis.get(self._task_key(task_id))
        if raw is None:
            return None
        data = raw if isinstance(raw, dict) else json.loads(raw)
        return Task.from_dict(data)

    def get_tasks_for_agent(self, agent_id: str, status: str = None) -> list:
        keys = self._redis.keys(f"{self.TASK_PREFIX}*")
        results = []
        for key in keys:
            raw = self._redis.get(key)
            if raw is not None:
                data = raw if isinstance(raw, dict) else json.loads(raw)
                task = Task.from_dict(data)
                if task.provider_id == agent_id:
                    if status is None or task.status == status:
                        results.append(task)
        results.sort(key=lambda t: t.created_at, reverse=True)
        return results

    def get_tasks_by_requester(self, agent_id: str) -> list:
        keys = self._redis.keys(f"{self.TASK_PREFIX}*")
        results = []
        for key in keys:
            raw = self._redis.get(key)
            if raw is not None:
                data = raw if isinstance(raw, dict) else json.loads(raw)
                task = Task.from_dict(data)
                if task.requester_id == agent_id:
                    results.append(task)
        results.sort(key=lambda t: t.created_at, reverse=True)
        return results
