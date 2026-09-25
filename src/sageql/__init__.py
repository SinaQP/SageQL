"""Public API for SageQL."""

from sageql.core import Candidate, GeneratedQuery, SQLProvider, generate_sql
from sageql.conversation import (
    ChatConfig,
    ChatError,
    ChatProvider,
    DatabaseConfig,
    LLMConfig,
    Message,
    ReportConversation,
)
from sageql.errors import GenerationError, InvalidSQL
from sageql.validation import validate_sql
from sageql.understanding import RequestAssessment, RequestUnderstandingSession, UnderstandingProvider

__all__ = [
    "Candidate",
    "ChatConfig",
    "ChatError",
    "ChatProvider",
    "DatabaseConfig",
    "GeneratedQuery",
    "GenerationError",
    "InvalidSQL",
    "LLMConfig",
    "Message",
    "ReportConversation",
    "RequestAssessment",
    "RequestUnderstandingSession",
    "SQLProvider",
    "UnderstandingProvider",
    "generate_sql",
    "validate_sql",
]
