from types import SimpleNamespace

import pytest

from sageql import ChatError, LLMConfig, Message
from sageql.chat_provider import OpenAIChatProvider
from sageql.context import ResolvedContext
from sageql.discovery import DiscoveryCandidates, DiscoveryError
from sageql.schema import Column, Definition, Relation, Table


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


def test_understanding_question_conservatively_overrides_ready_flag():
    completions = FakeCompletions(
        '{"enough_information":true,"request_understanding":"A sales report",'
        '"clarification_question":"Which period?"}'
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    provider = OpenAIChatProvider(LLMConfig(api_key="secret"), client=client)

    result = provider.assess([Message("user", "A sales report")])

    assert not result.enough_information
    assert result.clarification_question == "Which period?"


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


def test_context_resolution_uses_structured_output():
    completions = FakeCompletions(
        '{"ready":true,"time_period":"last quarter","entities":["sales","region"],'
        '"metrics":["revenue"],"filters":[],"comparison_period":"",'
        '"clarification_question":""}'
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    provider = OpenAIChatProvider(LLMConfig(api_key="secret"), client=client)

    result = provider.resolve_context(
        [Message("user", "Revenue by region last quarter")],
        "Revenue by region last quarter.",
    )

    assert result.ready
    assert result.context.time_period == "last quarter"
    assert result.context.entities == ("sales", "region")
    assert result.context.filters == ()
    assert completions.kwargs["response_format"]["type"] == "json_schema"
    assert "secret" not in str(completions.kwargs)


def test_context_question_conservatively_overrides_ready_flag():
    completions = FakeCompletions(
        '{"ready":true,"time_period":"","entities":["region"],'
        '"metrics":["sales"],"filters":[],"comparison_period":"",'
        '"clarification_question":"Which time period?"}'
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    provider = OpenAIChatProvider(LLMConfig(api_key="secret"), client=client)

    result = provider.resolve_context([Message("user", "Sales by region")], "Sales by region")

    assert not result.ready
    assert result.clarification_question == "Which time period?"


def test_missing_time_period_triggers_clarification():
    completions = FakeCompletions(
        '{"ready":true,"time_period":"","entities":["region"],'
        '"metrics":["sales"],"filters":[],"comparison_period":"",'
        '"clarification_question":""}'
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    provider = OpenAIChatProvider(LLMConfig(api_key="secret"), client=client)

    result = provider.resolve_context([Message("user", "Sales by region")], "Sales by region")

    assert not result.ready
    assert "time period" in result.clarification_question.lower()


@pytest.mark.parametrize(
    "content",
    [
        "not-json",
        '{"ready":true,"time_period":"2025","entities":"sales","metrics":["revenue"],"filters":[],"comparison_period":"","clarification_question":""}',
        '{"ready":true,"time_period":"2025","entities":[],"metrics":[],"filters":[],"comparison_period":"","clarification_question":""}',
        '{"ready":false,"time_period":"","entities":["sales"],"metrics":[],"filters":[],"comparison_period":"","clarification_question":""}',
        '{"ready":true,"time_period":"2025","entities":["orders"],"metrics":["revenue"],"filters":["status = completed"],"comparison_period":"","clarification_question":""}',
    ],
)
def test_context_resolution_rejects_invalid_output(content):
    completions = FakeCompletions(content)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    provider = OpenAIChatProvider(LLMConfig(api_key="secret"), client=client)
    with pytest.raises(ChatError, match="invalid report context"):
        provider.resolve_context([Message("user", "Report")], "A report")


def test_query_space_selection_sends_schema_but_not_connection_fields():
    completions = FakeCompletions(
        '{"table_ids":["t0","t1"],"column_ids":["c0"],'
        '"relation_ids":["r0"],"definition_ids":["d0"]}'
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    provider = OpenAIChatProvider(LLMConfig(api_key="secret"), client=client)
    candidates = DiscoveryCandidates(
        {"t0": Table("orders"), "t1": Table("regions")},
        {"c0": Column("orders", "revenue", "decimal")},
        {"r0": Relation("fk", "orders", ("region_id",), "regions", ("id",))},
        {"d0": Definition("orders.revenue", "Booked revenue", "ODBC column remark")},
    )
    context = ResolvedContext("2025", ("region",), ("revenue",), (), "")

    result = provider.select_query_space("Revenue by region", context, candidates)

    assert result.table_ids == ("t0", "t1")
    assert result.definition_ids == ("d0",)
    payload = str(completions.kwargs)
    assert "Booked revenue" in payload
    assert "secret" not in payload
    assert "private-host" not in payload
    assert completions.kwargs["response_format"]["type"] == "json_schema"


@pytest.mark.parametrize("content", [
    "not-json",
    '{"table_ids":"t0","column_ids":[],"relation_ids":[],"definition_ids":[]}',
    '{"table_ids":[1],"column_ids":[],"relation_ids":[],"definition_ids":[]}',
    '{"table_ids":[],"column_ids":[],"relation_ids":[]}',
])
def test_query_space_selection_rejects_malformed_output(content):
    completions = FakeCompletions(content)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    provider = OpenAIChatProvider(LLMConfig(api_key="secret"), client=client)
    with pytest.raises(DiscoveryError, match="invalid query-space selection"):
        provider.select_query_space(
            "A report", ResolvedContext("2025", ("orders",), (), (), ""),
            DiscoveryCandidates({}, {}, {}, {}),
        )
