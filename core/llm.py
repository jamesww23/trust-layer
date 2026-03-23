"""OpenAI LLM integration for Trust Layer MVP.

Generates candidate outputs from multiple agent personas using OpenAI API.
Each persona has a fixed agent_id so reputation accumulates across runs.
"""

import os
import time
import uuid

from core.models import Candidate


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


def generate_candidates(prompt: str, task_id: str, personas: list = None,
                        model: str = "gpt-4o-mini") -> list:
    """Call OpenAI for each persona and return Candidate objects.

    Args:
        prompt: The task prompt to send to each persona.
        task_id: Task identifier for the candidates.
        personas: Optional list of persona dicts. Defaults to PERSONAS.
        model: OpenAI model to use. Default: gpt-4o-mini.

    Returns:
        list[Candidate]: One candidate per persona.

    Raises:
        EnvironmentError: If OPENAI_API_KEY is not set.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY environment variable is required")

    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    personas = personas or PERSONAS
    candidates = []

    for p in personas:
        start = time.time()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": p["system_prompt"]},
                {"role": "user", "content": prompt},
            ],
            max_tokens=500,
            temperature=0.7,
        )
        latency = int((time.time() - start) * 1000)
        output_text = response.choices[0].message.content

        candidates.append(Candidate(
            output_id=f"out_{p['agent_id']}_{uuid.uuid4().hex[:6]}",
            task_id=task_id,
            agent_id=p["agent_id"],
            output_text=output_text,
            latency_ms=latency,
        ))

    return candidates
