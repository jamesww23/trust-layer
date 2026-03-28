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
        i = Interaction(1, "req", "prov", True, 0.5, 0.6)
        d = i.to_dict()
        assert d["round"] == 1
        assert d["requester"] == "req"
        assert d["provider"] == "prov"
        assert d["outcome"] is True
        assert d["trust_before"] == 0.5
        assert d["trust_after"] == 0.6
