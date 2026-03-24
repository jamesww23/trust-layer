"""Multi-provider LLM integration for Trust Layer MVP.

Generates candidate outputs from real LLM providers (OpenAI, Anthropic, Groq).
Each provider acts as its own agent with persistent reputation.
Falls back to persona mode if only one provider is available.
"""

import os
import time
import uuid

from core.models import Candidate


# --- Real provider agents (each provider IS the agent) ---
PROVIDERS = [
    {
        "agent_id": "agent_openai",
        "agent_name": "OpenAI GPT-4o-mini",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "env_key": "OPENAI_API_KEY",
    },
    {
        "agent_id": "agent_claude",
        "agent_name": "Anthropic Claude Haiku",
        "provider": "anthropic",
        "model": "claude-3-5-haiku-20241022",
        "env_key": "ANTHROPIC_API_KEY",
    },
    {
        "agent_id": "agent_groq",
        "agent_name": "Groq LLaMA 3 70B",
        "provider": "groq",
        "model": "llama3-70b-8192",
        "env_key": "GROQ_API_KEY",
    },
]

# --- Fallback personas (used when only 1 provider key is set) ---
PERSONAS = [
    {
        "agent_id": "persona_analyst",
        "agent_name": "Concise Analyst",
        "system_prompt": (
            "You are a concise analyst. Provide brief, data-driven responses. "
            "Focus on key facts and metrics. Keep your response under 100 words."
        ),
    },
    {
        "agent_id": "persona_researcher",
        "agent_name": "Detailed Researcher",
        "system_prompt": (
            "You are a detailed researcher. Provide thorough, well-structured responses. "
            "Include context, evidence, and nuance. Aim for 150-200 words."
        ),
    },
    {
        "agent_id": "persona_creative",
        "agent_name": "Creative Thinker",
        "system_prompt": (
            "You are a creative thinker. Provide innovative, outside-the-box responses. "
            "Use analogies and fresh perspectives. Keep it engaging and around 100-150 words."
        ),
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


def generate_candidates(prompt: str, task_id: str, personas: list = None,
                        model: str = "gpt-4o-mini") -> list:
    """Generate candidates from available LLM providers.

    Multi-provider mode: If 2+ provider API keys are set, calls each provider
    once with the same system prompt. Each provider IS the agent.

    Persona fallback: If only 1 provider key is set, uses persona mode —
    calls that provider 3 times with different system prompts.

    Args:
        prompt: The task prompt.
        task_id: Task identifier.
        personas: Optional override for persona mode.
        model: Model override (only used in persona fallback mode).

    Returns:
        list[Candidate]

    Raises:
        EnvironmentError: If no LLM API keys are set.
    """
    available = get_available_providers()

    if len(available) >= 2:
        # Multi-provider mode: each real provider is its own agent
        return _generate_multi_provider(prompt, task_id, available)
    elif len(available) == 1:
        # Persona fallback: one provider, multiple personas
        provider = available[0]
        return _generate_persona_fallback(prompt, task_id, provider, personas, model)
    else:
        raise EnvironmentError(
            "At least one LLM API key required. Set OPENAI_API_KEY, "
            "ANTHROPIC_API_KEY, or GROQ_API_KEY."
        )


def _generate_multi_provider(prompt: str, task_id: str, providers: list) -> list:
    """Call each available provider once with the same prompt."""
    candidates = []
    for p in providers:
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
            # If one provider fails, continue with others
            candidates.append(Candidate(
                output_id=f"out_{p['agent_id']}_{uuid.uuid4().hex[:6]}",
                task_id=task_id,
                agent_id=p["agent_id"],
                output_text=f"[Error: {p['provider']} call failed: {e}]",
                latency_ms=0,
            ))
    return candidates


def _generate_persona_fallback(prompt: str, task_id: str, provider: dict,
                                personas: list = None, model: str = None) -> list:
    """Call one provider multiple times with different personas."""
    api_key = os.environ.get(provider["env_key"])
    caller = CALLER_MAP[provider["provider"]]
    use_model = model or provider["model"]
    personas = personas or PERSONAS
    candidates = []

    for p in personas:
        system_prompt = p.get("system_prompt", DEFAULT_SYSTEM_PROMPT)
        output_text, latency = caller(prompt, system_prompt, use_model, api_key)
        candidates.append(Candidate(
            output_id=f"out_{p['agent_id']}_{uuid.uuid4().hex[:6]}",
            task_id=task_id,
            agent_id=p["agent_id"],
            output_text=output_text,
            latency_ms=latency,
        ))

    return candidates
