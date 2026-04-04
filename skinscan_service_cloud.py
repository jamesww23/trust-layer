#!/usr/bin/env python3
"""
skinscan_service_cloud.py — Unified SkinScanAgent for Railway deployment
------------------------------------------------------------------------
Supports three ML models, selected via MODEL_TYPE environment variable:

  MODEL_TYPE=logistic_smote  → Logistic Regression + SMOTE  (SkinScanAgent)
  MODEL_TYPE=cart            → Decision Tree / CART          (SkinScanAgent2)
  MODEL_TYPE=cart_smote      → CART + SMOTE                  (SkinScanAgent3)

Environment variables:
  MODEL_TYPE        One of: logistic_smote, cart, cart_smote  (default: logistic_smote)
  AGENT_ID          Agent identifier on the trust layer       (default: skinscan_agent)
  AGENT_NAME        Display name                              (default: SkinScanAgent)
  TRUST_LAYER_URL   Trust layer base URL                      (default: http://localhost:4000)
  POLL_INTERVAL     Seconds between inbox polls               (default: 5)

Railway deployment:
  Create 3 services from the same repo, each with different env vars.
  See railway.toml for build/deploy settings.
"""

import json
import os
import sys
import time

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier
from sklearn.linear_model import LogisticRegression
from imblearn.over_sampling import SMOTE
import urllib.request
import urllib.error

# ---------------------------------------------------------------------------
# Configuration from environment
# ---------------------------------------------------------------------------

MODEL_TYPE   = os.environ.get("MODEL_TYPE", "logistic_smote").lower()
AGENT_ID     = os.environ.get("AGENT_ID", "skinscan_agent")
AGENT_NAME   = os.environ.get("AGENT_NAME", "SkinScanAgent")
BASE_URL     = os.environ.get("TRUST_LAYER_URL",
               sys.argv[1] if len(sys.argv) > 1 else "http://localhost:4000")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "5"))
RANDOM_SEED  = 2025

# Dataset: bundled in repo at data/hmnist_8_8_L.csv
CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "hmnist_8_8_L.csv")

FEATURE_COLS = [
    "mean_brightness", "std_brightness", "min_brightness", "max_brightness",
    "brightness_range", "vertical_asymmetry", "horizontal_asymmetry",
    "center_brightness", "border_brightness", "center_border_diff",
    "pixel_variance", "edge_density", "percentile_25", "percentile_75", "iqr",
]

# ---------------------------------------------------------------------------
# Skill description per model type
# ---------------------------------------------------------------------------

SKILL_MD_TEMPLATES = {
    "logistic_smote": (
        "# {name} — Melanoma Detection (Logistic Regression)\n\n"
        "I analyze skin lesion images to detect melanoma using Logistic Regression + SMOTE.\n\n"
        "## Skills\n"
        "- Skin lesion classification (melanoma vs benign)\n"
        "- Risk level assessment (LOW / MODERATE / HIGH)\n"
        "- Trained on HAM10000 dataset (10,015 images)\n\n"
        "## Model\n"
        "- Algorithm: Logistic Regression + SMOTE oversampling\n"
        "- Features: 15 engineered from 8x8 grayscale images\n"
        "- AUC: ~0.797 | Melanoma Recall: ~49%\n\n"
        "## Best For\nScreening-level melanoma risk from dermatoscopic images."
    ),
    "cart": (
        "# {name} — Melanoma Detection (Decision Tree)\n\n"
        "I analyze skin lesion images to detect melanoma using a CART Decision Tree.\n\n"
        "## Skills\n"
        "- Skin lesion classification (melanoma vs benign)\n"
        "- skin melanoma detection lesion\n"
        "- Risk level assessment (LOW / MODERATE / HIGH)\n"
        "- Trained on HAM10000 dataset (10,015 images)\n\n"
        "## Model\n"
        "- Algorithm: Decision Tree (CART), max_depth=10\n"
        "- Features: 15 engineered from 8x8 grayscale images\n"
        "- AUC: ~0.75 | Higher interpretability\n\n"
        "## Best For\nInterpretable melanoma screening with explainable decisions."
    ),
    "cart_smote": (
        "# {name} — Melanoma Detection (CART + SMOTE)\n\n"
        "I analyze skin lesion images using a CART Decision Tree with SMOTE oversampling.\n\n"
        "## Skills\n"
        "- Skin lesion classification (melanoma vs benign)\n"
        "- skin melanoma detection lesion\n"
        "- Risk level assessment (LOW / MODERATE / HIGH)\n"
        "- Trained on HAM10000 dataset (10,015 images)\n\n"
        "## Model\n"
        "- Algorithm: Decision Tree + SMOTE for class imbalance\n"
        "- Features: 15 engineered from 8x8 grayscale images\n"
        "- AUC: ~0.78 | Improved melanoma recall\n\n"
        "## Best For\nMelanoma screening with improved sensitivity via oversampling."
    ),
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log(msg):
    ts = time.strftime("%H:%M:%S")
    print(f"  [{ts}] {msg}", flush=True)

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
# Feature extraction
# ---------------------------------------------------------------------------

def extract_features(img):
    features = {}
    features["mean_brightness"]     = img.mean()
    features["std_brightness"]      = img.std()
    features["min_brightness"]      = float(img.min())
    features["max_brightness"]      = float(img.max())
    features["brightness_range"]    = float(img.max() - img.min())
    top_half    = img[:4, :].mean()
    bottom_half = img[4:, :].mean()
    left_half   = img[:, :4].mean()
    right_half  = img[:, 4:].mean()
    features["vertical_asymmetry"]   = abs(top_half - bottom_half)
    features["horizontal_asymmetry"] = abs(left_half - right_half)
    center = img[2:6, 2:6].mean()
    border_pixels = np.concatenate([img[0, :], img[7, :], img[1:7, 0], img[1:7, 7]])
    border = border_pixels.mean()
    features["center_brightness"]   = center
    features["border_brightness"]   = border
    features["center_border_diff"]  = center - border
    features["pixel_variance"]      = img.var()
    h_edges = np.abs(np.diff(img, axis=1)).mean()
    v_edges = np.abs(np.diff(img, axis=0)).mean()
    features["edge_density"]        = h_edges + v_edges
    features["percentile_25"]       = float(np.percentile(img, 25))
    features["percentile_75"]       = float(np.percentile(img, 75))
    features["iqr"]                 = features["percentile_75"] - features["percentile_25"]
    return features

# ---------------------------------------------------------------------------
# Model training
# ---------------------------------------------------------------------------

def train_model():
    log(f"Loading dataset: {CSV_PATH}")
    df = pd.read_csv(CSV_PATH)
    pixel_features = df.drop(columns=["label"])
    labels = df["label"]
    images = pixel_features.values.reshape(-1, 8, 8)
    log(f"Extracting features from {len(images)} images...")
    feature_list = [extract_features(images[i]) for i in range(len(images))]
    img_features = pd.DataFrame(feature_list)
    y = (labels == 6).astype(int)
    X = img_features[FEATURE_COLS]
    train_X, test_X, train_y, test_y = train_test_split(
        X, y, test_size=0.3, random_state=RANDOM_SEED
    )

    if MODEL_TYPE == "logistic_smote":
        smote = SMOTE(random_state=RANDOM_SEED)
        train_X_r, train_y_r = smote.fit_resample(train_X, train_y)
        model = LogisticRegression(max_iter=5000, random_state=RANDOM_SEED)
        model.fit(train_X_r, train_y_r)

    elif MODEL_TYPE == "cart":
        model = DecisionTreeClassifier(
            max_depth=10, min_samples_leaf=5, random_state=RANDOM_SEED
        )
        model.fit(train_X, train_y)

    elif MODEL_TYPE == "cart_smote":
        smote = SMOTE(random_state=RANDOM_SEED)
        train_X_r, train_y_r = smote.fit_resample(train_X, train_y)
        model = DecisionTreeClassifier(
            max_depth=10, min_samples_leaf=5, random_state=RANDOM_SEED
        )
        model.fit(train_X_r, train_y_r)

    else:
        raise ValueError(f"Unknown MODEL_TYPE: {MODEL_TYPE}. Use: logistic_smote, cart, cart_smote")

    auc = roc_auc_score(test_y, model.predict_proba(test_X)[:, 1])
    log(f"Model trained ({MODEL_TYPE}) — AUC: {auc:.4f}")
    return model

# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------

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
        "model_type": MODEL_TYPE,
    }

# ---------------------------------------------------------------------------
# Main service loop
# ---------------------------------------------------------------------------

def main():
    skill_md = SKILL_MD_TEMPLATES.get(MODEL_TYPE, SKILL_MD_TEMPLATES["logistic_smote"])
    skill_md = skill_md.format(name=AGENT_NAME)

    print(flush=True)
    print("=" * 60, flush=True)
    print(f"  {AGENT_NAME} — Melanoma Detection ({MODEL_TYPE})", flush=True)
    print(f"  Server: {BASE_URL}", flush=True)
    print("=" * 60, flush=True)

    # Check connectivity
    result = api("GET", "/api/agents")
    if result.get("_error"):
        print(f"\n  ERROR: Cannot reach server at {BASE_URL}", flush=True)
        sys.exit(1)

    # Train model
    if not os.path.exists(CSV_PATH):
        print(f"\n  ERROR: Dataset not found at {CSV_PATH}", flush=True)
        sys.exit(1)
    model = train_model()

    # Register
    log("Registering on trust layer...")
    result = api("POST", "/api/register-agent", {
        "agent_id": AGENT_ID,
        "agent_name": AGENT_NAME,
        "skill_md": skill_md,
    })
    if result.get("_error"):
        if "already registered" in str(result.get("error", "")):
            log("Already registered — resuming service")
        else:
            log(f"Registration failed: {result}")
            sys.exit(1)
    else:
        log(f"Registered as {AGENT_NAME} (trust: {result['agent']['trust_score']*100:.0f}%)")

    # Check trust
    agent_info = api("GET", "/api/agents")
    for a in agent_info.get("agents", []):
        if a["agent_id"] == AGENT_ID:
            trust = a["trust_score"]
            status = "ready to accept tasks" if trust >= 0.3 else "below 30% gate — needs vouching"
            log(f"Trust is {trust*100:.0f}% — {status}")
            break

    log("Listening for tasks... (Ctrl+C to stop)\n")

    while True:
        try:
            result = api("GET", f"/api/tasks?agent_id={AGENT_ID}&status=pending")
            for task in result.get("tasks", []):
                task_id = task["task_id"]
                log(f"NEW TASK: {task.get('description', '')}")
                log(f"  Task ID: {task_id} | From: {task['requester_id']}")

                try:
                    payload_data = json.loads(task.get("payload", "{}") or "{}")
                except json.JSONDecodeError:
                    payload_data = {}

                pixel_data = payload_data.get("pixel_data")
                if not pixel_data or len(pixel_data) != 64:
                    log("  ERROR: Invalid pixel_data. Skipping.")
                    api("POST", "/api/submit-result", {
                        "task_id": task_id,
                        "result": json.dumps({"error": "Invalid payload"}),
                    })
                    continue

                prediction = predict(model, pixel_data)
                log(f"  → {prediction['prediction'].upper()} "
                    f"(prob: {prediction['melanoma_probability']:.1%}, "
                    f"risk: {prediction['risk_level']})")

                api("POST", "/api/submit-result", {
                    "task_id": task_id,
                    "result": json.dumps(prediction),
                })
                log(f"  Result submitted.\n")

            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            log("Service stopped.")
            break
        except Exception as e:
            log(f"Error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
