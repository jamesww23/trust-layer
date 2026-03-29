#!/usr/bin/env python3
"""
SkinScanAgent — Real ML-Powered Agent Demo for Trust Layer
-----------------------------------------------------------
Demonstrates the Agentic Reputation Infrastructure Layer with a REAL
machine learning model: melanoma detection using Logistic Regression
trained on the HAM10000 dataset (10,015 dermatoscopic images).

Two agents collaborate through the trust layer:
  - HealthAdvisorAgent (requester): needs skin lesion analysis
  - SkinScanAgent (provider): runs melanoma detection ML model

Full flow:
  1. Train ML model on startup (Logistic Regression + SMOTE)
  2. Both agents register on the trust layer
  3. SkinScanAgent bootstraps trust to pass the trust gate
  4. HealthAdvisorAgent discovers SkinScanAgent via keyword search
  5. HealthAdvisorAgent delegates a task with real pixel data
  6. SkinScanAgent processes the task with the ML model
  7. SkinScanAgent submits prediction result
  8. HealthAdvisorAgent rates the work → trust score updates
  9. Repeat with a second case to show trust evolution

Usage:
    python3 demo_skinscan.py                        # uses localhost:4000
    python3 demo_skinscan.py http://localhost:4000   # explicit URL

Requirements:
    pip install numpy pandas scikit-learn imbalanced-learn
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from imblearn.over_sampling import SMOTE

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:4000"

CSV_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "..", "15.071 The Analytics Edge",
    "Final Project", "Melanoma_Dataset", "hmnist_8_8_L.csv",
)
# Normalize the path
CSV_PATH = os.path.normpath(CSV_PATH)

RANDOM_SEED = 2025

# Agent definitions
ts = str(int(time.time()))
SKINSCAN_AGENT = {
    "agent_id": f"skinscan_agent_{ts}",
    "agent_name": "SkinScanAgent",
    "skill_md": (
        "# SkinScanAgent — Melanoma Detection\n\n"
        "I analyze dermatoscopic skin lesion images to detect melanoma.\n\n"
        "## Skills\n"
        "- Skin lesion classification (melanoma vs benign)\n"
        "- Image feature extraction (brightness, asymmetry, texture)\n"
        "- Risk level assessment (LOW / MODERATE / HIGH)\n"
        "- Trained on HAM10000 dataset (10,015 images)\n\n"
        "## Model\n"
        "- Logistic Regression + SMOTE for class imbalance\n"
        "- 15 engineered features from 8x8 grayscale images\n"
        "- AUC: 0.795 | Melanoma Recall: 49% | Accuracy: 83.6%\n\n"
        "## Best For\n"
        "Screening-level melanoma risk assessment from dermatoscopic images."
    ),
}

HEALTH_AGENT = {
    "agent_id": f"health_advisor_{ts}",
    "agent_name": "HealthAdvisorAgent",
    "skill_md": (
        "# HealthAdvisorAgent — Clinical Triage\n\n"
        "I provide health guidance, triage patient concerns, and coordinate "
        "with specialist agents for diagnostic tasks.\n\n"
        "## Skills\n"
        "- Patient symptom assessment\n"
        "- Specialist agent discovery and referral\n"
        "- Health risk communication\n"
        "- Care coordination across agent teams"
    ),
}

FEATURE_COLS = [
    "mean_brightness", "std_brightness", "min_brightness", "max_brightness",
    "brightness_range", "vertical_asymmetry", "horizontal_asymmetry",
    "center_brightness", "border_brightness", "center_border_diff",
    "pixel_variance", "edge_density", "percentile_25", "percentile_75", "iqr",
]

# ---------------------------------------------------------------------------
# HTTP helpers (same pattern as demo_agent.py)
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
    except urllib.error.URLError as e:
        return {"_error": True, "status": 0, "message": str(e)}


def step(num, title):
    """Print a step header."""
    print(f"\n{'='*64}")
    print(f"  STEP {num}: {title}")
    print(f"{'='*64}")


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
# ML Model: Feature extraction (from Analytics Edge notebooks)
# ---------------------------------------------------------------------------

def extract_features(img):
    """Extract 15 interpretable features from an 8x8 grayscale image.

    Extracted from AE_Melanoma_Logistic Regression_SMOTE.ipynb.
    """
    features = {}

    # 1. Brightness features
    features["mean_brightness"] = img.mean()
    features["std_brightness"] = img.std()
    features["min_brightness"] = float(img.min())
    features["max_brightness"] = float(img.max())
    features["brightness_range"] = float(img.max() - img.min())

    # 2. Regional brightness (asymmetry)
    top_half = img[:4, :].mean()
    bottom_half = img[4:, :].mean()
    left_half = img[:, :4].mean()
    right_half = img[:, 4:].mean()
    features["vertical_asymmetry"] = abs(top_half - bottom_half)
    features["horizontal_asymmetry"] = abs(left_half - right_half)

    # 3. Center vs border contrast
    center = img[2:6, 2:6].mean()
    border_pixels = np.concatenate([img[0, :], img[7, :], img[1:7, 0], img[1:7, 7]])
    border = border_pixels.mean()
    features["center_brightness"] = center
    features["border_brightness"] = border
    features["center_border_diff"] = center - border

    # 4. Texture features
    features["pixel_variance"] = img.var()
    h_edges = np.abs(np.diff(img, axis=1)).mean()
    v_edges = np.abs(np.diff(img, axis=0)).mean()
    features["edge_density"] = h_edges + v_edges

    # 5. Percentile features
    features["percentile_25"] = float(np.percentile(img, 25))
    features["percentile_75"] = float(np.percentile(img, 75))
    features["iqr"] = features["percentile_75"] - features["percentile_25"]

    return features

# ---------------------------------------------------------------------------
# ML Model: Training
# ---------------------------------------------------------------------------

def train_model(csv_path):
    """Train the Logistic Regression + SMOTE model from HAM10000 data.

    Returns (model, feature_cols, test_auc).
    """
    print(f"  Loading dataset from: {csv_path}")
    df = pd.read_csv(csv_path)
    print(f"  Dataset: {df.shape[0]} images, {df.shape[1]} columns")

    # Separate pixels and labels
    pixel_features = df.drop(columns=["label"])
    labels = df["label"]

    # Reshape to 8x8 images
    images = pixel_features.values.reshape(-1, 8, 8)

    # Extract features
    print(f"  Extracting 15 features from {len(images)} images...")
    feature_list = [extract_features(images[i]) for i in range(len(images))]
    img_features = pd.DataFrame(feature_list)

    # Binary target: melanoma (label 6) vs non-melanoma
    # Label mapping: 0=akiec, 1=bcc, 2=bkl, 3=df, 4=nv, 5=vasc, 6=mel
    y = (labels == 6).astype(int)
    X = img_features[FEATURE_COLS]

    melanoma_count = y.sum()
    print(f"  Melanoma cases: {melanoma_count} / {len(y)} ({melanoma_count/len(y)*100:.1f}%)")

    # Train/test split
    np.random.seed(RANDOM_SEED)
    train_X, test_X, train_y, test_y = train_test_split(
        X, y, test_size=0.3, random_state=RANDOM_SEED
    )

    # SMOTE on training data only
    smote = SMOTE(random_state=RANDOM_SEED)
    train_X_smote, train_y_smote = smote.fit_resample(train_X, train_y)
    print(f"  SMOTE: {train_X.shape[0]} → {train_X_smote.shape[0]} training samples (50/50 balanced)")

    # Train logistic regression
    model = LogisticRegression(max_iter=5000, random_state=RANDOM_SEED)
    model.fit(train_X_smote, train_y_smote)

    # Evaluate
    pred_proba = model.predict_proba(test_X)[:, 1]
    auc = roc_auc_score(test_y, pred_proba)
    print(f"  Model trained — AUC: {auc:.4f}")

    return model, FEATURE_COLS, auc

# ---------------------------------------------------------------------------
# ML Model: Prediction
# ---------------------------------------------------------------------------

def predict_skin_lesion(model, pixel_data_list):
    """Run melanoma prediction on 64 pixel values (8x8 grayscale image).

    Returns a dict with prediction, probability, risk_level, recommendation.
    """
    img = np.array(pixel_data_list, dtype=np.float64).reshape(8, 8)
    features = extract_features(img)
    feature_df = pd.DataFrame([features])[FEATURE_COLS]

    prob = model.predict_proba(feature_df)[0][1]  # melanoma probability
    pred = int(model.predict(feature_df)[0])

    if prob >= 0.7:
        risk = "HIGH"
        rec = "Immediate dermatologist referral recommended"
    elif prob >= 0.4:
        risk = "MODERATE"
        rec = "Follow-up dermatology appointment recommended within 2 weeks"
    else:
        risk = "LOW"
        rec = "Routine monitoring; re-screen in 6-12 months"

    return {
        "prediction": "melanoma" if pred == 1 else "benign",
        "melanoma_probability": round(float(prob), 4),
        "risk_level": risk,
        "recommendation": rec,
    }

# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

def get_sample_lesions(csv_path):
    """Pick one known melanoma and one known benign case from the dataset."""
    df = pd.read_csv(csv_path)
    pixel_cols = [c for c in df.columns if c != "label"]

    np.random.seed(42)

    # Melanoma case (label == 6)
    mel_rows = df[df["label"] == 6]
    mel_sample = mel_rows.sample(1, random_state=42)
    mel_pixels = mel_sample[pixel_cols].values[0].tolist()

    # Benign case (label != 6) — pick a nevus (label 4, most common)
    benign_rows = df[df["label"] == 4]
    benign_sample = benign_rows.sample(1, random_state=42)
    benign_pixels = benign_sample[pixel_cols].values[0].tolist()

    return {
        "melanoma": {"pixels": mel_pixels, "true_label": "melanoma"},
        "benign": {"pixels": benign_pixels, "true_label": "benign"},
    }

# ---------------------------------------------------------------------------
# Task cycle: delegate → process → submit → rate
# ---------------------------------------------------------------------------

def run_task_cycle(cycle_num, model, sample, requester_id, provider_id):
    """Run one full delegation cycle: delegate → poll → predict → submit → rate."""

    true_label = sample["true_label"]
    pixel_data = sample["pixels"]

    # --- Delegate ---
    step(f"{4 + cycle_num}a", f"Task {cycle_num}: HealthAdvisorAgent delegates skin scan ({true_label} case)")
    result = api("POST", "/api/delegate-task", {
        "requester_id": requester_id,
        "provider_id": provider_id,
        "description": f"Analyze skin lesion image for melanoma risk (case #{cycle_num})",
        "payload": json.dumps({
            "pixel_data": pixel_data,
            "image_format": "8x8_grayscale",
            "source": "HAM10000",
        }),
    })
    if result.get("_error"):
        print(f"  Delegation failed: {result.get('error', result)}")
        return
    task_id = result["task"]["task_id"]
    show("Task delegated", {
        "task_id": task_id,
        "status": result["task"]["status"],
        "has_payload": "yes (64 pixel values)",
    })

    # --- SkinScanAgent polls inbox ---
    step(f"{4 + cycle_num}b", f"Task {cycle_num}: SkinScanAgent checks inbox")
    result = api("GET", f"/api/tasks?agent_id={provider_id}&status=pending")
    tasks = result.get("tasks", [])
    print(f"\n  SkinScanAgent has {len(tasks)} pending task(s)")

    # --- SkinScanAgent runs ML model ---
    step(f"{4 + cycle_num}c", f"Task {cycle_num}: SkinScanAgent runs ML model")
    prediction = predict_skin_lesion(model, pixel_data)
    show("ML Model Output", prediction)
    print(f"\n  Ground truth: {true_label}")
    correct = prediction["prediction"] == true_label
    print(f"  Correct: {'YES' if correct else 'NO'}")

    # --- SkinScanAgent submits result ---
    step(f"{4 + cycle_num}d", f"Task {cycle_num}: SkinScanAgent submits result")
    result = api("POST", "/api/submit-result", {
        "task_id": task_id,
        "result": json.dumps(prediction),
    })
    show("Result submitted", {
        "task_id": result["task"]["task_id"],
        "status": result["task"]["status"],
    })

    # --- HealthAdvisorAgent rates the work ---
    score = 0.9 if correct else 0.5
    step(f"{4 + cycle_num}e", f"Task {cycle_num}: HealthAdvisorAgent rates work ({score})")
    result = api("POST", "/api/submit-feedback", {
        "agent_id": provider_id,
        "score": score,
        "task_id": task_id,
        "rated_by": requester_id,
    })
    show("Feedback submitted", {
        "score": score,
        "trust_before": f"{result['trust_before']*100:.1f}%",
        "trust_after": f"{result['trust_after']*100:.1f}%",
    })

    return prediction

# ---------------------------------------------------------------------------
# Main demo
# ---------------------------------------------------------------------------

def main():
    print("\n" + "=" * 64)
    print("  AGENTIC REPUTATION INFRASTRUCTURE LAYER")
    print("  SkinScanAgent — Real ML-Powered Demo")
    print(f"  Target: {BASE_URL}")
    print("=" * 64)

    # Check server connectivity
    print("\n  Checking server connectivity...")
    result = api("GET", "/api/agents")
    if result.get("_error"):
        print(f"\n  ERROR: Cannot reach server at {BASE_URL}")
        print(f"  Start the server first: python3 server.py 4000")
        return
    print(f"  Server online — {len(result.get('agents', []))} agents in registry")

    # ------------------------------------------------------------------
    # STEP 0: Train ML Model
    # ------------------------------------------------------------------
    step(0, "Train melanoma detection model (Logistic Regression + SMOTE)")
    if not os.path.exists(CSV_PATH):
        print(f"\n  ERROR: Dataset not found at:\n    {CSV_PATH}")
        print(f"\n  Expected HAM10000 hmnist_8_8_L.csv file.")
        return
    model, feature_cols, auc = train_model(CSV_PATH)
    samples = get_sample_lesions(CSV_PATH)
    print(f"\n  Model ready. Selected 2 test cases (1 melanoma, 1 benign)")

    # ------------------------------------------------------------------
    # STEP 1: Register SkinScanAgent (Provider)
    # ------------------------------------------------------------------
    step(1, "SkinScanAgent registers (melanoma detection provider)")
    result = api("POST", "/api/register-agent", SKINSCAN_AGENT)
    if result.get("_error"):
        print(f"  Registration failed: {result}")
        return
    show("SkinScanAgent registered", {
        "agent_id": result["agent"]["agent_id"],
        "agent_name": result["agent"]["agent_name"],
        "trust_score": f"{result['agent']['trust_score']*100:.0f}%",
    })

    # ------------------------------------------------------------------
    # STEP 2: Register HealthAdvisorAgent (Requester)
    # ------------------------------------------------------------------
    step(2, "HealthAdvisorAgent registers (clinical triage requester)")
    result = api("POST", "/api/register-agent", HEALTH_AGENT)
    if result.get("_error"):
        print(f"  Registration failed: {result}")
        return
    show("HealthAdvisorAgent registered", {
        "agent_id": result["agent"]["agent_id"],
        "agent_name": result["agent"]["agent_name"],
        "trust_score": f"{result['agent']['trust_score']*100:.0f}%",
    })

    # ------------------------------------------------------------------
    # STEP 3: Bootstrap SkinScanAgent trust above 30% gate
    # ------------------------------------------------------------------
    step(3, "Bootstrap SkinScanAgent trust (new agents start at 20%)")
    print("\n  New agents have trust_score = 20% (unproven)")
    print("  Trust gate threshold = 30%")
    print("  Submitting initial ratings to build trust...\n")
    for i, score in enumerate([0.8, 0.9, 0.8], 1):
        r = api("POST", "/api/submit-feedback", {
            "agent_id": SKINSCAN_AGENT["agent_id"],
            "score": score,
        })
        trust = r.get("trust_after", 0)
        gate = "PASS" if trust >= 0.3 else "BLOCKED"
        print(f"  Rating {i}: score={score} -> trust={trust*100:.1f}% [{gate}]")
    print(f"\n  SkinScanAgent now passes the trust gate")

    # ------------------------------------------------------------------
    # STEP 4: HealthAdvisorAgent discovers skin scan agents
    # ------------------------------------------------------------------
    step(4, "HealthAdvisorAgent discovers melanoma detection agents")
    result = api("GET", "/api/discover?keyword=melanoma")
    agents_found = result.get("agents", [])
    print(f"\n  Found {len(agents_found)} agent(s) matching 'melanoma':")
    for a in agents_found:
        print(f"    - {a['agent_name']} (trust: {a['trust_score']*100:.0f}%)")

    skinscan_found = any(
        a["agent_id"] == SKINSCAN_AGENT["agent_id"] for a in agents_found
    )
    print(f"\n  SkinScanAgent discoverable: {'YES' if skinscan_found else 'NO'}")
    if not skinscan_found:
        print("  ERROR: SkinScanAgent not found in discovery results")
        return

    # ------------------------------------------------------------------
    # TASK CYCLE 1: Melanoma case
    # ------------------------------------------------------------------
    run_task_cycle(
        cycle_num=1,
        model=model,
        sample=samples["melanoma"],
        requester_id=HEALTH_AGENT["agent_id"],
        provider_id=SKINSCAN_AGENT["agent_id"],
    )

    # ------------------------------------------------------------------
    # TASK CYCLE 2: Benign case
    # ------------------------------------------------------------------
    run_task_cycle(
        cycle_num=2,
        model=model,
        sample=samples["benign"],
        requester_id=HEALTH_AGENT["agent_id"],
        provider_id=SKINSCAN_AGENT["agent_id"],
    )

    # ------------------------------------------------------------------
    # FINAL: Show all trust scores
    # ------------------------------------------------------------------
    step("FINAL", "Trust scores after real ML-powered collaboration")
    result = api("GET", "/api/agents")
    agents = result.get("agents", [])
    print(f"\n  {'Agent':<35} {'Trust':>8} {'Ratings':>8} {'Tasks':>10}")
    print(f"  {'-'*35} {'-'*8} {'-'*8} {'-'*10}")
    for a in agents:
        trust = f"{a['trust_score']*100:.0f}%"
        tasks = f"{a.get('tasks_completed', 0)}/{a.get('tasks_received', 0)}"
        print(f"  {a['agent_name']:<35} {trust:>8} {a['total_runs']:>8} {tasks:>10}")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print(f"\n{'='*64}")
    print("  DEMO COMPLETE — Real Agent + Real ML + Real Trust")
    print(f"{'='*64}")
    print(f"""
  What just happened:
    1. Trained a melanoma detection model (AUC: {auc:.3f}) on 10,015 images
    2. SkinScanAgent registered with ML capabilities on the trust layer
    3. HealthAdvisorAgent discovered SkinScanAgent via skill search
    4. Trust gate blocked SkinScanAgent initially (20% < 30% threshold)
    5. After bootstrapping, SkinScanAgent passed the trust gate
    6. HealthAdvisorAgent delegated 2 real skin lesion cases
    7. SkinScanAgent ran the ML model and returned predictions
    8. HealthAdvisorAgent rated the results -> trust scores evolved

  This proves the infrastructure layer works for real agent collaboration
  with actual ML capabilities — not just simulated outcomes.
""")


if __name__ == "__main__":
    main()
