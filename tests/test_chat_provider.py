import json
from types import SimpleNamespace

import pytest

from sageql import ChatError, LLMConfig, Message
from sageql.chat_provider import OpenAIChatProvider
from sageql.context import ResolvedContext
from sageql.discovery import DiscoveryCandidates, DiscoveryError, QuerySpace
from sageql.planning import PlanCandidates, PlanningError, create_query_plan
from sageql.schema import Column, Definition, Relation, Table


class FakeCompletions:
    def __init__(self, content):
        self.content = content
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))])


class SequencedCompletions:
    def __init__(self, *contents):
        self.contents = iter(contents)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content=next(self.contents)))])


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
    assert "بازه زمانی" in result.clarification_question


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


def test_query_planning_uses_structured_output_and_selected_ids():
    completions = FakeCompletions(
        '{"base_table_id":"t0","joins":[{"relation_id":"r0","to_table_id":"t1",'
        '"join_type":"left"}],"time_column_id":"c1","time_grain":"month",'
        '"dimensions":["c2"],"measures":[{"metric_id":"m0",'
        '"aggregation":"sum","column_id":"c0"}],"filters":[]}'
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    provider = OpenAIChatProvider(LLMConfig(api_key="secret"), client=client)
    candidates = PlanCandidates(
        {"t0": Table("orders"), "t1": Table("regions")},
        {"c0": Column("orders", "amount", "decimal"),
         "c1": Column("orders", "ordered_at", "date"),
         "c2": Column("regions", "name", "text")},
        {"r0": Relation("fk", "orders", ("region_id",), "regions", ("id",))},
        (Definition("revenue", "Sum of orders.amount", "user glossary"),),
    )
    context = ResolvedContext("monthly 2025", ("region",), ("revenue",), (), "")

    proposal = provider.propose_query_plan("Monthly revenue by region", context, candidates)

    assert proposal.joins[0].join_type == "left"
    assert proposal.measures[0].aggregation == "sum"
    assert proposal.measures[0].source_metric == "revenue"
    assert completions.kwargs["response_format"]["type"] == "json_schema"
    plan_properties = completions.kwargs["response_format"]["json_schema"]["schema"]["properties"]
    assert plan_properties["base_table_id"]["enum"] == ["t0", "t1"]
    assert plan_properties["measures"]["items"]["properties"]["metric_id"]["enum"] == ["m0"]
    payload = str(completions.kwargs)
    assert "Sum of orders.amount" in payload
    assert "secret" not in payload
    assert json.loads(completions.kwargs["messages"][1]["content"])["context"]["metrics"] == [
        {"id": "m0", "text": "revenue"}
    ]


def test_query_planning_binds_context_ids_to_original_phrases():
    context = ResolvedContext(
        "2025", ("orders",), ("Net revenue (USD)", "Number of orders"),
        ("Completed orders", "Online channel"), "",
    )
    query_space = QuerySpace(
        (Table("orders"),),
        (Column("orders", "amount", "decimal"), Column("orders", "order_date", "date"),
         Column("orders", "status", "text"), Column("orders", "channel", "text")),
        (), (),
    )
    result = {
        "base_table_id": "t0", "joins": [], "time_column_id": "c1", "time_grain": "none",
        "dimensions": [],
        "measures": [
            {"metric_id": "m1", "aggregation": "count_rows", "column_id": ""},
            {"metric_id": "m0", "aggregation": "sum", "column_id": "c0"},
        ],
        "filters": [
            {"filter_id": "f1", "column_id": "c3", "operator": "eq", "values": ["Online"]},
            {"filter_id": "f0", "column_id": "c2", "operator": "eq", "values": ["Completed"]},
        ],
    }
    completions = FakeCompletions(json.dumps(result))
    provider = OpenAIChatProvider(
        LLMConfig(api_key="secret"),
        client=SimpleNamespace(chat=SimpleNamespace(completions=completions)),
    )

    plan = create_query_plan("Orders in 2025", context, query_space, provider)

    assert [item.source_metric for item in plan.measures] == [
        "Number of orders", "Net revenue (USD)"
    ]
    assert [item.source_filter for item in plan.filters] == [
        "Online channel", "Completed orders"
    ]
    sent_context = json.loads(completions.kwargs["messages"][1]["content"])["context"]
    assert sent_context["metrics"] == [
        {"id": "m0", "text": "Net revenue (USD)"},
        {"id": "m1", "text": "Number of orders"},
    ]
    assert sent_context["filters"] == [
        {"id": "f0", "text": "Completed orders"},
        {"id": "f1", "text": "Online channel"},
    ]


@pytest.mark.parametrize("field, bad_id", [("metric_id", "m99"), ("filter_id", "f99")])
def test_query_planning_rejects_unknown_context_ids(field, bad_id):
    output = {
        "base_table_id": "t0", "joins": [], "time_column_id": "", "time_grain": "none",
        "dimensions": [], "measures": [{"metric_id": "m0", "aggregation": "count_rows", "column_id": ""}],
        "filters": [{"filter_id": "f0", "column_id": "c0", "operator": "eq", "values": ["x"]}],
    }
    output["measures" if field == "metric_id" else "filters"][0][field] = bad_id
    provider = OpenAIChatProvider(
        LLMConfig(api_key="secret"),
        client=SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions(json.dumps(output)))),
    )
    with pytest.raises(PlanningError, match="invalid query plan"):
        provider.propose_query_plan(
            "Report", ResolvedContext("2025", ("orders",), ("revenue",), ("active",), ""),
            PlanCandidates({}, {}, {}, ()),
        )


@pytest.mark.parametrize("content", [
    "not-json",
    '{"base_table_id":"t0","joins":[],"time_column_id":"c0","time_grain":"month",'
    '"dimensions":[],"measures":"bad","filters":[]}',
    '{"base_table_id":"t0","joins":[{"relation_id":1,"to_table_id":"t1",'
    '"join_type":"left"}],"time_column_id":"c0","time_grain":"month",'
    '"dimensions":[],"measures":[],"filters":[]}',
])
def test_query_planning_rejects_malformed_model_output(content):
    completions = FakeCompletions(content)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    provider = OpenAIChatProvider(LLMConfig(api_key="secret"), client=client)
    with pytest.raises(PlanningError, match="invalid query plan"):
        provider.propose_query_plan(
            "Report", ResolvedContext("2025", ("orders",), (), (), ""),
            PlanCandidates({}, {}, {}, ()),
        )


def test_planning_recovers_from_malformed_model_response_without_echoing_it():
    query_space = QuerySpace(
        (Table("orders"),),
        (Column("orders", "amount", "decimal"), Column("orders", "ordered_at", "date")),
        (), (),
    )
    valid = {"base_table_id": "t0", "joins": [], "time_column_id": "c1",
             "time_grain": "none", "dimensions": [],
             "measures": [{"metric_id": "m0", "aggregation": "sum", "column_id": "c0"}],
             "filters": []}
    completions = SequencedCompletions("private malformed output", json.dumps(valid))
    provider = OpenAIChatProvider(
        LLMConfig(api_key="secret"),
        client=SimpleNamespace(chat=SimpleNamespace(completions=completions)),
    )

    plan = create_query_plan(
        "Order revenue in 2025", ResolvedContext("2025", ("orders",), ("revenue",), (), ""),
        query_space, provider,
    )

    assert plan.measures[0].source_metric == "revenue"
    assert len(completions.calls) == 2
    assert "private malformed output" not in str(completions.calls[1])
    assert "required JSON plan structure" in completions.calls[1]["messages"][-1]["content"]
