"""Tests verifying all PRD v2.1 success criteria."""
import json
import os
import tempfile
import unittest

from trust_layer.schemas import (
    AgentProfile,
    Candidate,
    Task,
    ScoringConfig,
    ConfigError,
    DEFAULT_CONFIG,
)
from trust_layer.scoring_engine import ScoringEngine
from trust_layer.reputation_store import ReputationStore
from trust_layer.controller import TrustController


class TestScoringEngine(unittest.TestCase):
    def setUp(self):
        self.engine = ScoringEngine()

    def test_relevancy_exact_match(self):
        """PRD §8: agent_gpt4 matches 5/5 keywords = 1.00"""
        text = "Solar and wind energy are clean, sustainable sources that reduce carbon emissions."
        keywords = ["solar", "wind", "sustainable", "carbon", "clean"]
        self.assertEqual(self.engine.compute_relevancy(text, keywords), 1.0)

    def test_relevancy_no_match(self):
        """PRD §8: agent_claude matches 0/5 = 0.00"""
        text = "Renewable energy offers many environmental and economic benefits."
        keywords = ["solar", "wind", "sustainable", "carbon", "clean"]
        self.assertEqual(self.engine.compute_relevancy(text, keywords), 0.0)

    def test_relevancy_partial_match(self):
        """PRD §8: agent_llama matches 4/5 = 0.80"""
        text = "Wind and solar power are sustainable and help reduce carbon output."
        keywords = ["solar", "wind", "sustainable", "carbon", "clean"]
        self.assertEqual(self.engine.compute_relevancy(text, keywords), 0.8)

    def test_whole_word_matching(self):
        """PRD criterion #8: 'solar' must not match 'solarize' or 'parasolar'."""
        keywords = ["solar"]
        self.assertEqual(self.engine.compute_relevancy("solarize panels", keywords), 0.0)
        self.assertEqual(self.engine.compute_relevancy("parasolar shield", keywords), 0.0)
        self.assertEqual(self.engine.compute_relevancy("solar energy", keywords), 1.0)

    def test_empty_keywords_neutral(self):
        self.assertEqual(self.engine.compute_relevancy("any text", []), 0.5)

    def test_trust_score_computation(self):
        """PRD §8: agent_gpt4 trust = 0.6*0.80 + 0.4*1.00 = 0.8800"""
        self.assertEqual(self.engine.compute_trust_score(0.80, 1.00), 0.8800)
        self.assertEqual(self.engine.compute_trust_score(0.50, 0.80), 0.6200)
        self.assertEqual(self.engine.compute_trust_score(0.65, 0.00), 0.3900)


class TestReputationStore(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "reputation.json")
        self.store = ReputationStore(path=self.path)

    def test_get_nonexistent_returns_none(self):
        self.assertIsNone(self.store.get("nonexistent"))

    def test_upsert_and_get(self):
        profile = AgentProfile.default("test_agent")
        self.store.upsert(profile)
        loaded = self.store.get("test_agent")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.agent_id, "test_agent")
        self.assertEqual(loaded.success_rate, 0.5)

    def test_persistence_across_instances(self):
        """PRD criterion #4: reputation persists across process restarts."""
        profile = AgentProfile.default("agent_x")
        profile.success_rate = 0.75
        self.store.upsert(profile)

        new_store = ReputationStore(path=self.path)
        loaded = new_store.get("agent_x")
        self.assertEqual(loaded.success_rate, 0.75)


class TestTrustController(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "reputation.json")
        self.store = ReputationStore(path=self.path)
        self.engine = ScoringEngine()

        # Seed PRD example profiles
        self.store.upsert(AgentProfile("agent_gpt4", "GPT-4", "1.0", 0.80, 10))
        self.store.upsert(AgentProfile("agent_claude", "Claude", "1.0", 0.65, 4))

    def _make_task_and_candidates(self):
        task = Task("task-001", "Summarize the benefits of renewable energy.",
                     ["solar", "wind", "sustainable", "carbon", "clean"])
        candidates = [
            Candidate("out-001", "task-001", "agent_gpt4",
                      "Solar and wind energy are clean, sustainable sources that reduce carbon emissions.", 1200),
            Candidate("out-002", "task-001", "agent_claude",
                      "Renewable energy offers many environmental and economic benefits.", 800),
            Candidate("out-003", "task-001", "agent_llama",
                      "Wind and solar power are sustainable and help reduce carbon output.", 2000),
        ]
        return task, candidates

    def test_end_to_end_prd_example(self):
        """PRD criteria #1, #2, #3: full loop, correct scores, deterministic winner."""
        task, candidates = self._make_task_and_candidates()
        ctrl = TrustController(self.store, self.engine)
        result = ctrl.run_task(task, candidates)

        self.assertEqual(result.winner_agent_id, "agent_gpt4")
        self.assertEqual(result.winner_score, 0.8800)
        self.assertTrue(result.outcome)

        # Verify ranking order
        self.assertEqual(result.ranking[0]["agent_id"], "agent_gpt4")
        self.assertEqual(result.ranking[1]["agent_id"], "agent_llama")
        self.assertEqual(result.ranking[2]["agent_id"], "agent_claude")

    def test_deterministic_winner(self):
        """PRD criterion #3: same input always produces same winner."""
        task, candidates = self._make_task_and_candidates()
        results = []
        for _ in range(3):
            # Reset store each time
            store = ReputationStore(path=os.path.join(self.tmpdir, "rep_det.json"))
            store.upsert(AgentProfile("agent_gpt4", "GPT-4", "1.0", 0.80, 10))
            store.upsert(AgentProfile("agent_claude", "Claude", "1.0", 0.65, 4))
            ctrl = TrustController(store, self.engine)
            results.append(ctrl.run_task(task, candidates).winner_agent_id)
        self.assertEqual(len(set(results)), 1)

    def test_default_profile_for_unknown_agent(self):
        """PRD criterion #5: new agent gets default profile."""
        task, candidates = self._make_task_and_candidates()
        ctrl = TrustController(self.store, self.engine)
        ctrl.run_task(task, candidates)

        llama = self.store.get("agent_llama")
        self.assertIsNotNone(llama)

    def test_reputation_update(self):
        """PRD §8: winner reputation updates correctly."""
        task, candidates = self._make_task_and_candidates()
        ctrl = TrustController(self.store, self.engine)
        ctrl.run_task(task, candidates)

        gpt4 = self.store.get("agent_gpt4")
        self.assertAlmostEqual(gpt4.success_rate, 0.818182, places=5)
        self.assertEqual(gpt4.total_runs, 11)

    def test_tie_break_deterministic(self):
        """PRD criterion #7: ties broken by total_runs then agent_id."""
        store = ReputationStore(path=os.path.join(self.tmpdir, "rep_tie.json"))
        store.upsert(AgentProfile("agent_a", "A", "1.0", 0.5, 5))
        store.upsert(AgentProfile("agent_b", "B", "1.0", 0.5, 5))

        task = Task("t1", "test", ["keyword"])
        candidates = [
            Candidate("o1", "t1", "agent_a", "keyword here", 0),
            Candidate("o2", "t1", "agent_b", "keyword here", 0),
        ]
        ctrl = TrustController(store, self.engine)
        result = ctrl.run_task(task, candidates)
        # Same scores, same total_runs → lower agent_id wins
        self.assertEqual(result.winner_agent_id, "agent_a")

    def test_minimum_candidates_validation(self):
        task = Task("t1", "test", ["kw"])
        candidates = [Candidate("o1", "t1", "agent_a", "text", 0)]
        ctrl = TrustController(self.store, self.engine)
        with self.assertRaises(ValueError):
            ctrl.run_task(task, candidates)

    def test_duplicate_agent_id_validation(self):
        task = Task("t1", "test", ["kw"])
        candidates = [
            Candidate("o1", "t1", "agent_a", "text", 0),
            Candidate("o2", "t1", "agent_a", "other text", 0),
        ]
        ctrl = TrustController(self.store, self.engine)
        with self.assertRaises(ValueError):
            ctrl.run_task(task, candidates)


class TestConfigValidation(unittest.TestCase):
    def test_valid_config(self):
        config = ScoringConfig.from_dict({"w_reputation": 0.6, "w_relevancy": 0.4})
        self.assertEqual(config.w_reputation, 0.6)

    def test_invalid_config_raises(self):
        """PRD criterion #9: bad weights raise ConfigError."""
        with self.assertRaises(ConfigError):
            ScoringConfig.from_dict({"w_reputation": 0.7, "w_relevancy": 0.5})


if __name__ == "__main__":
    unittest.main()
