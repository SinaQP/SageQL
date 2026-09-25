"""Provider-independent text-to-SQL contract."""

from dataclasses import dataclass
from typing import Protocol

from sageql.errors import GenerationError
from sageql.validation import validate_sql


@dataclass(frozen=True)
class Candidate:
    sql: str
    explanation: str = ""


@dataclass(frozen=True)
class GeneratedQuery:
    sql: str
    explanation: str


class SQLProvider(Protocol):
    def generate(self, question: str, schema: str) -> Candidate:
        """Return an untrusted candidate for a SQLite query."""


def generate_sql(question: str, schema: str, provider: SQLProvider) -> GeneratedQuery:
    """Generate and validate a proposed query without executing it.

    The supplied schema is context for the model, not an authorization policy.
    """
    if not question.strip():
        raise ValueError("question must not be empty")
    if not schema.strip():
        raise ValueError("schema must not be empty")

    try:
        candidate = provider.generate(question, schema)
    except GenerationError:
        raise
    except Exception as exc:
        raise GenerationError("model provider failed") from exc

    if not isinstance(candidate, Candidate):
        raise GenerationError("model provider returned an invalid candidate")
    sql = validate_sql(candidate.sql)
    return GeneratedQuery(sql=sql, explanation=candidate.explanation)
