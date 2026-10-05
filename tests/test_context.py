import pytest

from sageql import ChatConfig, ChatError, DatabaseConfig, LLMConfig, Message
from sageql.context import ContextResolution, ContextResolutionSession, ResolvedContext


def config():
    return ChatConfig(
        DatabaseConfig("private-host", "private-db", "Windows", "driver"),
        LLMConfig(api_key="test-key"),
    )


def initial_history():
    return (
        Message("user", "Show revenue by month for 2025"),
        Message("assistant", "Monthly revenue for 2025."),
    )


def context(time_period="2025"):
    return ResolvedContext(
        time_period=time_period,
        entities=("sales",),
        metrics=("revenue",),
        filters=(),
        comparison_period="",
    )


def test_ready_context_on_first_assessment():
    class Provider:
        def __init__(self):
            self.calls = []

        def resolve_context(self, messages, understanding):
            self.calls.append((tuple(messages), understanding))
            return ContextResolution(True, context(), "")

    provider = Provider()
    session = ContextResolutionSession(config(), provider, initial_history(), "Monthly revenue for 2025.")
    result = session.start()

    assert result.ready
    assert result.context.time_period == "2025"
    assert result.context.filters == ()
    assert result.context.comparison_period == ""
    assert session.context == result.context
    assert provider.calls == [(initial_history(), "Monthly revenue for 2025.")]
    assert "private-host" not in str(provider.calls)


def test_clarifies_context_and_keeps_answer():
    class Provider:
        def __init__(self):
            self.calls = []

        def resolve_context(self, messages, understanding):
            self.calls.append(tuple(messages))
            if len(messages) == 2:
                return ContextResolution(False, context(""), "Which time period?")
            return ContextResolution(True, context("last quarter"), "")

    provider = Provider()
    session = ContextResolutionSession(config(), provider, initial_history(), "Monthly revenue report.")
    first = session.start()
    assert not first.ready
    assert session.context is None
    assert session.provisional_context == context("")
    second = session.submit("Last quarter")

    assert second.ready
    assert second.context.time_period == "last quarter"
    assert session.provisional_context == second.context
    assert provider.calls[1][-2:] == (
        Message("assistant", "Which time period?"),
        Message("user", "Last quarter"),
    )
    assert session.history[-2:] == provider.calls[1][-2:]
    with pytest.raises(ValueError, match="already complete"):
        session.submit("More")


def test_failed_context_call_does_not_advance_history():
    class Provider:
        def resolve_context(self, messages, understanding):
            raise RuntimeError("provider detail")

    session = ContextResolutionSession(config(), Provider(), initial_history(), "Revenue report.")
    with pytest.raises(ChatError, match="context provider failed"):
        session.start()
    assert session.history == initial_history()
    assert session.context is None
    assert session.provisional_context is None


@pytest.mark.parametrize(
    "result",
    [
        lambda: ContextResolution(True, context(), "Which period?"),
        lambda: ContextResolution(False, context(), ""),
        lambda: ContextResolution(True, ResolvedContext("", (), (), (), ""), ""),
        lambda: ContextResolution(True, context(""), ""),
        lambda: ResolvedContext("", ("",), (), (), ""),
        lambda: ResolvedContext("2025", ("orders",), ("revenue",), ("status = completed",), ""),
    ],
)
def test_rejects_invalid_context(result):
    with pytest.raises(ValueError):
        result()
