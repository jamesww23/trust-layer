"""Tests for TrustController — full loop, tie-break, validation."""

import pytest
from core.models import AgentProfile, Task, Candidate, ScoringConfig
from core.scoring import ScoringEngine
from core.store import MemoryStore
from core.controller import TrustController


def make_controller(profiles: dict, config: ScoringConfig = None):
    """Helper to build a controller with a MemoryStore."""
    config = config or ScoringConfig(w_reputation=0.6, w_relevancy=0.4)
    store = MemoryStore(initial=profiles)
    engine = ScoringEngine(config)
    return TrustController(store, engine, config), store


class TestFullLoop:
    def test_deterministic_winner(self, sample_task, sample_candidates, seed_profiles):
        ctrl, store = make_controller(seed_profiles)
        result = ctrl.run_task(sample_task, sample_candidates)

        # agent_alpha has higher success_rate (0.8 vs 0.7) and both match same keywords
        assert result.winner_agent_id == "agent_alpha"
        assert result.winner_score > 0
        assert result.outcome is True  # output has >= 3 words
        assert len(result.ranking) == 2

    def test_winner_reputation_updated(self, sample_task, sample_candidates, seed_profiles):
        ctrl, store = make_controller(seed_profiles)
        result = ctrl.run_task(sample_task, sample_candidates)

        winner = store.get(result.winner_agent_id)
        # alpha: old_sr=0.8, old_runs=10, outcome=True(1.0)
        # new_sr = (0.8 * 10 + 1.0) / 11 = 9.0 / 11 = 0.8182
        assert winner.total_runs == 11
        assert abs(winner.success_rate - round((0.8 * 10 + 1.0) / 11, 4)) < 1e-4

    def test_loser_not_updated(self, sample_task, sample_candidates, seed_profiles):
        ctrl, store = make_controller(seed_profiles)
        ctrl.run_task(sample_task, sample_candidates)

        loser = store.get("agent_beta")
        assert loser.total_runs == 5  # unchanged
        assert loser.success_rate == 0.7  # unchanged

    def test_explicit_outcome_false(self, sample_task, sample_candidates, seed_profiles):
        ctrl, store = make_controller(seed_profiles)
        result = ctrl.run_task(sample_task, sample_candidates, outcome=False)

        assert result.outcome is False
        winner = store.get(result.winner_agent_id)
        # alpha: (0.8 * 10 + 0.0) / 11 = 8.0 / 11 ≈ 0.7273
        assert winner.total_runs == 11
        assert abs(winner.success_rate - round((0.8 * 10 + 0.0) / 11, 4)) < 1e-4

    def test_auto_outcome_short_text(self, seed_profiles):
        """Output with < 3 words → outcome=False."""
        task = Task(task_id="t1", prompt="Test.", expected_keywords=["test"])
        candidates = [
            Candidate(output_id="o1", task_id="t1", agent_id="agent_alpha",
                      output_text="Two words"),
            Candidate(output_id="o2", task_id="t1", agent_id="agent_beta",
                      output_text="Also two"),
        ]
        ctrl, _ = make_controller(seed_profiles)
        result = ctrl.run_task(task, candidates)
        assert result.outcome is False

    def test_logs_produced(self, sample_task, sample_candidates, seed_profiles):
        ctrl, _ = make_controller(seed_profiles)
        ctrl.run_task(sample_task, sample_candidates)
        logs = ctrl.get_logs()
        sections = {log.split("]")[0].strip("[") for log in logs}
        assert "CONFIG" in sections
        assert "LOAD" in sections
        assert "SCORE" in sections
        assert "RANK" in sections
        assert "SELECT" in sections
        assert "PERSIST" in sections


class TestTieBreak:
    def test_same_score_higher_runs_wins(self):
        """When trust_score ties, prefer higher total_runs."""
        profiles = {
            "agent_a": AgentProfile("agent_a", "A", success_rate=0.8, total_runs=20),
            "agent_b": AgentProfile("agent_b", "B", success_rate=0.8, total_runs=10),
        }
        task = Task(task_id="t1", prompt="Test", expected_keywords=["test"])
        candidates = [
            Candidate("o1", "t1", "agent_a", "Test output text here"),
            Candidate("o2", "t1", "agent_b", "Test output text here"),
        ]
        ctrl, _ = make_controller(profiles)
        result = ctrl.run_task(task, candidates)
        assert result.winner_agent_id == "agent_a"

    def test_same_score_same_runs_lexicographic(self):
        """When score and runs tie, prefer lexicographically lower agent_id."""
        profiles = {
            "agent_b": AgentProfile("agent_b", "B", success_rate=0.8, total_runs=10),
            "agent_a": AgentProfile("agent_a", "A", success_rate=0.8, total_runs=10),
        }
        task = Task(task_id="t1", prompt="Test", expected_keywords=["test"])
        candidates = [
            Candidate("o1", "t1", "agent_b", "Test output text here"),
            Candidate("o2", "t1", "agent_a", "Test output text here"),
        ]
        ctrl, _ = make_controller(profiles)
        result = ctrl.run_task(task, candidates)
        assert result.winner_agent_id == "agent_a"

    def test_deterministic_across_runs(self):
        """Same input must always produce same winner."""
        profiles = {
            "agent_x": AgentProfile("agent_x", "X", success_rate=0.75, total_runs=8),
            "agent_y": AgentProfile("agent_y", "Y", success_rate=0.75, total_runs=8),
        }
        task = Task(task_id="t1", prompt="Test", expected_keywords=["hello"])
        candidates = [
            Candidate("o1", "t1", "agent_x", "Hello world from X"),
            Candidate("o2", "t1", "agent_y", "Hello world from Y"),
        ]
        winners = set()
        for _ in range(10):
            ctrl, _ = make_controller(profiles)
            result = ctrl.run_task(task, candidates)
            winners.add(result.winner_agent_id)
        assert len(winners) == 1  # always the same winner


class TestWinnerOnlyPersistence:
    """Regression tests: only the winner should be written to storage."""

    def test_unknown_loser_not_persisted(self):
        """If a losing agent is not in storage, it must NOT be created.

        This is the critical regression for the winner-only persistence bug.
        """
        # Only seed one agent — the other is unknown to storage
        profiles = {
            "agent_known": AgentProfile("agent_known", "Known",
                                        success_rate=0.9, total_runs=20),
        }
        task = Task(task_id="t1", prompt="Test task", expected_keywords=["test"])
        candidates = [
            Candidate("o1", "t1", "agent_known", "Test output with many words here"),
            Candidate("o2", "t1", "agent_unknown", "Test output also has words"),
        ]
        ctrl, store = make_controller(profiles)
        result = ctrl.run_task(task, candidates)

        # agent_known should win (higher success_rate from seed)
        assert result.winner_agent_id == "agent_known"

        # The loser agent_unknown must NOT exist in storage
        stored_ids = {p.agent_id for p in store.list_all()}
        assert "agent_unknown" not in stored_ids
        assert "agent_known" in stored_ids

    def test_known_loser_not_modified(self, sample_task, sample_candidates, seed_profiles):
        """A seeded loser's profile should not be touched."""
        ctrl, store = make_controller(seed_profiles)
        ctrl.run_task(sample_task, sample_candidates)

        loser = store.lookup("agent_beta")
        assert loser.total_runs == 5
        assert loser.success_rate == 0.7

    def test_store_size_unchanged_for_unknown_losers(self):
        """Store should only grow by the winner if winner was unknown."""
        profiles = {}  # empty store
        task = Task(task_id="t1", prompt="Test", expected_keywords=["test"])
        candidates = [
            Candidate("o1", "t1", "agent_a", "Test output text here is long enough"),
            Candidate("o2", "t1", "agent_b", "Test output text here is long enough"),
        ]
        ctrl, store = make_controller(profiles)
        assert store.is_empty()

        result = ctrl.run_task(task, candidates)

        # Only the winner should be in storage
        stored = store.list_all()
        assert len(stored) == 1
        assert stored[0].agent_id == result.winner_agent_id


class TestValidation:
    def test_fewer_than_2_candidates_raises(self, seed_profiles):
        task = Task(task_id="t1", prompt="Test", expected_keywords=[])
        candidates = [
            Candidate("o1", "t1", "agent_alpha", "Some output text here"),
        ]
        ctrl, _ = make_controller(seed_profiles)
        with pytest.raises(ValueError, match="At least 2 candidates"):
            ctrl.run_task(task, candidates)

    def test_duplicate_agent_id_raises(self, seed_profiles):
        task = Task(task_id="t1", prompt="Test", expected_keywords=[])
        candidates = [
            Candidate("o1", "t1", "agent_alpha", "Output one text"),
            Candidate("o2", "t1", "agent_alpha", "Output two text"),
        ]
        ctrl, _ = make_controller(seed_profiles)
        with pytest.raises(ValueError, match="Duplicate agent_id"):
            ctrl.run_task(task, candidates)

    def test_mismatched_task_id_raises(self, seed_profiles):
        task = Task(task_id="t1", prompt="Test", expected_keywords=[])
        candidates = [
            Candidate("o1", "t1", "agent_alpha", "Output one text"),
            Candidate("o2", "t2", "agent_beta", "Output two text"),
        ]
        ctrl, _ = make_controller(seed_profiles)
        with pytest.raises(ValueError, match="does not match"):
            ctrl.run_task(task, candidates)

    def test_empty_task_id_raises(self):
        with pytest.raises(ValueError, match="task_id cannot be empty"):
            Task(task_id="", prompt="Test", expected_keywords=[])

    def test_empty_prompt_raises(self):
        with pytest.raises(ValueError, match="prompt cannot be empty"):
            Task(task_id="t1", prompt="", expected_keywords=[])
