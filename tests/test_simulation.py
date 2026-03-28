"""Tests for simulation controller."""

import pytest
from core.models import Agent
from core.store import MemoryStore
from core.controller import (
    run_simulation, update_trust, determine_outcome,
    apply_trust_gate, compute_feedback_score, submit_feedback,
)


def _proven_agent(agent_id, name, skill_md, success_rate=0.5, total_runs=10):
    """Create an agent with enough history for its trust_score to reflect success_rate."""
    return Agent(agent_id, name, skill_md,
                 success_rate=success_rate, total_runs=total_runs)


def _seeded_store():
    store = MemoryStore()
    store.register(_proven_agent("a1", "Summarizer", "I summarize legal documents."))
    store.register(_proven_agent("a2", "Translator", "I translate text and code."))
    store.register(_proven_agent("a3", "Analyst", "I analyze data and finance."))
    return store


class TestUpdateTrust:
    def test_high_feedback_increases_trust(self):
        agent = _proven_agent("a1", "Test", "Skill", success_rate=0.5)
        new_sr = update_trust(agent, 0.9)
        assert new_sr > 0.5
        assert agent.total_runs == 11

    def test_low_feedback_decreases_trust(self):
        agent = _proven_agent("a1", "Test", "Skill", success_rate=0.5)
        new_sr = update_trust(agent, 0.1)
        assert new_sr < 0.5
        assert agent.total_runs == 11

    def test_first_run_perfect_feedback(self):
        agent = Agent("a1", "Test", "Skill", success_rate=0.5, total_runs=0)
        new_sr = update_trust(agent, 1.0)
        assert new_sr == 1.0
        assert agent.total_runs == 1

    def test_first_run_zero_feedback(self):
        agent = Agent("a1", "Test", "Skill", success_rate=0.5, total_runs=0)
        new_sr = update_trust(agent, 0.0)
        assert new_sr == 0.0
        assert agent.total_runs == 1

    def test_formula_correct(self):
        agent = Agent("a1", "Test", "Skill", success_rate=0.6, total_runs=5)
        update_trust(agent, 0.8)
        expected = round((0.6 * 5 + 0.8) / 6, 4)
        assert agent.success_rate == expected

    def test_fractional_feedback_produces_fractional_trust(self):
        agent = Agent("a1", "Test", "Skill", success_rate=0.5, total_runs=4)
        update_trust(agent, 0.7)
        expected = round((0.5 * 4 + 0.7) / 5, 4)
        assert agent.success_rate == expected


class TestDetermineOutcome:
    def test_returns_bool(self):
        agent = _proven_agent("a1", "Test", "Skill", success_rate=0.5)
        result = determine_outcome(agent)
        assert isinstance(result, bool)

    def test_high_trust_more_likely_success(self):
        agent = _proven_agent("a1", "Test", "Skill", success_rate=0.9)
        results = [determine_outcome(agent) for _ in range(100)]
        success_count = sum(results)
        assert success_count > 50  # should be ~90 successes

    def test_low_trust_more_likely_failure(self):
        agent = _proven_agent("a1", "Test", "Skill", success_rate=0.1)
        results = [determine_outcome(agent) for _ in range(100)]
        success_count = sum(results)
        assert success_count < 50  # should be ~10 successes


class TestTrustGate:
    def test_all_pass(self):
        agents = [
            _proven_agent("a1", "A", "Skill", success_rate=0.5),
            _proven_agent("a2", "B", "Skill", success_rate=0.8),
        ]
        passed, rejected = apply_trust_gate(agents, 0.3)
        assert len(passed) == 2
        assert len(rejected) == 0

    def test_some_rejected(self):
        agents = [
            _proven_agent("a1", "A", "Skill", success_rate=0.2),
            _proven_agent("a2", "B", "Skill", success_rate=0.8),
        ]
        passed, rejected = apply_trust_gate(agents, 0.3)
        assert len(passed) == 1
        assert passed[0].agent_id == "a2"
        assert len(rejected) == 1
        assert rejected[0].agent_id == "a1"

    def test_all_rejected(self):
        agents = [
            _proven_agent("a1", "A", "Skill", success_rate=0.1),
            _proven_agent("a2", "B", "Skill", success_rate=0.2),
        ]
        passed, rejected = apply_trust_gate(agents, 0.5)
        assert len(passed) == 0
        assert len(rejected) == 2

    def test_threshold_boundary(self):
        agents = [_proven_agent("a1", "A", "Skill", success_rate=0.3)]
        passed, rejected = apply_trust_gate(agents, 0.3)
        assert len(passed) == 1  # exactly at threshold passes

    def test_new_agent_below_gate(self):
        """New agent with 0 tasks should have low trust_score and get gated."""
        agent = Agent("a1", "New", "Skill", success_rate=0.5, total_runs=0)
        assert agent.trust_score < 0.3  # unproven = 0.2
        passed, rejected = apply_trust_gate([agent], 0.3)
        assert len(passed) == 0
        assert len(rejected) == 1


class TestComputeFeedback:
    def test_success_feedback_positive(self):
        agent = _proven_agent("a1", "Test", "Skill", success_rate=0.8)
        scores = [compute_feedback_score(True, agent) for _ in range(50)]
        avg = sum(scores) / len(scores)
        assert avg > 0.5

    def test_failure_feedback_lower(self):
        agent = _proven_agent("a1", "Test", "Skill", success_rate=0.5)
        success_scores = [compute_feedback_score(True, agent) for _ in range(50)]
        failure_scores = [compute_feedback_score(False, agent) for _ in range(50)]
        assert sum(success_scores) / len(success_scores) > sum(failure_scores) / len(failure_scores)

    def test_feedback_in_range(self):
        agent = _proven_agent("a1", "Test", "Skill", success_rate=0.5)
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
        assert result["agent"]["success_rate"] > 0.5
        assert result["trust_after"] >= result["trust_before"]

    def test_negative_feedback_lowers_trust(self):
        store = MemoryStore()
        store.register(Agent("a1", "Test", "Skill", success_rate=0.5))
        result = submit_feedback(store, "a1", 0.0)
        assert result["agent"]["success_rate"] < 0.5
        assert result["trust_after"] <= result["trust_before"]

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
        assert "discovery_candidates" in entry
        assert "gate_passed" in entry
        assert "gate_rejected" in entry
        assert "feedback_score" in entry

    def test_trust_scores_change(self):
        store = _seeded_store()
        initial = {a.agent_id: a.trust_score for a in store.list_all()}
        run_simulation(store, rounds=10)
        final = {a.agent_id: a.trust_score for a in store.list_all()}
        changed = any(initial[aid] != final[aid] for aid in initial)
        assert changed

    def test_total_runs_increase(self):
        store = _seeded_store()
        initial_runs = sum(a.total_runs for a in store.list_all())
        run_simulation(store, rounds=5)
        final_runs = sum(a.total_runs for a in store.list_all())
        assert final_runs > initial_runs

    def test_final_agents_sorted_by_trust(self):
        store = _seeded_store()
        result = run_simulation(store, rounds=10)
        scores = [a["trust_score"] for a in result["final_agents"]]
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
        store.register(_proven_agent("a1", "Low", "I summarize.", success_rate=0.2))
        store.register(_proven_agent("a2", "High", "I summarize.", success_rate=0.8))
        result = run_simulation(store, rounds=10, trust_threshold=0.5)
        any_rejected = any(len(h.get("gate_rejected", [])) > 0 for h in result["history"])
        assert any_rejected

    def test_flagged_count_tracks_rejections(self):
        store = MemoryStore()
        store.register(_proven_agent("a1", "Low", "I code and translate.", success_rate=0.1))
        store.register(_proven_agent("a2", "High", "I code and translate.", success_rate=0.9))
        run_simulation(store, rounds=20, trust_threshold=0.5)
        a1 = store.get("a1")
        assert a1.flagged > 0

    def test_feedback_score_drives_trust_update(self):
        store = _seeded_store()
        result = run_simulation(store, rounds=20)
        for entry in result["history"]:
            if entry["gate_passed"] and entry["outcome"] is not None:
                fb = entry["feedback_score"]
                assert isinstance(fb, float)
                assert 0.0 <= fb <= 1.0
                if entry["outcome"]:
                    assert fb < 1.0 or fb > 0.0


class TestTrustScoreComposite:
    """Tests for the new composite trust scoring system."""

    def test_new_agent_has_low_trust(self):
        agent = Agent("a1", "New", "Skill", success_rate=0.5, total_runs=0)
        assert agent.trust_score == 0.2  # prior only

    def test_proven_agent_reflects_rating(self):
        agent = _proven_agent("a1", "Proven", "Skill", success_rate=0.8)
        assert agent.trust_score == 0.8  # fully confident

    def test_partial_experience(self):
        agent = Agent("a1", "Mid", "Skill", success_rate=0.8, total_runs=5)
        # confidence = 0.5, trust = 0.2 * 0.5 + 0.8 * 0.5 = 0.5
        assert agent.trust_score == 0.5

    def test_completion_rate_penalty(self):
        """Agents who don't complete tasks get penalized."""
        agent = Agent("a1", "Flaky", "Skill", success_rate=0.8, total_runs=10,
                      tasks_received=5, tasks_completed=0)
        no_tasks = Agent("a2", "Active", "Skill", success_rate=0.8, total_runs=10)
        assert agent.trust_score < no_tasks.trust_score
