"""Scoring engine for Agentic Reputation Infrastructure Layer.

trust_score = success_rate (MVP simplicity)
"""


def compute_trust_score(success_rate: float) -> float:
    """Compute trust score from success rate.

    For MVP: trust_score = success_rate
    Clamped to [0.0, 1.0], rounded to 4 decimals.
    """
    return round(max(0.0, min(1.0, success_rate)), 4)


def compute_popularity(total_runs: int, max_runs: int) -> float:
    """Compute popularity score based on how often an agent is chosen.

    Returns a 0-1 score normalized against the most-chosen agent.
    """
    if max_runs == 0:
        return 0.0
    return round(total_runs / max_runs, 4)
