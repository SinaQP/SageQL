"""Assess a report request through a clarification conversation."""

from dataclasses import dataclass
from typing import Protocol, Sequence

from sageql.conversation import ChatConfig, ChatError, Message


@dataclass(frozen=True)
class RequestAssessment:
    enough_information: bool
    request_understanding: str
    clarification_question: str

    def __post_init__(self) -> None:
        if type(self.enough_information) is not bool:
            raise ValueError("enough_information must be a boolean")
        if not isinstance(self.request_understanding, str):
            raise ValueError("request_understanding must be text")
        if not isinstance(self.clarification_question, str):
            raise ValueError("clarification_question must be text")
        if self.enough_information:
            if not self.request_understanding.strip() or self.clarification_question.strip():
                raise ValueError("a ready request needs an understanding and no question")
        elif not self.clarification_question.strip():
            raise ValueError("an incomplete request needs a clarification question")


class UnderstandingProvider(Protocol):
    def assess(self, messages: Sequence[Message]) -> RequestAssessment:
        """Assess the full conversation, including the latest user message."""


class RequestUnderstandingSession:
    """Gather just enough detail to describe the user's report request."""

    def __init__(self, config: ChatConfig, provider: UnderstandingProvider) -> None:
        self.config = config
        self._provider = provider
        self._history: list[Message] = []
        self._complete = False

    @property
    def history(self) -> tuple[Message, ...]:
        return tuple(self._history)

    @property
    def complete(self) -> bool:
        return self._complete

    def submit(self, user_message: str) -> RequestAssessment:
        if self._complete:
            raise ValueError("request understanding is already complete")
        if not user_message.strip():
            raise ValueError("user message must not be empty")

        pending = (*self._history, Message("user", user_message.strip()))
        try:
            assessment = self._provider.assess(pending)
        except ChatError:
            raise
        except Exception as exc:
            raise ChatError("understanding provider failed") from exc
        if not isinstance(assessment, RequestAssessment):
            raise ChatError("understanding provider returned an invalid assessment")

        assistant_text = (
            assessment.request_understanding
            if assessment.enough_information
            else assessment.clarification_question
        )
        self._history.extend((pending[-1], Message("assistant", assistant_text.strip())))
        self._complete = assessment.enough_information
        return assessment
