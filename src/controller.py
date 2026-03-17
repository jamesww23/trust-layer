"""TrustController — orchestrates the full 11-step agent loop.

Steps:
1.  Validate Task
2.  Load Agent Profiles
3.  Validate Candidates
4.  Compute Relevancy
5.  Compute Trust Score
6.  Rank Candidates
7.  Select Winner
8.  Determine Outcome
9.  Update Reputation (winner only)
10. Persist State
11. Return TaskResult
"""

import json
from typing import Optional, List, Dict
from datetime import datetime, timezone

from models import (
    AgentProfile,
    Candidate,
    Task,
    TaskResult,
    ScoringConfig,
    DEFAULT_CONFIG,
)
from scoring import ScoringEngine
from store import ReputationStore
from utils import TrustLogger


class TrustController:
    def __init__(
        self,
        store: ReputationStore,
        engine: ScoringEngine,
        config: ScoringConfig = DEFAULT_CONFIG,
        logger: Optional[TrustLogger] = None,
    ):
        self.store = store
        self.engine = engine
        self.config = config
        self.logger = logger or TrustLogger()

    def run_task(
        self,
        task: Task,
        candidates: List[Candidate],
        outcome: Optional[bool] = None,
    ) -> TaskResult:
        """Execute the full Trust Layer loop. Returns TaskResult."""

        self.logger.header(task.task_id)

        # ---------------------------------------------------------------
        # [CONFIG] — log active weights
        # ---------------------------------------------------------------
        self.logger.config(self.config)

        # ---------------------------------------------------------------
        # Step 1: Validate Task
        # ---------------------------------------------------------------
        if not task.task_id:
            raise ValueError("task_id must not be empty")
        if not task.prompt:
            raise ValueError("prompt must not be empty")
        if not task.expected_keywords:
            raise ValueError("expected_keywords must have at least 1 keyword")

        # ---------------------------------------------------------------
        # Step 3: Validate Candidates (before loading profiles)
        # ---------------------------------------------------------------
        if len(candidates) < 2:
            raise ValueError("Must have at least 2 candidates")

        agent_ids = [c.agent_id for c in candidates]
        if len(agent_ids) != len(set(agent_ids)):
            raise ValueError("Duplicate agent_id in candidates")

        for c in candidates:
            if c.task_id != task.task_id:
                raise ValueError(
                    f"Candidate {c.output_id} task_id={c.task_id} "
                    f"does not match task {task.task_id}"
                )

        # ---------------------------------------------------------------
        # Step 2: Load Agent Profiles
        # ---------------------------------------------------------------
        profiles: Dict[str, AgentProfile] = {}
        for c in candidates:
            profile = self.store.get(c.agent_id)
            if profile is None:
                profile = AgentProfile.default(c.agent_id)
                self.store.upsert(profile)
                self.logger.init_profile(profile)
            else:
                self.logger.load_profile(profile)
            profiles[c.agent_id] = profile

        # ---------------------------------------------------------------
        # Steps 4-5: Compute Relevancy + Trust Score
        # ---------------------------------------------------------------
        scored = []
        for c in candidates:
            sc = self.engine.score(c, task, profiles[c.agent_id], self.config)
            scored.append(sc)
            self.logger.score(c.agent_id, sc.relevancy, sc.trust_score)

        # ---------------------------------------------------------------
        # Step 6: Rank Candidates (deterministic)
        # ---------------------------------------------------------------
        scored.sort(
            key=lambda s: (
                -s.trust_score,
                -profiles[s.candidate.agent_id].total_runs,
                s.candidate.agent_id,
            )
        )

        # Warn on tie
        if len(scored) >= 2 and scored[0].trust_score == scored[1].trust_score:
            self.logger.warn_tie(
                scored[0].candidate.agent_id,
                scored[1].candidate.agent_id,
                scored[0].trust_score,
            )

        for i, sc in enumerate(scored, 1):
            self.logger.rank(i, sc.candidate.agent_id, sc.trust_score)

        # ---------------------------------------------------------------
        # Step 7: Select Winner
        # ---------------------------------------------------------------
        winner_sc = scored[0]
        winner = winner_sc.candidate
        winner_profile = profiles[winner.agent_id]

        # ---------------------------------------------------------------
        # Step 8: Determine Outcome
        # ---------------------------------------------------------------
        auto = outcome is None
        if auto:
            final_outcome = len(winner.output_text.strip().split()) >= 3
        else:
            final_outcome = outcome

        self.logger.select(winner.agent_id, winner_sc.trust_score, final_outcome, auto)

        # ---------------------------------------------------------------
        # Step 9: Update Reputation (winner only)
        # ---------------------------------------------------------------
        o = 1.0 if final_outcome else 0.0
        old_rate = winner_profile.success_rate
        old_runs = winner_profile.total_runs

        new_rate = round(
            (old_rate * old_runs + o) / (old_runs + 1),
            6,
        )
        new_runs = old_runs + 1

        winner_profile.success_rate = new_rate
        winner_profile.total_runs = new_runs
        winner_profile.updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        self.logger.update(winner.agent_id, old_rate, new_rate, old_runs, new_runs)

        # ---------------------------------------------------------------
        # Step 10: Persist State
        # ---------------------------------------------------------------
        self.store.upsert(winner_profile)
        self.logger.persist(self.store.path)

        # ---------------------------------------------------------------
        # Step 11: Return TaskResult
        # ---------------------------------------------------------------
        ranking = [
            {
                "agent_id": sc.candidate.agent_id,
                "trust_score": sc.trust_score,
                "relevancy": sc.relevancy,
                "success_rate": profiles[sc.candidate.agent_id].success_rate,
            }
            for sc in scored
        ]

        explanation = (
            f"{winner.agent_id} selected: trust={winner_sc.trust_score:.4f} "
            f"(rep={old_rate:.2f}, rel={winner_sc.relevancy:.2f})"
        )

        result = TaskResult(
            task_id=task.task_id,
            winner_agent_id=winner.agent_id,
            winner_score=winner_sc.trust_score,
            ranking=ranking,
            explanation=explanation,
            outcome=final_outcome,
        )

        self.logger.done(task.task_id)
        return result
