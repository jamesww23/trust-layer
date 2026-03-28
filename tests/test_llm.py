"""Tests for multi-provider LLM integration (mocked clients)."""

import pytest
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm import PROVIDERS, get_available_providers


def _mock_llm_modules():
    """Create mock modules for openai, anthropic, groq."""
    def make_chat_response(content="This is a mock response about the topic."):
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = content
        return resp

    def make_anthropic_response(content="This is a mock Anthropic response."):
        resp = MagicMock()
        resp.content = [MagicMock()]
        resp.content[0].text = content
        return resp

    openai_mod = MagicMock()
    openai_mod.OpenAI.return_value.chat.completions.create.return_value = make_chat_response("OpenAI response text here.")

    anthropic_mod = MagicMock()
    anthropic_mod.Anthropic.return_value.messages.create.return_value = make_anthropic_response("Anthropic response text here.")

    groq_mod = MagicMock()
    groq_mod.Groq.return_value.chat.completions.create.return_value = make_chat_response("Groq response text here.")

    return openai_mod, anthropic_mod, groq_mod


def _run_with_providers(env_vars, prompt="Test prompt", task_id="task_1"):
    """Run generate_candidates with specified env vars and mocked modules."""
    openai_mod, anthropic_mod, groq_mod = _mock_llm_modules()
    with patch.dict("sys.modules", {
        "openai": openai_mod,
        "anthropic": anthropic_mod,
        "groq": groq_mod,
    }):
        with patch.dict(os.environ, env_vars, clear=True):
            import importlib
            import core.llm
            importlib.reload(core.llm)
            candidates = core.llm.generate_candidates(prompt, task_id)
    return candidates


class TestGetAvailableProviders:
    def test_no_keys_returns_empty(self):
        with patch.dict(os.environ, {}, clear=True):
            assert get_available_providers() == []

    def test_openai_only(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test"}, clear=True):
            providers = get_available_providers()
            assert len(providers) == 1
            assert providers[0]["provider"] == "openai"

    def test_all_providers(self):
        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "test",
            "ANTHROPIC_API_KEY": "test",
            "GROQ_API_KEY": "test",
        }, clear=True):
            providers = get_available_providers()
            assert len(providers) == 3


class TestMultiProvider:
    """Requires 2+ provider keys to generate candidates."""

    def test_two_providers_returns_2_candidates(self):
        candidates = _run_with_providers({
            "OPENAI_API_KEY": "test",
            "ANTHROPIC_API_KEY": "test",
        })
        assert len(candidates) == 2
        ids = {c.agent_id for c in candidates}
        assert "agent_gpt4" in ids
        assert "agent_claude" in ids

    def test_three_providers_returns_3_candidates(self):
        candidates = _run_with_providers({
            "OPENAI_API_KEY": "test",
            "ANTHROPIC_API_KEY": "test",
            "GROQ_API_KEY": "test",
        })
        assert len(candidates) == 3
        ids = {c.agent_id for c in candidates}
        assert ids == {"agent_gpt4", "agent_claude", "agent_llama"}

    def test_each_candidate_has_output(self):
        candidates = _run_with_providers({
            "OPENAI_API_KEY": "test",
            "ANTHROPIC_API_KEY": "test",
        })
        for c in candidates:
            assert len(c.output_text) > 0

    def test_provider_failure_returns_error_candidate(self):
        """If one provider fails, others should still return."""
        openai_mod, anthropic_mod, groq_mod = _mock_llm_modules()
        anthropic_mod.Anthropic.return_value.messages.create.side_effect = Exception("API down")
        with patch.dict("sys.modules", {
            "openai": openai_mod, "anthropic": anthropic_mod, "groq": groq_mod,
        }):
            with patch.dict(os.environ, {
                "OPENAI_API_KEY": "test", "ANTHROPIC_API_KEY": "test",
            }, clear=True):
                import importlib, core.llm
                importlib.reload(core.llm)
                candidates = core.llm.generate_candidates("Test", "t1")
        assert len(candidates) == 2
        error_cand = next(c for c in candidates if c.agent_id == "agent_claude")
        assert "[Error:" in error_cand.output_text


class TestInsufficientProviders:
    def test_no_keys_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            import importlib, core.llm
            importlib.reload(core.llm)
            with pytest.raises(EnvironmentError, match="API key"):
                core.llm.generate_candidates("Test", "t1")

    def test_one_key_raises(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test"}, clear=True):
            import importlib, core.llm
            importlib.reload(core.llm)
            with pytest.raises(EnvironmentError, match="At least 2"):
                core.llm.generate_candidates("Test", "t1")
