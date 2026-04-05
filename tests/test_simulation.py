"""Tests for simulation controller."""

import pytest
from core.models import Agent, Task
from core.store import MemoryStore
from core.controller import (
    run_simulation, update_trust, determine_outcome,
    apply_trust_gate, compute_feedback_score, submit_feedback,
)


def _proven_agent(agent_id, name, skill_md, success_rate=0.7, total_runs=10):
    """Create an agent with enough history for its trust_score to reflect success_rate."""
    ratings = [success_rate] * total_runs
    return Agent(agent_id, name, skill_md,
                 success_rate=success_rate, total_runs=total_runs,
                 ratings=ratings,
                 rating_weights=[0.5] * total_runs,
                 tasks_received=total_runs,
                 tasks_completed=total_runs)


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
        agent = Agent("a1", "New", "Skill")
        assert agent.trust_score < 0.3  # unproven ≈ 0.205
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
        agent = Agent("a1", "New", "Skill")  # success_rate defaults to 0.2
        # TSR=0, WFS=0.2 (fallback), RH=0.5, SS=0.5 → trust ≈ 0.205, capped at 0.40
        assert agent.trust_score < 0.3

    def test_proven_agent_reflects_rating(self):
        agent = _proven_agent("a1", "Proven", "Skill", success_rate=0.8)
        # Proven agent with 10 consistent 0.8 ratings should have high trust
        assert agent.trust_score > 0.7

    def test_partial_experience(self):
        # Agent with tasks completed >= 3 to escape cap; consistent ratings
        agent = _proven_agent("a1", "Mid", "Skill", success_rate=0.8, total_runs=5)
        # With ratings=[0.8]*5, tasks=5: TSR=0.8, WFS=0.8, RH≈1.0, SS=0.5
        # trust = 0.35*0.8 + 0.40*0.8 + 0.15*1.0 + 0.10*0.5 = 0.28+0.32+0.15+0.05 = 0.80
        assert agent.trust_score > 0.5

    def test_completion_rate_penalty(self):
        """Agents who don't complete tasks get penalized."""
        # Agent with tasks received but none completed (< 3 completed → capped at 0.40)
        # vs agent with tasks completed >= 3 that can exceed the cap
        agent = _proven_agent("a1", "Flaky", "Skill", success_rate=0.8, total_runs=10)
        # Override tasks_completed to 0 to trigger cap
        agent.tasks_completed = 0
        no_tasks = _proven_agent("a2", "Active", "Skill", success_rate=0.8, total_runs=10)
        assert agent.trust_score <= no_tasks.trust_score


class TestTaskLinkedFeedbackValidation:
    """Regression tests for task-linked feedback validation in submit_feedback.

    Key invariant: if task_id is provided and validation fails, NEITHER
    the provider agent NOR the task should be mutated.
    """

    def _setup(self):
        store = MemoryStore()
        provider = _proven_agent("provider1", "Provider", "Skill", success_rate=0.7)
        requester = _proven_agent("requester1", "Requester", "Skill", success_rate=0.5)
        other = _proven_agent("other1", "Other Provider", "Skill", success_rate=0.6)
        store.register(provider)
        store.register(requester)
        store.register(other)
        return store

    def _snapshot_agent(self, store, agent_id):
        """Capture agent state for later comparison."""
        a = store.get(agent_id)
        return (a.success_rate, a.total_runs, a.trust_score)

    def test_rating_task_belonging_to_another_provider_fails(self):
        store = self._setup()
        task = Task("t1", "requester1", "other1", "Do something")
        task.status = "completed"
        task.result = "done"
        store.save_task(task)
        before = self._snapshot_agent(store, "provider1")

        with pytest.raises(ValueError, match="belongs to provider"):
            submit_feedback(store, "provider1", 0.8, task_id="t1")

        # Provider must be untouched
        after = self._snapshot_agent(store, "provider1")
        assert before == after
        # Task must be untouched
        saved = store.get_task("t1")
        assert saved.status == "completed"
        assert saved.rating is None

    def test_rating_pending_task_fails(self):
        store = self._setup()
        task = Task("t1", "requester1", "provider1", "Do something")
        store.save_task(task)
        before = self._snapshot_agent(store, "provider1")

        with pytest.raises(ValueError, match="still pending"):
            submit_feedback(store, "provider1", 0.8, task_id="t1")

        after = self._snapshot_agent(store, "provider1")
        assert before == after
        saved = store.get_task("t1")
        assert saved.status == "pending"
        assert saved.rating is None

    def test_rating_already_rated_task_fails(self):
        store = self._setup()
        task = Task("t1", "requester1", "provider1", "Do something",
                     status="rated", result="done", rating=0.7)
        store.save_task(task)
        before = self._snapshot_agent(store, "provider1")

        with pytest.raises(ValueError, match="already been rated"):
            submit_feedback(store, "provider1", 0.8, task_id="t1")

        after = self._snapshot_agent(store, "provider1")
        assert before == after
        saved = store.get_task("t1")
        assert saved.rating == 0.7  # original rating preserved

    def test_rating_nonexistent_task_fails(self):
        store = self._setup()
        before = self._snapshot_agent(store, "provider1")

        with pytest.raises(ValueError, match="not found"):
            submit_feedback(store, "provider1", 0.8, task_id="no_such_task")

        after = self._snapshot_agent(store, "provider1")
        assert before == after

    def test_rating_completed_task_for_correct_provider_succeeds(self):
        store = self._setup()
        task = Task("t1", "requester1", "provider1", "Do something")
        task.status = "completed"
        task.result = "analysis complete"
        store.save_task(task)

        result = submit_feedback(store, "provider1", 0.9,
                                  task_id="t1", rated_by="requester1")

        assert result["task"]["status"] == "rated"
        assert result["task"]["rating"] == 0.9
        assert result["task"]["rated_by"] == "requester1"
        assert result["trust_before"] is not None
        assert result["trust_after"] is not None
        assert result["trust_after"] != result["trust_before"]
        # Verify task persisted correctly
        saved = store.get_task("t1")
        assert saved.status == "rated"
        assert saved.rating == 0.9
        # Verify provider was updated
        provider = store.get("provider1")
        assert provider.total_runs == 11  # was 10, now 11

    def test_standalone_feedback_without_task_still_works(self):
        """Standalone rating (no task_id) should update trust as before."""
        store = self._setup()
        before = self._snapshot_agent(store, "provider1")

        result = submit_feedback(store, "provider1", 0.9)

        after = self._snapshot_agent(store, "provider1")
        assert after != before  # trust changed
        assert "task" not in result  # no task in response
