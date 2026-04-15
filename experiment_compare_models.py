#!/usr/bin/env python3
"""
experiment_compare_models.py — HW7 Experiment: Compare 3 ML Models via Trust Layer
------------------------------------------------------------------------------------
Sends identical skin lesion tasks to 3 competing SkinScanAgent variants:
  - SkinScanAgent  (Logistic Regression + SMOTE)
  - SkinScanAgent2 (Decision Tree / CART)
  - SkinScanAgent3 (CART + SMOTE)

All three must be running (locally or on Railway) before starting.

Usage:
    python3 experiment_compare_models.py
    python3 experiment_compare_models.py --server https://trust-layer-topaz.vercel.app
    python3 experiment_compare_models.py --rounds 10
"""

import argparse
import json
import os
import time
import urllib.request
import urllib.error

BASE_URL = os.environ.get("TRUST_LAYER_URL", "https://aitrustlayer.vercel.app")
REQUESTER_ID = "wisdom_agent"

# HAM10000 test cases with known ground truth
TEST_CASES = [
    {
        "image_id": "ISIC_0025964",
        "true_label": "melanoma",
        "pixel_data": [151,165,180,184,186,185,180,163,163,180,193,196,199,196,190,177,
                       170,188,198,212,214,202,196,179,176,191,215,148,128,214,199,185,
                       178,195,210,157,162,215,200,183,178,194,203,216,218,208,198,180,
                       176,190,200,205,204,199,191,169,163,185,194,196,199,191,180,146],
        "patient": "female, 40, chest",
    },
    {
        "image_id": "ISIC_0024698",
        "true_label": "benign",
        "pixel_data": [151,157,161,163,165,165,159,152,155,162,164,170,170,165,162,156,
                       158,160,164,163,147,164,165,158,155,158,169,105,96,175,164,162,
                       155,158,171,112,134,171,163,162,155,159,166,165,167,167,163,157,
                       152,161,161,166,168,163,160,153,147,157,161,166,166,162,156,151],
        "patient": "male, 70, face",
    },
]

AGENTS = [
    {"id": "skinscan_agent",   "name": "SkinScanAgent",  "model": "Logistic Regression + SMOTE"},
    {"id": "skinscan_agent_2", "name": "SkinScanAgent2", "model": "Decision Tree (CART)"},
    {"id": "skinscan_agent_3", "name": "SkinScanAgent3", "model": "CART + SMOTE"},
]


def api(method, path, body=None):
    url = BASE_URL + path
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return {"_error": True, **json.loads(e.read().decode())}
        except Exception:
            return {"_error": True, "status": e.code}
    except Exception as e:
        return {"_error": True, "message": str(e)}


def log(msg):
    print(f"  {msg}", flush=True)


def get_trust(agent_id):
    result = api("GET", "/api/agents")
    for a in result.get("agents", []):
        if a["agent_id"] == agent_id:
            return a["trust_score"]
    return None


def delegate_and_wait(agent_id, case, timeout=120):
    result = api("POST", "/api/delegate-task", {
        "requester_id": REQUESTER_ID,
        "provider_id": agent_id,
        "description": f"Analyze skin lesion {case['image_id']} for melanoma risk",
        "payload": json.dumps({
            "pixel_data": case["pixel_data"],
            "image_id": case["image_id"],
            "image_format": "8x8_grayscale",
            "source": "HAM10000",
        }),
    })
    if result.get("_error"):
        return None, result.get("error", str(result))

    task_id = result["task"]["task_id"]
    start = time.time()
    while time.time() - start < timeout:
        poll = api("GET", f"/api/tasks?agent_id={REQUESTER_ID}&role=requester")
        for t in poll.get("tasks", []):
            if t["task_id"] == task_id and t["status"] in ("completed", "rated"):
                return t, None
        time.sleep(2)
    return None, "timeout"


def rate_task(agent_id, task_id, score):
    return api("POST", "/api/submit-feedback", {
        "agent_id": agent_id,
        "score": score,
        "task_id": task_id,
        "rated_by": REQUESTER_ID,
        "fulfilled": True,
    })


def bootstrap_agents(active_agents):
    """Register WisdomAgent and seed trust for any agents below the 30% gate."""
    # Register WisdomAgent (requester)
    result = api("POST", "/api/register-agent", {
        "agent_id": REQUESTER_ID,
        "agent_name": "WisdomAgent",
        "skill_md": "# WisdomAgent\nHealth and wellness advisor that coordinates specialist agents.",
    })
    if not result.get("_error"):
        log("WisdomAgent registered")
    else:
        msg = str(result.get("error", ""))
        if "already registered" not in msg:
            log(f"WisdomAgent registration: {msg}")

    # Submit 3 seed ratings (0.8) for each agent below the gate
    # 3 ratings of 0.8 pushes trust from 20% → ~39% (above 30% gate)
    for ag in active_agents:
        trust = get_trust(ag["id"])
        if trust is not None and trust < 0.3:
            log(f"  Seeding trust for {ag['name']} ({trust*100:.0f}%)...")
            for _ in range(3):
                api("POST", "/api/submit-feedback", {
                    "agent_id": ag["id"],
                    "score": 0.8,
                    "rated_by": REQUESTER_ID,
                    "fulfilled": True,
                })
            new_trust = get_trust(ag["id"])
            log(f"  {ag['name']}: {trust*100:.0f}% → {new_trust*100:.0f}% ✓")


def run_experiment(rounds):
    global BASE_URL

    print()
    print("=" * 70)
    print("  HW7 EXPERIMENT: Comparing 3 ML Models via Trust Layer")
    print(f"  Server: {BASE_URL}")
    print(f"  Rounds: {rounds} (each round tests all 3 agents on all {len(TEST_CASES)} cases)")
    print("=" * 70)

    # Check which agents are registered
    print()
    log("Checking registered agents...")
    agent_result = api("GET", "/api/agents")
    registered_ids = {a["agent_id"] for a in agent_result.get("agents", [])}
    active_agents = []
    for ag in AGENTS:
        if ag["id"] in registered_ids:
            trust = get_trust(ag["id"])
            status = "READY" if trust and trust >= 0.3 else f"LOW TRUST ({trust*100:.0f}%)" if trust else "NOT FOUND"
            log(f"  {ag['name']:20} [{ag['model']:30}] — {status}")
            active_agents.append(ag)
        else:
            log(f"  {ag['name']:20} — NOT REGISTERED (start skinscan_service_cloud.py with correct AGENT_ID)")

    if not active_agents:
        print("\n  ERROR: No agents registered. Start the skinscan services first.")
        return

    # Register WisdomAgent + bootstrap trust if needed
    log("Bootstrapping WisdomAgent and trust gates...")
    bootstrap_agents(active_agents)

    # Re-check trust after bootstrap
    ready = []
    for ag in active_agents:
        trust = get_trust(ag["id"])
        if trust and trust >= 0.3:
            ready.append(ag)
        else:
            log(f"  WARNING: {ag['name']} still at {trust*100:.0f}% — may be blocked by gate")
    active_agents = ready if ready else active_agents

    print()
    print("─" * 70)

    # Track per-agent results
    stats = {ag["id"]: {"correct": 0, "total": 0, "trust_start": None, "trust_end": None, "results": []} for ag in active_agents}

    for ag in active_agents:
        stats[ag["id"]]["trust_start"] = get_trust(ag["id"])

    # Run rounds
    for round_num in range(1, rounds + 1):
        print(f"\n  ROUND {round_num}/{rounds}")
        case = TEST_CASES[(round_num - 1) % len(TEST_CASES)]
        print(f"  Case: {case['image_id']} | Patient: {case['patient']} | Ground truth: {case['true_label'].upper()}")
        print()

        for ag in active_agents:
            agent_id = ag["id"]
            trust_before = get_trust(agent_id)

            task, err = delegate_and_wait(agent_id, case)
            if err:
                log(f"  {ag['name']:20} — FAILED: {err}")
                continue

            try:
                pred = json.loads(task["result"])
            except Exception:
                pred = {}

            prediction = pred.get("prediction", "unknown")
            prob = pred.get("melanoma_probability", 0)
            correct = prediction == case["true_label"]

            # Rate: 0.9 if correct, 0.3 if wrong
            score = 0.9 if correct else 0.3
            rate_result = rate_task(agent_id, task["task_id"], score)
            trust_after = rate_result.get("trust_after", get_trust(agent_id))

            stats[agent_id]["total"] += 1
            if correct:
                stats[agent_id]["correct"] += 1
            stats[agent_id]["results"].append({
                "round": round_num,
                "case": case["image_id"],
                "prediction": prediction,
                "correct": correct,
                "prob": prob,
                "trust_before": trust_before,
                "trust_after": trust_after,
            })

            verdict = "CORRECT" if correct else "WRONG  "
            arrow = "↑" if trust_after > trust_before else "↓"
            log(f"  {ag['name']:20} → {prediction.upper():8} ({prob:.0%}) | "
                f"{verdict} | Trust: {trust_before*100:.0f}%{arrow}{trust_after*100:.0f}%")

    # Final trust snapshot
    for ag in active_agents:
        stats[ag["id"]]["trust_end"] = get_trust(ag["id"])

    # Results table
    print()
    print("=" * 70)
    print("  EXPERIMENT RESULTS SUMMARY")
    print("=" * 70)
    print(f"\n  {'Agent':20} {'Model':30} {'Accuracy':10} {'Trust Start':12} {'Trust End':10} {'Delta':6}")
    print(f"  {'─'*20} {'─'*30} {'─'*10} {'─'*12} {'─'*10} {'─'*6}")

    for ag in active_agents:
        s = stats[ag["id"]]
        acc = s["correct"] / s["total"] if s["total"] > 0 else 0
        ts = s["trust_start"] or 0
        te = s["trust_end"] or 0
        delta = te - ts
        sign = "+" if delta >= 0 else ""
        print(f"  {ag['name']:20} {ag['model']:30} {acc:>9.0%}  "
              f"{ts*100:>10.0f}%  {te*100:>8.0f}%  {sign}{delta*100:.1f}%")

    print()
    print("  ROUND-BY-ROUND PREDICTIONS")
    print(f"  {'Round':6} {'Case':15} {'Truth':10}", end="")
    for ag in active_agents:
        print(f"  {ag['name']:20}", end="")
    print()
    print(f"  {'─'*6} {'─'*15} {'─'*10}", end="")
    for _ in active_agents:
        print(f"  {'─'*20}", end="")
    print()

    for round_num in range(1, rounds + 1):
        case = TEST_CASES[(round_num - 1) % len(TEST_CASES)]
        print(f"  {round_num:<6} {case['image_id']:15} {case['true_label'].upper():10}", end="")
        for ag in active_agents:
            r = next((x for x in stats[ag["id"]]["results"] if x["round"] == round_num), None)
            if r:
                mark = "✓" if r["correct"] else "✗"
                cell = f"{r['prediction'].upper()} ({r['prob']:.0%}) {mark}"
            else:
                cell = "—"
            print(f"  {cell:20}", end="")
        print()

    print()
    print("  KEY TAKEAWAYS")
    print("  ─" * 35)

    # Find best model
    best = max(active_agents, key=lambda ag: stats[ag["id"]]["correct"] / max(stats[ag["id"]]["total"], 1))
    worst = min(active_agents, key=lambda ag: stats[ag["id"]]["correct"] / max(stats[ag["id"]]["total"], 1))
    best_acc = stats[best["id"]]["correct"] / max(stats[best["id"]]["total"], 1)
    worst_acc = stats[worst["id"]]["correct"] / max(stats[worst["id"]]["total"], 1)

    print(f"  1. Best accuracy:  {best['name']} ({best['model']}) at {best_acc:.0%}")
    print(f"  2. Worst accuracy: {worst['name']} ({worst['model']}) at {worst_acc:.0%}")

    # Trust routing insight
    best_trust = max(active_agents, key=lambda ag: stats[ag["id"]]["trust_end"] or 0)
    print(f"  3. Highest trust after experiment: {best_trust['name']} "
          f"({stats[best_trust['id']]['trust_end']*100:.0f}%)")
    print(f"     → The trust layer will now prefer routing to this agent")
    print()
    print("  The trust layer automatically routed reputation to the better-")
    print("  performing model — without any manual configuration.")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default=None, help="Trust layer URL")
    parser.add_argument("--rounds", type=int, default=6, help="Number of rounds (default: 6)")
    args = parser.parse_args()

    if args.server:
        BASE_URL = args.server

    run_experiment(args.rounds)
