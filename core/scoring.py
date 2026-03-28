"""Scoring engine for Agentic Reputation Infrastructure Layer.

Trust score is a composite of:
- Rating average (success_rate) — quality of work
- Confidence — how many tasks rated (experience)
- Completion rate — tasks completed vs received (reliability)

New agents start with low trust (20%) until they prove themselves.
"""


def compute_trust_score(agent) -> float:
    """Compute composite trust score from agent state.

    Uses the agent's trust_score property which combines:
    - prior (0.2) weighted by inexperience
    - rating average weighted by experience
    - completion rate penalty if they don't deliver
    """
    return agent.trust_score


def compute_popularity(total_runs: int, max_runs: int) -> float:
    """Compute popularity score based on how often an agent is chosen.

    Returns a 0-1 score normalized against the most-chosen agent.
    """
    if max_runs == 0:
        return 0.0
    return round(total_runs / max_runs, 4)
