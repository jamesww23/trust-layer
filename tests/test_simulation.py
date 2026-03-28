"""Tests for simulation controller."""

import pytest
from core.models import Agent
from core.store import MemoryStore
from core.controller import (
    run_simulation, update_trust, determine_outcome,
    apply_trust_gate, compute_feedback_score, submit_feedback,
)


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


class TestTrustGate:
    def test_all_pass(self):
        agents = [
            Agent("a1", "A", "Skill", success_rate=0.5),
            Agent("a2", "B", "Skill", success_rate=0.8),
        ]
        passed, rejected = apply_trust_gate(agents, 0.3)
        assert len(passed) == 2
        assert len(rejected) == 0

    def test_some_rejected(self):
        agents = [
            Agent("a1", "A", "Skill", success_rate=0.2),
            Agent("a2", "B", "Skill", success_rate=0.8),
        ]
        passed, rejected = apply_trust_gate(agents, 0.3)
        assert len(passed) == 1
        assert passed[0].agent_id == "a2"
        assert len(rejected) == 1
        assert rejected[0].agent_id == "a1"

    def test_all_rejected(self):
        agents = [
            Agent("a1", "A", "Skill", success_rate=0.1),
            Agent("a2", "B", "Skill", success_rate=0.2),
        ]
        passed, rejected = apply_trust_gate(agents, 0.5)
        assert len(passed) == 0
        assert len(rejected) == 2

    def test_threshold_boundary(self):
        agents = [Agent("a1", "A", "Skill", success_rate=0.3)]
        passed, rejected = apply_trust_gate(agents, 0.3)
        assert len(passed) == 1  # exactly at threshold passes


class TestComputeFeedback:
    def test_success_feedback_positive(self):
        agent = Agent("a1", "Test", "Skill", success_rate=0.8)
        scores = [compute_feedback_score(True, agent) for _ in range(50)]
        avg = sum(scores) / len(scores)
        assert avg > 0.5

    def test_failure_feedback_lower(self):
        agent = Agent("a1", "Test", "Skill", success_rate=0.5)
        success_scores = [compute_feedback_score(True, agent) for _ in range(50)]
        failure_scores = [compute_feedback_score(False, agent) for _ in range(50)]
        assert sum(success_scores) / len(success_scores) > sum(failure_scores) / len(failure_scores)

    def test_feedback_in_range(self):
        agent = Agent("a1", "Test", "Skill", success_rate=0.5)
        for _ in range(100):
            score = compute_feedback_score(True, agent)
            assert 0.0 <= score <= 1.0
            score = compute_feedback_score(False, agent)
            assert 0.0 <= score <= 1.0


class TestSubmitFeedback:
    def test_positive_feedback_raises_trust(self):
        store = MemoryStore()
        store.register(Agent("a1", "Test", "Skill", success_rate=0.5))
        result = submit_feedback(store, "a1", 1.0)
        assert result["success_rate"] > 0.5

    def test_negative_feedback_lowers_trust(self):
        store = MemoryStore()
        store.register(Agent("a1", "Test", "Skill", success_rate=0.5))
        result = submit_feedback(store, "a1", 0.0)
        assert result["success_rate"] < 0.5

    def test_invalid_score_rejected(self):
        store = MemoryStore()
        store.register(Agent("a1", "Test", "Skill"))
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            submit_feedback(store, "a1", 1.5)

    def test_unknown_agent_rejected(self):
        store = MemoryStore()
        with pytest.raises(ValueError, match="not found"):
            submit_feedback(store, "nonexistent", 0.5)


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
        assert "task" in entry
        assert "outcome" in entry
        assert "trust_before" in entry
        assert "trust_after" in entry
        # New 6-component fields
        assert "discovery_candidates" in entry
        assert "gate_passed" in entry
        assert "gate_rejected" in entry
        assert "feedback_score" in entry

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
        # Each round either delegates (1 provider run) or rejects all (0 runs)
        assert total <= 5
        assert total > 0

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
            if entry["gate_passed"]:
                assert entry["requester"] != entry["provider"]

    def test_trust_threshold_in_result(self):
        store = _seeded_store()
        result = run_simulation(store, rounds=5, trust_threshold=0.4)
        assert result["trust_threshold"] == 0.4

    def test_high_threshold_causes_rejections(self):
        store = MemoryStore()
        store.register(Agent("a1", "Low", "I summarize.", success_rate=0.2))
        store.register(Agent("a2", "High", "I summarize.", success_rate=0.8))
        result = run_simulation(store, rounds=10, trust_threshold=0.5)
        # a1 should get flagged since it's below 0.5 threshold
        final = {a["agent_id"]: a for a in result["final_agents"]}
        # At least some rejections should have occurred
        any_rejected = any(len(h.get("gate_rejected", [])) > 0 for h in result["history"])
        assert any_rejected

    def test_flagged_count_tracks_rejections(self):
        store = MemoryStore()
        store.register(Agent("a1", "Low", "I code and translate.", success_rate=0.1))
        store.register(Agent("a2", "High", "I code and translate.", success_rate=0.9))
        run_simulation(store, rounds=20, trust_threshold=0.5)
        a1 = store.get("a1")
        assert a1.flagged > 0  # should have been rejected multiple times
