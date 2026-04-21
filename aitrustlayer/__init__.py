"""
aitrustlayer — Python SDK for the Agentic Reputation Infrastructure Layer

A comprehensive client library for interacting with the trust layer API,
enabling agent registration, task delegation, reputation management, and
multi-agent coordination through verified trust scores.
"""

__version__ = "0.1.0"
__author__ = "MIT SFMBA MAS.664 Team 8"

from .client import TrustClient
from .models import (
    Agent,
    Task,
    ActivityEvent,
    RegistrationResponse,
    DelegationResponse,
    SubmitResultResponse,
    FeedbackResponse,
    VouchResponse,
    Leaderboard,
)
from .exceptions import (
    TrustLayerError,
    ConnectionError,
    ServerError,
    ClientError,
    ValidationError,
    NotFoundError,
    AuthenticationError,
    ConflictError,
    TrustGateError,
    FeedbackRequired,
    TimeoutError,
)
from .utils import (
    format_agent_info,
    format_leaderboard,
    validate_score,
    merge_task_result,
    parse_skill_keywords,
    format_timestamp,
    json_dumps,
)

__all__ = [
    # Client
    "TrustClient",
    # Models
    "Agent",
    "Task",
    "ActivityEvent",
    "RegistrationResponse",
    "DelegationResponse",
    "SubmitResultResponse",
    "FeedbackResponse",
    "VouchResponse",
    "Leaderboard",
    # Exceptions
    "TrustLayerError",
    "ConnectionError",
    "ServerError",
    "ClientError",
    "ValidationError",
    "NotFoundError",
    "AuthenticationError",
    "ConflictError",
    "TrustGateError",
    "FeedbackRequired",
    "TimeoutError",
    # Utils
    "format_agent_info",
    "format_leaderboard",
    "validate_score",
    "merge_task_result",
    "parse_skill_keywords",
    "format_timestamp",
    "json_dumps",
]
