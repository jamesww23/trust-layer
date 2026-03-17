from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


@dataclass
class AgentProfile:
    agent_id: str
    agent_name: str
    version: str
    success_rate: float  # [0.0, 1.0]
    total_runs: int
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "AgentProfile":
        return cls(**d)

    @classmethod
    def default(cls, agent_id: str) -> "AgentProfile":
        return cls(
            agent_id=agent_id,
            agent_name=agent_id,
            version="1.0",
            success_rate=0.5,
            total_runs=0,
        )


@dataclass
class Task:
    task_id: str
    prompt: str
    expected_keywords: list

    @classmethod
    def from_dict(cls, d: dict) -> "Task":
        return cls(**d)


@dataclass
class Candidate:
    output_id: str
    task_id: str
    agent_id: str
    output_text: str
    latency_ms: int = 0
    timestamp: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "Candidate":
        return cls(**d)


@dataclass
class ScoredCandidate:
    candidate: Candidate
    relevancy: float
    trust_score: float


@dataclass
class RankEntry:
    agent_id: str
    trust_score: float
    relevancy: float
    success_rate: float


@dataclass
class TaskResult:
    task_id: str
    winner_agent_id: str
    winner_score: float
    ranking: list  # list of RankEntry dicts
    explanation: str
    outcome: bool
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class ScoringConfig:
    w_reputation: float = 0.6
    w_relevancy: float = 0.4

    def validate(self):
        if abs((self.w_reputation + self.w_relevancy) - 1.0) > 1e-6:
            raise ConfigError(
                f"Weights must sum to 1.0, got {self.w_reputation} + {self.w_relevancy} "
                f"= {self.w_reputation + self.w_relevancy}"
            )

    @classmethod
    def from_dict(cls, d: dict) -> "ScoringConfig":
        config = cls(
            w_reputation=d.get("w_reputation", 0.6),
            w_relevancy=d.get("w_relevancy", 0.4),
        )
        config.validate()
        return config


DEFAULT_CONFIG = ScoringConfig()


class ConfigError(Exception):
    pass


class StorageError(Exception):
    pass
