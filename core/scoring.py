"""Scoring engine for Trust Layer MVP."""

import os
import re
from typing import Optional

from core.models import ScoringConfig


JUDGE_SYSTEM_PROMPT = (
    "You are an impartial judge evaluating AI assistant responses. "
    "Rate the following response to the given prompt on a scale from 0.0 to 1.0, where:\n"
    "- 0.0 = completely irrelevant, wrong, or refuses to answer\n"
    "- 0.5 = partially relevant but incomplete or generic\n"
    "- 1.0 = excellent, thorough, and directly addresses the prompt\n\n"
    "Reply with ONLY a single number between 0.0 and 1.0. Nothing else."
)


def llm_judge_score(prompt: str, response_text: str) -> Optional[float]:
    """Use an LLM to score a response's quality/relevance.

    Calls Groq (fastest/cheapest) to judge the response.
    Returns a float in [0.0, 1.0], or None if the call fails.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return None

    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": f"Prompt: {prompt}\n\nResponse: {response_text}"},
            ],
            max_tokens=10,
            temperature=0.0,
        )
        score_text = response.choices[0].message.content.strip()
        score = float(score_text)
        return max(0.0, min(1.0, round(score, 4)))
    except Exception:
        return None


class ScoringEngine:
    """Computes relevancy and trust scores for candidates."""

    def __init__(self, config: ScoringConfig):
        self.config = config

    def compute_relevancy(self, output_text: str, expected_keywords: list,
                          judge_score: float = None) -> float:
        """Compute relevancy from keywords and/or LLM judge score.

        Priority:
        - Keywords + judge: average both signals (0.5 * keyword + 0.5 * judge)
        - Keywords only: keyword matching score
        - Judge only: judge score directly
        - Neither: 0.5 default

        Returns float in [0.0, 1.0], rounded to 4 decimals.
        """
        has_keywords = bool(expected_keywords)
        has_judge = judge_score is not None

        if has_keywords:
            text_lower = output_text.lower()
            matched = 0
            for keyword in expected_keywords:
                pattern = r"\b" + re.escape(keyword.lower()) + r"\b"
                if re.search(pattern, text_lower):
                    matched += 1
            keyword_score = matched / len(expected_keywords)

            if has_judge:
                return round(0.5 * keyword_score + 0.5 * judge_score, 4)
            return round(keyword_score, 4)

        if has_judge:
            return round(judge_score, 4)

        return 0.5

    def compute_trust_score(self, success_rate: float, relevancy: float) -> float:
        """Compute trust score from reputation and relevancy.

        trust_score = w_reputation * success_rate + w_relevancy * relevancy

        Both inputs must be in [0.0, 1.0].
        Output rounded to 4 decimals.
        """
        success_rate = max(0.0, min(1.0, success_rate))
        relevancy = max(0.0, min(1.0, relevancy))

        score = (self.config.w_reputation * success_rate +
                 self.config.w_relevancy * relevancy)
        return round(score, 4)
