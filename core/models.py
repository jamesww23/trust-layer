"""Data models for Agentic Reputation Infrastructure Layer."""

from datetime import datetime, timezone


class Agent:
    """An agent registered in the reputation layer."""

    def __init__(self, agent_id: str, agent_name: str, skill_md: str,
                 success_rate: float = 0.5, total_runs: int = 0,
                 flagged: int = 0,
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
        self.success_rate = success_rate
        self.total_runs = total_runs
        self.flagged = flagged  # times rejected by trust gate
        now = datetime.now(timezone.utc).isoformat()
        self.created_at = created_at or now
        self.updated_at = updated_at or now

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "skill_md": self.skill_md,
            "success_rate": self.success_rate,
            "total_runs": self.total_runs,
            "flagged": self.flagged,
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
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    def __repr__(self):
        return (f"Agent(id={self.agent_id!r}, name={self.agent_name!r}, "
                f"success_rate={self.success_rate}, total_runs={self.total_runs})")


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
