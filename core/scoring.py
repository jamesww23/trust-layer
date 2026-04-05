"""Scoring engine for Agentic Reputation Infrastructure Layer.

Team-agreed trust formula (Assignment 5 report):

    trust = 0.35 × TSR  +  0.40 × WFS  +  0.15 × RH  +  0.10 × SS

    TSR  Task Success Rate      quality-weighted completions / tasks_received
                                (only tasks rated >= 0.5 count as 'successful')
    WFS  Weighted Feedback      avg rating, each weighted by requester's trust score
    RH   Reliability History    consistency of last 10 ratings (1 - std deviation)
    SS   Specialization Score   keyword overlap between tasks received and skill_md

New agent behaviour:
    - 0 tasks, 0 ratings → trust ≈ 0.21 (below 30% gate — must earn access)
    - Ratings alone can NOT push trust above 40% until 3 tasks are completed
      (anti-manipulation cap)

See CLAUDE.md for full design rationale and anti-manipulation rules.
"""

import statistics


# Formula weights — update here AND in CLAUDE.md together
W_TSR = 0.35
W_WFS = 0.40
W_RH  = 0.15
W_SS  = 0.10

PRIOR_TRUST       = 0.20   # new agent baseline
MAX_TRUST_NO_WORK = 0.40   # cap until 3 tasks completed (anti-manipulation)
SUCCESS_THRESHOLD = 0.50   # minimum rating for a task to count as 'successful'

# Stop words excluded from specialization keyword matching
_STOP = {
    'a','an','the','to','for','and','or','in','on','at','is','it','of',
    'this','that','with','be','are','was','i','by','my','me','we','us',
    'do','has','have','had','from','as','if','but','not','so','its',
}


def compute_tsr(tasks_received: int, ratings: list) -> float:
    """Task Success Rate: fraction of received tasks that were successfully completed.

    A task counts as 'successful' only if it was completed AND rated >= 0.5.
    This prevents agents that always deliver low-quality work from gaming TSR.

    Returns 0.0 for agents with fewer than 3 tasks received (new agents are
    not penalised before they've had a chance to work, but they also don't get
    credit until they prove themselves).
    """
    if tasks_received < 3:
        return 0.0
    good = sum(1 for r in ratings if r >= SUCCESS_THRESHOLD)
    return round(good / tasks_received, 4)


def compute_wfs(ratings: list, rating_weights: list,
                fallback_success_rate: float = PRIOR_TRUST) -> float:
    """Weighted Feedback Score: requester-trust-weighted average of ratings.

    Each rating is weighted by the requester's trust score at submission time.
    A 90%-trust requester's feedback counts ~4.5× more than a 20%-trust one's.

    Falls back to simple average if weights are missing (legacy agents).
    Falls back to prior (0.2) if no ratings at all.
    """
    if not ratings:
        return fallback_success_rate

    if rating_weights and len(rating_weights) == len(ratings):
        total_w = sum(rating_weights)
        if total_w > 0:
            return round(
                sum(r * w for r, w in zip(ratings, rating_weights)) / total_w, 4
            )

    return round(sum(ratings) / len(ratings), 4)


def compute_rh(ratings: list) -> float:
    """Reliability History: consistency of the last 10 ratings.

    rh = 1 - std_deviation(last_10_ratings)

    - Perfectly consistent agent (e.g. all 0.9) → rh ≈ 1.0
    - Highly variable agent (alternating 0.1 / 0.9) → rh ≈ 0.43
    - Returns 0.5 (neutral) for fewer than 2 ratings.
    """
    recent = ratings[-10:] if len(ratings) >= 10 else ratings
    if len(recent) < 2:
        return 0.5
    return round(max(0.0, 1.0 - statistics.stdev(recent)), 4)


def compute_ss(task_description: str, skill_md: str) -> float:
    """Specialization Score: how well the task matched the agent's declared skills.

    Computes keyword overlap between task description and skill_md.
    Higher overlap → agent is used for what it's good at.

    Returns 0.5 (neutral) if either string is empty.
    """
    if not task_description or not skill_md:
        return 0.5

    task_words = {
        w.strip('.,!?()[]#-*_:') for w in task_description.lower().split()
        if len(w) >= 3
    } - _STOP

    skill_words = {
        w.strip('.,!?()[]#-*_:') for w in skill_md.lower().split()
        if len(w) >= 3
    } - _STOP

    if not task_words or not skill_words:
        return 0.5

    overlap = len(task_words & skill_words) / len(task_words)
    return round(min(1.0, overlap * 2.5), 4)


def compute_trust_score(
    tasks_received: int,
    tasks_completed: int,
    ratings: list,
    rating_weights: list,
    specialization_score: float,
    fallback_success_rate: float = PRIOR_TRUST,
) -> float:
    """Compute the 4-signal composite trust score.

        trust = 0.35×TSR + 0.40×WFS + 0.15×RH + 0.10×SS

    New agent (no tasks, no ratings):
        TSR = 0.0, WFS = 0.2, RH = 0.5, SS = 0.5
        trust = 0 + 0.08 + 0.075 + 0.05 = 0.205  (below 30% gate ✓)

    Anti-manipulation cap:
        tasks_completed < 3 → trust capped at 40%
        Ensures agents must do real work, not just collect ratings.
    """
    tsr = compute_tsr(tasks_received, ratings)
    wfs = compute_wfs(ratings, rating_weights, fallback_success_rate)
    rh  = compute_rh(ratings)
    ss  = specialization_score if specialization_score is not None else 0.5

    trust = W_TSR * tsr + W_WFS * wfs + W_RH * rh + W_SS * ss

    # Anti-manipulation: must complete real tasks to exceed 40%
    if tasks_completed < 3:
        trust = min(trust, MAX_TRUST_NO_WORK)

    return round(max(0.0, min(1.0, trust)), 4)


def compute_popularity(total_runs: int, max_runs: int) -> float:
    """Popularity score normalised against the most-chosen agent."""
    if max_runs == 0:
        return 0.0
    return round(total_runs / max_runs, 4)
