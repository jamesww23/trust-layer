"""GET /api/experiment3 — Experiment 3: Failure Recovery Behavior.

Assignment 7: Does the Trust Layer detect failure and reward recovery?

Tests an agent through 3 phases:
  Phase 1 (Reliable):  Agent performs well → trust rises
  Phase 2 (Degraded):  Agent starts failing → trust drops
  Phase 3 (Recovery):  Agent improves again → trust recovers

Also runs a control agent that performs consistently throughout.
Demonstrates the trust formula's responsiveness to quality changes.

Query params:
  ?rounds_per_phase=4  (1-8, default 4 → 12 total rounds)
"""

import json
import random
import uuid
import sys
import os
import urllib.request
import urllib.error
import urllib.parse
from http.server import BaseHTTPRequestHandler
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.store import RedisStore
from core.models import Agent, Task
from core.controller import (
    validate_delegation, submit_feedback, update_agent_latency,
    DEFAULT_TRUST_THRESHOLD,
)
from core.fixtures import seed_store

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CITIES = ["Boston", "Tokyo", "London", "Sydney", "Paris",
          "Berlin", "Mumbai", "Toronto", "Seoul", "Dubai",
          "Rome", "Bangkok"]

AGENTS_SPEC = {
    "judge": {
        "id": "agent_recovery_judge",
        "name": "RecoveryJudge",
        "skill_md": (
            "# RecoveryJudge\nEvaluates weather forecast accuracy across "
            "multiple phases. Monitors agent reliability over time."
        ),
    },
    "test": {
        "id": "agent_weather_unstable",
        "name": "UnstableWeatherBot",
        "skill_md": (
            "# UnstableWeatherBot\nProvides weather forecasts for any city. "
            "Returns temperature, humidity, and sky condition data. "
            "Performance may vary over time."
        ),
    },
    "control": {
        "id": "agent_weather_steady",
        "name": "SteadyWeatherBot",
        "skill_md": (
            "# SteadyWeatherBot\nProvides consistent weather forecasts "
            "for any city. Returns temperature, humidity, and conditions "
            "using reliable data sources."
        ),
    },
}

WMO_CODES = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "depositing rime fog",
    51: "light drizzle", 53: "moderate drizzle", 55: "dense drizzle",
    61: "slight rain", 63: "moderate rain", 65: "heavy rain",
    71: "slight snow fall", 73: "moderate snow fall", 75: "heavy snow fall",
    80: "slight rain showers", 81: "moderate rain showers",
    95: "thunderstorm", 96: "thunderstorm with slight hail",
}

CONDITION_GROUPS = {
    "clear":   [0, 1],
    "cloudy":  [2, 3],
    "fog":     [45, 48],
    "drizzle": [51, 53, 55],
    "rain":    [61, 63, 65, 80, 81],
    "snow":    [71, 73, 75],
    "storm":   [95, 96],
}

FAKE_CONDITIONS = [
    "clear sky", "partly cloudy", "moderate rain", "slight snow fall",
    "overcast", "fog", "thunderstorm", "light drizzle",
]


# ---------------------------------------------------------------------------
# Open-Meteo helpers
# ---------------------------------------------------------------------------

def _get_external(url):
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def geocode(city):
    url = (
        f"https://geocoding-api.open-meteo.com/v1/search?"
        f"name={urllib.parse.quote(city)}&count=1"
    )
    data = _get_external(url)
    r = data["results"][0]
    return r["latitude"], r["longitude"]


def fetch_real_weather(lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,weather_code"
    )
    data = _get_external(url)
    c = data["current"]
    code = c["weather_code"]
    return {
        "temperature_c": c["temperature_2m"],
        "humidity_pct": c["relative_humidity_2m"],
        "weather_code": code,
        "condition": WMO_CODES.get(code, f"code {code}"),
    }


# ---------------------------------------------------------------------------
# Response generators for each phase
# ---------------------------------------------------------------------------

def generate_good_response(city, ground_truth):
    """Near-accurate response: small deviations from ground truth."""
    return {
        "agent": "response",
        "city": city,
        "temperature_c": round(ground_truth["temperature_c"] + random.uniform(-1.5, 1.5), 1),
        "humidity_pct": ground_truth["humidity_pct"] + random.randint(-5, 5),
        "condition": ground_truth["condition"],
        "source": "accurate (near ground truth)",
    }


def generate_bad_response(city, ground_truth):
    """Poor response: large deviations, often wrong condition."""
    return {
        "agent": "response",
        "city": city,
        "temperature_c": round(random.uniform(-10, 45), 1),
        "humidity_pct": random.randint(10, 100),
        "condition": random.choice(FAKE_CONDITIONS),
        "source": "degraded (random data)",
    }


def generate_steady_response(city, ground_truth):
    """Consistently good response (control agent)."""
    return {
        "agent": "response",
        "city": city,
        "temperature_c": round(ground_truth["temperature_c"] + random.uniform(-2.0, 2.0), 1),
        "humidity_pct": ground_truth["humidity_pct"] + random.randint(-8, 8),
        "condition": ground_truth["condition"],
        "source": "steady (near ground truth)",
    }


# ---------------------------------------------------------------------------
# Accuracy scoring (same as experiment2)
# ---------------------------------------------------------------------------

def _condition_group(condition):
    for group, codes in CONDITION_GROUPS.items():
        for code in codes:
            if WMO_CODES.get(code, "") == condition:
                return group
    return "unknown"


def score_accuracy(reported, ground_truth):
    temp_diff = abs(reported["temperature_c"] - ground_truth["temperature_c"])
    temp_score = max(0.0, 1.0 - temp_diff / 15.0)

    humid_diff = abs(reported["humidity_pct"] - ground_truth["humidity_pct"])
    humid_score = max(0.0, 1.0 - humid_diff / 50.0)

    rep_group = _condition_group(reported["condition"])
    truth_group = _condition_group(ground_truth["condition"])
    if rep_group == truth_group:
        cond_score = 1.0
    elif rep_group in ("rain", "drizzle", "storm") and truth_group in ("rain", "drizzle", "storm"):
        cond_score = 0.3
    else:
        cond_score = 0.0

    overall = 0.45 * temp_score + 0.25 * humid_score + 0.30 * cond_score
    return overall, {
        "temp_diff": round(temp_diff, 1),
        "temp_score": round(temp_score, 3),
        "humid_diff": round(humid_diff, 1),
        "humid_score": round(humid_score, 3),
        "condition_match": rep_group == truth_group,
        "cond_score": round(cond_score, 3),
        "overall": round(overall, 3),
    }


def accuracy_to_rating(accuracy):
    if accuracy >= 0.75:
        return round(random.uniform(0.85, 0.95), 2)
    elif accuracy >= 0.45:
        return round(random.uniform(0.50, 0.70), 2)
    else:
        return round(random.uniform(0.20, 0.40), 2)


# ---------------------------------------------------------------------------
# Experiment logic
# ---------------------------------------------------------------------------

def register_agents(store):
    results = []
    for label, spec in AGENTS_SPEC.items():
        existing = store.get(spec["id"])
        if existing:
            results.append({
                "agent": spec["name"],
                "agent_id": spec["id"],
                "status": "already_exists",
                "trust_score": existing.trust_score,
            })
        else:
            agent = Agent(
                agent_id=spec["id"],
                agent_name=spec["name"],
                skill_md=spec["skill_md"],
            )
            store.register(agent)
            results.append({
                "agent": spec["name"],
                "agent_id": spec["id"],
                "status": "registered",
                "trust_score": agent.trust_score,
            })
    return results


def process_agent(store, agent_id, judge_id, city, response, ground_truth):
    """Delegate task, submit result, score, and rate one agent."""
    result = {"agent_id": agent_id, "response": response}

    provider = store.get(agent_id)
    if not provider:
        result["error"] = "Agent not found"
        return result

    # Delegate
    task_id = None
    try:
        validate_delegation(store, judge_id, agent_id, DEFAULT_TRUST_THRESHOLD)
        task_id = "task_" + uuid.uuid4().hex[:12]
        task = Task(
            task_id=task_id,
            requester_id=judge_id,
            provider_id=agent_id,
            description=f"Provide current weather for {city}",
            payload=json.dumps({"city": city}),
        )
        store.save_task(task)
        provider.tasks_received += 1
        store.upsert(provider)
        result["task_id"] = task_id
    except ValueError as e:
        result["delegation_blocked"] = str(e)

    # Submit result
    if task_id:
        task = store.get_task(task_id)
        now = datetime.now(timezone.utc)
        task.status = "completed"
        task.result = json.dumps(response)
        task.completed_at = now.isoformat()
        created = datetime.fromisoformat(task.created_at)
        task.latency_ms = round((now - created).total_seconds() * 1000, 1)
        store.save_task(task)
        update_agent_latency(provider, task.latency_ms)
        provider.tasks_completed += 1
        store.upsert(provider)

    # Score
    accuracy, details = score_accuracy(response, ground_truth)
    rating = accuracy_to_rating(accuracy)
    result["accuracy"] = details
    result["rating"] = rating

    # Feedback
    try:
        fb = submit_feedback(store, provider_id=agent_id, score=rating,
                             task_id=task_id, rated_by=judge_id)
        result["trust_before"] = fb.get("trust_before")
        result["trust_after"] = fb.get("trust_after")
    except ValueError:
        try:
            fb = submit_feedback(store, provider_id=agent_id, score=rating,
                                 rated_by=judge_id)
            result["trust_before"] = fb.get("trust_before")
            result["trust_after"] = fb.get("trust_after")
        except ValueError as e2:
            result["feedback_error"] = str(e2)

    return result


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            started = datetime.now(timezone.utc)
            store = RedisStore()
            seed_store(store)

            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            rpp = max(1, min(8, int(qs.get("rounds_per_phase", ["4"])[0])))
            total_rounds = rpp * 3

            experiment = {
                "experiment": "Experiment 3: Failure Recovery Behavior",
                "question": "Does the Trust Layer detect failure and reward recovery?",
                "started_at": started.isoformat(),
                "platform": "trust-layer-topaz.vercel.app (internal)",
                "rounds_per_phase": rpp,
                "total_rounds": total_rounds,
                "phases": {
                    1: {"name": "Reliable", "description": "Both agents perform well", "rounds": f"1-{rpp}"},
                    2: {"name": "Degraded", "description": "Test agent starts failing, control stays steady", "rounds": f"{rpp+1}-{rpp*2}"},
                    3: {"name": "Recovery", "description": "Test agent recovers to good performance", "rounds": f"{rpp*2+1}-{total_rounds}"},
                },
            }

            # Register
            experiment["registration"] = register_agents(store)

            judge_id = AGENTS_SPEC["judge"]["id"]
            test_id = AGENTS_SPEC["test"]["id"]
            control_id = AGENTS_SPEC["control"]["id"]

            # Run rounds
            rounds = []
            trust_trajectory = {"test": [], "control": []}
            rating_trajectory = {"test": [], "control": []}
            cities_cycle = (CITIES * 3)[:total_rounds]

            for i in range(total_rounds):
                round_num = i + 1
                city = cities_cycle[i]

                # Determine phase
                if round_num <= rpp:
                    phase = 1
                    phase_name = "Reliable"
                elif round_num <= rpp * 2:
                    phase = 2
                    phase_name = "Degraded"
                else:
                    phase = 3
                    phase_name = "Recovery"

                # Geocode + ground truth
                lat, lon = geocode(city)
                ground_truth = fetch_real_weather(lat, lon)

                # Generate responses based on phase
                if phase == 1 or phase == 3:
                    test_response = generate_good_response(city, ground_truth)
                else:
                    test_response = generate_bad_response(city, ground_truth)

                control_response = generate_steady_response(city, ground_truth)

                # Process both agents
                test_result = process_agent(
                    store, test_id, judge_id, city, test_response, ground_truth
                )
                control_result = process_agent(
                    store, control_id, judge_id, city, control_response, ground_truth
                )

                # Track trajectories
                test_trust = test_result.get("trust_after", test_result.get("trust_before", 0.2))
                control_trust = control_result.get("trust_after", control_result.get("trust_before", 0.2))
                trust_trajectory["test"].append(round(test_trust, 4))
                trust_trajectory["control"].append(round(control_trust, 4))
                rating_trajectory["test"].append(test_result.get("rating", 0))
                rating_trajectory["control"].append(control_result.get("rating", 0))

                rounds.append({
                    "round": round_num,
                    "phase": phase,
                    "phase_name": phase_name,
                    "city": city,
                    "coordinates": {"lat": lat, "lon": lon},
                    "ground_truth": ground_truth,
                    "test_agent": test_result,
                    "control_agent": control_result,
                })

            experiment["rounds"] = rounds
            experiment["trust_trajectory"] = trust_trajectory
            experiment["rating_trajectory"] = rating_trajectory

            # Final scores
            test_agent = store.get(test_id)
            control_agent = store.get(control_id)

            experiment["final_scores"] = {
                "test": {
                    "agent_name": "UnstableWeatherBot",
                    "trust_score": round(test_agent.trust_score, 4) if test_agent else 0,
                    "tasks_completed": test_agent.tasks_completed if test_agent else 0,
                },
                "control": {
                    "agent_name": "SteadyWeatherBot",
                    "trust_score": round(control_agent.trust_score, 4) if control_agent else 0,
                    "tasks_completed": control_agent.tasks_completed if control_agent else 0,
                },
            }

            # Analysis
            test_trust_arr = trust_trajectory["test"]
            phase1_end = test_trust_arr[rpp - 1] if len(test_trust_arr) >= rpp else 0
            phase2_end = test_trust_arr[rpp * 2 - 1] if len(test_trust_arr) >= rpp * 2 else 0
            phase3_end = test_trust_arr[-1] if test_trust_arr else 0

            trust_dropped = phase2_end < phase1_end
            trust_recovered = phase3_end > phase2_end
            control_stable = abs(trust_trajectory["control"][-1] - trust_trajectory["control"][0]) < 0.15 if trust_trajectory["control"] else False

            if trust_dropped and trust_recovered:
                conclusion = (
                    f"SUCCESS: Trust score correctly responded to quality changes. "
                    f"UnstableWeatherBot trust: {phase1_end:.3f} (reliable) -> "
                    f"{phase2_end:.3f} (degraded, -{(phase1_end - phase2_end):.3f}) -> "
                    f"{phase3_end:.3f} (recovered, +{(phase3_end - phase2_end):.3f}). "
                    f"SteadyWeatherBot maintained trust at {trust_trajectory['control'][-1]:.3f}. "
                    f"The trust formula detects failure AND rewards recovery."
                )
            elif trust_dropped and not trust_recovered:
                conclusion = (
                    f"PARTIAL: Trust dropped during failure ({phase1_end:.3f} -> {phase2_end:.3f}) "
                    f"but recovery was slow ({phase3_end:.3f}). More rounds may be needed "
                    f"for full recovery. The formula is appropriately cautious."
                )
            else:
                conclusion = (
                    f"INCONCLUSIVE: Trust trajectory did not show clear phases. "
                    f"End-of-phase trust: {phase1_end:.3f} / {phase2_end:.3f} / {phase3_end:.3f}. "
                    f"The anti-manipulation cap or insufficient rounds may be limiting divergence."
                )

            experiment["analysis"] = {
                "phase1_end_trust": round(phase1_end, 4),
                "phase2_end_trust": round(phase2_end, 4),
                "phase3_end_trust": round(phase3_end, 4),
                "trust_dropped_in_phase2": trust_dropped,
                "trust_recovered_in_phase3": trust_recovered,
                "control_remained_stable": control_stable,
                "drop_magnitude": round(phase1_end - phase2_end, 4),
                "recovery_magnitude": round(phase3_end - phase2_end, 4),
            }
            experiment["conclusion"] = conclusion
            experiment["completed_at"] = datetime.now(timezone.utc).isoformat()
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
            experiment["elapsed_seconds"] = round(elapsed, 1)

            self._json(200, experiment)

        except Exception as e:
            import traceback
            self._json(500, {"error": str(e), "traceback": traceback.format_exc()})

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _json(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())
