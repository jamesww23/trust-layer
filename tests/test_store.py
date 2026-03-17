"""Tests for ReputationStore (MemoryStore implementation)."""

import pytest
from core.models import AgentProfile
from core.store import MemoryStore


class TestMemoryStoreGet:
    def test_get_existing_agent(self, memory_store):
        profile = memory_store.get("agent_alpha")
        assert profile.agent_id == "agent_alpha"
        assert profile.success_rate == 0.8
        assert profile.total_runs == 10

    def test_get_missing_agent_creates_default(self):
        store = MemoryStore()
        profile = store.get("agent_unknown")
        assert profile.agent_id == "agent_unknown"
        assert profile.agent_name == "agent_unknown"
        assert profile.success_rate == 0.5
        assert profile.total_runs == 0

    def test_get_missing_agent_persists_default(self):
        store = MemoryStore()
        store.get("agent_new")
        # Second call should return the same default (now stored)
        profile = store.get("agent_new")
        assert profile.agent_id == "agent_new"
        assert profile.total_runs == 0


class TestMemoryStoreUpsert:
    def test_upsert_updates_existing(self, memory_store):
        profile = memory_store.get("agent_alpha")
        profile.success_rate = 0.9
        profile.total_runs = 11
        memory_store.upsert(profile)

        updated = memory_store.get("agent_alpha")
        assert updated.success_rate == 0.9
        assert updated.total_runs == 11

    def test_upsert_creates_new(self):
        store = MemoryStore()
        profile = AgentProfile(
            agent_id="agent_new",
            agent_name="New Agent",
            success_rate=0.75,
            total_runs=3,
        )
        store.upsert(profile)

        retrieved = store.get("agent_new")
        assert retrieved.success_rate == 0.75
        assert retrieved.total_runs == 3

    def test_upsert_sets_updated_at(self, memory_store):
        profile = memory_store.get("agent_alpha")
        old_updated = profile.updated_at
        profile.success_rate = 0.95
        memory_store.upsert(profile)
        assert memory_store.get("agent_alpha").updated_at >= old_updated


class TestMemoryStoreListAll:
    def test_list_all_returns_all(self, memory_store):
        profiles = memory_store.list_all()
        ids = {p.agent_id for p in profiles}
        assert ids == {"agent_alpha", "agent_beta"}

    def test_list_all_empty_store(self):
        store = MemoryStore()
        assert store.list_all() == []


class TestMemoryStoreReset:
    def test_reset_wipes_and_reseeds(self, memory_store):
        new_seed = {
            "agent_gamma": AgentProfile(
                agent_id="agent_gamma",
                agent_name="Gamma",
                success_rate=0.6,
                total_runs=2,
            ),
        }
        memory_store.reset(new_seed)
        profiles = memory_store.list_all()
        assert len(profiles) == 1
        assert profiles[0].agent_id == "agent_gamma"

    def test_reset_removes_previous_data(self, memory_store):
        memory_store.reset({})
        assert memory_store.list_all() == []
        assert memory_store.is_empty()


class TestMemoryStoreLookup:
    """Tests for read-only lookup that must NOT persist on cache miss."""

    def test_lookup_existing_agent_returns_profile(self, memory_store):
        profile = memory_store.lookup("agent_alpha")
        assert profile.agent_id == "agent_alpha"
        assert profile.success_rate == 0.8
        assert profile.total_runs == 10

    def test_lookup_missing_agent_returns_default(self):
        store = MemoryStore()
        profile = store.lookup("agent_unknown")
        assert profile.agent_id == "agent_unknown"
        assert profile.success_rate == 0.5
        assert profile.total_runs == 0

    def test_lookup_missing_agent_does_NOT_persist(self):
        """This is the critical invariant: lookup must not write to storage."""
        store = MemoryStore()
        store.lookup("agent_ghost")
        assert store.is_empty()
        assert store.list_all() == []

    def test_lookup_does_not_pollute_list_all(self, memory_store):
        """lookup of a missing agent must not appear in list_all."""
        before_count = len(memory_store.list_all())
        memory_store.lookup("agent_nonexistent")
        after_count = len(memory_store.list_all())
        assert after_count == before_count


class TestMemoryStoreIsEmpty:
    def test_empty_on_init(self):
        store = MemoryStore()
        assert store.is_empty()

    def test_not_empty_with_data(self, memory_store):
        assert not memory_store.is_empty()
