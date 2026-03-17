"""Scoring engine for Trust Layer MVP."""

import re

from core.models import ScoringConfig


class ScoringEngine:
    """Computes relevancy and trust scores for candidates."""

    def __init__(self, config: ScoringConfig):
        self.config = config

    def compute_relevancy(self, output_text: str, expected_keywords: list) -> float:
        """Compute keyword relevancy using whole-word regex matching.

        - Uses regex word boundaries to avoid substring false positives.
        - If expected_keywords is empty, returns 0.5.
        - Returns float in [0.0, 1.0], rounded to 4 decimals.
        """
        if not expected_keywords:
            return 0.5

        text_lower = output_text.lower()
        matched = 0

        for keyword in expected_keywords:
            pattern = r"\b" + re.escape(keyword.lower()) + r"\b"
            if re.search(pattern, text_lower):
                matched += 1

        relevancy = matched / len(expected_keywords)
        return round(relevancy, 4)

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
