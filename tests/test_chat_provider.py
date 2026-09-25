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


def test_assessment_uses_structured_output_and_history():
    completions = FakeCompletions(
        '{"enough_information":false,"request_understanding":"Sales report",'
        '"clarification_question":"Which time period?"}'
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    provider = OpenAIChatProvider(LLMConfig(api_key="secret"), client=client)

    result = provider.assess([Message("user", "Sales report")])

    assert not result.enough_information
    assert result.clarification_question == "Which time period?"
    assert completions.kwargs["response_format"]["type"] == "json_schema"
    assert [message["role"] for message in completions.kwargs["messages"]] == ["system", "user"]


@pytest.mark.parametrize(
    "content",
    [
        "not-json",
        '{"enough_information":"yes","request_understanding":"A report","clarification_question":""}',
        '{"enough_information":true,"request_understanding":"","clarification_question":""}',
        '{"enough_information":false,"request_understanding":"A report","clarification_question":""}',
        '{"enough_information":true,"request_understanding":"A report","clarification_question":"","extra":1}',
    ],
)
def test_assessment_rejects_invalid_output(content):
    completions = FakeCompletions(content)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    provider = OpenAIChatProvider(LLMConfig(api_key="secret"), client=client)
    with pytest.raises(ChatError, match="invalid request assessment"):
        provider.assess([Message("user", "Report")])
