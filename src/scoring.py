"""ScoringEngine — computes relevancy and Trust Score per candidate.

Relevancy: whole-word keyword overlap between output_text and Task.expected_keywords.
Trust Score: weighted combination of reputation (success_rate) and relevancy.
"""

import re
from typing import List

from models import (
    AgentProfile,
    Candidate,
    Task,
    ScoredCandidate,
    ScoringConfig,
    DEFAULT_CONFIG,
)


class ScoringEngine:

    def compute_relevancy(self, output_text: str, expected_keywords: List[str]) -> float:
        """Whole-word keyword match. Returns float [0.0, 1.0].

        - Empty keywords -> 0.5 (neutral, prevents reputation from being sole signal)
        - Uses regex word boundaries to prevent 'solar' matching 'solarize'
        """
        if not expected_keywords:
            return 0.5
        text_lower = output_text.lower()
        matched = sum(
            1
            for kw in expected_keywords
            if re.search(r"\b" + re.escape(kw.lower()) + r"\b", text_lower)
        )
        return round(matched / len(expected_keywords), 4)

    def compute_trust_score(
        self,
        success_rate: float,
        relevancy: float,
        w_rep: float = 0.6,
        w_rel: float = 0.4,
    ) -> float:
        """trust_score = (w_rep * success_rate) + (w_rel * relevancy). Clamped [0,1]."""
        score = (w_rep * success_rate) + (w_rel * relevancy)
        return round(min(max(score, 0.0), 1.0), 4)

    def score(
        self,
        candidate: Candidate,
        task: Task,
        profile: AgentProfile,
        config: ScoringConfig = DEFAULT_CONFIG,
    ) -> ScoredCandidate:
        """Full scoring pipeline for one candidate."""
        relevancy = self.compute_relevancy(candidate.output_text, task.expected_keywords)
        trust_score = self.compute_trust_score(
            profile.success_rate,
            relevancy,
            config.w_reputation,
            config.w_relevancy,
        )
        return ScoredCandidate(
            candidate=candidate,
            relevancy=relevancy,
            trust_score=trust_score,
        )
