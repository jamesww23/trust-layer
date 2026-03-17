import json
import sys
from .schemas import AgentProfile, ScoringConfig


class TrustLogger:
    def _log(self, section: str, message: str, level: str = "INFO"):
        entry = {"section": section, "level": level, "message": message}
        print(json.dumps(entry), file=sys.stdout)

    def _human(self, text: str):
        print(text, file=sys.stdout)

    def header(self, task_id: str):
        self._human(f"\n=== TRUST LAYER RUN === task_id={task_id}\n")

    def config(self, config: ScoringConfig):
        src = "loaded from ./config/scoring.json" if config else "DEFAULT"
        self._human(
            f"[CONFIG]  w_reputation={config.w_reputation}  w_relevancy={config.w_relevancy}  ({src})\n"
        )

    def load_profile(self, profile: AgentProfile):
        self._human(
            f"[LOAD]    {profile.agent_id:<14s} success_rate={profile.success_rate:.3f}  total_runs={profile.total_runs}"
        )

    def init_profile(self, profile: AgentProfile):
        self._human(
            f"[INIT]    {profile.agent_id:<14s} success_rate={profile.success_rate:.3f}  total_runs={profile.total_runs}  (default — not found in store)"
        )

    def score(self, agent_id: str, relevancy: float, trust_score: float):
        self._human(
            f"[SCORE]   {agent_id:<14s} relevancy={relevancy:.3f}  trust_score={trust_score:.4f}"
        )

    def warn_tie(self, agent1: str, agent2: str, score: float):
        self._human(f"[WARN]    Tie between {agent1} and {agent2} at trust_score={score:.4f}")

    def rank(self, position: int, agent_id: str, trust_score: float):
        self._human(f"[RANK]    {position}. {agent_id:<14s} {trust_score:.4f}")

    def select(self, agent_id: str, score: float, outcome: bool):
        detect = "auto-detected" if outcome else "auto-detected"
        self._human(
            f"\n[SELECT]  winner={agent_id}  score={score:.4f}  outcome={outcome}  ({detect})\n"
        )

    def update(self, agent_id: str, old_rate: float, new_rate: float, old_runs: int, new_runs: int):
        self._human(
            f"[UPDATE]  {agent_id}  success_rate: {old_rate:.6f} → {new_rate:.6f}  total_runs: {old_runs} → {new_runs}"
        )

    def persist(self, path: str):
        self._human(f"[PERSIST] written to {path}")

    def done(self, task_id: str):
        self._human(f"\n=== DONE === task_id={task_id}\n")
