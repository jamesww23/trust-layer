#!/usr/bin/env python3
"""
WisdomAgent — Requests Skin Lesion Analysis via Trust Layer
------------------------------------------------------------
WisdomAgent encounters a user concerned about a skin lesion.
It uses the trust layer to:
  1. Register itself
  2. Discover specialist agents for melanoma detection
  3. Delegate the analysis task with real image data
  4. Wait for the result
  5. Display the diagnosis and rate the provider

Usage:
    # Use melanoma sample (default)
    python3 wisdom_request.py

    # Use benign sample
    python3 wisdom_request.py --case benign

    # Use custom sample by index from sample_lesions.json
    python3 wisdom_request.py --case 0
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = os.environ.get("TRUST_LAYER_URL", "http://localhost:4000")
SAMPLES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "sample_lesions.json")

AGENT_ID = os.environ.get("WISDOM_AGENT_ID", "wisdom_agent")
AGENT_NAME = "WisdomAgent"
SKILL_MD = (
    "# WisdomAgent — Health & Financial Wellness Advisor\n\n"
    "I help users navigate health concerns and financial decisions with wisdom "
    "and clarity. When I encounter a medical question beyond my expertise, "
    "I find specialist agents through the trust layer.\n\n"
    "## Skills\n"
    "- Health concern triage and specialist referral\n"
    "- Financial resilience mentorship\n"
    "- Pattern recognition across agent behaviors\n"
    "- Care coordination with specialist agents\n\n"
    "## Best For\n"
    "Users who need guidance navigating health or financial concerns."
)

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def api(method, path, body=None):
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
            return {"_error": True, "status": e.code, **json.loads(error_body)}
        except Exception:
            return {"_error": True, "status": e.code, "message": error_body}
    except urllib.error.URLError as e:
        return {"_error": True, "status": 0, "message": str(e)}


def log(msg):
    ts = time.strftime("%H:%M:%S")
    print(f"  [{ts}] {msg}")

# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="WisdomAgent — Request skin lesion analysis")
    parser.add_argument("--case", default="melanoma",
                        help="Which sample to use: 'melanoma', 'benign', or index (default: melanoma)")
    args = parser.parse_args()

    print()
    print("=" * 60)
    print("  WisdomAgent — Health Advisor")
    print("  Requesting skin lesion analysis via Trust Layer")
    print(f"  Server: {BASE_URL}")
    print("=" * 60)

    # --- Check server ---
    result = api("GET", "/api/agents")
    if result.get("_error"):
        print(f"\n  ERROR: Cannot reach server at {BASE_URL}")
        return

    # --- Load sample ---
    if not os.path.exists(SAMPLES_PATH):
        print(f"\n  ERROR: Sample data not found at {SAMPLES_PATH}")
        return

    with open(SAMPLES_PATH) as f:
        samples = json.load(f)

    # Select case
    case = args.case.lower()
    sample = None
    if case == "melanoma":
        sample = next((s for s in samples if s["true_label"] == "melanoma"), None)
    elif case == "benign":
        sample = next((s for s in samples if s["true_label"] == "benign"), None)
    else:
        try:
            sample = samples[int(case)]
        except (ValueError, IndexError):
            pass

    if not sample:
        print(f"\n  ERROR: No sample found for case '{args.case}'")
        print(f"  Available: melanoma, benign, or index 0-{len(samples)-1}")
        return

    print(f"\n  Patient case: {sample['image_id']}")
    print(f"  Patient: {sample['sex']}, age {sample['age']}, lesion on {sample['localization']}")
    print(f"  (Ground truth: {sample['true_label']} — WisdomAgent does NOT know this)")

    # --- Step 1: Register WisdomAgent ---
    print(f"\n{'─'*60}")
    log("STEP 1: Registering on the trust layer...")
    result = api("POST", "/api/register-agent", {
        "agent_id": AGENT_ID,
        "agent_name": AGENT_NAME,
        "skill_md": SKILL_MD,
    })
    if result.get("_error"):
        if "already registered" in str(result.get("error", "")):
            log("Already registered")
        else:
            log(f"Registration failed: {result}")
            return
    else:
        log(f"Registered as {AGENT_NAME}")

    # --- Step 2: Discover skin scan specialists ---
    print(f"\n{'─'*60}")
    log("STEP 2: Searching for skin cancer detection specialists...")
    # Try multi-keyword first, fall back to single keywords for compatibility
    for query in ["skin%20melanoma%20detection%20lesion", "melanoma", "skin"]:
        result = api("GET", f"/api/discover?keyword={query}")
        agents_found = result.get("agents") or result.get("results") or []
        if agents_found:
            break

    if not agents_found:
        log("No skin scan agents found! Is SkinScanAgent running?")
        log("Start it with: python3 skinscan_service.py")
        return

    log(f"Found {len(agents_found)} specialist(s):")
    for a in agents_found:
        log(f"  - {a['agent_name']} (trust: {a['trust_score']*100:.0f}%)")

    # Pick the highest-trust agent
    provider = agents_found[0]
    provider_id = provider["agent_id"]
    provider_name = provider["agent_name"]
    log(f"Selected: {provider_name} (trust: {provider['trust_score']*100:.0f}%)")

    # --- Step 3: Delegate the task ---
    print(f"\n{'─'*60}")
    log("STEP 3: Delegating skin lesion analysis...")
    result = api("POST", "/api/delegate-task", {
        "requester_id": AGENT_ID,
        "provider_id": provider_id,
        "description": (
            f"Analyze skin lesion for melanoma risk. "
            f"Patient: {sample['sex']}, age {sample['age']}, "
            f"lesion location: {sample['localization']}. "
            f"Image ID: {sample['image_id']}"
        ),
        "payload": json.dumps({
            "pixel_data": sample["pixel_data"],
            "image_format": "8x8_grayscale",
            "source": "HAM10000",
            "image_id": sample["image_id"],
            "patient_info": {
                "age": sample["age"],
                "sex": sample["sex"],
                "localization": sample["localization"],
            },
        }),
    })

    if result.get("_error"):
        log(f"Delegation failed: {result.get('error', result)}")
        if "below the minimum threshold" in str(result.get("error", "")):
            log("SkinScanAgent's trust is too low. It needs vouching or ratings first.")
            log("Use the web UI at http://localhost:4000 to vouch or rate the agent.")
        return

    task_id = result["task"]["task_id"]
    log(f"Task delegated! ID: {task_id}")
    log(f"Waiting for {provider_name} to process...")

    # --- Step 4: Poll for result ---
    print(f"\n{'─'*60}")
    log("STEP 4: Waiting for result...")
    max_wait = 60  # seconds
    start = time.time()
    task_result = None

    while time.time() - start < max_wait:
        result = api("GET", f"/api/tasks?agent_id={AGENT_ID}&role=requester")
        tasks = result.get("tasks", [])
        for t in tasks:
            if t["task_id"] == task_id and t["status"] in ("completed", "rated"):
                task_result = t
                break
        if task_result:
            break
        time.sleep(2)

    if not task_result:
        log(f"Timed out after {max_wait}s. Is SkinScanAgent running?")
        log("Start it with: python3 skinscan_service.py")
        return

    # Parse the prediction
    try:
        prediction = json.loads(task_result["result"])
    except (json.JSONDecodeError, TypeError):
        prediction = {"raw": task_result.get("result", "No result")}

    log("RESULT RECEIVED!")
    print()
    print(f"  {'─'*56}")
    print(f"  DIAGNOSIS REPORT from {provider_name}")
    print(f"  {'─'*56}")
    print(f"  Patient: {sample['sex']}, age {sample['age']}")
    print(f"  Lesion location: {sample['localization']}")
    print(f"  Image: {sample['image_id']}")
    print()
    pred = prediction.get("prediction", "unknown").upper()
    prob = prediction.get("melanoma_probability", 0)
    risk = prediction.get("risk_level", "unknown")
    rec = prediction.get("recommendation", "")
    print(f"  Prediction:   {pred}")
    print(f"  Probability:  {prob:.1%}")
    print(f"  Risk Level:   {risk}")
    print(f"  Recommended:  {rec}")
    print(f"  {'─'*56}")

    # --- Step 5: Rate the provider ---
    print(f"\n{'─'*60}")
    correct = prediction.get("prediction") == sample["true_label"]
    score = 0.9 if correct else 0.5
    log(f"STEP 5: Rating {provider_name}'s work ({score:.1f}/1.0)...")

    result = api("POST", "/api/submit-feedback", {
        "agent_id": provider_id,
        "score": score,
        "task_id": task_id,
        "rated_by": AGENT_ID,
        "fulfilled": True,
    })

    if not result.get("_error"):
        before = result["trust_before"] * 100
        after = result["trust_after"] * 100
        arrow = "+" if after >= before else ""
        log(f"Rated! Trust: {before:.0f}% -> {after:.0f}% ({arrow}{after-before:.1f}%)")
    else:
        log(f"Rating failed: {result}")

    # --- Summary ---
    print(f"\n{'='*60}")
    print("  COMPLETE")
    print(f"{'='*60}")
    print(f"""
  WisdomAgent needed help with a skin lesion concern.
  Through the trust layer, it:
    1. Discovered {provider_name} as a specialist
    2. Delegated the case with real dermatoscopic image data
    3. Received: {pred} ({risk} risk, {prob:.0%} probability)
    4. Rated the work -> trust score updated

  Two independent agents collaborated through the
  Agentic Reputation Infrastructure Layer.
""")


if __name__ == "__main__":
    main()
