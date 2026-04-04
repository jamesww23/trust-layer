"""Tests for seed data loading."""

from core.fixtures import load_seed_agents, seed_store
from core.store import MemoryStore


class TestLoadSeedAgents:
    def test_loads_agents(self):
        agents = load_seed_agents()
        assert len(agents) == 12

    def test_agents_have_required_fields(self):
        for agent in load_seed_agents():
            assert agent.agent_id
            assert agent.agent_name
            assert agent.skill_md
            assert agent.success_rate == 0.5
            assert agent.total_runs == 0

    def test_unique_agent_ids(self):
        agents = load_seed_agents()
        ids = [a.agent_id for a in agents]
        assert len(ids) == len(set(ids))


class TestSeedStore:
    def test_seeds_empty_store(self):
        store = MemoryStore()
        seed_store(store)
        assert len(store.list_all()) == 12

    def test_does_not_overwrite_existing(self):
        store = MemoryStore()
        seed_store(store)
        # Modify an agent
        agent = store.get("agent_summarizer")
        agent.success_rate = 0.9
        store.upsert(agent)
        # Seed again — should not overwrite
        seed_store(store)
        assert store.get("agent_summarizer").success_rate == 0.9
