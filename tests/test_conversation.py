import pytest

from sageql import (
    ChatConfig,
    ChatError,
    DatabaseConfig,
    LLMConfig,
    Message,
    ReportConversation,
)


def config():
    return ChatConfig(
        database=DatabaseConfig(
            server_host="private-host",
            database="private-db",
            authentication="Windows",
            odbc_driver="ODBC Driver 18",
        ),
        llm=LLMConfig(api_key="secret-api-key", base_url="https://example.test/v1", model="demo"),
    )


def test_conversation_keeps_successful_turns_without_database_config():
    class Provider:
        def __init__(self):
            self.calls = []

        def reply(self, messages):
            self.calls.append(tuple(messages))
            return "Which date range?" if len(messages) == 1 else "Thanks, I have the date range."

    provider = Provider()
    conversation = ReportConversation(config(), provider)

    assert conversation.ask("Monthly sales report") == "Which date range?"
    assert conversation.ask("Last quarter") == "Thanks, I have the date range."
    assert provider.calls[0] == (Message("user", "Monthly sales report"),)
    assert provider.calls[1] == (
        Message("user", "Monthly sales report"),
        Message("assistant", "Which date range?"),
        Message("user", "Last quarter"),
    )
    assert len(conversation.history) == 4
    assert "private-host" not in str(provider.calls)
    assert "secret-api-key" not in repr(config().llm)


def test_failed_reply_does_not_change_history():
    class Provider:
        def reply(self, messages):
            raise RuntimeError("network detail")

    conversation = ReportConversation(config(), Provider())
    with pytest.raises(ChatError, match="chat provider failed"):
        conversation.ask("Report please")
    assert conversation.history == ()


def test_failed_reply_can_be_retried():
    class Provider:
        calls = 0

        def reply(self, messages):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("temporary failure")
            return "Which date range?"

    conversation = ReportConversation(config(), Provider())
    with pytest.raises(ChatError):
        conversation.ask("Sales report")
    assert conversation.ask("Sales report") == "Which date range?"
    assert conversation.history == (
        Message("user", "Sales report"),
        Message("assistant", "Which date range?"),
    )


def test_empty_message_or_answer_is_rejected():
    class Provider:
        def reply(self, messages):
            return " "

    conversation = ReportConversation(config(), Provider())
    with pytest.raises(ValueError):
        conversation.ask(" ")
    with pytest.raises(ChatError, match="empty answer"):
        conversation.ask("Report please")
    assert conversation.history == ()


def test_config_requires_each_field():
    with pytest.raises(ValueError, match="server_host"):
        DatabaseConfig(" ", "db", "Windows", "driver")
    with pytest.raises(ValueError, match="api_key"):
        LLMConfig(api_key=" ")
    with pytest.raises(ValueError, match="base_url"):
        LLMConfig(api_key="secret", base_url="not-a-url")
