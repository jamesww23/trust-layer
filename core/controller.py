"""Simulation controller for Agentic Reputation Infrastructure Layer.

Runs multi-round agent interaction simulations that demonstrate
trust score evolution through agent-to-agent delegation and feedback.
"""

import random
import uuid

from core.models import Agent, Interaction
from core.store import AgentStore

# Keywords used to match requesters to providers during simulation
SIMULATION_KEYWORDS = [
    "summarize", "translate", "analyze", "code", "research",
    "legal", "finance", "data", "writing", "security",
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

    prob = 0.5 + (success_rate - 0.5)
    = success_rate (clamped to [0.1, 0.9] to avoid extremes)
    """
    prob = max(0.1, min(0.9, provider.success_rate))
    return random.random() < prob


def run_simulation(store: AgentStore, rounds: int = 5) -> dict:
    """Run a multi-round agent interaction simulation.

    Each round:
    1. Select a random requester agent
    2. Pick a random keyword
    3. Discover candidate providers (excluding requester)
    4. Select provider (highest trust or random among top 2)
    5. Simulate output and determine outcome
    6. Update provider trust score
    7. Persist updated agent

    Args:
        store: AgentStore with registered agents.
        rounds: Number of interaction rounds to run.

    Returns:
        dict with history (per-round trace) and final_agents.
    """
    agents = store.list_all()
    if len(agents) < 2:
        raise ValueError("At least 2 registered agents required to run simulation")

    history = []

    for round_num in range(1, rounds + 1):
        # 1. Select requester
        requester = random.choice(agents)

        # 2. Pick keyword
        keyword = random.choice(SIMULATION_KEYWORDS)

        # 3. Discover candidates (exclude requester)
        candidates = store.discover(keyword)
        candidates = [c for c in candidates if c.agent_id != requester.agent_id]

        # If no keyword match, fall back to all agents except requester
        if not candidates:
            candidates = [a for a in store.list_all() if a.agent_id != requester.agent_id]

        if not candidates:
            continue

        # 4. Select provider — highest trust, with some randomness among top 2
        candidates.sort(key=lambda a: -a.success_rate)
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
