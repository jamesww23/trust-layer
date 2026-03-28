"""Tests for RunRecord model and store run methods."""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import RunRecord, AgentProfile
from core.store import MemoryStore


def _sample_run(run_id="run_001", source="demo"):
    return RunRecord(
        run_id=run_id,
        task={"task_id": "t1", "prompt": "test", "expected_keywords": ["a"]},
        candidates=[{"output_id": "o1", "task_id": "t1", "agent_id": "a1", "output_text": "text"}],
        result={"task_id": "t1", "winner_agent_id": "a1", "winner_score": 0.8,
                "ranking": [], "explanation": "test", "outcome": True},
        logs=["[CONFIG] test"],
        profiles_before=[],
        profiles_after=[],
        source=source,
    )


class TestRunRecordModel:
    def test_to_dict_roundtrip(self):
        record = _sample_run()
        d = record.to_dict()
        restored = RunRecord.from_dict(d)
        assert restored.run_id == record.run_id
        assert restored.source == record.source
        assert restored.result == record.result
        assert restored.feedback_override is None

    def test_feedback_override_persists(self):
        record = _sample_run()
        record.feedback_override = {"original_outcome": True, "new_outcome": False}
        d = record.to_dict()
        restored = RunRecord.from_dict(d)
        assert restored.feedback_override["new_outcome"] is False

    def test_created_at_auto_set(self):
        record = _sample_run()
        assert record.created_at is not None


class TestMemoryStoreRuns:
    def test_save_and_get_run(self):
        store = MemoryStore()
        record = _sample_run("run_abc")
        store.save_run(record)
        retrieved = store.get_run("run_abc")
        assert retrieved is not None
        assert retrieved.run_id == "run_abc"

    def test_get_missing_run_returns_none(self):
        store = MemoryStore()
        assert store.get_run("nonexistent") is None

    def test_list_runs_newest_first(self):
        store = MemoryStore()
        store.save_run(_sample_run("run_1"))
        store.save_run(_sample_run("run_2"))
        store.save_run(_sample_run("run_3"))
        runs = store.list_runs()
        assert [r.run_id for r in runs] == ["run_3", "run_2", "run_1"]

    def test_list_runs_with_limit(self):
        store = MemoryStore()
        for i in range(10):
            store.save_run(_sample_run(f"run_{i}"))
        runs = store.list_runs(limit=3)
        assert len(runs) == 3

    def test_list_runs_with_offset(self):
        store = MemoryStore()
        store.save_run(_sample_run("run_1"))
        store.save_run(_sample_run("run_2"))
        store.save_run(_sample_run("run_3"))
        runs = store.list_runs(limit=10, offset=1)
        assert len(runs) == 2
        assert runs[0].run_id == "run_2"

    def test_update_run(self):
        store = MemoryStore()
        record = _sample_run("run_upd")
        store.save_run(record)
        record.feedback_override = {"new_outcome": False}
        store.update_run(record)
        updated = store.get_run("run_upd")
        assert updated.feedback_override is not None

    def test_clear_runs(self):
        store = MemoryStore()
        store.save_run(_sample_run("run_1"))
        store.save_run(_sample_run("run_2"))
        store.clear_runs()
        assert store.list_runs() == []
        assert store.get_run("run_1") is None

    def test_clear_runs_does_not_affect_profiles(self):
        store = MemoryStore({"agent_a": AgentProfile("agent_a", "A")})
        store.save_run(_sample_run("run_1"))
        store.clear_runs()
        assert len(store.list_all()) == 1
        assert store.list_runs() == []


class TestResetClearsAllState:
    """Regression: reset must clear tasks and submissions, not just profiles/runs."""

    def test_reset_clears_stored_tasks(self):
        store = MemoryStore({"agent_a": AgentProfile("agent_a", "A")})
        store.store_task("task_ext_1", {"prompt": "test", "keywords": []})
        store.store_task("task_ext_2", {"prompt": "test2", "keywords": []})

        store.reset({"agent_a": AgentProfile("agent_a", "A")})
        store.clear_runs()
        store.clear_all_tasks()

        assert store.get_task("task_ext_1") is None
        assert store.get_task("task_ext_2") is None

    def test_reset_clears_queued_submissions(self):
        store = MemoryStore({"agent_a": AgentProfile("agent_a", "A")})
        store.queue_submission("task_1", {"agent_id": "bot1", "output_text": "hello"})
        store.queue_submission("task_1", {"agent_id": "bot2", "output_text": "world"})
        store.queue_submission("task_2", {"agent_id": "bot3", "output_text": "foo"})

        store.clear_all_tasks()

        assert store.get_submissions("task_1") == []
        assert store.get_submissions("task_2") == []

    def test_clear_all_tasks_does_not_affect_profiles_or_runs(self):
        store = MemoryStore({"agent_a": AgentProfile("agent_a", "A")})
        store.save_run(_sample_run("run_1"))
        store.store_task("task_ext", {"prompt": "test"})

        store.clear_all_tasks()

        assert len(store.list_all()) == 1
        assert store.get_run("run_1") is not None
        assert store.get_task("task_ext") is None

    def test_full_reset_sequence_clears_everything(self):
        """Simulate exact reset flow: reset profiles + clear_runs + clear_all_tasks."""
        store = MemoryStore({"agent_a": AgentProfile("agent_a", "A", success_rate=0.9, total_runs=50)})
        store.save_run(_sample_run("run_1"))
        store.store_task("task_ext", {"prompt": "test"})
        store.queue_submission("task_ext", {"agent_id": "bot", "output_text": "hi"})

        seed = {"agent_a": AgentProfile("agent_a", "A", success_rate=0.5, total_runs=0)}
        store.reset(seed)
        store.clear_runs()
        store.clear_all_tasks()

        # Profiles reset to seed
        assert store.lookup("agent_a").success_rate == 0.5
        assert store.lookup("agent_a").total_runs == 0
        # Runs cleared
        assert store.list_runs() == []
        # Tasks and queues cleared
        assert store.get_task("task_ext") is None
        assert store.get_submissions("task_ext") == []
