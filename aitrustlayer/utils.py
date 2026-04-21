"""Utility functions for the aitrustlayer SDK."""

from typing import Dict, Any, List
import json


def format_agent_info(agent: Any) -> str:
    """
    Format agent information for display.

    Args:
        agent: Agent object

    Returns:
        Formatted string representation
    """
    return (
        f"{agent.agent_name} ({agent.agent_id})\n"
        f"  Trust Score: {agent.trust_score:.1%}\n"
        f"  Tasks: {agent.tasks_completed}/{agent.tasks_received} completed\n"
        f"  Rating Count: {agent.ratings_count}"
    )


def format_leaderboard(agents: List[Any], max_entries: int = 10) -> str:
    """
    Format a leaderboard for display.

    Args:
        agents: List of Agent objects
        max_entries: Maximum entries to display

    Returns:
        Formatted leaderboard string
    """
    lines = ["Trust Layer Leaderboard", "=" * 60]
    for i, agent in enumerate(agents[:max_entries], 1):
        lines.append(
            f"{i:2d}. {agent.agent_name:<30s} {agent.trust_score:>6.1%} "
            f"({agent.tasks_completed} tasks)"
        )
    return "\n".join(lines)


def validate_score(score: float) -> bool:
    """
    Validate a feedback score.

    Args:
        score: Score to validate

    Returns:
        True if valid (0.0-1.0), False otherwise
    """
    return isinstance(score, (int, float)) and 0.0 <= score <= 1.0


def merge_task_result(task_payload: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge a task result with its original payload for context.

    Args:
        task_payload: Original task payload
        result: Task result

    Returns:
        Merged dictionary
    """
    return {
        "payload": task_payload,
        "result": result,
    }


def parse_skill_keywords(skill_md: str) -> List[str]:
    """
    Extract keywords from a skill markdown document.

    Simple implementation: splits by whitespace and filters common words.

    Args:
        skill_md: Skill markdown content

    Returns:
        List of keywords
    """
    common_words = {
        "a", "an", "the", "and", "or", "of", "to", "in", "on", "at",
        "for", "with", "by", "is", "are", "be", "i", "you", "he", "she",
        "it", "we", "they", "can", "will", "would", "could", "should",
    }

    text = skill_md.lower()
    # Split on whitespace and punctuation
    words = []
    current_word = ""
    for char in text:
        if char.isalnum() or char == "_":
            current_word += char
        else:
            if current_word and current_word not in common_words:
                words.append(current_word)
            current_word = ""

    if current_word and current_word not in common_words:
        words.append(current_word)

    # Return unique words, sorted
    return sorted(set(words))


def format_timestamp(iso_string: str) -> str:
    """
    Format an ISO 8601 timestamp for display.

    Args:
        iso_string: ISO 8601 timestamp string

    Returns:
        Human-readable timestamp
    """
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return iso_string


def json_dumps(obj: Any, indent: int = 2) -> str:
    """
    Serialize object to JSON string.

    Args:
        obj: Object to serialize
        indent: Indentation level

    Returns:
        JSON string
    """
    return json.dumps(obj, indent=indent, default=str)
