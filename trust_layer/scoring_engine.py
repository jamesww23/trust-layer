import re
from typing import List
from .schemas import (
    AgentProfile,
    Candidate,
    Task,
    ScoredCandidate,
    ScoringConfig,
    DEFAULT_CONFIG,
)


class ScoringEngine:
    def compute_relevancy(self, output_text: str, expected_keywords: List[str]) -> float:
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
        score = (w_rep * success_rate) + (w_rel * relevancy)
        return round(min(max(score, 0.0), 1.0), 4)

    def score(
        self,
        candidate: Candidate,
        task: Task,
        profile: AgentProfile,
        config: ScoringConfig = DEFAULT_CONFIG,
    ) -> ScoredCandidate:
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
