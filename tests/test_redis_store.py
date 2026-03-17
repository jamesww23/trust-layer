"""Tests for RedisStore behavior using a mock Redis backend.

No live Redis required. We use object.__new__ to bypass __init__ and
inject a MagicMock as the Redis client. This verifies serialization,
key naming, and — critically — that lookup() never writes.
"""

import json
import os
import sys
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import AgentProfile
from core.store import RedisStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_redis_store():
    """Create a RedisStore with a mock Redis client, bypassing __init__."""
    store = object.__new__(RedisStore)
    store._redis = MagicMock()
    return store, store._redis


SAMPLE_PROFILE = AgentProfile(
    agent_id="agent_test",
    agent_name="Test Agent",
    version="1.0",
    success_rate=0.75,
    total_runs=10,
    created_at="2025-01-01T00:00:00Z",
    updated_at="2025-01-01T00:00:00Z",
)


# ---------------------------------------------------------------------------
# Tests: env var handling
# ---------------------------------------------------------------------------

class TestRedisStoreInit:
    def test_missing_env_vars_raises(self):
        mock_module = MagicMock()
        with patch.dict("sys.modules", {"upstash_redis": mock_module}):
            with patch.dict(os.environ, {}, clear=True):
                with pytest.raises(EnvironmentError, match="Redis credentials not found"):
                    RedisStore()

    def test_primary_env_vars_used(self):
        mock_module = MagicMock()
        with patch.dict("sys.modules", {"upstash_redis": mock_module}):
            with patch.dict(os.environ, {
                "UPSTASH_REDIS_REST_URL": "https://primary.io",
                "UPSTASH_REDIS_REST_TOKEN": "primary-token",
            }, clear=True):
                store = RedisStore()
                mock_module.Redis.assert_called_once_with(
                    url="https://primary.io", token="primary-token"
                )

    def test_fallback_env_vars_used(self):
        mock_module = MagicMock()
        with patch.dict("sys.modules", {"upstash_redis": mock_module}):
            with patch.dict(os.environ, {
                "KV_REST_API_URL": "https://fallback.io",
                "KV_REST_API_TOKEN": "fallback-token",
            }, clear=True):
                store = RedisStore()
                mock_module.Redis.assert_called_once_with(
                    url="https://fallback.io", token="fallback-token"
                )


# ---------------------------------------------------------------------------
# Tests: get (persists on miss)
# ---------------------------------------------------------------------------

class TestRedisStoreGet:
    def test_get_existing_deserializes(self):
        store, mock_redis = _make_redis_store()
        mock_redis.get.return_value = json.dumps(SAMPLE_PROFILE.to_dict())

        profile = store.get("agent_test")
        mock_redis.get.assert_called_once_with("agent:agent_test")
        assert profile.agent_id == "agent_test"
        assert profile.success_rate == 0.75

    def test_get_existing_handles_dict_response(self):
        """Upstash client may return dict directly instead of string."""
        store, mock_redis = _make_redis_store()
        mock_redis.get.return_value = SAMPLE_PROFILE.to_dict()

        profile = store.get("agent_test")
        assert profile.agent_id == "agent_test"

    def test_get_missing_persists_default(self):
        """get() on cache miss MUST call set() to persist the default."""
        store, mock_redis = _make_redis_store()
        mock_redis.get.return_value = None

        profile = store.get("agent_new")
        assert profile.agent_id == "agent_new"
        assert profile.success_rate == 0.5
        assert profile.total_runs == 0
        # Verify set was called (persist on miss)
        mock_redis.set.assert_called_once()
        key_arg = mock_redis.set.call_args[0][0]
        assert key_arg == "agent:agent_new"


# ---------------------------------------------------------------------------
# Tests: lookup (MUST NOT persist on miss) — critical invariant
# ---------------------------------------------------------------------------

class TestRedisStoreLookup:
    def test_lookup_existing_returns_profile(self):
        store, mock_redis = _make_redis_store()
        mock_redis.get.return_value = json.dumps(SAMPLE_PROFILE.to_dict())

        profile = store.lookup("agent_test")
        assert profile.agent_id == "agent_test"
        assert profile.success_rate == 0.75

    def test_lookup_missing_returns_default(self):
        store, mock_redis = _make_redis_store()
        mock_redis.get.return_value = None

        profile = store.lookup("agent_ghost")
        assert profile.agent_id == "agent_ghost"
        assert profile.success_rate == 0.5
        assert profile.total_runs == 0

    def test_lookup_missing_does_NOT_call_set(self):
        """Critical: lookup must NEVER write to Redis on cache miss."""
        store, mock_redis = _make_redis_store()
        mock_redis.get.return_value = None

        store.lookup("agent_ghost")
        mock_redis.set.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: upsert
# ---------------------------------------------------------------------------

class TestRedisStoreUpsert:
    def test_upsert_serializes_and_sets(self):
        store, mock_redis = _make_redis_store()

        profile = AgentProfile("agent_x", "X", success_rate=0.9, total_runs=5)
        store.upsert(profile)

        mock_redis.set.assert_called_once()
        key, value = mock_redis.set.call_args[0]
        assert key == "agent:agent_x"
        data = json.loads(value)
        assert data["agent_id"] == "agent_x"
        assert data["success_rate"] == 0.9


# ---------------------------------------------------------------------------
# Tests: list_all, reset, is_empty
# ---------------------------------------------------------------------------

class TestRedisStoreListAll:
    def test_list_all_returns_all_profiles(self):
        store, mock_redis = _make_redis_store()
        mock_redis.keys.return_value = ["agent:a", "agent:b"]
        mock_redis.get.side_effect = [
            json.dumps({"agent_id": "a", "agent_name": "A", "success_rate": 0.8,
                        "total_runs": 5, "version": "1.0",
                        "created_at": "2025-01-01T00:00:00Z",
                        "updated_at": "2025-01-01T00:00:00Z"}),
            json.dumps({"agent_id": "b", "agent_name": "B", "success_rate": 0.6,
                        "total_runs": 3, "version": "1.0",
                        "created_at": "2025-01-01T00:00:00Z",
                        "updated_at": "2025-01-01T00:00:00Z"}),
        ]

        profiles = store.list_all()
        assert len(profiles) == 2
        ids = {p.agent_id for p in profiles}
        assert ids == {"a", "b"}

    def test_list_all_empty(self):
        store, mock_redis = _make_redis_store()
        mock_redis.keys.return_value = []
        assert store.list_all() == []


class TestRedisStoreReset:
    def test_reset_deletes_then_seeds(self):
        store, mock_redis = _make_redis_store()
        mock_redis.keys.return_value = ["agent:old1", "agent:old2"]

        seed = {
            "agent_new": AgentProfile("agent_new", "New", success_rate=0.5, total_runs=0),
        }
        store.reset(seed)

        assert mock_redis.delete.call_count == 2
        mock_redis.set.assert_called_once()
        key = mock_redis.set.call_args[0][0]
        assert key == "agent:agent_new"


class TestRedisStoreIsEmpty:
    def test_empty_when_no_keys(self):
        store, mock_redis = _make_redis_store()
        mock_redis.keys.return_value = []
        assert store.is_empty() is True

    def test_not_empty_when_keys_exist(self):
        store, mock_redis = _make_redis_store()
        mock_redis.keys.return_value = ["agent:x"]
        assert store.is_empty() is False
