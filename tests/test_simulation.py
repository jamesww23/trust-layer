"""Tests for simulation controller."""

import pytest
from core.models import Agent
from core.store import MemoryStore
from core.controller import run_simulation, update_trust, determine_outcome


def _seeded_store():
    store = MemoryStore()
    store.register(Agent("a1", "Summarizer", "I summarize legal documents.", success_rate=0.5))
    store.register(Agent("a2", "Translator", "I translate text and code.", success_rate=0.5))
    store.register(Agent("a3", "Analyst", "I analyze data and finance.", success_rate=0.5))
    return store


class TestUpdateTrust:
    def test_success_increases_trust(self):
        agent = Agent("a1", "Test", "Skill", success_rate=0.5, total_runs=10)
        new_sr = update_trust(agent, True)
        assert new_sr > 0.5
        assert agent.total_runs == 11

    def test_failure_decreases_trust(self):
        agent = Agent("a1", "Test", "Skill", success_rate=0.5, total_runs=10)
        new_sr = update_trust(agent, False)
        assert new_sr < 0.5
        assert agent.total_runs == 11

    def test_first_run_success(self):
        agent = Agent("a1", "Test", "Skill", success_rate=0.5, total_runs=0)
        new_sr = update_trust(agent, True)
        assert new_sr == 1.0
        assert agent.total_runs == 1

    def test_first_run_failure(self):
        agent = Agent("a1", "Test", "Skill", success_rate=0.5, total_runs=0)
        new_sr = update_trust(agent, False)
        assert new_sr == 0.0
        assert agent.total_runs == 1

    def test_formula_correct(self):
        agent = Agent("a1", "Test", "Skill", success_rate=0.6, total_runs=5)
        update_trust(agent, True)
        expected = round((0.6 * 5 + 1.0) / 6, 4)
        assert agent.success_rate == expected


class TestDetermineOutcome:
    def test_returns_bool(self):
        agent = Agent("a1", "Test", "Skill", success_rate=0.5)
        result = determine_outcome(agent)
        assert isinstance(result, bool)

    def test_high_trust_more_likely_success(self):
        agent = Agent("a1", "Test", "Skill", success_rate=0.9)
        results = [determine_outcome(agent) for _ in range(100)]
        success_count = sum(results)
        assert success_count > 50  # should be ~90 successes

    def test_low_trust_more_likely_failure(self):
        agent = Agent("a1", "Test", "Skill", success_rate=0.1)
        results = [determine_outcome(agent) for _ in range(100)]
        success_count = sum(results)
        assert success_count < 50  # should be ~10 successes


class TestRunSimulation:
    def test_basic_simulation(self):
        store = _seeded_store()
        result = run_simulation(store, rounds=5)
        assert result["rounds"] == 5
        assert len(result["history"]) == 5
        assert len(result["final_agents"]) == 3

    def test_history_has_required_fields(self):
        store = _seeded_store()
        result = run_simulation(store, rounds=1)
        entry = result["history"][0]
        assert "round" in entry
        assert "requester" in entry
        assert "provider" in entry
        assert "outcome" in entry
        assert "trust_before" in entry
        assert "trust_after" in entry

    def test_trust_scores_change(self):
        store = _seeded_store()
        initial = {a.agent_id: a.success_rate for a in store.list_all()}
        run_simulation(store, rounds=10)
        final = {a.agent_id: a.success_rate for a in store.list_all()}
        changed = any(initial[aid] != final[aid] for aid in initial)
        assert changed

    def test_total_runs_increase(self):
        store = _seeded_store()
        run_simulation(store, rounds=5)
        total = sum(a.total_runs for a in store.list_all())
        assert total == 5  # each round updates exactly one provider

    def test_final_agents_sorted_by_trust(self):
        store = _seeded_store()
        result = run_simulation(store, rounds=10)
        scores = [a["success_rate"] for a in result["final_agents"]]
        assert scores == sorted(scores, reverse=True)

    def test_too_few_agents_raises(self):
        store = MemoryStore()
        store.register(Agent("a1", "Solo", "I am alone."))
        with pytest.raises(ValueError, match="At least 2"):
            run_simulation(store, rounds=1)

    def test_many_rounds(self):
        store = _seeded_store()
        result = run_simulation(store, rounds=50)
        assert len(result["history"]) == 50

    def test_requester_not_provider(self):
        store = _seeded_store()
        result = run_simulation(store, rounds=20)
        for entry in result["history"]:
            assert entry["requester"] != entry["provider"]
