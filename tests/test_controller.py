"""Tests for TrustController — full loop, tie-break, validation."""

import sys
import os
import io
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from controller import TrustController
from scoring import ScoringEngine
from store import ReputationStore
from models import AgentProfile, Candidate, Task, ScoringConfig, ConfigError
from utils import TrustLogger


def _quiet_logger():
    """Logger that writes to a buffer instead of stdout."""
    return TrustLogger(stream=io.StringIO())


class TestEndToEnd(unittest.TestCase):
    """Verify the PRD §8 example end-to-end."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "rep.json")
        self.store = ReputationStore(path=self.path)
        self.engine = ScoringEngine()

        # Seed PRD example profiles
        self.store.upsert(AgentProfile("agent_gpt4", "GPT-4", "1.0", 0.80, 10))
        self.store.upsert(AgentProfile("agent_claude", "Claude", "1.0", 0.65, 4))

        self.task = Task(
            "task-001",
            "Summarize the benefits of renewable energy.",
            ["solar", "wind", "sustainable", "carbon", "clean"],
        )
        self.candidates = [
            Candidate("out-001", "task-001", "agent_gpt4",
                      "Solar and wind energy are clean, sustainable sources that reduce carbon emissions.", 1200),
            Candidate("out-002", "task-001", "agent_claude",
                      "Renewable energy offers many environmental and economic benefits.", 800),
            Candidate("out-003", "task-001", "agent_llama",
                      "Wind and solar power are sustainable and help reduce carbon output.", 2000),
        ]

    def test_winner_is_agent_gpt4(self):
        ctrl = TrustController(self.store, self.engine, logger=_quiet_logger())
        result = ctrl.run_task(self.task, self.candidates)
        self.assertEqual(result.winner_agent_id, "agent_gpt4")

    def test_winner_score_matches_prd(self):
        ctrl = TrustController(self.store, self.engine, logger=_quiet_logger())
        result = ctrl.run_task(self.task, self.candidates)
        self.assertEqual(result.winner_score, 0.8800)

    def test_ranking_order(self):
        ctrl = TrustController(self.store, self.engine, logger=_quiet_logger())
        result = ctrl.run_task(self.task, self.candidates)
        ids = [r["agent_id"] for r in result.ranking]
        self.assertEqual(ids, ["agent_gpt4", "agent_llama", "agent_claude"])

    def test_outcome_auto_detected_true(self):
        ctrl = TrustController(self.store, self.engine, logger=_quiet_logger())
        result = ctrl.run_task(self.task, self.candidates)
        self.assertTrue(result.outcome)

    def test_reputation_updated_correctly(self):
        ctrl = TrustController(self.store, self.engine, logger=_quiet_logger())
        ctrl.run_task(self.task, self.candidates)
        gpt4 = self.store.get("agent_gpt4")
        self.assertAlmostEqual(gpt4.success_rate, 0.818182, places=5)
        self.assertEqual(gpt4.total_runs, 11)

    def test_unknown_agent_gets_default_profile(self):
        ctrl = TrustController(self.store, self.engine, logger=_quiet_logger())
        ctrl.run_task(self.task, self.candidates)
        llama = self.store.get("agent_llama")
        self.assertIsNotNone(llama)

    def test_losers_not_updated(self):
        ctrl = TrustController(self.store, self.engine, logger=_quiet_logger())
        ctrl.run_task(self.task, self.candidates)
        claude = self.store.get("agent_claude")
        self.assertEqual(claude.success_rate, 0.65)
        self.assertEqual(claude.total_runs, 4)


class TestDeterminism(unittest.TestCase):
    def test_same_input_same_winner(self):
        """Run 3 times with identical inputs. Winner must be identical every time."""
        engine = ScoringEngine()
        task = Task("t1", "test", ["solar", "wind"])
        candidates = [
            Candidate("o1", "t1", "a1", "solar and wind", 0),
            Candidate("o2", "t1", "a2", "nothing here", 0),
        ]
        results = []
        for _ in range(3):
            tmpdir = tempfile.mkdtemp()
            store = ReputationStore(path=os.path.join(tmpdir, "r.json"))
            store.upsert(AgentProfile("a1", "A1", "1.0", 0.7, 5))
            store.upsert(AgentProfile("a2", "A2", "1.0", 0.7, 5))
            ctrl = TrustController(store, engine, logger=_quiet_logger())
            results.append(ctrl.run_task(task, candidates).winner_agent_id)
        self.assertEqual(len(set(results)), 1)


class TestTieBreak(unittest.TestCase):
    def test_tie_prefers_higher_total_runs(self):
        tmpdir = tempfile.mkdtemp()
        store = ReputationStore(path=os.path.join(tmpdir, "r.json"))
        store.upsert(AgentProfile("agent_a", "A", "1.0", 0.5, 3))
        store.upsert(AgentProfile("agent_b", "B", "1.0", 0.5, 10))

        task = Task("t1", "test", ["keyword"])
        candidates = [
            Candidate("o1", "t1", "agent_a", "keyword here", 0),
            Candidate("o2", "t1", "agent_b", "keyword here", 0),
        ]
        ctrl = TrustController(store, ScoringEngine(), logger=_quiet_logger())
        result = ctrl.run_task(task, candidates)
        self.assertEqual(result.winner_agent_id, "agent_b")

    def test_tie_prefers_lower_agent_id_when_runs_equal(self):
        tmpdir = tempfile.mkdtemp()
        store = ReputationStore(path=os.path.join(tmpdir, "r.json"))
        store.upsert(AgentProfile("agent_a", "A", "1.0", 0.5, 5))
        store.upsert(AgentProfile("agent_b", "B", "1.0", 0.5, 5))

        task = Task("t1", "test", ["keyword"])
        candidates = [
            Candidate("o1", "t1", "agent_a", "keyword here", 0),
            Candidate("o2", "t1", "agent_b", "keyword here", 0),
        ]
        ctrl = TrustController(store, ScoringEngine(), logger=_quiet_logger())
        result = ctrl.run_task(task, candidates)
        self.assertEqual(result.winner_agent_id, "agent_a")


class TestValidation(unittest.TestCase):
    def _make_ctrl(self):
        tmpdir = tempfile.mkdtemp()
        store = ReputationStore(path=os.path.join(tmpdir, "r.json"))
        return TrustController(store, ScoringEngine(), logger=_quiet_logger())

    def test_min_2_candidates(self):
        ctrl = self._make_ctrl()
        task = Task("t1", "test", ["kw"])
        with self.assertRaises(ValueError):
            ctrl.run_task(task, [Candidate("o1", "t1", "a1", "text", 0)])

    def test_duplicate_agent_id_rejected(self):
        ctrl = self._make_ctrl()
        task = Task("t1", "test", ["kw"])
        candidates = [
            Candidate("o1", "t1", "a1", "text one", 0),
            Candidate("o2", "t1", "a1", "text two", 0),
        ]
        with self.assertRaises(ValueError):
            ctrl.run_task(task, candidates)

    def test_mismatched_task_id_rejected(self):
        ctrl = self._make_ctrl()
        task = Task("t1", "test", ["kw"])
        candidates = [
            Candidate("o1", "t1", "a1", "text one", 0),
            Candidate("o2", "t2", "a2", "text two", 0),  # wrong task_id
        ]
        with self.assertRaises(ValueError):
            ctrl.run_task(task, candidates)

    def test_empty_task_id_rejected(self):
        ctrl = self._make_ctrl()
        with self.assertRaises(ValueError):
            ctrl.run_task(
                Task("", "test", ["kw"]),
                [Candidate("o1", "", "a1", "t", 0), Candidate("o2", "", "a2", "t", 0)],
            )

    def test_empty_prompt_rejected(self):
        ctrl = self._make_ctrl()
        with self.assertRaises(ValueError):
            ctrl.run_task(
                Task("t1", "", ["kw"]),
                [Candidate("o1", "t1", "a1", "t", 0), Candidate("o2", "t1", "a2", "t", 0)],
            )


class TestOutcome(unittest.TestCase):
    def test_explicit_outcome_overrides_auto(self):
        tmpdir = tempfile.mkdtemp()
        store = ReputationStore(path=os.path.join(tmpdir, "r.json"))
        task = Task("t1", "test", ["kw"])
        candidates = [
            Candidate("o1", "t1", "a1", "kw", 0),  # only 1 word, auto=False
            Candidate("o2", "t1", "a2", "no match here text", 0),
        ]
        ctrl = TrustController(store, ScoringEngine(), logger=_quiet_logger())
        result = ctrl.run_task(task, candidates, outcome=True)
        self.assertTrue(result.outcome)

    def test_auto_outcome_false_for_short_text(self):
        tmpdir = tempfile.mkdtemp()
        store = ReputationStore(path=os.path.join(tmpdir, "r.json"))
        task = Task("t1", "test", ["kw"])
        candidates = [
            Candidate("o1", "t1", "a1", "kw", 0),        # 1 word
            Candidate("o2", "t1", "a2", "no match", 0),   # 2 words
        ]
        ctrl = TrustController(store, ScoringEngine(), logger=_quiet_logger())
        result = ctrl.run_task(task, candidates)
        self.assertFalse(result.outcome)


class TestConfigValidation(unittest.TestCase):
    def test_valid_config(self):
        c = ScoringConfig.from_dict({"w_reputation": 0.6, "w_relevancy": 0.4})
        self.assertEqual(c.w_reputation, 0.6)

    def test_invalid_weights_raise(self):
        with self.assertRaises(ConfigError):
            ScoringConfig.from_dict({"w_reputation": 0.7, "w_relevancy": 0.5})


class TestLogSections(unittest.TestCase):
    """Verify all 6 required log sections are emitted."""

    def test_all_sections_present(self):
        tmpdir = tempfile.mkdtemp()
        store = ReputationStore(path=os.path.join(tmpdir, "r.json"))
        store.upsert(AgentProfile("a1", "A1", "1.0", 0.8, 10))
        store.upsert(AgentProfile("a2", "A2", "1.0", 0.6, 4))

        buf = io.StringIO()
        logger = TrustLogger(stream=buf)
        ctrl = TrustController(store, ScoringEngine(), logger=logger)

        task = Task("t1", "test", ["solar"])
        candidates = [
            Candidate("o1", "t1", "a1", "solar power", 0),
            Candidate("o2", "t1", "a2", "nothing", 0),
        ]
        ctrl.run_task(task, candidates)

        output = buf.getvalue()
        for section in ["[CONFIG]", "[LOAD]", "[SCORE]", "[RANK]", "[SELECT]", "[UPDATE]", "[PERSIST]"]:
            self.assertIn(section, output, f"Missing log section: {section}")


if __name__ == "__main__":
    unittest.main()
