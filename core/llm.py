"""Multi-provider LLM integration for Trust Layer MVP.

Generates candidate outputs from real LLM providers (OpenAI, Anthropic, Groq).
Each provider acts as its own agent with persistent reputation.
"""

import os
import time
import uuid

from core.models import Candidate


# --- Provider agents (each provider IS the agent) ---
PROVIDERS = [
    {
        "agent_id": "agent_gpt4",
        "agent_name": "GPT-4",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "env_key": "OPENAI_API_KEY",
    },
    {
        "agent_id": "agent_claude",
        "agent_name": "Claude",
        "provider": "anthropic",
        "model": "claude-haiku-4-5-20251001",
        "env_key": "ANTHROPIC_API_KEY",
    },
    {
        "agent_id": "agent_llama",
        "agent_name": "LLaMA",
        "provider": "groq",
        "model": "llama-3.3-70b-versatile",
        "env_key": "GROQ_API_KEY",
    },
]

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful AI assistant. Answer the following question or task "
    "clearly and thoroughly."
)


def get_available_providers() -> list:
    """Return list of provider dicts for which API keys are set."""
    available = []
    for p in PROVIDERS:
        if os.environ.get(p["env_key"]):
            available.append(p)
    return available


def _call_openai(prompt: str, system_prompt: str, model: str, api_key: str) -> tuple:
    """Call OpenAI API. Returns (output_text, latency_ms)."""
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    start = time.time()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        max_tokens=500,
        temperature=0.7,
    )
    latency = int((time.time() - start) * 1000)
    return response.choices[0].message.content, latency


def _call_anthropic(prompt: str, system_prompt: str, model: str, api_key: str) -> tuple:
    """Call Anthropic API. Returns (output_text, latency_ms)."""
    from anthropic import Anthropic
    client = Anthropic(api_key=api_key)
    start = time.time()
    response = client.messages.create(
        model=model,
        max_tokens=500,
        system=system_prompt,
        messages=[{"role": "user", "content": prompt}],
    )
    latency = int((time.time() - start) * 1000)
    return response.content[0].text, latency


def _call_groq(prompt: str, system_prompt: str, model: str, api_key: str) -> tuple:
    """Call Groq API. Returns (output_text, latency_ms)."""
    from groq import Groq
    client = Groq(api_key=api_key)
    start = time.time()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        max_tokens=500,
        temperature=0.7,
    )
    latency = int((time.time() - start) * 1000)
    return response.choices[0].message.content, latency


CALLER_MAP = {
    "openai": _call_openai,
    "anthropic": _call_anthropic,
    "groq": _call_groq,
}


def generate_candidates(prompt: str, task_id: str) -> list:
    """Generate candidates from available LLM providers.

    Calls each provider with an API key set. Each provider IS the agent.
    Requires at least 2 providers to be available.

    Args:
        prompt: The task prompt.
        task_id: Task identifier.

    Returns:
        list[Candidate]

    Raises:
        EnvironmentError: If fewer than 2 LLM API keys are set.
    """
    available = get_available_providers()

    if len(available) < 2:
        raise EnvironmentError(
            "At least 2 LLM API keys required. Set OPENAI_API_KEY, "
            "ANTHROPIC_API_KEY, and/or GROQ_API_KEY."
        )

    candidates = []
    for p in available:
        api_key = os.environ.get(p["env_key"])
        caller = CALLER_MAP[p["provider"]]
        try:
            output_text, latency = caller(prompt, DEFAULT_SYSTEM_PROMPT, p["model"], api_key)
            candidates.append(Candidate(
                output_id=f"out_{p['agent_id']}_{uuid.uuid4().hex[:6]}",
                task_id=task_id,
                agent_id=p["agent_id"],
                output_text=output_text,
                latency_ms=latency,
            ))
        except Exception as e:
            candidates.append(Candidate(
                output_id=f"out_{p['agent_id']}_{uuid.uuid4().hex[:6]}",
                task_id=task_id,
                agent_id=p["agent_id"],
                output_text=f"[Error: {p['provider']} call failed: {e}]",
                latency_ms=0,
            ))
    return candidates
