"""Tests for batch evaluation logic."""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import AgentProfile, Task, Candidate, ScoringConfig
from core.scoring import ScoringEngine
from core.controller import TrustController, build_run_record
from core.store import MemoryStore
from core.fixtures import list_scenarios, load_scenario


def _make_store():
    return MemoryStore({
        "agent_gpt4": AgentProfile("agent_gpt4", "GPT-4", success_rate=0.85, total_runs=20),
        "agent_claude": AgentProfile("agent_claude", "Claude", success_rate=0.78, total_runs=15),
        "agent_llama": AgentProfile("agent_llama", "LLaMA", success_rate=0.60, total_runs=10),
    })


class TestBatchEvaluation:
    def test_batch_all_scenarios(self):
        """Run all 4 scenarios sequentially, verify results."""
        store = _make_store()
        config = ScoringConfig()
        engine = ScoringEngine(config)
        results = []

        scenarios = list_scenarios()
        for s in scenarios:
            task, candidates = load_scenario(s["task_id"])
            controller = TrustController(store, engine, config)
            result = controller.run_task(task, candidates)
            record = build_run_record(task, candidates, result,
                                      controller.get_logs(), [], [], source="batch")
            store.save_run(record)
            results.append(result)

        assert len(results) == 4
        for r in results:
            assert r.winner_agent_id is not None

    def test_reputation_changes_across_runs(self):
        """Reputation should shift after each batch run."""
        store = _make_store()
        config = ScoringConfig()
        engine = ScoringEngine(config)

        initial_profiles = {p.agent_id: p.success_rate for p in store.list_all()}

        for s in list_scenarios():
            task, candidates = load_scenario(s["task_id"])
            controller = TrustController(store, engine, config)
            controller.run_task(task, candidates)

        final_profiles = {p.agent_id: p.success_rate for p in store.list_all()}

        # At least one agent's success_rate should have changed
        changed = any(
            initial_profiles.get(aid) != final_profiles.get(aid)
            for aid in final_profiles
        )
        assert changed

    def test_runs_persisted_to_history(self):
        """Each batch run should be saved to run history."""
        store = _make_store()
        config = ScoringConfig()
        engine = ScoringEngine(config)

        for s in list_scenarios():
            task, candidates = load_scenario(s["task_id"])
            controller = TrustController(store, engine, config)
            result = controller.run_task(task, candidates)
            record = build_run_record(task, candidates, result,
                                      controller.get_logs(), [], [], source="batch")
            store.save_run(record)

        runs = store.list_runs()
        assert len(runs) == 4
        for run in runs:
            assert run.source == "batch"

    def test_repeat_same_scenario(self):
        """Repeating the same scenario N times should produce N results."""
        store = _make_store()
        config = ScoringConfig()
        engine = ScoringEngine(config)

        task, candidates = load_scenario("task_renewable_energy")
        results = []
        for _ in range(3):
            controller = TrustController(store, engine, config)
            result = controller.run_task(task, candidates)
            results.append(result)

        assert len(results) == 3
        # Winner should be deterministic for same fixture
        assert all(r.winner_agent_id == results[0].winner_agent_id for r in results)

    def test_aggregate_stats_computation(self):
        """Verify win count aggregation works correctly."""
        store = _make_store()
        config = ScoringConfig()
        engine = ScoringEngine(config)

        win_counts = {}
        for s in list_scenarios():
            task, candidates = load_scenario(s["task_id"])
            controller = TrustController(store, engine, config)
            result = controller.run_task(task, candidates)
            win_counts[result.winner_agent_id] = win_counts.get(result.winner_agent_id, 0) + 1

        total_wins = sum(win_counts.values())
        assert total_wins == 4


class TestBuildRunRecord:
    def test_returns_run_record_with_id(self):
        task = Task("t1", "test prompt", ["a", "b"])
        candidates = [
            Candidate("o1", "t1", "a1", "text one here"),
            Candidate("o2", "t1", "a2", "text two here"),
        ]
        store = _make_store()
        config = ScoringConfig()
        engine = ScoringEngine(config)
        controller = TrustController(store, engine, config)
        result = controller.run_task(task, candidates)

        record = build_run_record(task, candidates, result,
                                  controller.get_logs(), [], [], source="test")
        assert record.run_id is not None
        assert len(record.run_id) == 12
        assert record.source == "test"
        assert record.result["winner_agent_id"] is not None
