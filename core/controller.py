"""Simulation controller for Agentic Reputation Infrastructure Layer.

Runs multi-round agent interaction simulations that demonstrate
trust score evolution through agent-to-agent delegation and feedback.
"""

import random
import uuid

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


def update_trust(agent: Agent, outcome: bool) -> float:
    """Update agent trust score based on interaction outcome.

    new_success_rate = (old * total_runs + outcome) / (total_runs + 1)

    Returns the new success_rate.
    """
    old_sr = agent.success_rate
    outcome_val = 1.0 if outcome else 0.0
    new_sr = (old_sr * agent.total_runs + outcome_val) / (agent.total_runs + 1)
    agent.success_rate = round(new_sr, 4)
    agent.total_runs += 1
    return agent.success_rate


def determine_outcome(provider: Agent) -> bool:
    """Determine interaction outcome with probability influenced by trust.

    prob = success_rate (clamped to [0.1, 0.9] to avoid extremes)
    """
    prob = max(0.1, min(0.9, provider.success_rate))
    return random.random() < prob


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
    # Sort by match relevance, then by trust
    scored.sort(key=lambda x: (-x[1], -x[0].success_rate))
    return [agent for agent, _ in scored]


def run_simulation(store: AgentStore, rounds: int = 5) -> dict:
    """Run a multi-round agent interaction simulation.

    Each round:
    1. Select a random requester agent
    2. Pick a random task from the catalog
    3. Discover candidate providers by skill match
    4. Select provider (highest relevance + trust, with some randomness)
    5. Simulate output and determine outcome
    6. Update provider trust score
    7. Persist updated agent

    Returns dict with history (per-round trace) and final_agents.
    """
    agents = store.list_all()
    if len(agents) < 2:
        raise ValueError("At least 2 registered agents required to run simulation")

    history = []

    for round_num in range(1, rounds + 1):
        # 1. Select requester
        requester = random.choice(agents)

        # 2. Pick a task
        task_entry = random.choice(TASK_CATALOG)

        # 3. Discover candidates by skill match (exclude requester)
        candidates = _find_providers(store, task_entry, requester.agent_id)

        # Fall back to all agents except requester if no skill match
        if not candidates:
            candidates = [a for a in store.list_all() if a.agent_id != requester.agent_id]

        if not candidates:
            continue

        # 4. Select provider — best match, with randomness among top 2
        top = candidates[:min(2, len(candidates))]
        provider = random.choice(top)

        # 5. Determine outcome
        trust_before = provider.success_rate

        outcome = determine_outcome(provider)

        # 6. Update trust
        trust_after = update_trust(provider, outcome)

        # 7. Persist
        store.upsert(provider)

        # Record interaction
        interaction = Interaction(
            round_num=round_num,
            requester_agent_id=requester.agent_id,
            provider_agent_id=provider.agent_id,
            task=task_entry["task"],
            outcome=outcome,
            trust_before=trust_before,
            trust_after=trust_after,
        )
        history.append(interaction.to_dict())

        # Refresh agents list for next round
        agents = store.list_all()

    # Final state
    final_agents = [a.to_dict() for a in store.list_all()]
    final_agents.sort(key=lambda a: -a["success_rate"])

    return {
        "rounds": rounds,
        "history": history,
        "final_agents": final_agents,
    }
