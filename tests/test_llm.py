"""Tests for LLM integration (mocked OpenAI client)."""

import pytest
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm import PERSONAS


def _mock_openai_module():
    """Create a mock openai module with a working client."""
    mock_module = MagicMock()

    def make_response(content="This is a mock response about the topic."):
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = content
        return resp

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = make_response()
    mock_module.OpenAI.return_value = mock_client
    return mock_module, mock_client


def _run_generate(prompt="Test prompt", task_id="task_1", **kwargs):
    """Run generate_candidates with mocked OpenAI."""
    mock_module, mock_client = _mock_openai_module()
    with patch.dict("sys.modules", {"openai": mock_module}):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            # Re-import to pick up the mocked module
            import importlib
            import core.llm
            importlib.reload(core.llm)
            candidates = core.llm.generate_candidates(prompt, task_id, **kwargs)
    return candidates, mock_client


class TestGenerateCandidates:
    def test_returns_correct_count(self):
        candidates, _ = _run_generate()
        assert len(candidates) == 3

    def test_candidate_agent_ids_match_personas(self):
        candidates, _ = _run_generate()
        agent_ids = [c.agent_id for c in candidates]
        expected = [p["agent_id"] for p in PERSONAS]
        assert agent_ids == expected

    def test_candidate_task_id_set(self):
        candidates, _ = _run_generate(task_id="task_xyz")
        for c in candidates:
            assert c.task_id == "task_xyz"

    def test_candidate_has_output_text(self):
        candidates, _ = _run_generate()
        for c in candidates:
            assert len(c.output_text) > 0

    def test_candidate_has_latency(self):
        candidates, _ = _run_generate()
        for c in candidates:
            assert c.latency_ms >= 0

    def test_custom_model_passed(self):
        _, mock_client = _run_generate(model="gpt-4o")
        calls = mock_client.chat.completions.create.call_args_list
        for call in calls:
            assert call.kwargs["model"] == "gpt-4o"

    def test_missing_api_key_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OPENAI_API_KEY", None)
            import importlib
            import core.llm
            importlib.reload(core.llm)
            with pytest.raises(EnvironmentError, match="OPENAI_API_KEY"):
                core.llm.generate_candidates("Test", "t1")

    def test_custom_personas(self):
        custom = [
            {"agent_id": "custom_a", "agent_name": "A", "system_prompt": "You are A."},
            {"agent_id": "custom_b", "agent_name": "B", "system_prompt": "You are B."},
        ]
        candidates, _ = _run_generate(personas=custom)
        assert len(candidates) == 2
        assert candidates[0].agent_id == "custom_a"
        assert candidates[1].agent_id == "custom_b"
