"""Tests for MemoryStore."""

import pytest
from core.models import Agent
from core.store import MemoryStore


def _make_agent(agent_id="a1", name="Test", skill="I do things."):
    return Agent(agent_id, name, skill)


class TestRegister:
    def test_register_new_agent(self):
        store = MemoryStore()
        agent = _make_agent()
        store.register(agent)
        assert store.get("a1").agent_id == "a1"

    def test_register_duplicate_raises(self):
        store = MemoryStore()
        store.register(_make_agent())
        with pytest.raises(ValueError, match="already registered"):
            store.register(_make_agent())

    def test_register_multiple(self):
        store = MemoryStore()
        store.register(_make_agent("a1", "Agent 1", "Skill 1"))
        store.register(_make_agent("a2", "Agent 2", "Skill 2"))
        assert len(store.list_all()) == 2


class TestGet:
    def test_get_existing(self):
        store = MemoryStore()
        store.register(_make_agent())
        assert store.get("a1") is not None

    def test_get_missing_returns_none(self):
        store = MemoryStore()
        assert store.get("nonexistent") is None


class TestDiscover:
    def test_discover_by_keyword(self):
        store = MemoryStore()
        store.register(Agent("a1", "Summarizer", "I summarize legal documents."))
        store.register(Agent("a2", "Coder", "I write code."))
        results = store.discover("legal")
        assert len(results) == 1
        assert results[0].agent_id == "a1"

    def test_discover_case_insensitive(self):
        store = MemoryStore()
        store.register(Agent("a1", "Test", "I do DATA analysis."))
        results = store.discover("data")
        assert len(results) == 1

    def test_discover_with_min_trust(self):
        store = MemoryStore()
        a1 = Agent("a1", "Good", "I do things.", success_rate=0.8)
        a2 = Agent("a2", "Bad", "I do things too.", success_rate=0.3)
        store.register(a1)
        store.register(a2)
        results = store.discover("things", min_trust=0.5)
        assert len(results) == 1
        assert results[0].agent_id == "a1"

    def test_discover_no_match(self):
        store = MemoryStore()
        store.register(Agent("a1", "Test", "I do code."))
        results = store.discover("cooking")
        assert len(results) == 0

    def test_discover_sorted_by_trust(self):
        store = MemoryStore()
        store.register(Agent("a1", "Low", "I analyze data.", success_rate=0.3))
        store.register(Agent("a2", "High", "I analyze data.", success_rate=0.9))
        results = store.discover("analyze")
        assert results[0].agent_id == "a2"


class TestUpsert:
    def test_upsert_updates_existing(self):
        store = MemoryStore()
        store.register(_make_agent())
        agent = store.get("a1")
        agent.success_rate = 0.9
        store.upsert(agent)
        assert store.get("a1").success_rate == 0.9


class TestReset:
    def test_reset_clears_all(self):
        store = MemoryStore()
        store.register(_make_agent())
        store.reset()
        assert store.is_empty()


class TestIsEmpty:
    def test_empty_on_init(self):
        assert MemoryStore().is_empty()

    def test_not_empty_after_register(self):
        store = MemoryStore()
        store.register(_make_agent())
        assert not store.is_empty()
