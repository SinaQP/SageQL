import pytest

from sageql import (
    ChatConfig,
    ChatError,
    DatabaseConfig,
    LLMConfig,
    Message,
    RequestAssessment,
    RequestUnderstandingSession,
)


def config():
    return ChatConfig(
        database=DatabaseConfig("private-host", "private-db", "Windows", "driver"),
        llm=LLMConfig(api_key="test-key"),
    )


def test_clarifies_then_printable_understanding():
    class Provider:
        def __init__(self):
            self.calls = []

        def assess(self, messages):
            self.calls.append(tuple(messages))
            if len(messages) == 1:
                return RequestAssessment(False, "A sales report", "Which time period?")
            return RequestAssessment(True, "Monthly sales for last quarter.", "")

    provider = Provider()
    session = RequestUnderstandingSession(config(), provider)
    first = session.submit("I want a sales report")
    assert first.clarification_question == "Which time period?"
    assert not session.complete
    second = session.submit("Monthly, for last quarter")
    assert second.request_understanding == "Monthly sales for last quarter."
    assert session.complete
    assert provider.calls[1] == (
        Message("user", "I want a sales report"),
        Message("assistant", "Which time period?"),
        Message("user", "Monthly, for last quarter"),
    )
    assert "private-host" not in str(provider.calls)
    with pytest.raises(ValueError, match="already complete"):
        session.submit("Another detail")


def test_ready_on_first_message():
    class Provider:
        def assess(self, messages):
            return RequestAssessment(True, "Revenue by month for 2025.", "")

    session = RequestUnderstandingSession(config(), Provider())
    assert session.submit("Revenue by month for 2025").enough_information
    assert len(session.history) == 2


def test_failed_assessment_preserves_history():
    class Provider:
        def assess(self, messages):
            raise RuntimeError("network detail")

    session = RequestUnderstandingSession(config(), Provider())
    with pytest.raises(ChatError, match="understanding provider failed"):
        session.submit("A sales report")
    assert session.history == ()


@pytest.mark.parametrize(
    "assessment",
    [
        (True, "", ""),
        (True, "A report", "What period?"),
        (False, "A report", ""),
        ("yes", "A report", ""),
    ],
)
def test_rejects_contradictory_assessment(assessment):
    with pytest.raises(ValueError):
        RequestAssessment(*assessment)
