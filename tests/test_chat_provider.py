from types import SimpleNamespace

import pytest

from sageql import ChatError, LLMConfig, Message
from sageql.chat_provider import OpenAIChatProvider


class FakeCompletions:
    def __init__(self, content):
        self.content = content
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))])


def test_chat_provider_sends_history_and_model_only():
    completions = FakeCompletions("Which metric matters most?")
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    config = LLMConfig(api_key="secret", base_url="https://example.test/v1", model="demo")
    provider = OpenAIChatProvider(config, client=client)

    answer = provider.reply([Message("user", "Sales report"), Message("assistant", "Period?"), Message("user", "June")])

    assert answer == "Which metric matters most?"
    assert completions.kwargs["model"] == "demo"
    assert [message["role"] for message in completions.kwargs["messages"]] == [
        "system", "user", "assistant", "user"
    ]
    assert "secret" not in str(completions.kwargs)


def test_chat_provider_rejects_empty_output():
    completions = FakeCompletions(None)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    provider = OpenAIChatProvider(LLMConfig(api_key="secret"), client=client)
    with pytest.raises(ChatError, match="empty answer"):
        provider.reply([Message("user", "Report")])
