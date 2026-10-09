"""Jalali month model contracts use fake transport and no database or network."""

from dataclasses import replace
from datetime import date
import json
from types import SimpleNamespace

import pytest

from sageql import Column, LLMConfig, Message, Table
from sageql.sdk import (
    ConceptRef, DatasetDefinition, Interpretation, MetricDefinition, OpenAIReportAgent,
    OpenAIReportInterpreter, PeriodSelection, ReportingCatalog, ReportSpec,
    ReportIntent, TimeDefinition,
)


class Client:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.calls = []
        self.chat = SimpleNamespace(completions=self)

    def with_options(self, **options):
        return self

    def create(self, **options):
        self.calls.append(options)
        raw = json.dumps(next(self.responses), ensure_ascii=False)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=raw))])


@pytest.fixture
def catalog():
    table = Table("private_activity_source")
    return ReportingCatalog((DatasetDefinition(
        "activities", "فعالیت‌ها", table,
        (Column(table.key, "private_day", "date"),
         Column(table.key, "private_hours", "decimal")),
        (MetricDefinition("hours", "ساعات فعالیت", "sum", "private_hours", "ساعت"),),
        time=TimeDefinition("private_day"),
    ),))


def report():
    return ReportSpec("activities", ("hours",),
                      period=PeriodSelection("jalali_month", year=1405, month=6),
                      time_grain="day", chart="line")


def output(spec):
    return {"status": "ready", "spec": spec.to_dict(), "question": "",
            "message": "گزارش ساعات فعالیت شهریور ۱۴۰۵."}


def intent(*, missing=(), turn_kind="new"):
    return ReportIntent(metrics=(ConceptRef("activities", "hours"),),
                        missing=missing, turn_kind=turn_kind,
                        period=None if missing else report().period).to_dict()


def provider(kind, *responses):
    client = Client(*responses)
    interpreter = kind(LLMConfig("fake-key", "https://example.test/v1", "fake-model"), client=client)
    return interpreter, client


def test_interpreter_schema_and_decode_accept_explicit_jalali_month_without_model_conversion(catalog):
    expected = report()
    interpreter, client = provider(OpenAIReportInterpreter, output(expected))

    result = interpreter.interpret((Message("user", "ساعات روزانه شهریور ۱۴۰۵ را نشان بده."),),
                                   None, catalog, date(2026, 10, 8))

    assert result.spec == expected
    response_format = client.calls[0]["response_format"]
    assert response_format["json_schema"]["strict"] is True
    schema = response_format["json_schema"]["schema"]["properties"]["spec"]["anyOf"][0]
    for period in (schema["properties"]["period"], schema["properties"]["comparison"]["anyOf"][0]):
        assert "jalali_month" in period["properties"]["kind"]["enum"]
        assert period["additionalProperties"] is False
        assert set(period["required"]) == {"kind", "start", "end", "year", "month", "count", "unit"}
    instructions = client.calls[0]["messages"][0]["content"]
    assert "The host converts the month to date bounds locally" in instructions
    assert "never invent a calendar conversion" in instructions
    assert "Never infer a missing year" in instructions
    assert result.spec.period.start is None and result.spec.period.end is None


def test_agent_sends_calendar_scope_to_both_stages_and_reviews_unconverted_candidate(catalog):
    expected = report()
    agent, client = provider(OpenAIReportAgent, intent(), output(expected), {"approved": True, "feedback": ""})

    result = agent.interpret((Message("user", "روند ساعات فعالیت شهریور ۱۴۰۵ را نشان بده."),),
                             None, catalog, date(2026, 10, 8))

    assert result.spec == expected and len(client.calls) == 3
    for call in client.calls:
        instructions = call["messages"][0]["content"]
        assert "jalali_month" in instructions and "شهریور=6" in instructions
        assert "The host converts the month to date bounds locally" in instructions
        assert "Jalali relative periods" in instructions
        payload = json.loads(call["messages"][1]["content"])
        assert payload["catalog"]["datasets"][0]["time"]["calendar"] == "gregorian"
        assert "private_" not in call["messages"][1]["content"]
    reviewed = json.loads(client.calls[2]["messages"][1]["content"])["candidate"]
    assert reviewed["spec"]["period"] == expected.to_dict()["period"]
    assert reviewed["spec"]["period"]["start"] is None


@pytest.mark.parametrize("kind", [OpenAIReportInterpreter, OpenAIReportAgent])
def test_missing_persian_month_year_remains_a_business_clarification(catalog, kind):
    question = "شهریور کدام سال را در نظر دارید؟"
    incomplete = {"status": "needs_clarification", "spec": None, "question": question, "message": ""}
    responses = [incomplete]
    if kind is OpenAIReportAgent:
        responses.insert(0, intent(missing=("year",)))
        responses.append({"approved": True, "feedback": ""})
    interpreter, client = provider(kind, *responses)

    result = interpreter.interpret((Message("user", "ساعات شهریور را نشان بده."),),
                                   None, catalog, date(2026, 10, 8))

    assert result.status == "needs_clarification" and result.question == question and result.spec is None
    assert bool(result.clarification_key) == (kind is OpenAIReportAgent)
    assert "Never infer a missing year" in client.calls[0]["messages"][0]["content"]
    assert "ask only for a missing year, not which calendar they mean" in client.calls[0]["messages"][0]["content"]


def test_agent_refinement_preserves_jalali_selection_in_current_context(catalog):
    current = report()
    expected = replace(current, time_grain="none", chart="kpi")
    agent, client = provider(OpenAIReportAgent, intent(turn_kind="refine"), output(expected), {"approved": True, "feedback": ""})

    result = agent.interpret((Message("user", "مجموع همین ماه را در یک کارت عددی نشان بده."),),
                             current, catalog, date(2026, 10, 8))

    assert result.spec == expected
    for call in client.calls:
        payload = json.loads(call["messages"][1]["content"])
        assert payload["current_spec"]["period"] == current.to_dict()["period"]
