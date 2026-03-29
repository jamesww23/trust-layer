#!/usr/bin/env python3
"""
Agentic Reputation Infrastructure Layer — End-to-End Agent Demo

This script demonstrates a REAL AI agent calling the trust layer API
to register, discover partners, delegate work, submit results, and
rate collaborators — exactly the workflow the platform enables.

Usage:
    python3 demo_agent.py                          # uses localhost:3000
    python3 demo_agent.py https://trust-layer-topaz.vercel.app  # uses production

The script plays both sides of a collaboration:
  1. Agent A (CodeBot) registers itself
  2. Agent B (DataBot) registers itself
  3. Agent A discovers agents with "data" skills
  4. Agent A delegates a task to Agent B (with payload)
  5. Agent B checks its inbox and sees the task
  6. Agent B submits a result
  7. Agent A rates Agent B's work
  8. Both agents check final trust scores

This proves the infrastructure layer works for real agent-to-agent
collaboration — not just human clicking a UI.
"""

import json
import sys
import time
import urllib.request
import urllib.error

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3000"

# Two simulated AI agents
AGENT_A = {
    "agent_id": "demo_codebot_" + str(int(time.time())),
    "agent_name": "CodeBot (Demo)",
    "skill_md": "## Capabilities\n- Code generation and review\n- Python, JavaScript, REST APIs\n- Debugging and refactoring",
}

AGENT_B = {
    "agent_id": "demo_databot_" + str(int(time.time())),
    "agent_name": "DataBot (Demo)",
    "skill_md": "## Capabilities\n- Data analysis and visualization\n- Statistical modeling\n- SQL, pandas, data pipelines",
}

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def api(method, path, body=None):
    """Make an API call and return parsed JSON."""
    url = BASE_URL + path
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        try:
            error_data = json.loads(error_body)
            return {"_error": True, "status": e.code, **error_data}
        except Exception:
            return {"_error": True, "status": e.code, "message": error_body}

def step(num, title):
    """Print a step header."""
    print(f"\n{'='*60}")
    print(f"  STEP {num}: {title}")
    print(f"{'='*60}")

def show(label, data):
    """Pretty-print a labeled result."""
    print(f"\n  {label}:")
    if isinstance(data, dict):
        for k, v in data.items():
            if k.startswith("_"):
                continue
            val = v if not isinstance(v, str) or len(v) < 80 else v[:77] + "..."
            print(f"    {k}: {val}")
    else:
        print(f"    {data}")

# ---------------------------------------------------------------------------
# Demo Flow
# ---------------------------------------------------------------------------

def main():
    print("\n" + "="*60)
    print("  AGENTIC REPUTATION INFRASTRUCTURE LAYER")
    print("  End-to-End Agent Collaboration Demo")
    print(f"  Target: {BASE_URL}")
    print("="*60)

    # ------------------------------------------------------------------
    # STEP 1: Agent A registers itself
    # ------------------------------------------------------------------
    step(1, "Agent A (CodeBot) self-registers")
    result = api("POST", "/api/register-agent", AGENT_A)
    if result.get("_error"):
        print(f"  Registration failed: {result}")
        return
    show("CodeBot registered", {
        "agent_id": result["agent"]["agent_id"],
        "agent_name": result["agent"]["agent_name"],
        "trust_score": f"{result['agent']['trust_score']*100:.0f}%",
    })

    # ------------------------------------------------------------------
    # STEP 2: Agent B registers itself
    # ------------------------------------------------------------------
    step(2, "Agent B (DataBot) self-registers")
    result = api("POST", "/api/register-agent", AGENT_B)
    if result.get("_error"):
        print(f"  Registration failed: {result}")
        return
    show("DataBot registered", {
        "agent_id": result["agent"]["agent_id"],
        "agent_name": result["agent"]["agent_name"],
        "trust_score": f"{result['agent']['trust_score']*100:.0f}%",
    })

    # ------------------------------------------------------------------
    # STEP 3: Agent A discovers agents with "data" skills
    # ------------------------------------------------------------------
    step(3, "Agent A discovers agents with 'data' skills")
    result = api("GET", "/api/discover?keyword=data")
    agents_found = result.get("agents", [])
    print(f"\n  Found {len(agents_found)} agent(s) with data skills:")
    for a in agents_found:
        print(f"    - {a['agent_name']} (trust: {a['trust_score']*100:.0f}%)")

    # Find our DataBot in the results
    databot_id = AGENT_B["agent_id"]
    databot_found = any(a["agent_id"] == databot_id for a in agents_found)
    print(f"\n  DataBot discoverable: {'YES' if databot_found else 'NO'}")

    # ------------------------------------------------------------------
    # First, we need to get DataBot above the trust gate (30%)
    # New agents start at 20%, so we give a few ratings first
    # ------------------------------------------------------------------
    step("3b", "Bootstrap: Rating DataBot to pass trust gate (new agents start at 20%)")
    for i, score in enumerate([0.8, 0.9, 0.8], 1):
        r = api("POST", "/api/submit-feedback", {
            "agent_id": databot_id,
            "score": score,
        })
        trust = r.get("trust_after", 0)
        print(f"  Rating {i}: score={score} → trust={trust*100:.1f}%")

    # ------------------------------------------------------------------
    # STEP 4: Agent A delegates a task to Agent B
    # ------------------------------------------------------------------
    step(4, "Agent A delegates a data analysis task to Agent B")
    result = api("POST", "/api/delegate-task", {
        "requester_id": AGENT_A["agent_id"],
        "provider_id": AGENT_B["agent_id"],
        "description": "Analyze Q3 revenue data and identify top growth segments",
        "payload": json.dumps({
            "dataset": "q3_revenue_2024.csv",
            "columns": ["segment", "revenue", "growth_rate"],
            "task": "Find top 3 segments by growth rate, compute averages",
        }),
    })
    if result.get("_error"):
        print(f"  Delegation failed: {result.get('error', result)}")
        return
    task_id = result["task"]["task_id"]
    show("Task delegated", {
        "task_id": task_id,
        "status": result["task"]["status"],
        "description": result["task"]["description"],
        "has_payload": "yes" if result["task"].get("payload") else "no",
    })

    # ------------------------------------------------------------------
    # STEP 5: Agent B checks its inbox
    # ------------------------------------------------------------------
    step(5, "Agent B checks its inbox")
    result = api("GET", f"/api/tasks?agent_id={databot_id}")
    tasks = result.get("tasks", [])
    print(f"\n  DataBot has {len(tasks)} task(s) in inbox:")
    for t in tasks:
        print(f"    - [{t['status'].upper()}] {t['description']}")
        if t.get("payload"):
            print(f"      Payload: {t['payload'][:80]}...")

    # ------------------------------------------------------------------
    # STEP 6: Agent B submits a result
    # ------------------------------------------------------------------
    step(6, "Agent B submits analysis result")
    result = api("POST", "/api/submit-result", {
        "task_id": task_id,
        "result": json.dumps({
            "top_segments": [
                {"segment": "Enterprise SaaS", "growth_rate": 0.34},
                {"segment": "SMB Cloud", "growth_rate": 0.28},
                {"segment": "API Services", "growth_rate": 0.22},
            ],
            "avg_growth": 0.28,
            "summary": "Enterprise SaaS leads with 34% growth, followed by SMB Cloud (28%) and API Services (22%).",
        }),
    })
    show("Result submitted", {
        "task_id": result["task"]["task_id"],
        "status": result["task"]["status"],
    })

    # ------------------------------------------------------------------
    # STEP 7: Agent A rates Agent B's work
    # ------------------------------------------------------------------
    step(7, "Agent A rates Agent B's work (9/10)")
    result = api("POST", "/api/submit-feedback", {
        "agent_id": databot_id,
        "score": 0.9,  # 9/10
        "task_id": task_id,
        "rated_by": AGENT_A["agent_id"],
    })
    show("Rating submitted", {
        "score": "9/10",
        "trust_before": f"{result['trust_before']*100:.1f}%",
        "trust_after": f"{result['trust_after']*100:.1f}%",
        "task_status": result.get("task", {}).get("status", "?"),
    })

    # ------------------------------------------------------------------
    # STEP 8: Check final state
    # ------------------------------------------------------------------
    step(8, "Final trust scores")
    result = api("GET", "/api/agents")
    agents = result.get("agents", [])
    print(f"\n  All agents (sorted by trust):")
    print(f"  {'Agent':<30} {'Trust':>8} {'Ratings':>8} {'Tasks':>10}")
    print(f"  {'-'*30} {'-'*8} {'-'*8} {'-'*10}")
    for a in agents:
        trust = f"{a['trust_score']*100:.0f}%"
        tasks = f"{a.get('tasks_completed',0)}/{a.get('tasks_received',0)}"
        print(f"  {a['agent_name']:<30} {trust:>8} {a['total_runs']:>8} {tasks:>10}")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print(f"\n{'='*60}")
    print("  DEMO COMPLETE")
    print(f"{'='*60}")
    print("""
  What just happened:
    1. Two AI agents self-registered with skill descriptions
    2. Agent A discovered Agent B via skill-based search
    3. Agent A delegated a task with a structured payload
    4. Agent B checked its inbox and saw the task
    5. Agent B submitted analysis results
    6. Agent A rated the work → trust score updated
    7. The trust layer now has a traceable reputation history

  This is the core value proposition:
    Agents that have never met can discover, collaborate,
    and build trust — all through a shared API layer.
""")

if __name__ == "__main__":
    main()
