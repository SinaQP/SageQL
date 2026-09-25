"""In-memory report-planning conversation."""

from dataclasses import dataclass, field
from typing import Literal, Protocol, Sequence
from urllib.parse import urlsplit


class ChatError(Exception):
    """The chat provider did not return a usable answer."""


@dataclass(frozen=True)
class DatabaseConfig:
    server_host: str
    database: str
    authentication: str
    odbc_driver: str

    def __post_init__(self) -> None:
        for name in ("server_host", "database", "authentication", "odbc_driver"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty")


@dataclass(frozen=True)
class LLMConfig:
    api_key: str = field(repr=False)
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-5-nano"

    def __post_init__(self) -> None:
        for name in ("api_key", "base_url", "model"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty")
        parsed = urlsplit(self.base_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("base_url must be an HTTP(S) endpoint without credentials or query")


@dataclass(frozen=True)
class ChatConfig:
    database: DatabaseConfig
    llm: LLMConfig


@dataclass(frozen=True)
class Message:
    role: Literal["user", "assistant"]
    content: str


class ChatProvider(Protocol):
    def reply(self, messages: Sequence[Message]) -> str:
        """Return an assistant reply for the full conversation so far."""


class ReportConversation:
    """Keep successful chat turns in memory; never access the database."""

    def __init__(self, config: ChatConfig, provider: ChatProvider) -> None:
        self.config = config
        self._provider = provider
        self._history: list[Message] = []

    @property
    def history(self) -> tuple[Message, ...]:
        return tuple(self._history)

    def ask(self, question: str) -> str:
        if not question.strip():
            raise ValueError("question must not be empty")

        pending = (*self._history, Message(role="user", content=question.strip()))
        try:
            answer = self._provider.reply(pending)
        except ChatError:
            raise
        except Exception as exc:
            raise ChatError("chat provider failed") from exc

        if not isinstance(answer, str) or not answer.strip():
            raise ChatError("chat provider returned an empty answer")

        self._history.extend((pending[-1], Message(role="assistant", content=answer.strip())))
        return answer.strip()
