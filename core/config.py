"""Config loader for Trust Layer scoring weights."""

import json
import os

from core.models import ScoringConfig

# Resolve paths relative to project root (one level up from core/)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_CONFIG_PATH = os.path.join(_PROJECT_ROOT, "config", "scoring.json")


def load_scoring_config(path: str = None) -> ScoringConfig:
    """Load scoring config from JSON file.

    Falls back to default weights (0.6/0.4) if file not found.
    Raises ValueError if weights are invalid.
    """
    config_path = path or _DEFAULT_CONFIG_PATH

    if not os.path.exists(config_path):
        return ScoringConfig()  # default 0.6 / 0.4

    with open(config_path, "r") as f:
        data = json.load(f)

    return ScoringConfig.from_dict(data)
