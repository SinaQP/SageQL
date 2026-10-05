"""Resolve report context from an understood request and conversation."""

from dataclasses import dataclass
from typing import Protocol, Sequence

from sageql.conversation import ChatConfig, ChatError, Message


@dataclass(frozen=True)
class ResolvedContext:
    time_period: str
    entities: tuple[str, ...]
    metrics: tuple[str, ...]
    filters: tuple[str, ...]
    comparison_period: str

    def __post_init__(self) -> None:
        for name in ("time_period", "comparison_period"):
            if not isinstance(getattr(self, name), str):
                raise ValueError(f"{name} must be text")
        for name in ("entities", "metrics", "filters"):
            values = getattr(self, name)
            if not isinstance(values, tuple) or any(
                not isinstance(value, str) or not value.strip() for value in values
            ):
                raise ValueError(f"{name} must be a sequence of nonempty text values")
        if any(any(operator in value for operator in ("=", "<", ">")) for value in self.filters):
            raise ValueError("filters must use plain language, not SQL expressions")


@dataclass(frozen=True)
class ContextResolution:
    ready: bool
    context: ResolvedContext
    clarification_question: str

    def __post_init__(self) -> None:
        if type(self.ready) is not bool:
            raise ValueError("ready must be a boolean")
        if not isinstance(self.context, ResolvedContext):
            raise ValueError("context must be a ResolvedContext")
        if not isinstance(self.clarification_question, str):
            raise ValueError("clarification_question must be text")
        if self.ready:
            if self.clarification_question.strip():
                raise ValueError("ready context must not have a clarification question")
            if not self.context.time_period.strip():
                raise ValueError("ready context needs a time period")
            if not self.context.entities and not self.context.metrics:
                raise ValueError("ready context needs an entity or metric")
        elif not self.clarification_question.strip():
            raise ValueError("incomplete context needs a clarification question")


class ContextProvider(Protocol):
    def resolve_context(
        self, messages: Sequence[Message], understanding: str
    ) -> ContextResolution:
        """Resolve the five context fields from the full request conversation."""


class ContextResolutionSession:
    """Clarify material context gaps and keep only successful turns."""

    def __init__(
        self,
        config: ChatConfig,
        provider: ContextProvider,
        history: Sequence[Message],
        understanding: str,
    ) -> None:
        if not understanding.strip():
            raise ValueError("request understanding must not be empty")
        if not history or not any(message.role == "user" for message in history):
            raise ValueError("request conversation must include a user message")
        self.config = config
        self._provider = provider
        self._history = list(history)
        self._understanding = understanding.strip()
        self._started = False
        self._context: ResolvedContext | None = None
        self._provisional_context: ResolvedContext | None = None

    @property
    def history(self) -> tuple[Message, ...]:
        return tuple(self._history)

    @property
    def context(self) -> ResolvedContext | None:
        return self._context

    @property
    def provisional_context(self) -> ResolvedContext | None:
        """Latest context snapshot, including one still awaiting clarification."""
        return self._provisional_context

    def start(self) -> ContextResolution:
        if self._started:
            raise ValueError("context resolution has already started")
        result = self._resolve(tuple(self._history))
        self._started = True
        self._accept_result(result, None)
        return result

    def submit(self, answer: str) -> ContextResolution:
        if not self._started:
            raise ValueError("start context resolution before answering")
        if self._context is not None:
            raise ValueError("context resolution is already complete")
        if not answer.strip():
            raise ValueError("answer must not be empty")

        user_message = Message("user", answer.strip())
        result = self._resolve((*self._history, user_message))
        self._accept_result(result, user_message)
        return result

    def _resolve(self, messages: Sequence[Message]) -> ContextResolution:
        try:
            result = self._provider.resolve_context(messages, self._understanding)
        except ChatError:
            raise
        except Exception as exc:
            raise ChatError("context provider failed") from exc
        if not isinstance(result, ContextResolution):
            raise ChatError("context provider returned an invalid resolution")
        return result

    def _accept_result(self, result: ContextResolution, user_message: Message | None) -> None:
        if user_message is not None:
            self._history.append(user_message)
        self._provisional_context = result.context
        if result.ready:
            self._context = result.context
        else:
            self._history.append(Message("assistant", result.clarification_question.strip()))
