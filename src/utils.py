"""Utilities — config loading and structured logging for Trust Layer MVP."""

import json
import os
import sys

from models import ScoringConfig, AgentProfile, DEFAULT_CONFIG


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def load_config(path: str = "./config/scoring.json") -> ScoringConfig:
    """Load ScoringConfig from JSON. Falls back to defaults if file absent."""
    if not os.path.exists(path):
        return DEFAULT_CONFIG
    with open(path, "r") as f:
        data = json.load(f)
    return ScoringConfig.from_dict(data)


# ---------------------------------------------------------------------------
# Structured logger
# ---------------------------------------------------------------------------

class TrustLogger:
    """Human-readable structured log output. All 6 required sections."""

    def __init__(self, stream=None):
        self._stream = stream or sys.stdout

    def _print(self, text: str):
        print(text, file=self._stream)

    # --- CONFIG ---
    def config(self, cfg: ScoringConfig, source: str = "loaded"):
        self._print(
            f"[CONFIG]  w_reputation={cfg.w_reputation}  "
            f"w_relevancy={cfg.w_relevancy}  ({source})"
        )

    # --- LOAD / INIT ---
    def load_profile(self, p: AgentProfile):
        self._print(
            f"[LOAD]    {p.agent_id:<16s} success_rate={p.success_rate:.3f}  "
            f"total_runs={p.total_runs}"
        )

    def init_profile(self, p: AgentProfile):
        self._print(
            f"[INIT]    {p.agent_id:<16s} success_rate={p.success_rate:.3f}  "
            f"total_runs={p.total_runs}  (default — not found in store)"
        )

    # --- SCORE ---
    def score(self, agent_id: str, relevancy: float, trust_score: float):
        self._print(
            f"[SCORE]   {agent_id:<16s} relevancy={relevancy:.3f}  "
            f"trust_score={trust_score:.4f}"
        )

    # --- RANK ---
    def rank(self, position: int, agent_id: str, trust_score: float):
        self._print(f"[RANK]    {position}. {agent_id:<16s} {trust_score:.4f}")

    def warn_tie(self, a1: str, a2: str, score: float):
        self._print(f"[WARN]    Tie: {a1} and {a2} at trust_score={score:.4f}")

    # --- SELECT ---
    def select(self, agent_id: str, score: float, outcome: bool, auto: bool):
        mode = "auto-detected" if auto else "explicit"
        self._print(
            f"[SELECT]  winner={agent_id}  score={score:.4f}  "
            f"outcome={outcome}  ({mode})"
        )

    # --- UPDATE ---
    def update(
        self, agent_id: str,
        old_rate: float, new_rate: float,
        old_runs: int, new_runs: int,
    ):
        self._print(
            f"[UPDATE]  {agent_id}  success_rate: {old_rate:.6f} -> {new_rate:.6f}  "
            f"total_runs: {old_runs} -> {new_runs}"
        )

    # --- PERSIST ---
    def persist(self, path: str):
        self._print(f"[PERSIST] written to {path}")

    # --- Framing ---
    def header(self, task_id: str):
        self._print(f"\n=== TRUST LAYER RUN === task_id={task_id}")
        self._print("")

    def done(self, task_id: str):
        self._print(f"\n=== DONE === task_id={task_id}")
