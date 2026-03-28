"""Regression tests for delegation validation: trust gate + self-delegation."""

import pytest
from core.models import Agent
from core.store import MemoryStore
from core.controller import validate_delegation, DEFAULT_TRUST_THRESHOLD


class TestSelfDelegation:
    """Self-delegation must be rejected."""

    def test_self_delegation_rejected(self):
        store = MemoryStore()
        store.register(Agent("a1", "Agent1", "I do things.", success_rate=0.9, total_runs=10))
        with pytest.raises(ValueError, match="Self-delegation"):
            validate_delegation(store, "a1", "a1")

    def test_self_delegation_rejected_regardless_of_trust(self):
        store = MemoryStore()
        store.register(Agent("a1", "Agent1", "I do things.", success_rate=1.0, total_runs=100))
        with pytest.raises(ValueError, match="Self-delegation"):
            validate_delegation(store, "a1", "a1")


class TestTrustGateInDelegation:
    """Provider must pass the trust gate to receive a delegation."""

    def test_low_trust_provider_rejected(self):
        store = MemoryStore()
        store.register(Agent("req", "Requester", "I ask.", success_rate=0.9, total_runs=10))
        store.register(Agent("prov", "Provider", "I help.", success_rate=0.1, total_runs=10))
        with pytest.raises(ValueError, match="below the minimum threshold"):
            validate_delegation(store, "req", "prov")

    def test_high_trust_provider_accepted(self):
        store = MemoryStore()
        store.register(Agent("req", "Requester", "I ask.", success_rate=0.9, total_runs=10))
        store.register(Agent("prov", "Provider", "I help.", success_rate=0.8, total_runs=10))
        # Should not raise
        validate_delegation(store, "req", "prov")

    def test_provider_exactly_at_threshold_accepted(self):
        """Provider at exactly the threshold should pass."""
        store = MemoryStore()
        store.register(Agent("req", "Requester", "I ask.", success_rate=0.9, total_runs=10))
        # With total_runs=10, confidence=1.0, so trust_score = success_rate
        store.register(Agent("prov", "Provider", "I help.",
                             success_rate=DEFAULT_TRUST_THRESHOLD, total_runs=10))
        validate_delegation(store, "req", "prov")

    def test_unproven_agent_rejected(self):
        """A new agent with 0 tasks has trust 0.2 (below default 0.3 threshold)."""
        store = MemoryStore()
        store.register(Agent("req", "Requester", "I ask.", success_rate=0.9, total_runs=10))
        store.register(Agent("prov", "NewAgent", "I'm new."))
        with pytest.raises(ValueError, match="below the minimum threshold"):
            validate_delegation(store, "req", "prov")

    def test_custom_threshold(self):
        store = MemoryStore()
        store.register(Agent("req", "Requester", "I ask.", success_rate=0.9, total_runs=10))
        store.register(Agent("prov", "Provider", "I help.", success_rate=0.5, total_runs=10))
        # Should pass at 0.5 threshold
        validate_delegation(store, "req", "prov", threshold=0.5)
        # Should fail at 0.6 threshold
        with pytest.raises(ValueError, match="below the minimum threshold"):
            validate_delegation(store, "req", "prov", threshold=0.6)

    def test_provider_not_found(self):
        store = MemoryStore()
        store.register(Agent("req", "Requester", "I ask.", success_rate=0.9, total_runs=10))
        with pytest.raises(ValueError, match="not found"):
            validate_delegation(store, "req", "nonexistent")


class TestValidDelegationStillWorks:
    """Ensure valid delegations are not broken by the new checks."""

    def test_valid_delegation_passes(self):
        store = MemoryStore()
        store.register(Agent("req", "Requester", "I ask.", success_rate=0.9, total_runs=10))
        store.register(Agent("prov", "Provider", "I help.", success_rate=0.8, total_runs=10))
        # Should not raise
        validate_delegation(store, "req", "prov")

    def test_valid_delegation_with_different_agents(self):
        store = MemoryStore()
        store.register(Agent("a1", "Agent1", "Code.", success_rate=0.7, total_runs=10))
        store.register(Agent("a2", "Agent2", "Data.", success_rate=0.6, total_runs=10))
        store.register(Agent("a3", "Agent3", "Research.", success_rate=0.5, total_runs=10))
        validate_delegation(store, "a1", "a2")
        validate_delegation(store, "a2", "a3")
        validate_delegation(store, "a3", "a1")
