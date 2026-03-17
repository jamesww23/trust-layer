"""Shared test fixtures for Trust Layer tests."""

import sys
import os
import pytest

# Ensure core/ is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import AgentProfile, Task, Candidate, ScoringConfig
from core.scoring import ScoringEngine
from core.store import MemoryStore


@pytest.fixture
def scoring_config():
    return ScoringConfig(w_reputation=0.6, w_relevancy=0.4)


@pytest.fixture
def engine(scoring_config):
    return ScoringEngine(scoring_config)


@pytest.fixture
def sample_task():
    return Task(
        task_id="task_test",
        prompt="Describe renewable energy benefits.",
        expected_keywords=["renewable", "energy", "solar", "wind"],
    )


@pytest.fixture
def sample_candidates():
    return [
        Candidate(
            output_id="out_a",
            task_id="task_test",
            agent_id="agent_alpha",
            output_text="Renewable energy from solar and wind sources is transformative.",
            latency_ms=100,
        ),
        Candidate(
            output_id="out_b",
            task_id="task_test",
            agent_id="agent_beta",
            output_text="Solar panels generate energy from renewable sources.",
            latency_ms=200,
        ),
    ]


@pytest.fixture
def seed_profiles():
    return {
        "agent_alpha": AgentProfile(
            agent_id="agent_alpha",
            agent_name="Alpha",
            success_rate=0.8,
            total_runs=10,
        ),
        "agent_beta": AgentProfile(
            agent_id="agent_beta",
            agent_name="Beta",
            success_rate=0.7,
            total_runs=5,
        ),
    }


@pytest.fixture
def memory_store(seed_profiles):
    return MemoryStore(initial=seed_profiles)
