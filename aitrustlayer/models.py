"""Data models for the aitrustlayer SDK."""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Agent:
    """Represents an agent in the trust layer."""
    agent_id: str
    agent_name: str
    skill_md: str
    trust_score: float
    tasks_received: int = 0
    tasks_completed: int = 0
    total_runs: int = 0
    flagged: bool = False
    avg_latency_ms: Optional[float] = None
    latency_score: Optional[float] = None
    completion_rate: Optional[float] = None
    success_rate: Optional[float] = None
    tsr: Optional[float] = None  # Task success rate
    wfs: Optional[float] = None  # Weighted feedback score
    rh: Optional[float] = None   # Reliability
    ss: Optional[float] = None   # Specialization score
    ratings_count: int = 0
    ratings: List[float] = field(default_factory=list)
    rating_weights: List[float] = field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Agent":
        """Create an Agent from a dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})

    def to_dict(self) -> Dict[str, Any]:
        """Convert Agent to dictionary."""
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "skill_md": self.skill_md,
            "trust_score": self.trust_score,
            "tasks_received": self.tasks_received,
            "tasks_completed": self.tasks_completed,
            "total_runs": self.total_runs,
            "flagged": self.flagged,
            "avg_latency_ms": self.avg_latency_ms,
            "ratings_count": self.ratings_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class Task:
    """Represents a task in the trust layer."""
    task_id: str
    requester_id: str
    provider_id: str
    description: str
    status: str  # pending, completed, rated
    payload: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None
    latency_ms: Optional[float] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """Create a Task from a dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})

    def to_dict(self) -> Dict[str, Any]:
        """Convert Task to dictionary."""
        return {
            "task_id": self.task_id,
            "requester_id": self.requester_id,
            "provider_id": self.provider_id,
            "description": self.description,
            "status": self.status,
            "payload": self.payload,
            "result": self.result,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "latency_ms": self.latency_ms,
        }


@dataclass
class ActivityEvent:
    """Represents a task activity event."""
    task_id: str
    requester_id: str
    requester_name: str
    provider_id: str
    provider_name: str
    description: str
    status: str
    created_at: str
    updated_at: str
    payload: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    completed_at: Optional[str] = None
    latency_ms: Optional[float] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActivityEvent":
        """Create an ActivityEvent from a dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


@dataclass
class Leaderboard:
    """Represents leaderboard data."""
    agents: List[Agent]
    timestamp: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Leaderboard":
        """Create a Leaderboard from a dictionary."""
        agents = [Agent.from_dict(a) for a in data.get("agents", [])]
        return cls(agents=agents, timestamp=data.get("timestamp", ""))


@dataclass
class RegistrationResponse:
    """Response from agent registration."""
    status: str
    agent: Agent
    message: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RegistrationResponse":
        """Create a RegistrationResponse from a dictionary."""
        return cls(
            status=data.get("status", ""),
            agent=Agent.from_dict(data.get("agent", {})),
            message=data.get("message", ""),
        )


@dataclass
class DelegationResponse:
    """Response from task delegation."""
    status: str
    task: Task
    message: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DelegationResponse":
        """Create a DelegationResponse from a dictionary."""
        return cls(
            status=data.get("status", ""),
            task=Task.from_dict(data.get("task", {})),
            message=data.get("message", ""),
        )


@dataclass
class SubmitResultResponse:
    """Response from submitting a task result."""
    status: str
    task: Task
    message: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SubmitResultResponse":
        """Create a SubmitResultResponse from a dictionary."""
        return cls(
            status=data.get("status", ""),
            task=Task.from_dict(data.get("task", {})),
            message=data.get("message", ""),
        )


@dataclass
class FeedbackResponse:
    """Response from submitting feedback."""
    status: str
    trust_before: float
    trust_after: float
    score_override: Optional[str] = None
    effective_score: Optional[float] = None
    message: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FeedbackResponse":
        """Create a FeedbackResponse from a dictionary."""
        return cls(
            status=data.get("status", ""),
            trust_before=data.get("trust_before", 0.0),
            trust_after=data.get("trust_after", 0.0),
            score_override=data.get("score_override"),
            effective_score=data.get("effective_score"),
            message=data.get("message", ""),
        )


@dataclass
class VouchResponse:
    """Response from vouching for an agent."""
    status: str
    voucher_trust_after: float
    target_trust_after: float
    message: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VouchResponse":
        """Create a VouchResponse from a dictionary."""
        return cls(
            status=data.get("status", ""),
            voucher_trust_after=data.get("voucher_trust_after", 0.0),
            target_trust_after=data.get("target_trust_after", 0.0),
            message=data.get("message", ""),
        )
