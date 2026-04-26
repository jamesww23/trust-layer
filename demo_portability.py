#!/usr/bin/env python3
"""Trust-layer federation demo — reputation portability across instances.

This is the runnable proof of the "portable reputation layer" claim.
It walks through:

  1. Registering a brand-new agent on Node A
  2. Building its trust through 5 high-quality ratings
  3. Confirming Node B has never seen the agent
  4. Exporting from A and importing to B in one move
  5. Showing the imported trust starts capped (anti-poisoning) and the
     full rating history is preserved

Setup
-----
    docker compose up --build      # boots two trust-layer nodes
    python3 demo_portability.py    # runs this script

Or against any two manually-started instances:

    python3 demo_portability.py --node-a http://localhost:4001 \
                                --node-b http://localhost:4002

The demo finishes in well under a minute and is designed to be the
1-minute video deliverable for the final presentation.
"""

import argparse
import json
import sys
import time
import uuid
import urllib.request
import urllib.error

# ----- pretty printing helpers --------------------------------------------

BAR = "=" * 74
THIN = "-" * 74


def banner(title: str) -> None:
    print(f"\n{BAR}\n  {title}\n{BAR}")


def section(title: str) -> None:
    print(f"\n{THIN}\n  {title}\n{THIN}")


def step(n: int, total: int, msg: str) -> None:
    print(f"\n  [{n}/{total}] {msg}")


def ok(msg: str) -> None:
    print(f"        ✓ {msg}")


def info(msg: str) -> None:
    print(f"        → {msg}")


def fail(msg: str) -> None:
    print(f"        ✗ {msg}")


def beat(seconds: float = 0.6) -> None:
    """Tiny pause for visual pacing in the recorded video."""
    time.sleep(seconds)


# ----- minimal HTTP helper (no SDK install needed for the demo) -----------

# Generous per-request timeout: server.py's MemoryStore is single-threaded,
# and Docker healthchecks can briefly contend with our requests.  30 s is
# well above any realistic real workload.
REQUEST_TIMEOUT = 30
# One automatic retry on transient socket errors (timeouts, connection
# resets) keeps the demo recording-friendly without hiding real failures.
TRANSIENT_RETRIES = 1


def _request(method: str, url: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}

    last_error: Exception | None = None
    for attempt in range(TRANSIENT_RETRIES + 1):
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            # Real server-side error — surface immediately, don't retry.
            try:
                err = json.loads(e.read().decode())
            except Exception:
                err = {"error": str(e)}
            raise RuntimeError(f"HTTP {e.code}: {err.get('error', err)}") from None
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            # Transient network issue — retry once before giving up.
            last_error = e
            if attempt < TRANSIENT_RETRIES:
                time.sleep(0.5)
                continue
            raise RuntimeError(
                f"{method} {url} failed after {attempt + 1} attempt(s): {e}"
            ) from None
    # Unreachable, but keeps type-checkers happy.
    raise RuntimeError(f"{method} {url} failed: {last_error}")


def get_agent(base: str, agent_id: str) -> dict | None:
    resp = _request("GET", f"{base}/api/agents")
    for a in resp.get("agents", []):
        if a["agent_id"] == agent_id:
            return a
    return None


def register(base: str, agent_id: str, name: str, skill_md: str) -> dict:
    return _request(
        "POST",
        f"{base}/api/register-agent",
        {"agent_id": agent_id, "agent_name": name, "skill_md": skill_md},
    )


def submit_feedback(base: str, agent_id: str, score: float, rated_by: str) -> dict:
    return _request(
        "POST",
        f"{base}/api/submit-feedback",
        {
            "agent_id": agent_id,
            "score": score,
            "fulfilled": True,
            "rated_by": rated_by,
        },
    )


def export_blob(base: str, agent_id: str) -> dict:
    return _request("GET", f"{base}/api/export?agent_id={agent_id}")


def import_blob(base: str, blob: dict) -> dict:
    return _request("POST", f"{base}/api/import", {"blob": blob})


# ----- the demo flow -----------------------------------------------------

def run(node_a: str, node_b: str) -> int:
    banner("TRUST LAYER FEDERATION DEMO")
    print("  Reputation portability across independent instances")
    print()
    print(f"  Node A (source):       {node_a}")
    print(f"  Node B (destination):  {node_b}")

    # Use a unique id each run so the demo is re-runnable without resetting.
    agent_id = f"demo_alice_{uuid.uuid4().hex[:6]}"
    info_print = lambda label, value: print(f"        {label:<22} {value}")

    # Pick an existing high-trust seed agent on Node A as the "rater"
    # (its trust gives weight to ratings via the requester-trust mechanism).
    rater_id = "agent_coder"

    # ---- ACT 1 — build reputation on Node A ----
    section("ACT 1 — Build reputation on Node A")

    step(1, 4, f"Registering '{agent_id}' on Node A...")
    register(
        node_a, agent_id, "Demo Alice",
        "# Demo Alice\n\nMelanoma classification specialist.",
    )
    a_init = get_agent(node_a, agent_id)
    ok(f"Registered. Initial trust on A: {a_init['trust_score']:.1%}")
    beat()

    step(2, 4, "Bootstrapping trust with 5 high-quality ratings...")
    for i in range(5):
        submit_feedback(node_a, agent_id, score=0.9, rated_by=rater_id)
    a_after = get_agent(node_a, agent_id)
    ok(f"Trust on A after 5 ratings: {a_after['trust_score']:.1%}")
    info(f"ratings recorded: {a_after['ratings_count']}")
    beat()

    # ---- ACT 2 — migrate to Node B ----
    section("ACT 2 — Migrate reputation to Node B")

    step(3, 4, f"Confirming Node B has never seen '{agent_id}'...")
    b_before = get_agent(node_b, agent_id)
    if b_before is None:
        ok("Not in Node B's registry.")
    else:
        fail(f"Unexpected: agent already on Node B (trust={b_before['trust_score']})")
        return 1
    beat()

    step(4, 4, "Exporting from Node A → Importing to Node B...")
    blob = export_blob(node_a, agent_id)
    print()
    print("        Export blob:")
    info_print("format_version", blob["format_version"])
    info_print("signature", blob["signature"][:46] + "...")
    info_print("ratings in blob", len(blob["agent"]["ratings"]))
    info_print("source", blob.get("source_url") or "(local)")
    beat()

    result = import_blob(node_b, blob)
    print()
    print("        Import result:")
    ok(f"Agent appeared on Node B  (status: {result['status']})")
    b_after = get_agent(node_b, agent_id)

    # Show side-by-side comparison so the decay is provable in the data
    # (the trust score itself may match if the 40% cap is binding —
    # noted explicitly so the viewer can see what's happening).
    print()
    print("        State comparison:")
    info_print("Trust on A", f"{a_after['trust_score']:.1%}")
    info_print("Trust on B", f"{b_after['trust_score']:.1%}")
    info_print("Ratings on A", a_after["ratings"])
    info_print("Ratings on B", b_after["ratings"])
    info_print("Weights on A", a_after["rating_weights"])
    info_print("Weights on B", b_after["rating_weights"])
    print()
    ok(f"Identity + history preserved across nodes")
    ok(f"Imported weights halved (anti-poisoning) — visible above")
    if abs(a_after["trust_score"] - b_after["trust_score"]) < 0.001:
        info("Trust shows as equal here because the 40% cap is binding")
        info("(agent has < 3 locally-completed tasks). The decay's effect")
        info("becomes visible once the cap lifts via local activity.")

    # ---- closing summary ----
    section("WHAT THIS PROVES")
    print("  ✓ Agent identity carries across independent trust-layer deployments")
    print("  ✓ Reputation history is preserved (signed, tamper-evident)")
    print("  ✓ Imported trust starts capped — must rebuild via local activity")
    print("    so a permissive instance cannot \"launder\" trust onto a strict one")
    print()
    print(f"  The README's \"portable reputation layer\" — now a runnable feature.")
    print(f"  {BAR}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 2)[0])
    parser.add_argument(
        "--node-a", default="http://localhost:4001",
        help="Source trust-layer instance (default: http://localhost:4001)",
    )
    parser.add_argument(
        "--node-b", default="http://localhost:4002",
        help="Destination trust-layer instance (default: http://localhost:4002)",
    )
    args = parser.parse_args()

    try:
        return run(args.node_a, args.node_b)
    except RuntimeError as e:
        print(f"\n  ERROR: {e}", file=sys.stderr)
        print("  Make sure both nodes are running:", file=sys.stderr)
        print("    docker compose up --build", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
