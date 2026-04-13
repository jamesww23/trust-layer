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
    """Redis store for deployment (Railway Redis or any standard Redis).

    Uses an agent index (Redis set) to avoid expensive .keys() scans.
    The index 'idx:agents' holds all agent IDs; 'idx:tasks' holds all task IDs.

    Connects via REDIS_URL env var (standard redis:// connection string).
    Falls back to Upstash env vars for backward compatibility.
    """

    KEY_PREFIX = "agent:"
    TASK_PREFIX = "task:"
    AGENT_INDEX = "idx:agents"
    TASK_INDEX = "idx:tasks"

    # Survives across calls in the same Vercel serverless instance
    # (warm start), preventing redundant seed checks on every request.
    _seeded = False

    def __init__(self):
        import redis

        # Railway Redis: RAILWAY_REDIS_URL takes priority, then REDIS_URL
        url = os.environ.get("RAILWAY_REDIS_URL") or os.environ.get("REDIS_URL")

        if not url:
            raise EnvironmentError(
                "Redis credentials not found. Set REDIS_URL env var "
                "(e.g. redis://default:password@host:port)."
            )

        # Railway public Redis doesn't use SSL on the proxy port
        self._redis = redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=10,
        )

    def _key(self, agent_id: str) -> str:
        return f"{self.KEY_PREFIX}{agent_id}"

    def _task_key(self, task_id: str) -> str:
        return f"{self.TASK_PREFIX}{task_id}"

    def register(self, agent: Agent) -> None:
        existing = self._redis.get(self._key(agent.agent_id))
        if existing is not None:
            raise ValueError(f"Agent '{agent.agent_id}' already registered")
        pipe = self._redis.pipeline()
        pipe.set(self._key(agent.agent_id), json.dumps(agent.to_dict()))
        pipe.sadd(self.AGENT_INDEX, agent.agent_id)
        pipe.execute()

    def get(self, agent_id: str) -> Agent:
        raw = self._redis.get(self._key(agent_id))
        if raw is None:
            return None
        data = json.loads(raw)
        return Agent.from_dict(data)

    def upsert(self, agent: Agent) -> None:
        agent.updated_at = datetime.now(timezone.utc).isoformat()
        pipe = self._redis.pipeline()
        pipe.set(self._key(agent.agent_id), json.dumps(agent.to_dict()))
        pipe.sadd(self.AGENT_INDEX, agent.agent_id)
        pipe.execute()

    def list_all(self) -> list:
        agent_ids = self._redis.smembers(self.AGENT_INDEX)
        if not agent_ids:
            return []
        # Batch fetch all agents in one round-trip
        keys = [self._key(aid) for aid in agent_ids]
        raw_list = self._redis.mget(keys)
        agents = []
        for raw in raw_list:
            if raw is not None:
                agents.append(Agent.from_dict(json.loads(raw)))
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
        # Delete agents
        agent_ids = self._redis.smembers(self.AGENT_INDEX) or set()
        if agent_ids:
            keys = [self._key(aid) for aid in agent_ids]
            self._redis.delete(*keys, self.AGENT_INDEX)
        else:
            self._redis.delete(self.AGENT_INDEX)
        # Delete tasks
        task_ids = self._redis.smembers(self.TASK_INDEX) or set()
        if task_ids:
            keys = [self._task_key(tid) for tid in task_ids]
            self._redis.delete(*keys, self.TASK_INDEX)
        else:
            self._redis.delete(self.TASK_INDEX)
        RedisStore._seeded = False

    def is_empty(self) -> bool:
        count = self._redis.scard(self.AGENT_INDEX)
        return count == 0

    # --- Task methods ---

    def save_task(self, task: Task) -> None:
        task.updated_at = datetime.now(timezone.utc).isoformat()
        pipe = self._redis.pipeline()
        pipe.set(self._task_key(task.task_id), json.dumps(task.to_dict()))
        pipe.sadd(self.TASK_INDEX, task.task_id)
        pipe.execute()

    def get_task(self, task_id: str) -> Task:
        raw = self._redis.get(self._task_key(task_id))
        if raw is None:
            return None
        return Task.from_dict(json.loads(raw))

    def _all_tasks(self) -> list:
        """Load all tasks using the index set + batch mget."""
        task_ids = self._redis.smembers(self.TASK_INDEX)
        if not task_ids:
            return []
        keys = [self._task_key(tid) for tid in task_ids]
        raw_list = self._redis.mget(keys)
        tasks = []
        for raw in raw_list:
            if raw is not None:
                tasks.append(Task.from_dict(json.loads(raw)))
        return tasks

    def get_tasks_for_agent(self, agent_id: str, status: str = None) -> list:
        results = []
        for task in self._all_tasks():
            if task.provider_id == agent_id:
                if status is None or task.status == status:
                    results.append(task)
        results.sort(key=lambda t: t.created_at, reverse=True)
        return results

    def get_tasks_by_requester(self, agent_id: str) -> list:
        results = []
        for task in self._all_tasks():
            if task.requester_id == agent_id:
                results.append(task)
        results.sort(key=lambda t: t.created_at, reverse=True)
        return results
