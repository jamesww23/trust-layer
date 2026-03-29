"""Simulation controller for Agentic Reputation Infrastructure Layer.

Implements all 6 architecture components:
1. Discovery API — find agents by skill match
2. Reputation Registry — trust scores evolve with interactions
3. Trust Gate — reject providers below configurable threshold
4. Feedback Ingestion — explicit feedback after task completion
5. Task Delegation — requester selects and delegates to provider
6. Outcome Flow — execute → feedback → registry update (or reject/flag)
"""

import random

from core.models import Agent, Interaction
from core.store import AgentStore

# Task types that agents can request — each maps to skill keywords
TASK_CATALOG = [
    {"task": "Summarize this legal contract", "keywords": ["summariz", "legal", "document", "contract"]},
    {"task": "Write a Python REST API", "keywords": ["code", "python", "api", "programming"]},
    {"task": "Analyze Q3 revenue trends", "keywords": ["analy", "finance", "data", "business", "market"]},
    {"task": "Research competitor landscape", "keywords": ["research", "analysis", "investigation", "competitive"]},
    {"task": "Translate docs to Spanish", "keywords": ["translat", "language", "localization", "documentation"]},
    {"task": "Review this pull request", "keywords": ["code", "review", "debug", "refactor"]},
    {"task": "Summarize research paper findings", "keywords": ["summariz", "research", "paper", "synthesis"]},
    {"task": "Build a data dashboard", "keywords": ["data", "analy", "report", "intelligence"]},
    {"task": "Investigate security vulnerability", "keywords": ["security", "research", "vulnerability", "analysis"]},
    {"task": "Translate API docs to Japanese", "keywords": ["translat", "api", "documentation", "language"]},
]

# Default trust gate threshold
DEFAULT_TRUST_THRESHOLD = 0.3


def update_trust(agent: Agent, feedback_score: float) -> float:
    """Update agent trust score using the requester's feedback score.

    The feedback score (0.0–1.0) is the signal from the requester after
    evaluating the outcome.  This is the value that enters the running
    average so that the full path is: Outcome → Feedback → Registry Update.

    new_success_rate = (old * total_runs + feedback_score) / (total_runs + 1)

    Returns the new success_rate.
    """
    old_sr = agent.success_rate
    new_sr = (old_sr * agent.total_runs + feedback_score) / (agent.total_runs + 1)
    agent.success_rate = round(new_sr, 4)
    agent.total_runs += 1
    return agent.success_rate


def determine_outcome(provider: Agent) -> bool:
    """Determine interaction outcome with probability influenced by trust.

    Uses composite trust_score (clamped to [0.1, 0.9] to avoid extremes).
    """
    prob = max(0.1, min(0.9, provider.trust_score))
    return random.random() < prob


def compute_feedback_score(outcome: bool, provider: Agent) -> float:
    """Compute explicit feedback score from requester to provider.

    Feedback is on a 0.0-1.0 scale, influenced by outcome and provider trust.
    Adds slight randomness to simulate real requester judgment.
    """
    if outcome:
        base = 0.7 + 0.2 * provider.trust_score
        noise = random.uniform(-0.1, 0.1)
    else:
        base = 0.1 + 0.2 * provider.trust_score
        noise = random.uniform(-0.05, 0.1)
    return round(max(0.0, min(1.0, base + noise)), 2)


def apply_trust_gate(candidates: list, threshold: float) -> tuple:
    """Apply trust gate — filter out agents below threshold.

    Uses the composite trust_score (not raw success_rate) so that
    unproven agents with 0 tasks are also gated appropriately.

    Returns (passed, rejected) where each is a list of agents.
    """
    passed = []
    rejected = []
    for agent in candidates:
        if agent.trust_score >= threshold:
            passed.append(agent)
        else:
            rejected.append(agent)
    return passed, rejected


def validate_delegation(store: AgentStore, requester_id: str, provider_id: str,
                        threshold: float = DEFAULT_TRUST_THRESHOLD) -> None:
    """Validate a delegation request. Raises ValueError if invalid.

    Checks:
    1. Self-delegation is not allowed.
    2. Provider must pass the trust gate.
    """
    if requester_id == provider_id:
        raise ValueError("Self-delegation is not allowed — an agent cannot delegate tasks to itself")

    provider = store.get(provider_id)
    if provider is None:
        raise ValueError(f"Provider agent '{provider_id}' not found")

    if provider.trust_score < threshold:
        raise ValueError(
            f"Provider '{provider_id}' has trust {provider.trust_score:.2f} "
            f"which is below the minimum threshold ({threshold:.2f}). "
            f"Delegation rejected."
        )


def submit_feedback(store: AgentStore, provider_id: str, score: float,
                    task_id: str = None, rated_by: str = None) -> dict:
    """Submit explicit feedback for an agent (standalone endpoint support).

    Uses the same update_trust path as the simulation loop so that
    the standalone endpoint and the simulation are coherent.

    Score is 0.0-1.0.  Treated as a feedback observation and folded
    into the running-average trust score.

    If task_id is provided, the task is marked as 'rated' with the score.

    Returns dict with agent, trust_before, trust_after, and task context.
    """
    from datetime import datetime, timezone

    if score < 0.0 or score > 1.0:
        raise ValueError("Feedback score must be between 0.0 and 1.0")
    agent = store.get(provider_id)
    if agent is None:
        raise ValueError(f"Agent '{provider_id}' not found")

    # If task_id provided, validate BEFORE any mutation
    if task_id:
        task = store.get_task(task_id)
        if task is None:
            raise ValueError(f"Task '{task_id}' not found")
        if task.provider_id != provider_id:
            raise ValueError(
                f"Task '{task_id}' belongs to provider '{task.provider_id}', "
                f"not '{provider_id}'. Cannot rate a task for a different provider."
            )
        if task.status == "pending":
            raise ValueError(
                f"Task '{task_id}' is still pending. "
                f"Cannot rate a task before the provider submits a result."
            )
        if task.status == "rated":
            raise ValueError(
                f"Task '{task_id}' has already been rated."
            )

    # All validation passed — now mutate agent trust
    trust_before = agent.trust_score
    update_trust(agent, score)
    trust_after = agent.trust_score
    store.upsert(agent)

    result = {
        "agent": agent.to_dict(),
        "trust_before": trust_before,
        "trust_after": trust_after,
        "provider_id": provider_id,
        "rating": score,
    }

    # Mark task as rated (already validated above)
    if task_id:
        task.status = "rated"
        task.rating = score
        task.rated_by = rated_by or task.requester_id
        task.rated_at = datetime.now(timezone.utc).isoformat()
        task.trust_before = trust_before
        task.trust_after = trust_after
        store.save_task(task)
        result["task"] = task.to_dict()
        result["requester_id"] = task.requester_id

    if rated_by:
        result["rated_by"] = rated_by

    return result


def _find_providers(store: AgentStore, task_entry: dict, exclude_id: str) -> list:
    """Find agents whose skill_md matches any of the task keywords."""
    all_agents = store.list_all()
    scored = []
    for agent in all_agents:
        if agent.agent_id == exclude_id:
            continue
        skill_lower = agent.skill_md.lower()
        match_count = sum(1 for kw in task_entry["keywords"] if kw in skill_lower)
        if match_count > 0:
            scored.append((agent, match_count))
    # Sort by match relevance, then by trust score
    scored.sort(key=lambda x: (-x[1], -x[0].trust_score))
    return [agent for agent, _ in scored]


def run_simulation(store: AgentStore, rounds: int = 5,
                   trust_threshold: float = DEFAULT_TRUST_THRESHOLD) -> dict:
    """Run a multi-round agent interaction simulation.

    Each round implements all 6 architecture components:
    1. DISCOVERY — find candidate providers by skill match
    2. TRUST GATE — reject candidates below trust threshold
    3. TASK DELEGATION — requester selects provider from gate-passed candidates
    4. OUTCOME — simulate task execution, determine success/failure
    5. FEEDBACK — requester submits explicit feedback score
    6. REGISTRY UPDATE — update provider trust score, persist changes

    Returns dict with history (per-round trace) and final_agents.
    """
    agents = store.list_all()
    if len(agents) < 2:
        raise ValueError("At least 2 registered agents required to run simulation")

    history = []

    for round_num in range(1, rounds + 1):
        # Select requester
        requester = random.choice(agents)

        # Pick a task
        task_entry = random.choice(TASK_CATALOG)

        # --- 1. DISCOVERY ---
        candidates = _find_providers(store, task_entry, requester.agent_id)

        # Fall back to all agents except requester if no skill match
        if not candidates:
            candidates = [a for a in store.list_all() if a.agent_id != requester.agent_id]

        if not candidates:
            continue

        discovery_count = len(candidates)

        # --- 2. TRUST GATE ---
        passed, rejected = apply_trust_gate(candidates, trust_threshold)

        # Flag rejected agents
        rejected_ids = []
        for rej_agent in rejected:
            rej_agent.flagged += 1
            store.upsert(rej_agent)
            rejected_ids.append(rej_agent.agent_id)

        # If all candidates rejected, record the rejection and continue
        if not passed:
            interaction = Interaction(
                round_num=round_num,
                requester_agent_id=requester.agent_id,
                provider_agent_id="none",
                task=task_entry["task"],
                discovery_candidates=discovery_count,
                gate_passed=False,
                gate_rejected=rejected_ids,
                outcome=None,
                feedback_score=None,
                trust_before=0.0,
                trust_after=0.0,
            )
            history.append(interaction.to_dict())
            continue

        # --- 3. TASK DELEGATION ---
        top = passed[:min(2, len(passed))]
        provider = random.choice(top)

        # Track task received
        provider.tasks_received += 1

        # --- 4. OUTCOME ---
        trust_before = provider.trust_score
        outcome = determine_outcome(provider)

        # Track task completed (result submitted)
        if outcome:
            provider.tasks_completed += 1

        # --- 5. FEEDBACK ---
        feedback_score = compute_feedback_score(outcome, provider)

        # --- 6. REGISTRY UPDATE (uses feedback, not raw outcome) ---
        update_trust(provider, feedback_score)
        trust_after = provider.trust_score
        store.upsert(provider)

        # Record full interaction trace
        interaction = Interaction(
            round_num=round_num,
            requester_agent_id=requester.agent_id,
            provider_agent_id=provider.agent_id,
            task=task_entry["task"],
            discovery_candidates=discovery_count,
            gate_passed=True,
            gate_rejected=rejected_ids,
            outcome=outcome,
            feedback_score=feedback_score,
            trust_before=trust_before,
            trust_after=trust_after,
        )
        history.append(interaction.to_dict())

        # Refresh agents list for next round
        agents = store.list_all()

    # Final state
    final_agents = [a.to_dict() for a in store.list_all()]
    final_agents.sort(key=lambda a: -a["trust_score"])

    return {
        "rounds": rounds,
        "trust_threshold": trust_threshold,
        "history": history,
        "final_agents": final_agents,
    }
