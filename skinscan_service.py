#!/usr/bin/env python3
"""
SkinScanAgent Service — Provider Agent for Melanoma Detection
--------------------------------------------------------------
Runs as a background service that:
  1. Registers on the trust layer
  2. Trains the ML model on startup
  3. Polls for incoming tasks every few seconds
  4. When a task arrives, runs the melanoma detection model
  5. Submits the prediction result back to the trust layer

Usage:
    # Terminal 1: Start the trust layer server
    python3 server.py 4000

    # Terminal 2: Start SkinScanAgent service
    python3 skinscan_service.py

    # Terminal 3: Submit a request (via wisdom_request.py or any agent)
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
POLL_INTERVAL = 3  # seconds between inbox checks

CSV_PATH = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "..", "15.071 The Analytics Edge",
    "Final Project", "Melanoma_Dataset", "hmnist_8_8_L.csv",
))

RANDOM_SEED = 2025
AGENT_ID = "skinscan_agent_service"
AGENT_NAME = "SkinScanAgent"

FEATURE_COLS = [
    "mean_brightness", "std_brightness", "min_brightness", "max_brightness",
    "brightness_range", "vertical_asymmetry", "horizontal_asymmetry",
    "center_brightness", "border_brightness", "center_border_diff",
    "pixel_variance", "edge_density", "percentile_25", "percentile_75", "iqr",
]

SKILL_MD = (
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
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log(msg):
    ts = time.strftime("%H:%M:%S")
    print(f"  [{ts}] {msg}")

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

# ---------------------------------------------------------------------------
# ML Model
# ---------------------------------------------------------------------------

def extract_features(img):
    features = {}
    features["mean_brightness"] = img.mean()
    features["std_brightness"] = img.std()
    features["min_brightness"] = float(img.min())
    features["max_brightness"] = float(img.max())
    features["brightness_range"] = float(img.max() - img.min())
    top_half = img[:4, :].mean()
    bottom_half = img[4:, :].mean()
    left_half = img[:, :4].mean()
    right_half = img[:, 4:].mean()
    features["vertical_asymmetry"] = abs(top_half - bottom_half)
    features["horizontal_asymmetry"] = abs(left_half - right_half)
    center = img[2:6, 2:6].mean()
    border_pixels = np.concatenate([img[0, :], img[7, :], img[1:7, 0], img[1:7, 7]])
    border = border_pixels.mean()
    features["center_brightness"] = center
    features["border_brightness"] = border
    features["center_border_diff"] = center - border
    features["pixel_variance"] = img.var()
    h_edges = np.abs(np.diff(img, axis=1)).mean()
    v_edges = np.abs(np.diff(img, axis=0)).mean()
    features["edge_density"] = h_edges + v_edges
    features["percentile_25"] = float(np.percentile(img, 25))
    features["percentile_75"] = float(np.percentile(img, 75))
    features["iqr"] = features["percentile_75"] - features["percentile_25"]
    return features


def train_model(csv_path):
    log(f"Loading dataset: {csv_path}")
    df = pd.read_csv(csv_path)
    pixel_features = df.drop(columns=["label"])
    labels = df["label"]
    images = pixel_features.values.reshape(-1, 8, 8)
    log(f"Extracting features from {len(images)} images...")
    feature_list = [extract_features(images[i]) for i in range(len(images))]
    img_features = pd.DataFrame(feature_list)
    y = (labels == 6).astype(int)
    X = img_features[FEATURE_COLS]
    np.random.seed(RANDOM_SEED)
    train_X, test_X, train_y, test_y = train_test_split(X, y, test_size=0.3, random_state=RANDOM_SEED)
    smote = SMOTE(random_state=RANDOM_SEED)
    train_X_smote, train_y_smote = smote.fit_resample(train_X, train_y)
    model = LogisticRegression(max_iter=5000, random_state=RANDOM_SEED)
    model.fit(train_X_smote, train_y_smote)
    auc = roc_auc_score(test_y, model.predict_proba(test_X)[:, 1])
    log(f"Model trained — AUC: {auc:.4f}")
    return model


def predict(model, pixel_data_list):
    img = np.array(pixel_data_list, dtype=np.float64).reshape(8, 8)
    features = extract_features(img)
    feature_df = pd.DataFrame([features])[FEATURE_COLS]
    prob = model.predict_proba(feature_df)[0][1]
    pred = int(model.predict(feature_df)[0])
    if prob >= 0.7:
        risk, rec = "HIGH", "Immediate dermatologist referral recommended"
    elif prob >= 0.4:
        risk, rec = "MODERATE", "Follow-up dermatology appointment recommended within 2 weeks"
    else:
        risk, rec = "LOW", "Routine monitoring; re-screen in 6-12 months"
    return {
        "prediction": "melanoma" if pred == 1 else "benign",
        "melanoma_probability": round(float(prob), 4),
        "risk_level": risk,
        "recommendation": rec,
    }

# ---------------------------------------------------------------------------
# Main service loop
# ---------------------------------------------------------------------------

def main():
    print()
    print("=" * 60)
    print("  SkinScanAgent — Melanoma Detection Service")
    print(f"  Server: {BASE_URL}")
    print("=" * 60)

    # Check connectivity
    result = api("GET", "/api/agents")
    if result.get("_error"):
        print(f"\n  ERROR: Cannot reach server at {BASE_URL}")
        print(f"  Start it first: python3 server.py 4000")
        return

    # Train model
    if not os.path.exists(CSV_PATH):
        print(f"\n  ERROR: Dataset not found at {CSV_PATH}")
        return
    model = train_model(CSV_PATH)

    # Register (or skip if already registered)
    log("Registering on trust layer...")
    result = api("POST", "/api/register-agent", {
        "agent_id": AGENT_ID,
        "agent_name": AGENT_NAME,
        "skill_md": SKILL_MD,
    })
    if result.get("_error"):
        if "already registered" in str(result.get("error", "")):
            log("Already registered — resuming service")
        else:
            log(f"Registration failed: {result}")
            return
    else:
        log(f"Registered as {AGENT_NAME} (trust: {result['agent']['trust_score']*100:.0f}%)")

    # Check if we need trust bootstrapping
    agent_info = api("GET", "/api/agents")
    for a in agent_info.get("agents", []):
        if a["agent_id"] == AGENT_ID:
            trust = a["trust_score"]
            if trust < 0.3:
                log(f"Trust is {trust*100:.0f}% (below 30% gate). Needs vouching or ratings to accept tasks.")
            else:
                log(f"Trust is {trust*100:.0f}% — ready to accept tasks")
            break

    # Poll loop
    log("Listening for tasks... (Ctrl+C to stop)\n")
    while True:
        try:
            result = api("GET", f"/api/tasks?agent_id={AGENT_ID}&status=pending")
            tasks = result.get("tasks", [])

            for task in tasks:
                task_id = task["task_id"]
                desc = task.get("description", "")
                log(f"NEW TASK: {desc}")
                log(f"  Task ID: {task_id}")
                log(f"  From: {task['requester_id']}")

                # Parse payload
                payload = task.get("payload", "")
                try:
                    payload_data = json.loads(payload) if payload else {}
                except json.JSONDecodeError:
                    payload_data = {}

                pixel_data = payload_data.get("pixel_data")
                if not pixel_data or len(pixel_data) != 64:
                    log("  ERROR: No valid pixel_data (need 64 values). Skipping.")
                    # Submit error result
                    api("POST", "/api/submit-result", {
                        "task_id": task_id,
                        "result": json.dumps({"error": "Invalid payload — expected pixel_data with 64 values"}),
                    })
                    continue

                # Run ML model
                log("  Running melanoma detection model...")
                prediction = predict(model, pixel_data)
                log(f"  Result: {prediction['prediction'].upper()} "
                    f"(probability: {prediction['melanoma_probability']:.1%}, "
                    f"risk: {prediction['risk_level']})")
                log(f"  Recommendation: {prediction['recommendation']}")

                # Submit result
                api("POST", "/api/submit-result", {
                    "task_id": task_id,
                    "result": json.dumps(prediction),
                })
                log(f"  Result submitted for task {task_id}")
                log("")

            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            log("\nService stopped.")
            break
        except Exception as e:
            log(f"Error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
