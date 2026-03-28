"""TrustController — orchestrates the full Trust Layer evaluation loop."""

import uuid
from datetime import datetime, timezone

from core.models import Task, Candidate, TaskResult, RunRecord, ScoringConfig
from core.scoring import ScoringEngine
from core.store import ReputationStore


class TrustController:
    """Orchestrates: load → score → rank → select → outcome → update → persist."""

    def __init__(self, store: ReputationStore, engine: ScoringEngine, config: ScoringConfig):
        self.store = store
        self.engine = engine
        self.config = config
        self._logs = []

    def _log(self, section: str, message: str):
        entry = f"[{section}] {message}"
        self._logs.append(entry)

    def run_task(self, task: Task, candidates: list, outcome: bool = None) -> TaskResult:
        """Execute the full Trust Layer evaluation loop.

        Args:
            task: The task being evaluated.
            candidates: List of Candidate objects (minimum 2).
            outcome: Optional explicit outcome override. If None, auto-detects.

        Returns:
            TaskResult with winner, ranking, and explanation.

        Raises:
            ValueError: On invalid input.
        """
        self._logs = []

        # --- VALIDATE ---
        self._validate(task, candidates)

        # --- CONFIG ---
        self._log("CONFIG", f"w_reputation={self.config.w_reputation}, "
                   f"w_relevancy={self.config.w_relevancy}")

        # --- LOAD ---
        self._log("LOAD", f"Task: {task.task_id} | Candidates: {len(candidates)} | "
                   f"Keywords: {task.expected_keywords}")

        # --- INIT (read-only lookup — does NOT persist unknown agents) ---
        profiles = {}
        for c in candidates:
            profile = self.store.lookup(c.agent_id)
            profiles[c.agent_id] = profile
            self._log("INIT", f"Agent {c.agent_id}: success_rate={profile.success_rate}, "
                       f"total_runs={profile.total_runs}")

        # --- JUDGE (LLM-as-judge for response quality) ---
        from core.scoring import llm_judge_score
        judge_scores = {}
        for c in candidates:
            score = llm_judge_score(task.prompt, c.output_text)
            judge_scores[c.agent_id] = score
            if score is not None:
                self._log("JUDGE", f"Agent {c.agent_id}: quality={score}")
            else:
                self._log("JUDGE", f"Agent {c.agent_id}: judge unavailable, using keyword fallback")

        # --- SCORE ---
        scored = []
        for c in candidates:
            profile = profiles[c.agent_id]
            relevancy = self.engine.compute_relevancy(
                c.output_text, task.expected_keywords,
                judge_score=judge_scores.get(c.agent_id))
            trust_score = self.engine.compute_trust_score(profile.success_rate, relevancy)
            scored.append({
                "agent_id": c.agent_id,
                "relevancy": relevancy,
                "trust_score": trust_score,
                "success_rate": profile.success_rate,
                "total_runs": profile.total_runs,
                "llm_judge_score": judge_scores.get(c.agent_id),
                "candidate": c,
            })
            self._log("SCORE", f"Agent {c.agent_id}: relevancy={relevancy}, "
                       f"trust_score={trust_score}")

        # --- RANK (deterministic tie-break) ---
        ranking = sorted(
            scored,
            key=lambda x: (-x["trust_score"], -x["total_runs"], x["agent_id"])
        )
        for i, entry in enumerate(ranking):
            self._log("RANK", f"#{i + 1} {entry['agent_id']} "
                       f"(score={entry['trust_score']})")

        # --- SELECT ---
        winner_entry = ranking[0]
        winner_candidate = winner_entry["candidate"]
        self._log("SELECT", f"Winner: {winner_entry['agent_id']} "
                   f"with score={winner_entry['trust_score']}")

        # --- OUTCOME ---
        if outcome is not None:
            actual_outcome = outcome
            self._log("OUTCOME", f"Explicit outcome: {actual_outcome}")
        else:
            word_count = len(winner_candidate.output_text.strip().split())
            actual_outcome = word_count >= 3
            self._log("OUTCOME", f"Auto-detect: {word_count} words → {actual_outcome}")

        # --- UPDATE (winner only) ---
        winner_profile = profiles[winner_entry["agent_id"]]
        old_sr = winner_profile.success_rate
        old_runs = winner_profile.total_runs

        outcome_val = 1.0 if actual_outcome else 0.0
        new_sr = (old_sr * old_runs + outcome_val) / (old_runs + 1)
        new_runs = old_runs + 1

        winner_profile.success_rate = round(new_sr, 4)
        winner_profile.total_runs = new_runs
        self._log("UPDATE", f"Agent {winner_profile.agent_id}: "
                   f"success_rate {old_sr} → {winner_profile.success_rate}, "
                   f"total_runs {old_runs} → {new_runs}")

        # --- PERSIST ---
        self.store.upsert(winner_profile)
        self._log("PERSIST", f"Saved {winner_profile.agent_id} to store")

        # --- BUILD RESULT ---
        ranking_dicts = [
            {
                "agent_id": entry["agent_id"],
                "trust_score": entry["trust_score"],
                "relevancy": entry["relevancy"],
                "success_rate": entry["success_rate"],
                "llm_judge_score": entry.get("llm_judge_score"),
            }
            for entry in ranking
        ]

        judge_used = any(judge_scores.get(c.agent_id) is not None for c in candidates)
        judge_note = ""
        if judge_used:
            winner_judge = judge_scores.get(winner_entry["agent_id"])
            judge_note = f" LLM judge quality={winner_judge}." if winner_judge is not None else ""

        explanation = (
            f"Winner: {winner_entry['agent_id']} with trust_score={winner_entry['trust_score']}. "
            f"Relevancy={winner_entry['relevancy']}, "
            f"success_rate={winner_entry['success_rate']}.{judge_note} "
            f"Outcome={'accepted' if actual_outcome else 'rejected'} "
            f"(structural validity)."
        )

        result = TaskResult(
            task_id=task.task_id,
            winner_agent_id=winner_entry["agent_id"],
            winner_score=winner_entry["trust_score"],
            ranking=ranking_dicts,
            explanation=explanation,
            outcome=actual_outcome,
        )

        return result

    def get_logs(self) -> list:
        """Return structured log entries from the last run."""
        return list(self._logs)

    def _validate(self, task: Task, candidates: list):
        """Validate inputs before running."""
        if len(candidates) < 2:
            raise ValueError(f"At least 2 candidates required, got {len(candidates)}")

        agent_ids = [c.agent_id for c in candidates]
        if len(agent_ids) != len(set(agent_ids)):
            dupes = [aid for aid in agent_ids if agent_ids.count(aid) > 1]
            raise ValueError(f"Duplicate agent_id(s) in candidates: {set(dupes)}")

        for c in candidates:
            if c.task_id != task.task_id:
                raise ValueError(
                    f"Candidate {c.output_id} task_id={c.task_id} "
                    f"does not match task.task_id={task.task_id}"
                )


def build_run_record(task, candidates, result, logs, profiles_before,
                     profiles_after, source="demo"):
    """Construct a RunRecord from evaluation outputs."""
    run_id = uuid.uuid4().hex[:12]
    return RunRecord(
        run_id=run_id,
        task=task.to_dict(),
        candidates=[c.to_dict() for c in candidates],
        result=result.to_dict(),
        logs=logs,
        profiles_before=profiles_before,
        profiles_after=profiles_after,
        source=source,
    )


def apply_feedback(store, run_record, new_outcome):
    """Override a run's outcome and adjust winner reputation.

    Args:
        store: ReputationStore instance.
        run_record: RunRecord instance to override.
        new_outcome: bool — the corrected outcome.

    Returns:
        Updated RunRecord.
    """
    result = run_record.result
    original_outcome = result["outcome"]

    if new_outcome == original_outcome:
        return run_record

    winner_id = result["winner_agent_id"]
    profile = store.lookup(winner_id)

    old_val = 1.0 if original_outcome else 0.0
    new_val = 1.0 if new_outcome else 0.0

    current_sr = profile.success_rate
    current_runs = profile.total_runs

    if current_runs > 0:
        adjusted_sr = (current_sr * current_runs - old_val + new_val) / current_runs
        profile.success_rate = round(max(0.0, min(1.0, adjusted_sr)), 4)
    store.upsert(profile)

    run_record.result["outcome"] = new_outcome
    run_record.feedback_override = {
        "original_outcome": original_outcome,
        "new_outcome": new_outcome,
        "overridden_at": datetime.now(timezone.utc).isoformat(),
    }

    # Update profiles_after snapshot to reflect corrected winner state
    updated_profile = store.lookup(winner_id)
    run_record.profiles_after = [
        updated_profile.to_dict() if p.get("agent_id") == winner_id else p
        for p in run_record.profiles_after
    ]

    store.update_run(run_record)
    return run_record
