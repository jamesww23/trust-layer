"""Data models for Agentic Reputation Infrastructure Layer."""

from datetime import datetime, timezone


class Agent:
    """An agent registered in the reputation layer."""

    # Trust system constants
    PRIOR_TRUST = 0.2       # unproven agent baseline
    CONFIDENCE_RAMP = 10    # tasks needed for full confidence

    def __init__(self, agent_id: str, agent_name: str, skill_md: str,
                 success_rate: float = 0.5, total_runs: int = 0,
                 flagged: int = 0,
                 tasks_received: int = 0, tasks_completed: int = 0,
                 created_at: str = None, updated_at: str = None):
        if not agent_id or not agent_id.strip():
            raise ValueError("agent_id cannot be empty")
        if not agent_name or not agent_name.strip():
            raise ValueError("agent_name cannot be empty")
        if not skill_md or not skill_md.strip():
            raise ValueError("skill_md cannot be empty")
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.skill_md = skill_md
        self.success_rate = success_rate   # running average of feedback scores
        self.total_runs = total_runs       # number of ratings received
        self.flagged = flagged             # times rejected by trust gate
        self.tasks_received = tasks_received
        self.tasks_completed = tasks_completed
        now = datetime.now(timezone.utc).isoformat()
        self.created_at = created_at or now
        self.updated_at = updated_at or now

    @property
    def confidence(self) -> float:
        """How much we trust the rating average (0-1). Ramps up with experience."""
        return min(self.total_runs / self.CONFIDENCE_RAMP, 1.0)

    @property
    def completion_rate(self) -> float:
        """Fraction of received tasks that were completed."""
        if self.tasks_received == 0:
            return 0.0
        return self.tasks_completed / self.tasks_received

    @property
    def trust_score(self) -> float:
        """Composite trust score factoring in rating, experience, and completion.

        trust = prior * (1 - confidence) + rating_avg * confidence
        Then boosted/penalized by completion rate if they have tasks.

        - 0 ratings: trust = 0.2 (unproven)
        - 5 ratings at 0.8 avg: trust ≈ 0.5
        - 10+ ratings at 0.8 avg: trust = 0.8
        """
        base = self.PRIOR_TRUST * (1 - self.confidence) + self.success_rate * self.confidence

        # Completion factor: penalize agents who don't deliver
        if self.tasks_received >= 3:
            completion_factor = 0.8 + 0.2 * self.completion_rate  # 0.8 to 1.0
            base *= completion_factor

        return round(max(0.0, min(1.0, base)), 4)

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "skill_md": self.skill_md,
            "success_rate": self.success_rate,
            "trust_score": self.trust_score,
            "total_runs": self.total_runs,
            "flagged": self.flagged,
            "tasks_received": self.tasks_received,
            "tasks_completed": self.tasks_completed,
            "completion_rate": round(self.completion_rate, 4),
            "confidence": round(self.confidence, 4),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Agent":
        return cls(
            agent_id=data["agent_id"],
            agent_name=data["agent_name"],
            skill_md=data.get("skill_md", ""),
            success_rate=data.get("success_rate", 0.5),
            total_runs=data.get("total_runs", 0),
            flagged=data.get("flagged", 0),
            tasks_received=data.get("tasks_received", 0),
            tasks_completed=data.get("tasks_completed", 0),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    def __repr__(self):
        return (f"Agent(id={self.agent_id!r}, name={self.agent_name!r}, "
                f"success_rate={self.success_rate}, total_runs={self.total_runs})")


class Task:
    """A delegated task from one agent to another."""

    def __init__(self, task_id: str, requester_id: str, provider_id: str,
                 description: str, payload: str = None,
                 status: str = "pending",
                 result: str = None,
                 rating: float = None, rated_by: str = None,
                 rated_at: str = None,
                 trust_before: float = None, trust_after: float = None,
                 created_at: str = None, updated_at: str = None):
        self.task_id = task_id
        self.requester_id = requester_id
        self.provider_id = provider_id
        self.description = description
        self.payload = payload  # actual work content for the provider
        self.status = status  # pending, completed, rated
        self.result = result
        self.rating = rating          # 0.0-1.0 score given by requester
        self.rated_by = rated_by      # agent_id of who rated
        self.rated_at = rated_at      # ISO timestamp of rating
        self.trust_before = trust_before  # provider trust before this rating
        self.trust_after = trust_after    # provider trust after this rating
        now = datetime.now(timezone.utc).isoformat()
        self.created_at = created_at or now
        self.updated_at = updated_at or now

    def to_dict(self) -> dict:
        d = {
            "task_id": self.task_id,
            "requester_id": self.requester_id,
            "provider_id": self.provider_id,
            "description": self.description,
            "status": self.status,
            "result": self.result,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self.payload is not None:
            d["payload"] = self.payload
        if self.rating is not None:
            d["rating"] = self.rating
        if self.rated_by is not None:
            d["rated_by"] = self.rated_by
        if self.rated_at is not None:
            d["rated_at"] = self.rated_at
        if self.trust_before is not None:
            d["trust_before"] = self.trust_before
        if self.trust_after is not None:
            d["trust_after"] = self.trust_after
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        return cls(
            task_id=data["task_id"],
            requester_id=data["requester_id"],
            provider_id=data["provider_id"],
            description=data["description"],
            payload=data.get("payload"),
            status=data.get("status", "pending"),
            result=data.get("result"),
            rating=data.get("rating"),
            rated_by=data.get("rated_by"),
            rated_at=data.get("rated_at"),
            trust_before=data.get("trust_before"),
            trust_after=data.get("trust_after"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


class Interaction:
    """Record of a single agent-to-agent interaction.

    Maps to the full flow:
    Discovery → Trust Gate → Delegation → Outcome → Feedback → Registry Update
    """

    def __init__(self, round_num: int, requester_agent_id: str,
                 provider_agent_id: str, task: str,
                 discovery_candidates: int = 0,
                 gate_passed: bool = True,
                 gate_rejected: list = None,
                 outcome: bool = None,
                 feedback_score: float = None,
                 trust_before: float = 0.0, trust_after: float = 0.0):
        self.round_num = round_num
        self.requester_agent_id = requester_agent_id
        self.provider_agent_id = provider_agent_id
        self.task = task
        self.discovery_candidates = discovery_candidates
        self.gate_passed = gate_passed
        self.gate_rejected = gate_rejected or []
        self.outcome = outcome
        self.feedback_score = feedback_score
        self.trust_before = trust_before
        self.trust_after = trust_after

    def to_dict(self) -> dict:
        return {
            "round": self.round_num,
            "requester": self.requester_agent_id,
            "provider": self.provider_agent_id,
            "task": self.task,
            "discovery_candidates": self.discovery_candidates,
            "gate_passed": self.gate_passed,
            "gate_rejected": self.gate_rejected,
            "outcome": self.outcome,
            "feedback_score": self.feedback_score,
            "trust_before": self.trust_before,
            "trust_after": self.trust_after,
        }
