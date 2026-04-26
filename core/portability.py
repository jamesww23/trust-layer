"""Portable reputation export / import.

Lets an agent's reputation be moved between trust-layer deployments,
turning the README's "portable reputation" promise into a runnable feature.

Format
------
The export blob is a self-describing JSON document:

    {
        "format_version": "1.0",
        "exported_at":   "2026-04-25T18:30:00+00:00",
        "source_url":    "https://aitrustlayer.vercel.app",
        "agent": { ...full Agent.to_dict()... },
        "task_history": [ ...rated Task.to_dict() entries... ],
        "signature":     "sha256:<hex>"   # integrity check over the canonical payload
    }

The signature is a SHA-256 hash of the canonical JSON of every field except
`signature` itself.  This catches accidental corruption and casual tampering.
True cryptographic provenance (asymmetric keys per source instance) is noted
as future work in the project README.

Anti-poisoning on import
------------------------
Imported ratings keep their values but their `rating_weights` are halved.
This means the imported trust score immediately starts at roughly half its
reported value, and rebuilds back up as the agent earns local ratings at
full weight.  Without this guard, a permissive instance could mint high
trust and an agent could "cash it in" on a strict instance.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from core.models import Agent, Task

FORMAT_VERSION = "1.0"
SUPPORTED_VERSIONS = {"1.0"}

# When importing, halve the weight of every rating so the trust score
# starts capped and rebuilds with new local ratings at full weight.
IMPORT_WEIGHT_DECAY = 0.5


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _canonical_json(payload: dict) -> str:
    """Serialize a dict to a stable byte-for-byte string for signing.

    Sorted keys + no extra whitespace ensures the same logical payload
    always produces the same hash, regardless of dict iteration order.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _sign(payload: dict) -> str:
    """Return `sha256:<hex>` over the canonical form of `payload`."""
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _verify_signature(blob: dict) -> None:
    """Raise ValueError if `blob['signature']` does not match the rest of the blob."""
    sig = blob.get("signature")
    if not sig:
        raise ValueError("Export blob is missing 'signature' field")

    body = {k: v for k, v in blob.items() if k != "signature"}
    expected = _sign(body)
    if sig != expected:
        raise ValueError(
            "Export blob signature mismatch — the blob was modified after export"
        )


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_agent(store, agent_id: str, source_url: str = "") -> dict:
    """Build a portable export blob for one agent.

    Args:
        store:       any object exposing .get(agent_id) and ._all_tasks() /
                     get_tasks_for_agent()
        agent_id:    agent to export
        source_url:  base URL of the trust-layer instance doing the export
                     (informational; recorded in the blob)

    Returns:
        Signed export blob ready to JSON-serialize.

    Raises:
        ValueError: if the agent does not exist
    """
    agent = store.get(agent_id)
    if agent is None:
        raise ValueError(f"Agent '{agent_id}' not found")

    # Collect rated task history (read-only, for auditability).
    rated_tasks: list[dict] = []
    if hasattr(store, "_all_tasks"):
        all_tasks = store._all_tasks()
    else:
        # MemoryStore exposes tasks via internal dict
        all_tasks = list(getattr(store, "_tasks", {}).values())

    for task in all_tasks:
        if not isinstance(task, Task):
            continue
        if task.provider_id != agent_id:
            continue
        if task.status != "rated":
            continue
        rated_tasks.append(task.to_dict())

    body = {
        "format_version": FORMAT_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "source_url": source_url or "",
        "agent": agent.to_dict(),
        "task_history": rated_tasks,
    }
    body["signature"] = _sign(body)
    return body


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

def import_agent(
    store,
    blob: dict,
    *,
    overwrite: bool = False,
    apply_decay: bool = True,
) -> dict:
    """Restore an agent from an export blob.

    Args:
        store:       any AgentStore implementation
        blob:        the export dict produced by export_agent
        overwrite:   if True, replace an existing agent with the same id;
                     if False (default), reject duplicates with ValueError
        apply_decay: if True (default), halve rating weights so imported
                     trust starts capped and rebuilds locally

    Returns:
        Summary dict: imported agent_id, applied_trust, decay_applied,
        ratings_imported, source_url.

    Raises:
        ValueError: if the blob is malformed, has a bad signature,
                    is an unsupported format version, or duplicates an
                    existing agent (unless overwrite=True).
    """
    if not isinstance(blob, dict):
        raise ValueError("Import payload must be a JSON object")

    version = blob.get("format_version")
    if version not in SUPPORTED_VERSIONS:
        raise ValueError(
            f"Unsupported export format version: {version!r} "
            f"(supported: {sorted(SUPPORTED_VERSIONS)})"
        )

    _verify_signature(blob)

    agent_data = blob.get("agent")
    if not isinstance(agent_data, dict):
        raise ValueError("Export blob is missing 'agent' object")

    agent_id = agent_data.get("agent_id")
    if not agent_id:
        raise ValueError("Imported agent has no agent_id")

    existing = store.get(agent_id)
    if existing is not None and not overwrite:
        raise ValueError(
            f"Agent '{agent_id}' already exists; pass overwrite=true to replace"
        )

    # Reconstruct the Agent.  Apply weight decay to imported ratings so the
    # trust score starts roughly halved and rebuilds via local activity.
    if apply_decay:
        weights = list(agent_data.get("rating_weights") or [])
        agent_data = dict(agent_data)  # shallow copy — we'll mutate below
        agent_data["rating_weights"] = [w * IMPORT_WEIGHT_DECAY for w in weights]

    agent = Agent.from_dict(agent_data)

    if existing is not None:
        store.upsert(agent)  # overwrite path
    else:
        store.register(agent)

    return {
        "status": "imported",
        "agent_id": agent.agent_id,
        "agent_name": agent.agent_name,
        "applied_trust": agent.trust_score,
        "decay_applied": bool(apply_decay),
        "ratings_imported": len(agent.ratings),
        "source_url": blob.get("source_url", ""),
        "exported_at": blob.get("exported_at", ""),
    }
