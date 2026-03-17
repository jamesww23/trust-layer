"""Data models for Trust Layer MVP."""

from datetime import datetime, timezone


class AgentProfile:
    """Persistent agent reputation profile."""

    def __init__(self, agent_id: str, agent_name: str, version: str = "1.0",
                 success_rate: float = 0.5, total_runs: int = 0,
                 created_at: str = None, updated_at: str = None):
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.version = version
        self.success_rate = success_rate
        self.total_runs = total_runs
        now = datetime.now(timezone.utc).isoformat()
        self.created_at = created_at or now
        self.updated_at = updated_at or now

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "version": self.version,
            "success_rate": self.success_rate,
            "total_runs": self.total_runs,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentProfile":
        return cls(
            agent_id=data["agent_id"],
            agent_name=data["agent_name"],
            version=data.get("version", "1.0"),
            success_rate=data.get("success_rate", 0.5),
            total_runs=data.get("total_runs", 0),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    def __repr__(self):
        return (f"AgentProfile(id={self.agent_id!r}, name={self.agent_name!r}, "
                f"success_rate={self.success_rate}, total_runs={self.total_runs})")


class Task:
    """A task with expected keywords for relevancy scoring."""

    def __init__(self, task_id: str, prompt: str, expected_keywords: list):
        if not task_id or not task_id.strip():
            raise ValueError("task_id cannot be empty")
        if not prompt or not prompt.strip():
            raise ValueError("prompt cannot be empty")
        self.task_id = task_id
        self.prompt = prompt
        self.expected_keywords = expected_keywords or []

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "prompt": self.prompt,
            "expected_keywords": self.expected_keywords,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        return cls(
            task_id=data["task_id"],
            prompt=data["prompt"],
            expected_keywords=data.get("expected_keywords", []),
        )


class Candidate:
    """A pre-supplied candidate output from an agent."""

    def __init__(self, output_id: str, task_id: str, agent_id: str,
                 output_text: str, latency_ms: int = 0, timestamp: str = None):
        self.output_id = output_id
        self.task_id = task_id
        self.agent_id = agent_id
        self.output_text = output_text
        self.latency_ms = latency_ms
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "output_id": self.output_id,
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "output_text": self.output_text,
            "latency_ms": self.latency_ms,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Candidate":
        return cls(
            output_id=data["output_id"],
            task_id=data["task_id"],
            agent_id=data["agent_id"],
            output_text=data["output_text"],
            latency_ms=data.get("latency_ms", 0),
            timestamp=data.get("timestamp"),
        )


class TaskResult:
    """Result of a Trust Layer evaluation run."""

    def __init__(self, task_id: str, winner_agent_id: str, winner_score: float,
                 ranking: list, explanation: str, outcome: bool,
                 created_at: str = None):
        self.task_id = task_id
        self.winner_agent_id = winner_agent_id
        self.winner_score = winner_score
        self.ranking = ranking
        self.explanation = explanation
        self.outcome = outcome
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "winner_agent_id": self.winner_agent_id,
            "winner_score": self.winner_score,
            "ranking": self.ranking,
            "explanation": self.explanation,
            "outcome": self.outcome,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TaskResult":
        return cls(
            task_id=data["task_id"],
            winner_agent_id=data["winner_agent_id"],
            winner_score=data["winner_score"],
            ranking=data["ranking"],
            explanation=data["explanation"],
            outcome=data["outcome"],
            created_at=data.get("created_at"),
        )


class ScoringConfig:
    """Weights for trust score computation."""

    def __init__(self, w_reputation: float = 0.6, w_relevancy: float = 0.4):
        total = w_reputation + w_relevancy
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"Scoring weights must sum to 1.0, got {total} "
                f"(w_reputation={w_reputation}, w_relevancy={w_relevancy})"
            )
        self.w_reputation = w_reputation
        self.w_relevancy = w_relevancy

    def to_dict(self) -> dict:
        return {
            "w_reputation": self.w_reputation,
            "w_relevancy": self.w_relevancy,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ScoringConfig":
        return cls(
            w_reputation=data["w_reputation"],
            w_relevancy=data["w_relevancy"],
        )
