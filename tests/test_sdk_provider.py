"""Remote report interpretation is tested entirely with an in-process transport."""

import json
from dataclasses import replace
from datetime import date
from types import SimpleNamespace

import pytest

from sageql.conversation import LLMConfig, Message
from sageql.schema import Column, Table
from sageql.sdk.models import (
    DatasetDefinition, DimensionDefinition, FilterDefinition, MetricDefinition,
    PeriodSelection, ReportingCatalog, ReportSpec, SDKError, TimeDefinition,
)
from sageql.sdk.provider import OpenAIReportInterpreter


class FakeClient:
    def __init__(self, content):
        self.content = content
        self.options = None
        self.calls = []
        self.chat = SimpleNamespace(completions=self)

    def with_options(self, **kwargs):
        self.options = kwargs
        return self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.content, Exception):
            raise self.content
        return SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content=self.content))])


@pytest.fixture
def catalog():
    return ReportingCatalog((DatasetDefinition(
        "activities", "Activities", Table("private_reporting_view", "private_schema"),
        (Column("private_schema.private_reporting_view", "hours", "decimal"),
         Column("private_schema.private_reporting_view", "employee", "nvarchar"),
         Column("private_schema.private_reporting_view", "activity_date", "date"),
         Column("private_schema.private_reporting_view", "private_tenant_key", "int")),
        (MetricDefinition("activity_hours", "Activity hours", "sum", "hours", "hours"),),
        (DimensionDefinition("employee", "Employee", "employee"),),
        (FilterDefinition("employee_filter", "Employee", "employee"),),
        TimeDefinition("activity_date"), row_key=("private_tenant_key",),
    ),))


def ready_output():
    return {"status": "ready", "question": "", "message": "Daily activity hours.",
            "spec": ReportSpec("activities", ("activity_hours",),
                               period=PeriodSelection("month", year=2026, month=9),
                               time_grain="day", chart="line").to_dict()}


def interpret(content, catalog, *, current_spec=None, messages=None):
    client = FakeClient(content)
    provider = OpenAIReportInterpreter(
        LLMConfig("private-api-key", "https://example.test/v1", "configured-model"),
        client=client, timeout_seconds=12, max_output_tokens=3072,
    )
    result = provider.interpret(messages or (Message("user", "Daily hours for September 2026"),),
                                current_spec, catalog, date(2026, 10, 5))
    return result, client


def test_structured_report_and_model_boundary(catalog):
    result, client = interpret(json.dumps(ready_output()), catalog)
    assert result.status == "ready"
    assert result.spec.metric_ids == ("activity_hours",)
    assert result.spec.period.month == 9
    assert client.options == {"timeout": 12, "max_retries": 0}
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["timeout"] == 12
    assert call["max_completion_tokens"] == 3072
    assert call["model"] == "configured-model"
    assert call["response_format"]["json_schema"]["strict"] is True
    properties = call["response_format"]["json_schema"]["schema"]["properties"]["spec"]["anyOf"][0]["properties"]
    assert properties["dataset_id"]["enum"] == ["activities"]
    assert properties["dimension_ids"]["items"]["enum"] == ["employee"]
    assert properties["metric_ids"]["items"]["enum"] == ["activity_hours"]
    assert properties["filters"]["items"]["properties"]["filter_id"]["enum"] == ["employee_filter"]
    assert properties["limit"] == {"type": "integer", "minimum": 1, "maximum": 10_000}
    assert "private_tenant_key" not in properties["order_by"]["enum"]
    payload = call["messages"][1]["content"]
    assert "Activity hours" in payload
    assert "private-api-key" not in payload
    assert "private_schema" not in payload
    assert "private_reporting_view" not in payload
    assert "private_tenant_key" not in payload
    assert "row_key" not in payload
    assert "policies" not in payload


def test_refinement_keeps_complete_spec_and_clarification_history(catalog):
    current = ReportSpec("activities", ("activity_hours",),
                         period=PeriodSelection("month", year=2026, month=9))
    messages = (Message("user", "September hours"), Message("assistant", "Which year?"),
                Message("user", "2026"), Message("assistant", "Report created."),
                Message("user", "Group by employee"))
    output = ready_output()
    output["spec"]["dimension_ids"] = ["employee"]
    output["spec"]["time_grain"] = "none"
    output["spec"]["chart"] = "bar"
    result, client = interpret(json.dumps(output), catalog, current_spec=current, messages=messages)
    assert result.spec.dimension_ids == ("employee",)
    payload = json.loads(client.calls[0]["messages"][1]["content"])
    assert payload["current_spec"] == current.to_dict()
    assert [item["text"] for item in payload["conversation"]] == [item.content for item in messages]


def listing_output():
    return {"status": "ready", "question": "", "message": "Employee names.",
            "spec": ReportSpec("activities", (), dimension_ids=("employee",)).to_dict()}


@pytest.fixture
def employee_catalog():
    table = Table("private_profiles", "private_schema")
    return ReportingCatalog((DatasetDefinition(
        "employees", "Employee profiles", table,
        tuple(Column(table.key, column, kind) for column, kind in (
            ("first_name", "nvarchar"), ("last_name", "nvarchar"),
            ("job_position", "nvarchar"), ("user_id", "int"),
        )),
        (MetricDefinition("employee_count", "Number of employee profiles", "count_rows"),),
        dimensions=(
            DimensionDefinition("first_name", "First name", "first_name"),
            DimensionDefinition("last_name", "Last name", "last_name"),
            DimensionDefinition("job_position", "Job position", "job_position"),
            DimensionDefinition("employee_id", "Employee ID", "user_id"),
        ),
    ),))


def test_clarification_uses_business_labels_instead_of_interpreter_options(employee_catalog):
    output = {
        "status": "needs_clarification", "spec": None,
        "question": "Do you want first_name, last_name, job_position, employee_id, or employee_count?",
        "message": "Use period all, time_grain none, and chart table for employees.",
    }
    result, _ = interpret(json.dumps(output), employee_catalog,
                          messages=(Message("user", "Hey"), Message("user", "Profiles")))
    assert result.question == "Do you want First name, Last name, Job position, Employee ID, or Number of employee profiles?"
    assert result.message == "Use all available dates, no date grouping, and a table for employees."
    for token in ("first_name", "last_name", "job_position", "employee_id", "employee_count",
                  "period all", "time_grain", "chart table"):
        assert token not in result.question + result.message


def test_straightforward_name_listing_is_ready_without_implementation_confirmation(employee_catalog):
    spec = ReportSpec("employees", (), dimension_ids=("first_name", "last_name"),
                      order_by="last_name")
    output = {"status": "ready", "spec": spec.to_dict(), "question": "",
              "message": "List first_name and last_name with period=all and time_grain=none."}
    result, client = interpret(json.dumps(output), employee_catalog,
                               messages=(Message("user", "Show my employees' names."),))
    assert result.status == "ready"
    assert result.question == ""
    assert result.spec == spec  # Display translations never alter registered IDs.
    assert result.message == "List First name and Last name with all available dates and no date grouping."
    instructions = client.calls[0]["messages"][0]["content"]
    assert "straightforward request for names is ready" in instructions
    assert "Do not ask the user to confirm implementation details" in instructions
    assert "business labels rather than a catalog dump" in instructions


def test_business_label_translation_preserves_required_year_question(catalog):
    output = {"status": "needs_clarification", "spec": None,
              "question": "Which year should September cover for activity_hours?",
              "message": "Please specify the year."}
    result, _ = interpret(json.dumps(output), catalog)
    assert result.question == "Which year should September cover for Activity hours?"
    assert result.spec is None


def test_display_translation_respects_identifier_boundaries(employee_catalog):
    output = {"status": "unsupported", "spec": None, "question": "",
              "message": "first_name appears in this request; first_name_extra is unavailable."}
    result, _ = interpret(json.dumps(output), employee_catalog)
    assert result.message == "First name appears in this request; first_name_extra is unavailable."


def test_display_translation_preserves_an_already_natural_employee_question(employee_catalog, catalog):
    output = {"status": "needs_clarification", "spec": None,
              "question": "Which employees do you mean?",
              "message": "Tell me which employee profiles you want to see."}
    for registered in (employee_catalog, catalog):
        result, _ = interpret(json.dumps(output), registered)
        assert result.question == output["question"]
        assert result.message == output["message"]


def test_display_translation_maps_a_backticked_dataset_id(employee_catalog):
    output = {"status": "unsupported", "spec": None, "question": "",
              "message": "You can report on `employees`. Which employees would you like to see?"}
    result, _ = interpret(json.dumps(output), employee_catalog)
    assert result.message == "You can report on Employee profiles. Which employees would you like to see?"


@pytest.mark.parametrize("message,question", [
    ("hey", "What would you like to know?"),
    ("profiles", "What would you like to know about employee profiles?"),
])
def test_incomplete_intent_clarifies_without_inventing_a_report(employee_catalog, message, question):
    output = {"status": "needs_clarification", "spec": None,
              "question": question, "message": "I can help with employee reports."}
    result, client = interpret(json.dumps(output), employee_catalog,
                               messages=(Message("user", message),))
    assert result.status == "needs_clarification"
    assert result.spec is None
    assert result.question == question
    instructions = client.calls[0]["messages"][0]["content"]
    assert "greeting or a message with no report question, return needs_clarification with null spec" in instructions
    assert "Never mark a greeting ready or infer a report from it" in instructions
    assert "A dataset name by itself" in instructions
    assert "instead of choosing a default listing or count" in instructions
    assert "An answer to an earlier clarification can be ready" in instructions


def test_dimension_listing_does_not_require_an_invented_metric(catalog):
    output = listing_output()
    result, client = interpret(json.dumps(output), catalog,
                               messages=(Message("user", "Send me employee names."),))
    assert result.spec.metric_ids == ()
    assert result.spec.dimension_ids == ("employee",)
    assert result.spec.period.kind == "all"
    assert result.spec.chart == "table"
    instructions = client.calls[0]["messages"][0]["content"]
    assert "distinct combinations" in instructions
    assert "do not invent an aggregate metric" in instructions


def test_dimension_listing_accepts_an_explicit_registered_date_restriction(catalog):
    output = listing_output()
    output["spec"]["period"] = {
        "kind": "month", "start": None, "end": None, "year": 2026, "month": 9,
    }
    result, _ = interpret(json.dumps(output), catalog)
    assert result.spec.period == PeriodSelection("month", year=2026, month=9)


@pytest.mark.parametrize("mutation", [
    lambda value: value["spec"].update(dimension_ids=[]),
    lambda value: value["spec"].update(chart="bar"),
    lambda value: value["spec"].update(chart="kpi"),
    lambda value: value["spec"].update(time_grain="day"),
    lambda value: value["spec"].update(limit=0),
    lambda value: value["spec"].update(order_by="time_bucket"),
    lambda value: value["spec"].update(order_by="period_label"),
    lambda value: value["spec"].update(comparison={
        "kind": "last_month", "start": None, "end": None, "year": None, "month": None,
    }),
])
def test_invalid_dimension_listing_is_rejected(catalog, mutation):
    output = listing_output()
    mutation(output)
    with pytest.raises(SDKError) as error:
        interpret(json.dumps(output), catalog)
    assert error.value.code == "invalid_interpretation"


def test_timeless_dataset_lists_names_without_a_period_question(catalog):
    timeless = ReportingCatalog((replace(catalog.datasets[0], time=None, metrics=()),))
    result, client = interpret(json.dumps(listing_output()), timeless,
                               messages=(Message("user", "List employees."),))
    assert result.spec.period.kind == "all"
    payload = json.loads(client.calls[0]["messages"][1]["content"])
    assert payload["catalog"]["datasets"][0]["time"] is None
    assert "no time definition always uses period all" in client.calls[0]["messages"][0]["content"]


def test_timeless_dataset_rejects_an_invented_date_restriction(catalog):
    timeless = ReportingCatalog((replace(catalog.datasets[0], time=None),))
    output = listing_output()
    output["spec"]["period"] = {
        "kind": "month", "start": None, "end": None, "year": 2026, "month": 9,
    }
    with pytest.raises(SDKError) as error:
        interpret(json.dumps(output), timeless)
    assert error.value.code == "invalid_interpretation"


def test_fresh_daily_request_preserves_latest_intent_in_provider_payload(catalog):
    messages = (
        Message("user", "Group it by employee instead"),
        Message("assistant", "That earlier request is unsupported."),
        Message("user", "Daily activity hours for September 2025"),
    )
    output = ready_output()
    output["spec"]["period"]["year"] = 2025
    result, client = interpret(json.dumps(output), catalog, messages=messages)
    assert result.spec.dimension_ids == ()
    assert result.spec.time_grain == "day"
    payload = json.loads(client.calls[0]["messages"][1]["content"])
    assert payload["conversation"][-1]["text"] == messages[-1].content
    instructions = client.calls[0]["messages"][0]["content"]
    assert "Interpret the latest user message first" in instructions
    assert "earlier unsupported request" in instructions


def test_ambiguous_year_can_clarify_calendar_without_repeating_year_question(catalog):
    messages = (Message("user", "September hours"),
                Message("assistant", "Which year?"), Message("user", "1403"))
    output = {"status": "needs_clarification", "spec": None,
              "question": "Do you mean the Jalali calendar or Gregorian year 1403?",
              "message": "Please specify the calendar."}
    result, client = interpret(json.dumps(output), catalog, messages=messages)
    assert "calendar" in result.question
    assert result.spec is None
    assert "instead of silently treating it as Gregorian" in client.calls[0]["messages"][0]["content"]


def test_confirmed_jalali_calendar_has_an_explicit_unsupported_outcome(catalog):
    messages = (Message("user", "Activity hours in 1403"),
                Message("assistant", "Which calendar?"), Message("user", "Jalali"))
    output = {"status": "unsupported", "spec": None, "question": "",
              "message": "This report supports Gregorian dates. Please supply Gregorian dates for your Jalali period."}
    result, client = interpret(json.dumps(output), catalog, messages=messages)
    assert result.status == "unsupported"
    assert "Gregorian dates" in result.message
    assert result.spec is None
    assert "Never invent a calendar conversion" in client.calls[0]["messages"][0]["content"]


@pytest.mark.parametrize("status,question,message", [
    ("needs_clarification", "Which year?", "Please specify the year."),
    ("unsupported", "", "The registered metrics do not support profit."),
])
def test_incomplete_outcomes(catalog, status, question, message):
    result, _ = interpret(json.dumps({"status": status, "spec": None,
                                    "question": question, "message": message}), catalog)
    assert result.spec is None
    assert result.status == status
    assert result.question == question


@pytest.mark.parametrize("mutation", [
    lambda value: value.update(sql="SELECT private_data"),
    lambda value: value.update(question="Which year?"),
    lambda value: value["spec"].update(dataset_id="not-registered"),
    lambda value: value["spec"].update(metric_ids=["private_metric"]),
    lambda value: value["spec"].update(metric_ids=["activity_hours", "activity_hours"]),
    lambda value: value["spec"].update(dimension_ids=["private_tenant_key"]),
    lambda value: value["spec"].update(filters=[{"filter_id": "employee_filter", "operator": "drop", "values": []}]),
    lambda value: value["spec"].update(filters=[{"filter_id": "employee_filter", "operator": "eq", "values": [{}]}]),
    lambda value: value["spec"].update(limit=True),
    lambda value: value["spec"].update(descending="yes"),
    lambda value: value["spec"].update(order_by="private_tenant_key"),
    lambda value: value["spec"].update(period={"kind": "month", "start": None, "end": None,
                                           "year": True, "month": 9}),
    lambda value: value["spec"].pop("comparison"),
])
def test_unsafe_or_malformed_specification_is_rejected(catalog, mutation):
    output = ready_output()
    mutation(output)
    with pytest.raises(SDKError, match="invalid interpretation") as error:
        interpret(json.dumps(output), catalog)
    assert error.value.code == "invalid_interpretation"


@pytest.mark.parametrize("content", [
    "not JSON", None, "[]",
    '{"status":"unsupported","spec":null,"question":"","message":"one","message":"two"}',
    '{"status":"unsupported","spec":null,"question":"","message":NaN}',
    '{"status":"needs_clarification","spec":null,"question":"","message":""}',
    '{"status":"unsupported","spec":null,"question":"why?","message":"Unsupported."}',
    '{"status":"unsupported","spec":null,"question":"","message":""}',
])
def test_invalid_responses_fail_without_echoing_content(catalog, content):
    with pytest.raises(SDKError) as error:
        interpret(content, catalog)
    assert error.value.code == "invalid_interpretation"
    assert "NaN" not in str(error.value)


def test_transport_failure_is_safe_and_not_retried(catalog):
    client = FakeClient(RuntimeError("private connection key and private host"))
    provider = OpenAIReportInterpreter(LLMConfig("secret"), client=client)
    with pytest.raises(SDKError) as error:
        provider.interpret((Message("user", "Hours"),), None, catalog, date(2026, 10, 5))
    assert error.value.code == "provider_failed"
    assert error.value.retryable
    assert "private" not in str(error.value)
    assert error.value.__suppress_context__ is True
    assert error.value.__cause__ is None
    assert len(client.calls) == 1


def test_input_bounds_fail_before_transport(catalog):
    client = FakeClient("unused")
    provider = OpenAIReportInterpreter(LLMConfig("secret"), client=client)
    with pytest.raises(SDKError) as error:
        provider.interpret((Message("user", "x" * 8001),), None, catalog, date(2026, 10, 5))
    assert error.value.code == "provider_input_limit"
    assert not client.calls


def metric_catalog(count, *, long_ids=False):
    datasets = []
    for dataset_index in range(2):
        table = Table("synthetic_source_" + str(dataset_index))
        metrics = tuple(MetricDefinition(
            "m" + "x" * 60 + f"{index:03d}" if long_ids else "metric_" + str(index),
            "Metric", "count_rows",
        ) for index in range(dataset_index * (count // 2),
                             (dataset_index + 1) * (count // 2)))
        datasets.append(DatasetDefinition(
            "dataset_" + str(dataset_index), "Dataset", table,
            (Column(table.key, "id", "int"),), metrics,
        ))
    return ReportingCatalog(tuple(datasets))


@pytest.mark.parametrize("count,long_ids", [(500, False), (300, True)],
                         ids=["total-enum-values", "single-enum-string-size"])
def test_response_schema_bounds_fail_before_transport(count, long_ids):
    from sageql.sdk.semantics import validate_catalog

    catalog = metric_catalog(count, long_ids=long_ids)
    validate_catalog(catalog)
    client = FakeClient("unused")
    provider = OpenAIReportInterpreter(LLMConfig("secret"), client=client)
    with pytest.raises(SDKError, match="response schema") as error:
        provider.interpret((Message("user", "Show a count"),), None, catalog, date(2026, 10, 5))
    assert error.value.code == "provider_input_limit"
    assert not error.value.retryable
    assert not client.calls


def test_large_catalog_within_response_schema_bounds_reaches_transport():
    response = json.dumps({"status": "unsupported", "spec": None,
                           "question": "", "message": "No matching concept."})
    result, client = interpret(response, metric_catalog(450))
    assert result.status == "unsupported"
    assert len(client.calls) == 1


@pytest.mark.parametrize("timeout", [True, 0, float("nan"), 181])
def test_timeout_must_be_bounded(timeout):
    with pytest.raises(ValueError):
        OpenAIReportInterpreter(LLMConfig("secret"), client=FakeClient("unused"),
                                timeout_seconds=timeout)


def test_injected_transport_must_allow_timeout_and_retry_configuration():
    with pytest.raises(ValueError, match="with_options"):
        OpenAIReportInterpreter(LLMConfig("secret"), client=SimpleNamespace())
