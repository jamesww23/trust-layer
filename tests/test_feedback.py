"""Tests for human outcome feedback / override logic."""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import AgentProfile, RunRecord
from core.store import MemoryStore
from core.controller import apply_feedback


def _make_store_and_run(original_outcome=True, sr=0.85, runs=20):
    """Create a store with a winner profile and a matching RunRecord."""
    # After the original run, the winner was updated:
    # new_sr = (sr * runs + outcome) / (runs + 1)
    outcome_val = 1.0 if original_outcome else 0.0
    post_sr = round((sr * runs + outcome_val) / (runs + 1), 4)
    post_runs = runs + 1

    store = MemoryStore({
        "agent_winner": AgentProfile(
            "agent_winner", "Winner",
            success_rate=post_sr, total_runs=post_runs),
        "agent_loser": AgentProfile(
            "agent_loser", "Loser",
            success_rate=0.5, total_runs=5),
    })

    record = RunRecord(
        run_id="run_fb_001",
        task={"task_id": "t1", "prompt": "test", "expected_keywords": []},
        candidates=[],
        result={
            "task_id": "t1",
            "winner_agent_id": "agent_winner",
            "winner_score": 0.9,
            "ranking": [],
            "explanation": "test",
            "outcome": original_outcome,
        },
        logs=[],
        profiles_before=[{"agent_id": "agent_winner", "success_rate": sr, "total_runs": runs}],
        profiles_after=[{"agent_id": "agent_winner", "success_rate": post_sr, "total_runs": post_runs}],
        source="demo",
    )
    store.save_run(record)
    return store, record


class TestApplyFeedback:
    def test_override_true_to_false_decreases_sr(self):
        store, record = _make_store_and_run(original_outcome=True, sr=0.85, runs=20)
        before_sr = store.lookup("agent_winner").success_rate

        updated = apply_feedback(store, record, new_outcome=False)
        after_sr = store.lookup("agent_winner").success_rate

        assert after_sr < before_sr
        assert updated.result["outcome"] is False
        assert updated.feedback_override is not None
        assert updated.feedback_override["original_outcome"] is True
        assert updated.feedback_override["new_outcome"] is False

    def test_override_false_to_true_increases_sr(self):
        store, record = _make_store_and_run(original_outcome=False, sr=0.85, runs=20)
        before_sr = store.lookup("agent_winner").success_rate

        updated = apply_feedback(store, record, new_outcome=True)
        after_sr = store.lookup("agent_winner").success_rate

        assert after_sr > before_sr
        assert updated.result["outcome"] is True

    def test_same_outcome_is_noop(self):
        store, record = _make_store_and_run(original_outcome=True)
        before_sr = store.lookup("agent_winner").success_rate

        updated = apply_feedback(store, record, new_outcome=True)
        after_sr = store.lookup("agent_winner").success_rate

        assert after_sr == before_sr
        assert updated.feedback_override is None

    def test_feedback_override_timestamp_set(self):
        store, record = _make_store_and_run(original_outcome=True)
        updated = apply_feedback(store, record, new_outcome=False)
        assert "overridden_at" in updated.feedback_override

    def test_loser_profile_unchanged(self):
        store, record = _make_store_and_run(original_outcome=True)
        loser_before = store.lookup("agent_loser").success_rate

        apply_feedback(store, record, new_outcome=False)
        loser_after = store.lookup("agent_loser").success_rate

        assert loser_after == loser_before

    def test_run_record_updated_in_store(self):
        store, record = _make_store_and_run(original_outcome=True)
        apply_feedback(store, record, new_outcome=False)

        stored = store.get_run("run_fb_001")
        assert stored.result["outcome"] is False
        assert stored.feedback_override is not None

    def test_math_correctness(self):
        """Verify the math: if sr=0.8, runs=10, won with True (sr became ~0.8182, runs=11),
        then override to False should adjust by -1/11."""
        store, record = _make_store_and_run(original_outcome=True, sr=0.8, runs=10)
        # Post-run: sr = (0.8*10 + 1.0)/11 = 9.0/11 = 0.8182
        profile = store.lookup("agent_winner")
        assert profile.total_runs == 11

        apply_feedback(store, record, new_outcome=False)
        profile = store.lookup("agent_winner")
        # adjusted = (0.8182*11 - 1.0 + 0.0)/11 = 8.0/11 = 0.7273
        expected = round((0.8 * 10 + 0.0) / 11, 4)
        assert profile.success_rate == expected
