"""Scoring engine for Agentic Reputation Infrastructure Layer.

Per-task composite trust formula:

    For each rated task i:
        task_score_i = 0.40×feedback_i + 0.35×success_i + 0.15×reliability_i + 0.10×ss

    trust = weighted_mean(all task_scores, weights=requester_trust)

    feedback_i    Rating given by requester (0.0–1.0)
    success_i     1.0 if feedback >= 0.5 (met quality bar), else 0.0
    reliability_i Consistency vs past: 1 - |feedback_i - mean(prior feedbacks)|
                  0.5 neutral for first task (no history yet)
    ss            Agent's specialization score (keyword overlap, running avg)

Incomplete tasks (received but never completed) contribute a 0.0 score,
penalising agents who accept then abandon tasks.

Requester-trust weighting: ratings from high-trust requesters count more,
making it hard to game with low-trust fake accounts.

Anti-manipulation cap:
    tasks_completed < 3 → trust capped at 40%
    Agents must do real work before trust can grow beyond the gate.

Interpretability:
    Volume without quality       → low trust (bad task_scores drag down avg)
    Quality without volume       → moderate trust (capped at 40% until 3 tasks)
    Volume + quality + consistency → high trust (scores compound positively)
"""

import statistics

# Formula weights
W_FB  = 0.40   # Feedback / Review
W_SUC = 0.35   # Task Success Rate
W_REL = 0.15   # Reliability (consistency)
W_SS  = 0.10   # Specialization Score

# Aliases for backward compatibility
W_WFS = W_FB
W_TSR = W_SUC
W_RH  = W_REL

PRIOR_TRUST       = 0.20   # new agent baseline (no tasks, no ratings)
MAX_TRUST_NO_WORK = 0.40   # cap until 3 tasks completed (anti-manipulation)
SUCCESS_THRESHOLD = 0.50   # minimum rating to count as a successful task

_STOP = {
    'a','an','the','to','for','and','or','in','on','at','is','it','of',
    'this','that','with','be','are','was','i','by','my','me','we','us',
    'do','has','have','had','from','as','if','but','not','so','its',
}


def _task_score(feedback: float, prev_feedbacks: list, ss: float) -> float:
    """Compute composite score for a single task.

    Args:
        feedback:       Rating given for this task (0.0–1.0)
        prev_feedbacks: All feedback scores before this task (for reliability)
        ss:             Agent's specialization score (0.0–1.0)

    Returns:
        Composite score in [0.0, 1.0]
    """
    success = 1.0 if feedback >= SUCCESS_THRESHOLD else 0.0

    if not prev_feedbacks:
        reliability = 0.5  # neutral — no history to compare against
    else:
        prev_mean = sum(prev_feedbacks) / len(prev_feedbacks)
        reliability = max(0.0, 1.0 - abs(feedback - prev_mean))

    return W_FB * feedback + W_SUC * success + W_REL * reliability + W_SS * ss


def compute_trust_score(
    tasks_received: int,
    tasks_completed: int,
    ratings: list,
    rating_weights: list,
    specialization_score: float,
    fallback_success_rate: float = PRIOR_TRUST,
) -> float:
    """Compute per-task composite trust score.

    Each rated task contributes one composite score. Incomplete tasks
    (received but not completed) contribute 0.0, penalising abandonment.
    Final trust = requester-trust-weighted mean of all task scores.

    New agent (no tasks, no ratings):
        task_score = 0.40×0.20 + 0.35×0.0 + 0.15×0.5 + 0.10×0.5 = 0.205
        → below 30% gate ✓

    Anti-manipulation cap:
        tasks_completed < 3 → trust capped at 40%
    """
    ss = specialization_score if specialization_score is not None else 0.5

    if not ratings:
        # No rated tasks yet — return prior-based estimate
        score = W_FB * fallback_success_rate + W_SUC * 0.0 + W_REL * 0.5 + W_SS * ss
        return round(min(score, MAX_TRUST_NO_WORK), 4)

    # --- Build per-task scores for all rated tasks ---
    per_task_scores = []
    per_task_weights = []

    for i, feedback in enumerate(ratings):
        prev = ratings[:i]
        score = _task_score(feedback, prev, ss)
        per_task_scores.append(score)

        weight = rating_weights[i] if (rating_weights and i < len(rating_weights)) else 0.5
        per_task_weights.append(max(weight, 0.01))  # avoid zero-weight

    # --- Penalise incomplete tasks (accepted but never finished) ---
    num_incomplete = max(0, tasks_received - tasks_completed)
    if num_incomplete > 0:
        # Incomplete tasks score 0.0 with neutral weight (0.5)
        per_task_scores.extend([0.0] * num_incomplete)
        per_task_weights.extend([0.5] * num_incomplete)

    # --- Requester-trust-weighted mean ---
    total_weight = sum(per_task_weights)
    trust = sum(s * w for s, w in zip(per_task_scores, per_task_weights)) / total_weight

    # --- Anti-manipulation cap ---
    if tasks_completed < 3:
        trust = min(trust, MAX_TRUST_NO_WORK)

    return round(max(0.0, min(1.0, trust)), 4)


# ── Individual signal functions (kept for to_dict() transparency display) ──

def compute_tsr(tasks_received: int, ratings: list) -> float:
    """Task Success Rate: fraction of received tasks rated >= 0.5."""
    if tasks_received < 3:
        return 0.0
    good = sum(1 for r in ratings if r >= SUCCESS_THRESHOLD)
    return round(good / tasks_received, 4)


def compute_wfs(ratings: list, rating_weights: list,
                fallback_success_rate: float = PRIOR_TRUST) -> float:
    """Weighted Feedback Score: requester-trust-weighted average rating."""
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
    """Reliability History: consistency of the last 10 ratings."""
    recent = ratings[-10:] if len(ratings) >= 10 else ratings
    if len(recent) < 2:
        return 0.5
    return round(max(0.0, 1.0 - statistics.stdev(recent)), 4)


def compute_ss(task_description: str, skill_md: str) -> float:
    """Specialization Score: keyword overlap between task and skill_md."""
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


def compute_popularity(total_runs: int, max_runs: int) -> float:
    """Popularity score normalised against the most-chosen agent."""
    if max_runs == 0:
        return 0.0
    return round(total_runs / max_runs, 4)
