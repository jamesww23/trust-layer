"""Tests for export / import of agent reputation."""

import json
import pytest

from core.models import Agent, Task
from core.store import MemoryStore
from core.portability import (
    export_agent,
    import_agent,
    FORMAT_VERSION,
    IMPORT_WEIGHT_DECAY,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_seasoned_agent(store, agent_id="alice", n_ratings=5):
    """Register an agent with a non-trivial rating history so trust is real."""
    agent = Agent(agent_id, agent_id.title(), "I do real things.")
    agent.tasks_received = n_ratings
    agent.tasks_completed = n_ratings
    agent.ratings = [0.9] * n_ratings
    agent.rating_weights = [0.7] * n_ratings
    agent.specialization_score = 0.8
    store.register(agent)
    return agent


def _make_rated_task(store, provider_id, requester_id="req", task_id="t1", rating=0.9):
    task = Task(
        task_id=task_id,
        requester_id=requester_id,
        provider_id=provider_id,
        description="Do a thing",
        status="rated",
        rating=rating,
        rated_by=requester_id,
    )
    store.save_task(task)
    return task


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

class TestExport:
    def test_export_basic_shape(self):
        store = MemoryStore()
        _make_seasoned_agent(store)

        blob = export_agent(store, "alice", source_url="https://example.com")

        assert blob["format_version"] == FORMAT_VERSION
        assert blob["source_url"] == "https://example.com"
        assert blob["agent"]["agent_id"] == "alice"
        assert "exported_at" in blob
        assert blob["signature"].startswith("sha256:")

    def test_export_includes_rated_tasks_only(self):
        store = MemoryStore()
        _make_seasoned_agent(store)
        # Register the requester so trust calc has a referent
        store.register(Agent("req", "Requester", "I rate things."))

        _make_rated_task(store, "alice", task_id="t_rated", rating=0.9)
        # A pending task should NOT appear in history
        store.save_task(Task("t_pending", "req", "alice", "Pending", status="pending"))

        blob = export_agent(store, "alice")
        ids = [t["task_id"] for t in blob["task_history"]]
        assert "t_rated" in ids
        assert "t_pending" not in ids

    def test_export_unknown_agent_raises(self):
        store = MemoryStore()
        with pytest.raises(ValueError, match="not found"):
            export_agent(store, "ghost")

    def test_export_signature_is_stable_and_deterministic(self):
        """Same agent state → same signature, regardless of dict ordering."""
        store = MemoryStore()
        _make_seasoned_agent(store)

        blob_1 = export_agent(store, "alice")
        blob_2 = export_agent(store, "alice")

        # exported_at differs by timestamp, but signing covers everything,
        # so the signatures should differ ONLY because of timestamp.
        # We test stability by removing the timestamp and re-signing.
        from core.portability import _sign  # private use is OK in tests
        body_1 = {k: v for k, v in blob_1.items() if k not in ("signature", "exported_at")}
        body_2 = {k: v for k, v in blob_2.items() if k not in ("signature", "exported_at")}
        assert _sign(body_1) == _sign(body_2)


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

class TestImport:
    def test_roundtrip_preserves_identity(self):
        src = MemoryStore()
        _make_seasoned_agent(src, agent_id="alice", n_ratings=5)

        blob = export_agent(src, "alice")

        dst = MemoryStore()
        result = import_agent(dst, blob)

        assert result["status"] == "imported"
        assert result["agent_id"] == "alice"
        assert result["ratings_imported"] == 5

        restored = dst.get("alice")
        assert restored is not None
        assert restored.agent_name == "Alice"
        assert restored.tasks_completed == 5

    def test_import_applies_weight_decay_by_default(self):
        src = MemoryStore()
        _make_seasoned_agent(src, agent_id="alice", n_ratings=5)
        original_trust = src.get("alice").trust_score

        blob = export_agent(src, "alice")

        dst = MemoryStore()
        import_agent(dst, blob)

        restored = dst.get("alice")
        # All rating_weights should be halved by the decay factor.
        assert restored.rating_weights == [0.7 * IMPORT_WEIGHT_DECAY] * 5
        # And trust must drop relative to the source instance.
        assert restored.trust_score < original_trust

    def test_import_can_skip_decay(self):
        src = MemoryStore()
        _make_seasoned_agent(src, agent_id="alice", n_ratings=5)
        blob = export_agent(src, "alice")

        dst = MemoryStore()
        import_agent(dst, blob, apply_decay=False)
        restored = dst.get("alice")
        assert restored.rating_weights == [0.7] * 5

    def test_tampered_blob_rejected(self):
        src = MemoryStore()
        _make_seasoned_agent(src, agent_id="alice")
        blob = export_agent(src, "alice")

        # Mutate the agent's reported trust without resigning.
        blob["agent"]["agent_name"] = "Mallory"

        dst = MemoryStore()
        with pytest.raises(ValueError, match="signature mismatch"):
            import_agent(dst, blob)

    def test_missing_signature_rejected(self):
        src = MemoryStore()
        _make_seasoned_agent(src, agent_id="alice")
        blob = export_agent(src, "alice")
        del blob["signature"]

        dst = MemoryStore()
        with pytest.raises(ValueError, match="signature"):
            import_agent(dst, blob)

    def test_unsupported_version_rejected(self):
        src = MemoryStore()
        _make_seasoned_agent(src, agent_id="alice")
        blob = export_agent(src, "alice")
        blob["format_version"] = "9.9"
        # re-sign so the version error fires before signature error
        from core.portability import _sign
        body = {k: v for k, v in blob.items() if k != "signature"}
        blob["signature"] = _sign(body)

        dst = MemoryStore()
        with pytest.raises(ValueError, match="format version"):
            import_agent(dst, blob)

    def test_duplicate_agent_rejected_without_overwrite(self):
        src = MemoryStore()
        _make_seasoned_agent(src, agent_id="alice")
        blob = export_agent(src, "alice")

        dst = MemoryStore()
        # Pre-register an agent with the same id
        dst.register(Agent("alice", "Existing Alice", "Already here"))

        with pytest.raises(ValueError, match="already exists"):
            import_agent(dst, blob)

    def test_overwrite_replaces_existing(self):
        src = MemoryStore()
        _make_seasoned_agent(src, agent_id="alice", n_ratings=5)
        blob = export_agent(src, "alice")

        dst = MemoryStore()
        dst.register(Agent("alice", "Existing Alice", "Already here"))
        result = import_agent(dst, blob, overwrite=True)

        assert result["status"] == "imported"
        assert dst.get("alice").agent_name == "Alice"  # from the imported blob

    def test_non_dict_payload_rejected(self):
        dst = MemoryStore()
        with pytest.raises(ValueError, match="JSON object"):
            import_agent(dst, "this is not a dict")

    def test_blob_serializes_to_json(self):
        """A real export blob must round-trip through json.dumps/loads."""
        src = MemoryStore()
        _make_seasoned_agent(src, agent_id="alice")
        blob = export_agent(src, "alice")

        wire = json.dumps(blob)
        restored = json.loads(wire)

        dst = MemoryStore()
        import_agent(dst, restored)
        assert dst.get("alice") is not None
