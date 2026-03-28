"""Tests for data models."""

import pytest
from core.models import Agent, Interaction


class TestAgent:
    def test_create_agent(self):
        a = Agent("a1", "Test Agent", "I do things.")
        assert a.agent_id == "a1"
        assert a.agent_name == "Test Agent"
        assert a.skill_md == "I do things."
        assert a.success_rate == 0.5
        assert a.total_runs == 0

    def test_to_dict(self):
        a = Agent("a1", "Test", "Skills here.")
        d = a.to_dict()
        assert d["agent_id"] == "a1"
        assert d["skill_md"] == "Skills here."
        assert "created_at" in d

    def test_from_dict(self):
        d = {"agent_id": "a1", "agent_name": "Test", "skill_md": "Skills.",
             "success_rate": 0.7, "total_runs": 5}
        a = Agent.from_dict(d)
        assert a.success_rate == 0.7
        assert a.total_runs == 5

    def test_empty_agent_id_rejected(self):
        with pytest.raises(ValueError, match="agent_id"):
            Agent("", "Name", "Skill")

    def test_empty_agent_name_rejected(self):
        with pytest.raises(ValueError, match="agent_name"):
            Agent("a1", "", "Skill")

    def test_empty_skill_md_rejected(self):
        with pytest.raises(ValueError, match="skill_md"):
            Agent("a1", "Name", "")


class TestInteraction:
    def test_to_dict(self):
        i = Interaction(
            round_num=1, requester_agent_id="req",
            provider_agent_id="prov", task="Summarize a doc",
            outcome=True, trust_before=0.5, trust_after=0.6,
        )
        d = i.to_dict()
        assert d["round"] == 1
        assert d["requester"] == "req"
        assert d["provider"] == "prov"
        assert d["task"] == "Summarize a doc"
        assert d["outcome"] is True
        assert d["trust_before"] == 0.5
        assert d["trust_after"] == 0.6

    def test_gate_fields(self):
        i = Interaction(
            round_num=1, requester_agent_id="req",
            provider_agent_id="prov", task="Test task",
            discovery_candidates=5, gate_passed=False,
            gate_rejected=["a1", "a2"], feedback_score=0.8,
        )
        d = i.to_dict()
        assert d["discovery_candidates"] == 5
        assert d["gate_passed"] is False
        assert d["gate_rejected"] == ["a1", "a2"]
        assert d["feedback_score"] == 0.8

    def test_flagged_default(self):
        a = Agent("a1", "Test", "Skill")
        assert a.flagged == 0

    def test_flagged_in_dict(self):
        a = Agent("a1", "Test", "Skill", flagged=3)
        d = a.to_dict()
        assert d["flagged"] == 3
