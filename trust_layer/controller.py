import json
from typing import Optional, List, Dict
from datetime import datetime, timezone
from .schemas import (
    AgentProfile,
    Candidate,
    Task,
    TaskResult,
    ScoringConfig,
    RankEntry,
    DEFAULT_CONFIG,
)
from .scoring_engine import ScoringEngine
from .reputation_store import ReputationStore
from .logger import TrustLogger


class TrustController:
    def __init__(self, store: ReputationStore, engine: ScoringEngine, config: ScoringConfig = DEFAULT_CONFIG):
        self.store = store
        self.engine = engine
        self.config = config
        self.logger = TrustLogger()

    def run_task(
        self,
        task: Task,
        candidates: List[Candidate],
        outcome: Optional[bool] = None,
    ) -> TaskResult:
        self.logger.header(task.task_id)

        # [CONFIG]
        self.logger.config(self.config)

        # Step 1: Validate Task
        if not task.task_id:
            raise ValueError("task_id must not be empty")
        if not task.prompt:
            raise ValueError("prompt must not be empty")
        if not task.expected_keywords:
            raise ValueError("expected_keywords must have at least 1 keyword")

        # Step 3: Validate Candidates
        if len(candidates) < 2:
            raise ValueError("Must have at least 2 candidates")
        agent_ids = [c.agent_id for c in candidates]
        if len(agent_ids) != len(set(agent_ids)):
            raise ValueError("Duplicate agent_id in candidates")
        for c in candidates:
            if c.task_id != task.task_id:
                raise ValueError(
                    f"Candidate {c.output_id} task_id={c.task_id} does not match task {task.task_id}"
                )

        # Step 2: Load Agent Profiles
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

        # Steps 4-5: Compute Relevancy + Trust Score
        scored = []
        for c in candidates:
            sc = self.engine.score(c, task, profiles[c.agent_id], self.config)
            scored.append(sc)
            self.logger.score(c.agent_id, sc.relevancy, sc.trust_score)

        # Step 6: Rank Candidates (deterministic tie-breaking)
        scored.sort(
            key=lambda s: (-s.trust_score, -profiles[s.candidate.agent_id].total_runs, s.candidate.agent_id)
        )

        # Check for ties and warn
        if len(scored) >= 2 and scored[0].trust_score == scored[1].trust_score:
            self.logger.warn_tie(scored[0].candidate.agent_id, scored[1].candidate.agent_id, scored[0].trust_score)

        # Log ranking
        for rank_idx, sc in enumerate(scored, 1):
            self.logger.rank(rank_idx, sc.candidate.agent_id, sc.trust_score)

        # Step 7: Select Winner
        winner_sc = scored[0]
        winner_candidate = winner_sc.candidate
        winner_profile = profiles[winner_candidate.agent_id]

        # Step 8: Determine Outcome
        if outcome is not None:
            final_outcome = outcome
        else:
            final_outcome = len(winner_candidate.output_text.strip().split()) >= 3

        self.logger.select(winner_candidate.agent_id, winner_sc.trust_score, final_outcome)

        # Step 9: Update Reputation (winner only)
        o = 1.0 if final_outcome else 0.0
        new_rate = round(
            (winner_profile.success_rate * winner_profile.total_runs + o)
            / (winner_profile.total_runs + 1),
            6,
        )
        old_rate = winner_profile.success_rate
        old_runs = winner_profile.total_runs

        winner_profile.success_rate = new_rate
        winner_profile.total_runs += 1
        winner_profile.updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        self.logger.update(winner_candidate.agent_id, old_rate, new_rate, old_runs, winner_profile.total_runs)

        # Step 10: Persist State
        self.store.upsert(winner_profile)
        self.logger.persist(self.store.path)

        # Step 11: Return TaskResult
        ranking = [
            RankEntry(
                agent_id=sc.candidate.agent_id,
                trust_score=sc.trust_score,
                relevancy=sc.relevancy,
                success_rate=profiles[sc.candidate.agent_id].success_rate,
            ).__dict__
            for sc in scored
        ]

        explanation = (
            f"{winner_candidate.agent_id} selected: trust={winner_sc.trust_score:.4f} "
            f"(rep={old_rate:.2f}, rel={winner_sc.relevancy:.2f})"
        )

        result = TaskResult(
            task_id=task.task_id,
            winner_agent_id=winner_candidate.agent_id,
            winner_score=winner_sc.trust_score,
            ranking=ranking,
            explanation=explanation,
            outcome=final_outcome,
        )

        self.logger.done(task.task_id)
        return result
