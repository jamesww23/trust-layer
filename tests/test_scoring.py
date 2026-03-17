"""Tests for ScoringEngine — relevancy and trust score computation."""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from scoring import ScoringEngine
from models import AgentProfile, Candidate, Task, ScoringConfig


class TestRelevancy(unittest.TestCase):
    def setUp(self):
        self.engine = ScoringEngine()
        self.keywords = ["solar", "wind", "sustainable", "carbon", "clean"]

    def test_full_match(self):
        """agent_gpt4: 5/5 keywords = 1.00"""
        text = "Solar and wind energy are clean, sustainable sources that reduce carbon emissions."
        self.assertEqual(self.engine.compute_relevancy(text, self.keywords), 1.0)

    def test_no_match(self):
        """agent_claude: 0/5 keywords = 0.00"""
        text = "Renewable energy offers many environmental and economic benefits."
        self.assertEqual(self.engine.compute_relevancy(text, self.keywords), 0.0)

    def test_partial_match(self):
        """agent_llama: 4/5 keywords = 0.80"""
        text = "Wind and solar power are sustainable and help reduce carbon output."
        self.assertEqual(self.engine.compute_relevancy(text, self.keywords), 0.8)

    def test_whole_word_no_substring(self):
        """'solar' must NOT match 'solarize' or 'parasolar'."""
        self.assertEqual(self.engine.compute_relevancy("solarize panels", ["solar"]), 0.0)
        self.assertEqual(self.engine.compute_relevancy("parasolar shield", ["solar"]), 0.0)

    def test_whole_word_positive(self):
        """'solar' MUST match 'solar energy'."""
        self.assertEqual(self.engine.compute_relevancy("solar energy", ["solar"]), 1.0)

    def test_empty_keywords_returns_neutral(self):
        """Empty keywords -> 0.5 (neutral)."""
        self.assertEqual(self.engine.compute_relevancy("anything here", []), 0.5)

    def test_case_insensitive(self):
        self.assertEqual(self.engine.compute_relevancy("SOLAR WIND", ["solar", "wind"]), 1.0)


class TestTrustScore(unittest.TestCase):
    def setUp(self):
        self.engine = ScoringEngine()

    def test_prd_agent_gpt4(self):
        """0.6*0.80 + 0.4*1.00 = 0.8800"""
        self.assertEqual(self.engine.compute_trust_score(0.80, 1.00), 0.8800)

    def test_prd_agent_llama(self):
        """0.6*0.50 + 0.4*0.80 = 0.6200"""
        self.assertEqual(self.engine.compute_trust_score(0.50, 0.80), 0.6200)

    def test_prd_agent_claude(self):
        """0.6*0.65 + 0.4*0.00 = 0.3900"""
        self.assertEqual(self.engine.compute_trust_score(0.65, 0.00), 0.3900)

    def test_clamped_to_unit(self):
        """Output stays in [0.0, 1.0] even with extreme inputs."""
        self.assertLessEqual(self.engine.compute_trust_score(1.0, 1.0), 1.0)
        self.assertGreaterEqual(self.engine.compute_trust_score(0.0, 0.0), 0.0)

    def test_custom_weights(self):
        """Custom weights: 0.3*0.80 + 0.7*1.00 = 0.94"""
        self.assertEqual(self.engine.compute_trust_score(0.80, 1.00, 0.3, 0.7), 0.94)


class TestFullScore(unittest.TestCase):
    def test_score_pipeline(self):
        """ScoringEngine.score() wires relevancy + trust_score correctly."""
        engine = ScoringEngine()
        task = Task("t1", "test", ["solar", "wind"])
        candidate = Candidate("o1", "t1", "a1", "solar and wind power", 100)
        profile = AgentProfile("a1", "Agent A", "1.0", 0.80, 10)

        sc = engine.score(candidate, task, profile)
        self.assertEqual(sc.relevancy, 1.0)
        self.assertEqual(sc.trust_score, 0.88)


if __name__ == "__main__":
    unittest.main()
