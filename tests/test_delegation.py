"""Tests for delegation validation: trust gate + self-delegation.

Under the 4-signal formula:
    trust = 0.35×TSR + 0.40×WFS + 0.15×RH + 0.10×SS

New agent (no tasks, no ratings):
    TSR=0.0, WFS=0.2, RH=0.5, SS=0.5
    trust ≈ 0.205  →  below 30% gate (blocked)

Proven good agent (10 tasks_received, ratings=[0.8]*10, tasks_completed=10):
    TSR=10/10=1.0 (all good), WFS=0.8, RH≈1.0, SS=0.5
    trust ≈ 0.35×1.0 + 0.40×0.8 + 0.15×1.0 + 0.10×0.5 = 0.875

Bad quality agent (10 tasks, ratings=[0.1]*10):
    TSR=0 (none rated >=0.5), WFS=0.1, RH≈1.0, SS=0.5
    trust ≈ 0 + 0.04 + 0.15 + 0.05 = 0.24  →  below gate (blocked)
"""

import pytest
from core.models import Agent
from core.store import MemoryStore
from core.controller import validate_delegation, DEFAULT_TRUST_THRESHOLD


def _agent_with_ratings(agent_id, name, skill, ratings, tasks_received=None,
                         tasks_completed=None, weights=None):
    """Helper: build an agent with an explicit ratings list."""
    tr = tasks_received if tasks_received is not None else len(ratings)
    tc = tasks_completed if tasks_completed is not None else len(ratings)
    return Agent(
        agent_id=agent_id,
        agent_name=name,
        skill_md=skill,
        ratings=ratings,
        rating_weights=weights or [0.5] * len(ratings),
        tasks_received=tr,
        tasks_completed=tc,
    )


class TestSelfDelegation:
    def test_self_delegation_rejected(self):
        store = MemoryStore()
        a = _agent_with_ratings("a1", "Agent1", "I do things.",
                                ratings=[0.9] * 10)
        store.register(a)
        with pytest.raises(ValueError, match="Self-delegation"):
            validate_delegation(store, "a1", "a1")

    def test_self_delegation_rejected_regardless_of_trust(self):
        store = MemoryStore()
        a = _agent_with_ratings("a1", "Agent1", "I do things.",
                                ratings=[1.0] * 20)
        store.register(a)
        with pytest.raises(ValueError, match="Self-delegation"):
            validate_delegation(store, "a1", "a1")


class TestTrustGateInDelegation:
    def test_low_quality_provider_rejected(self):
        """Agent that always delivers bad work stays below gate."""
        store = MemoryStore()
        req = _agent_with_ratings("req", "Requester", "I ask.", ratings=[0.9] * 10)
        # 10 tasks received, all rated 0.1 (bad quality) — TSR=0, WFS=0.1
        prov = _agent_with_ratings("prov", "Provider", "I help.",
                                   ratings=[0.1] * 10)
        store.register(req)
        store.register(prov)
        with pytest.raises(ValueError, match="below the minimum threshold"):
            validate_delegation(store, "req", "prov")

    def test_high_trust_provider_accepted(self):
        """Agent with consistently good ratings passes gate."""
        store = MemoryStore()
        req = _agent_with_ratings("req", "Requester", "I ask.", ratings=[0.9] * 10)
        prov = _agent_with_ratings("prov", "Provider", "I help.", ratings=[0.9] * 10)
        store.register(req)
        store.register(prov)
        validate_delegation(store, "req", "prov")  # should not raise

    def test_unproven_agent_rejected(self):
        """New agent with no tasks or ratings is blocked (trust ≈ 0.205)."""
        store = MemoryStore()
        req = _agent_with_ratings("req", "Requester", "I ask.", ratings=[0.9] * 10)
        new_agent = Agent("prov", "NewAgent", "I'm new.")
        store.register(req)
        store.register(new_agent)
        with pytest.raises(ValueError, match="below the minimum threshold"):
            validate_delegation(store, "req", "prov")

    def test_provider_not_found(self):
        store = MemoryStore()
        req = _agent_with_ratings("req", "Requester", "I ask.", ratings=[0.9] * 10)
        store.register(req)
        with pytest.raises(ValueError, match="not found"):
            validate_delegation(store, "req", "nonexistent")

    def test_custom_threshold_low(self):
        """Agent with moderate ratings passes a low custom threshold."""
        store = MemoryStore()
        req = _agent_with_ratings("req", "Requester", "I ask.", ratings=[0.9] * 10)
        # Moderate agent: ratings=[0.6]*10 — some tasks good, trust moderate
        prov = _agent_with_ratings("prov", "Provider", "I help.", ratings=[0.6] * 10)
        store.register(req)
        store.register(prov)
        validate_delegation(store, "req", "prov", threshold=0.1)  # very low threshold

    def test_custom_threshold_high_blocks_moderate_agent(self):
        """A high threshold blocks a moderate agent."""
        store = MemoryStore()
        req = _agent_with_ratings("req", "Requester", "I ask.", ratings=[0.9] * 10)
        prov = _agent_with_ratings("prov", "Provider", "I help.", ratings=[0.6] * 10)
        store.register(req)
        store.register(prov)
        with pytest.raises(ValueError, match="below the minimum threshold"):
            validate_delegation(store, "req", "prov", threshold=0.95)


class TestValidDelegationStillWorks:
    def test_valid_delegation_passes(self):
        store = MemoryStore()
        req = _agent_with_ratings("req", "Requester", "I ask.", ratings=[0.9] * 10)
        prov = _agent_with_ratings("prov", "Provider", "I help.", ratings=[0.8] * 10)
        store.register(req)
        store.register(prov)
        validate_delegation(store, "req", "prov")

    def test_valid_delegation_with_multiple_agents(self):
        store = MemoryStore()
        a1 = _agent_with_ratings("a1", "Agent1", "Code.", ratings=[0.8] * 10)
        a2 = _agent_with_ratings("a2", "Agent2", "Data.", ratings=[0.75] * 10)
        a3 = _agent_with_ratings("a3", "Agent3", "Research.", ratings=[0.7] * 10)
        for a in [a1, a2, a3]:
            store.register(a)
        validate_delegation(store, "a1", "a2")
        validate_delegation(store, "a2", "a3")
        validate_delegation(store, "a3", "a1")
