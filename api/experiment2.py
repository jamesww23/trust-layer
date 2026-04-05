"""GET /api/experiment2 — Experiment 2: Real Data vs Simulated Weather Agents.

Assignment 7: Does the Trust Layer reward accuracy?

Registers 3 weather agents (real, fake, stale) + a judge, delegates the same
weather query to each across multiple cities, compares results against
Open-Meteo ground truth, and submits accuracy-based ratings.

Uses internal core modules directly (no HTTP self-calls).

Query params:
  ?rounds=5  (1-10, default 5)
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

CITIES = ["Boston", "Tokyo", "London", "Sydney", "Paris"]

AGENTS_SPEC = {
    "judge": {
        "id": "agent_weather_judge",
        "name": "WeatherJudge",
        "skill_md": (
            "# WeatherJudge\nEvaluates weather forecast accuracy by "
            "comparing agent responses against Open-Meteo ground truth. "
            "Rates agents on temperature, humidity, and condition accuracy."
        ),
    },
    "real": {
        "id": "agent_weatherwatch",
        "name": "WeatherWatch",
        "skill_md": (
            "# WeatherWatch\nProvides real-time weather data from Open-Meteo API. "
            "Returns current temperature, humidity, UV index, wind speed, "
            "and conditions for any city worldwide."
        ),
    },
    "fake": {
        "id": "agent_weather_fake",
        "name": "FakeWeatherBot",
        "skill_md": (
            "# FakeWeatherBot\nReturns weather forecasts for any city. "
            "Provides temperature, humidity, and sky condition data."
        ),
    },
    "stale": {
        "id": "agent_weather_stale",
        "name": "StaleWeatherBot",
        "skill_md": (
            "# StaleWeatherBot\nReturns weather forecasts for any city. "
            "Provides temperature, humidity, and sky condition data."
        ),
    },
}

WMO_CODES = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "depositing rime fog",
    51: "light drizzle", 53: "moderate drizzle", 55: "dense drizzle",
    56: "light freezing drizzle", 57: "dense freezing drizzle",
    61: "slight rain", 63: "moderate rain", 65: "heavy rain",
    66: "light freezing rain", 67: "heavy freezing rain",
    71: "slight snow fall", 73: "moderate snow fall", 75: "heavy snow fall",
    77: "snow grains",
    80: "slight rain showers", 81: "moderate rain showers",
    82: "violent rain showers",
    85: "slight snow showers", 86: "heavy snow showers",
    95: "thunderstorm", 96: "thunderstorm with slight hail",
    99: "thunderstorm with heavy hail",
}

CONDITION_GROUPS = {
    "clear":   [0, 1],
    "cloudy":  [2, 3],
    "fog":     [45, 48],
    "drizzle": [51, 53, 55, 56, 57],
    "rain":    [61, 63, 65, 66, 67, 80, 81, 82],
    "snow":    [71, 73, 75, 77, 85, 86],
    "storm":   [95, 96, 99],
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
# Response generators
# ---------------------------------------------------------------------------

def generate_real_response(city, lat, lon):
    w = fetch_real_weather(lat, lon)
    return {
        "agent": "WeatherWatch",
        "city": city,
        "temperature_c": w["temperature_c"],
        "humidity_pct": w["humidity_pct"],
        "condition": w["condition"],
        "source": "Open-Meteo API (live)",
    }


def generate_fake_response(city):
    return {
        "agent": "FakeWeatherBot",
        "city": city,
        "temperature_c": round(random.uniform(-10, 45), 1),
        "humidity_pct": random.randint(10, 100),
        "condition": random.choice(FAKE_CONDITIONS),
        "source": "randomly generated",
    }


def generate_stale_response(city):
    return {
        "agent": "StaleWeatherBot",
        "city": city,
        "temperature_c": 22.0,
        "humidity_pct": 45,
        "condition": "clear sky",
        "source": "hardcoded stale data",
    }


# ---------------------------------------------------------------------------
# Accuracy scoring
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
    elif rep_group in ("rain", "drizzle", "storm") and truth_group in (
        "rain", "drizzle", "storm"
    ):
        cond_score = 0.3
    elif rep_group in ("rain", "drizzle", "storm") and truth_group in ("snow",):
        cond_score = 0.15
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
# Experiment logic (uses internal store directly)
# ---------------------------------------------------------------------------

def register_agents(store):
    """Ensure all experiment agents exist."""
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


def run_round(store, round_num, city):
    """Execute one round: delegate, respond, score, rate."""
    log = {"round": round_num, "city": city, "agents": {}}

    lat, lon = geocode(city)
    log["coordinates"] = {"lat": lat, "lon": lon}

    ground_truth = fetch_real_weather(lat, lon)
    log["ground_truth"] = ground_truth

    responses = {
        "real": generate_real_response(city, lat, lon),
        "fake": generate_fake_response(city),
        "stale": generate_stale_response(city),
    }

    judge_id = AGENTS_SPEC["judge"]["id"]

    for label in ["real", "fake", "stale"]:
        spec = AGENTS_SPEC[label]
        resp = responses[label]
        agent_log = {"agent_name": spec["name"], "response": resp}

        provider = store.get(spec["id"])
        if not provider:
            agent_log["error"] = "Agent not found in store"
            log["agents"][label] = agent_log
            continue

        # --- Delegation ---
        task_id = None
        try:
            validate_delegation(store, judge_id, spec["id"], DEFAULT_TRUST_THRESHOLD)

            task_id = "task_" + uuid.uuid4().hex[:12]
            task = Task(
                task_id=task_id,
                requester_id=judge_id,
                provider_id=spec["id"],
                description=f"Provide current weather for {city}",
                payload=json.dumps({"city": city, "lat": lat, "lon": lon}),
            )
            store.save_task(task)
            provider.tasks_received += 1
            store.upsert(provider)
            agent_log["task_id"] = task_id

        except ValueError as e:
            agent_log["delegation_blocked"] = str(e)

        # --- Submit result ---
        if task_id:
            task = store.get_task(task_id)
            now = datetime.now(timezone.utc)
            task.status = "completed"
            task.result = json.dumps(resp)
            task.completed_at = now.isoformat()
            created = datetime.fromisoformat(task.created_at)
            task.latency_ms = round((now - created).total_seconds() * 1000, 1)
            store.save_task(task)

            update_agent_latency(provider, task.latency_ms)
            provider.tasks_completed += 1
            store.upsert(provider)
            agent_log["submit_status"] = "completed"

        # --- Score accuracy ---
        accuracy, details = score_accuracy(resp, ground_truth)
        rating = accuracy_to_rating(accuracy)
        agent_log["accuracy"] = details
        agent_log["rating"] = rating

        # --- Submit feedback ---
        try:
            fb_result = submit_feedback(
                store,
                provider_id=spec["id"],
                score=rating,
                task_id=task_id,
                rated_by=judge_id,
            )
            agent_log["feedback_result"] = {
                "trust_before": fb_result.get("trust_before"),
                "trust_after": fb_result.get("trust_after"),
            }
        except ValueError as e:
            # If no task_id (trust gate blocked), do direct feedback
            agent_log["feedback_note"] = str(e)
            try:
                fb_result = submit_feedback(
                    store,
                    provider_id=spec["id"],
                    score=rating,
                    rated_by=judge_id,
                )
                agent_log["feedback_result"] = {
                    "trust_before": fb_result.get("trust_before"),
                    "trust_after": fb_result.get("trust_after"),
                }
            except ValueError as e2:
                agent_log["feedback_error"] = str(e2)

        log["agents"][label] = agent_log

    return log


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            started = datetime.now(timezone.utc)
            store = RedisStore()
            seed_store(store)

            # Parse rounds from query string
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            num_rounds = max(1, min(10, int(qs.get("rounds", ["5"])[0])))

            experiment = {
                "experiment": "Experiment 2: Real Data vs Simulated",
                "question": "Does the Trust Layer reward accuracy?",
                "started_at": started.isoformat(),
                "platform": "trust-layer-topaz.vercel.app (internal)",
                "cities": CITIES,
                "num_rounds": num_rounds,
            }

            # Step 1: Register agents
            experiment["registration"] = register_agents(store)

            # Step 2: Run rounds
            rounds = []
            cumulative_ratings = {"real": [], "fake": [], "stale": []}
            cities_to_use = (CITIES * 2)[:num_rounds]

            for i, city in enumerate(cities_to_use, 1):
                round_log = run_round(store, i, city)
                rounds.append(round_log)

                for label in ["real", "fake", "stale"]:
                    if label in round_log["agents"]:
                        rating = round_log["agents"][label].get("rating")
                        if rating is not None:
                            cumulative_ratings[label].append(rating)

            experiment["rounds"] = rounds

            # Step 3: Fetch final trust scores
            final_scores = {}
            for label, spec in AGENTS_SPEC.items():
                agent = store.get(spec["id"])
                if agent:
                    final_scores[spec["id"]] = {
                        "agent_name": agent.agent_name,
                        "trust_score": round(agent.trust_score, 4),
                        "tasks_completed": agent.tasks_completed,
                        "tasks_received": agent.tasks_received,
                        "total_runs": agent.total_runs,
                    }
            experiment["final_trust_scores"] = final_scores

            # Build summary
            summary = {}
            for label in ["real", "fake", "stale"]:
                spec = AGENTS_SPEC[label]
                ratings = cumulative_ratings[label]
                avg = sum(ratings) / len(ratings) if ratings else 0
                ts_info = final_scores.get(spec["id"], {})
                summary[label] = {
                    "agent_name": spec["name"],
                    "agent_id": spec["id"],
                    "avg_rating": round(avg, 3),
                    "trust_score": ts_info.get("trust_score", 0),
                    "rounds_completed": len(ratings),
                    "all_ratings": ratings,
                }
            experiment["summary"] = summary

            # Conclusion
            best_trust = max(summary.values(), key=lambda x: x["trust_score"])
            best_rating = max(summary.values(), key=lambda x: x["avg_rating"])

            if best_trust["agent_id"] == AGENTS_SPEC["real"]["id"]:
                conclusion = (
                    f"SUCCESS: The Trust Layer correctly surfaced "
                    f"{best_trust['agent_name']} (real data) as the most "
                    f"trustworthy agent with trust score "
                    f"{best_trust['trust_score']:.4f}. Accuracy IS rewarded."
                )
            elif best_rating["agent_id"] == AGENTS_SPEC["real"]["id"]:
                conclusion = (
                    f"PARTIAL: {best_rating['agent_name']} had the best "
                    f"ratings ({best_rating['avg_rating']:.3f}) but "
                    f"{best_trust['agent_name']} has higher trust due to "
                    f"prior history. More rounds may be needed."
                )
            else:
                conclusion = (
                    f"NEEDS MORE ROUNDS: Best trust: "
                    f"{best_trust['agent_name']}, Best rating: "
                    f"{best_rating['agent_name']}."
                )

            experiment["conclusion"] = conclusion
            experiment["completed_at"] = datetime.now(timezone.utc).isoformat()
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
            experiment["elapsed_seconds"] = round(elapsed, 1)

            self._json(200, experiment)

        except Exception as e:
            import traceback
            self._json(500, {
                "error": str(e),
                "traceback": traceback.format_exc(),
            })

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
