#!/usr/bin/env python3
"""
analyze_image.py — Submit a real skin lesion photo to SkinScanAgent via Trust Layer
-------------------------------------------------------------------------------------
Converts any skin lesion image to the 8x8 grayscale format expected by SkinScanAgent,
then runs the full WisdomAgent -> Trust Layer -> SkinScanAgent flow.

Requirements:
    pip install Pillow

Usage:
    # Analyze a real image file
    python3 analyze_image.py /path/to/lesion.jpg

    # Analyze against live site
    python3 analyze_image.py /path/to/lesion.jpg --server https://trust-layer-topaz.vercel.app

    # Test with a HAM10000 sample (no image needed)
    python3 analyze_image.py --sample melanoma
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

WISDOM_ID = os.environ.get("WISDOM_AGENT_ID", "wisdom_agent")
SKINSCAN_ID = os.environ.get("SKINSCAN_AGENT_ID", "skinscan_agent")

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
# Image preprocessing
# ---------------------------------------------------------------------------

def image_to_pixels(image_path):
    """Convert any image to 64 grayscale pixel values (8x8)."""
    try:
        from PIL import Image
    except ImportError:
        print("\n  ERROR: Pillow is required to process image files.")
        print("  Install it with: pip install Pillow")
        sys.exit(1)

    img = Image.open(image_path)
    # Convert to grayscale
    img = img.convert("L")
    # Resize to 8x8 using high-quality resampling
    img = img.resize((8, 8), Image.LANCZOS)
    # Extract pixel values as a flat list
    pixels = list(img.getdata())
    return pixels


def load_sample(case):
    """Load a sample from sample_lesions.json for testing."""
    if not os.path.exists(SAMPLES_PATH):
        print(f"\n  ERROR: Sample file not found at {SAMPLES_PATH}")
        sys.exit(1)
    with open(SAMPLES_PATH) as f:
        samples = json.load(f)
    case = case.lower()
    if case == "melanoma":
        sample = next((s for s in samples if s["true_label"] == "melanoma"), None)
    elif case == "benign":
        sample = next((s for s in samples if s["true_label"] == "benign"), None)
    else:
        try:
            sample = samples[int(case)]
        except (ValueError, IndexError):
            sample = None
    if not sample:
        print(f"\n  ERROR: No sample found for '{case}'")
        sys.exit(1)
    return sample

# ---------------------------------------------------------------------------
# Trust Layer flow
# ---------------------------------------------------------------------------

def ensure_registered(agent_id, agent_name, skill_md):
    result = api("POST", "/api/register-agent", {
        "agent_id": agent_id,
        "agent_name": agent_name,
        "skill_md": skill_md,
    })
    if result.get("_error"):
        if "already registered" in str(result.get("error", "")):
            log(f"{agent_name}: Already registered")
        else:
            log(f"{agent_name}: Registration failed: {result}")
            return False
    else:
        trust = result.get("agent", {}).get("trust_score", 0)
        log(f"{agent_name}: Registered (trust: {trust*100:.0f}%)")
    return True


def find_skinscan_agent():
    """Discover SkinScanAgent via trust layer."""
    for query in ["skin%20melanoma%20detection%20lesion", "melanoma", "skin", "skinscan"]:
        result = api("GET", f"/api/discover?keyword={query}")
        agents = result.get("agents") or result.get("results") or []
        if agents:
            return agents[0]
    return None


def delegate_and_wait(pixel_data, image_path, max_wait=90):
    """Delegate to SkinScanAgent and wait for result."""
    # Find provider
    provider = find_skinscan_agent()
    if not provider:
        log("ERROR: SkinScanAgent not found. Is skinscan_service.py running?")
        return None, None

    provider_id = provider["agent_id"]
    provider_name = provider["agent_name"]
    log(f"Found: {provider_name} (trust: {provider['trust_score']*100:.0f}%)")

    # Delegate
    fname = os.path.basename(image_path) if image_path else "uploaded_image"
    result = api("POST", "/api/delegate-task", {
        "requester_id": WISDOM_ID,
        "provider_id": provider_id,
        "description": (
            f"Analyze skin lesion image '{fname}' for melanoma risk. "
            f"Image preprocessed to 8x8 grayscale."
        ),
        "payload": json.dumps({
            "pixel_data": pixel_data,
            "image_format": "8x8_grayscale",
            "source": "user_upload",
            "image_id": fname,
            "patient_info": {
                "source_image": fname,
                "note": "Real photo converted to 8x8 grayscale for screening",
            },
        }),
    })

    if result.get("_error"):
        log(f"Delegation failed: {result.get('error', result)}")
        if "below the minimum threshold" in str(result.get("error", "")):
            log("SkinScanAgent's trust is too low.")
            log("Run skinscan_service.py first, then use the web UI to vouch it.")
        return None, None

    task_id = result["task"]["task_id"]
    log(f"Task delegated: {task_id}")
    log(f"Waiting for {provider_name} to process...")

    # Poll for result
    start = time.time()
    while time.time() - start < max_wait:
        result = api("GET", f"/api/tasks?agent_id={WISDOM_ID}&role=requester")
        for t in result.get("tasks", []):
            if t["task_id"] == task_id and t["status"] in ("completed", "rated"):
                return t, provider
        time.sleep(2)

    log(f"Timed out after {max_wait}s.")
    return None, provider

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global BASE_URL
    parser = argparse.ArgumentParser(description="Analyze a skin lesion image via SkinScanAgent")
    parser.add_argument("image", nargs="?", help="Path to skin lesion image (JPG/PNG)")
    parser.add_argument("--sample", default=None,
                        help="Use a HAM10000 sample instead: 'melanoma', 'benign', or index")
    parser.add_argument("--server", default=None,
                        help=f"Trust layer server URL (default: {BASE_URL})")
    args = parser.parse_args()

    if args.server:
        BASE_URL = args.server

    if not args.image and not args.sample:
        parser.print_help()
        print("\n  Example: python3 analyze_image.py my_lesion.jpg")
        print("  Example: python3 analyze_image.py --sample melanoma")
        sys.exit(1)

    print()
    print("=" * 60)
    print("  WisdomAgent — Skin Lesion Analysis")
    print(f"  Server: {BASE_URL}")
    print("=" * 60)

    # Check server
    result = api("GET", "/api/agents")
    if result.get("_error"):
        print(f"\n  ERROR: Cannot reach server at {BASE_URL}")
        print("  Start it with: python3 server.py 4000")
        return

    # --- Prepare pixel data ---
    if args.image:
        if not os.path.exists(args.image):
            print(f"\n  ERROR: Image file not found: {args.image}")
            return
        print(f"\n  Image: {args.image}")
        log("Converting image to 8x8 grayscale...")
        pixel_data = image_to_pixels(args.image)
        image_id = os.path.basename(args.image)
        true_label = None  # unknown for real uploads
        patient_note = "Real uploaded image"
    else:
        sample = load_sample(args.sample)
        pixel_data = sample["pixel_data"]
        image_id = sample["image_id"]
        true_label = sample["true_label"]
        print(f"\n  Sample: {image_id}")
        print(f"  Patient: {sample['sex']}, age {sample['age']}, {sample['localization']}")
        if true_label:
            print(f"  (Ground truth: {true_label} — shown for demo purposes)")
        patient_note = "HAM10000 sample"

    print(f"  Pixel values: [{pixel_data[0]}, {pixel_data[1]}, ... {pixel_data[-1]}] (64 values)")

    # --- Step 1: Register agents ---
    print(f"\n{'─'*60}")
    log("STEP 1: Registering agents...")

    ensure_registered(WISDOM_ID, "WisdomAgent",
        "# WisdomAgent — Health & Financial Wellness Advisor\n\n"
        "I help users navigate health concerns and financial decisions.\n\n"
        "## Skills\n- Health concern triage and specialist referral\n"
        "- Care coordination with specialist agents\n\n"
        "## Best For\nUsers who need guidance navigating health or financial concerns.")

    # --- Step 2: Discover SkinScanAgent ---
    print(f"\n{'─'*60}")
    log("STEP 2: Discovering SkinScanAgent...")

    # --- Step 3-4: Delegate and wait ---
    print(f"\n{'─'*60}")
    log("STEP 3: Delegating to SkinScanAgent...")
    task, provider = delegate_and_wait(pixel_data, args.image or image_id)

    if not task:
        print("\n  Could not get result. Is skinscan_service.py running?")
        print("  Start it: python3 skinscan_service.py")
        return

    # Parse result
    try:
        prediction = json.loads(task["result"])
    except (json.JSONDecodeError, TypeError):
        prediction = {"raw": task.get("result", "No result")}

    pred = prediction.get("prediction", "unknown").upper()
    prob = prediction.get("melanoma_probability", 0)
    risk = prediction.get("risk_level", "unknown")
    rec = prediction.get("recommendation", "")

    # --- Display result ---
    print()
    print(f"  {'═'*56}")
    print(f"  DIAGNOSIS REPORT from {provider['agent_name']}")
    print(f"  {'─'*56}")
    print(f"  Image:        {image_id}")
    if true_label:
        print(f"  Ground Truth: {true_label.upper()}")
    print()
    print(f"  Prediction:   {pred}")
    print(f"  Probability:  {prob:.1%}")
    print(f"  Risk Level:   {risk}")
    print(f"  Recommended:  {rec}")
    print(f"  {'═'*56}")

    # --- Step 5: Rate the provider ---
    print(f"\n{'─'*60}")
    if true_label:
        correct = prediction.get("prediction") == true_label
        score = 0.9 if correct else 0.5
        verdict = "CORRECT" if correct else "INCORRECT"
        log(f"STEP 4: Rating (ground truth: {true_label}, prediction: {pred.lower()}) → {verdict}")
    else:
        score = 0.8  # default rating for real uploads
        log("STEP 4: Rating SkinScanAgent's work (0.8/1.0 for completed analysis)...")

    result = api("POST", "/api/submit-feedback", {
        "agent_id": provider["agent_id"],
        "score": score,
        "task_id": task["task_id"],
        "rated_by": WISDOM_ID,
        "fulfilled": True,
    })

    if not result.get("_error"):
        before = result["trust_before"] * 100
        after = result["trust_after"] * 100
        arrow = "+" if after >= before else ""
        log(f"Rated! Trust: {before:.0f}% -> {after:.0f}% ({arrow}{after-before:.1f}%)")
    else:
        log(f"Rating: {result}")

    # --- Summary ---
    print(f"\n{'='*60}")
    print("  ANALYSIS COMPLETE")
    print(f"{'='*60}")
    print(f"""
  WisdomAgent received a skin lesion image for evaluation.
  Through the trust layer, it:

    1. Registered on the infrastructure
    2. Discovered {provider['agent_name']} as a melanoma specialist
    3. Delegated the image analysis task
    4. Received: {pred} ({risk} risk, {prob:.0%} probability)
    5. Action: {rec}

  ⚠  DISCLAIMER: This is a screening-level demo using a
     Logistic Regression model trained on 8x8 pixel data.
     It is NOT a clinical diagnostic tool. Consult a
     dermatologist for any real medical concern.
""")


if __name__ == "__main__":
    main()
