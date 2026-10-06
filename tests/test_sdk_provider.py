"""Remote report interpretation is tested entirely with an in-process transport."""

import json
from dataclasses import replace
from datetime import date
from types import SimpleNamespace

import pytest

from sageql.conversation import LLMConfig, Message
from sageql.schema import Column, Table
from sageql.sdk.models import (
    DatasetDefinition, DimensionDefinition, EntityLookupDefinition, FilterDefinition,
    FullNameFilterDefinition, LookupQualifier, MetricDefinition,
    PeriodSelection, ReportingCatalog, ReportSpec, SDKError, TimeDefinition, UserFilter,
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
        content = (self.content[len(self.calls) - 1]
                   if isinstance(self.content, (list, tuple)) else self.content)
        if isinstance(content, Exception):
            raise content
        return SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content=content))])


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


def interpret(content, catalog, *, current_spec=None, messages=None, language="fa"):
    client = FakeClient(content)
    provider = OpenAIReportInterpreter(
        LLMConfig("private-api-key", "https://example.test/v1", "configured-model"),
        client=client, timeout_seconds=12, max_output_tokens=3072,
        language=language,
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


def test_persian_default_preserves_unicode_conversation_and_literal_filters(catalog):
    name = "علي‌۱۲"
    messages = (Message("user", "ساعات فعاليت سپتامبر را بده"),
                Message("assistant", "کدام سال میلادی؟"), Message("user", "۲۰۲۶"),
                Message("user", f"فقط برای {name} و به صورت جدول"))
    output = ready_output()
    output["message"] = "گزارش ساعات فعالیت به صورت chart table در period month."
    output["spec"]["chart"] = "table"
    output["spec"]["filters"] = [{"filter_id": "employee_filter", "operator": "eq", "values": [name]}]
    result, client = interpret(json.dumps(output, ensure_ascii=False), catalog, messages=messages)
    call = client.calls[0]
    instructions = call["messages"][0]["content"]
    assert "in Persian (fa), even when the user writes in English" in instructions
    assert "۰۱۲۳۴۵۶۷۸۹" in instructions and "٠١٢٣٤٥٦٧٨٩" in instructions
    assert "ي/ی" in instructions and "ك/ک" in instructions
    assert "Never invent a calendar conversion" in instructions
    payload = json.loads(call["messages"][1]["content"])
    assert [item["text"] for item in payload["conversation"]] == [item.content for item in messages]
    assert result.spec.filters[0].values == (name,)
    assert result.spec.period.year == 2026
    assert result.message == "گزارش ساعات فعالیت به صورت جدول در ماه."
    assert "private_schema" not in call["messages"][1]["content"]


def test_explicit_english_provider_and_invalid_language(catalog):
    _, client = interpret(json.dumps(ready_output()), catalog, language="en")
    assert "in English (en)" in client.calls[0]["messages"][0]["content"]
    with pytest.raises(ValueError, match="language"):
        OpenAIReportInterpreter(LLMConfig("secret"), client=FakeClient(""), language="ar")


@pytest.fixture
def lookup_catalog(catalog):
    table = Table("private_profiles")
    source = DatasetDefinition("people", "کارکنان", table, (
        Column(table.key, "private_identity", "nvarchar"),
        Column(table.key, "private_given", "nvarchar"),
        Column(table.key, "private_surname", "nvarchar"),
        Column(table.key, "private_job", "nvarchar"),
    ), metrics=(), dimensions=(DimensionDefinition("person", "کارمند", "private_identity"),),
        filters=(FullNameFilterDefinition("full_name", "نام کامل", "private_given", ("eq",),
                                         ("private_given", "private_surname")),
                 FilterDefinition("job", "سمت", "private_job")))
    return replace(catalog, datasets=(*catalog.datasets, source), lookups=(
        EntityLookupDefinition("person_name", "نام کامل کارمند", "activities", "employee_filter",
                               "people", "person", "full_name",
                               (LookupQualifier("person_job", "سمت شغلی", "job"),)),
    ))


@pytest.mark.parametrize("job", [None, "مهندس"])
def test_registered_name_and_qualifier_decode_through_real_provider_boundary(lookup_catalog, job):
    filters = (UserFilter("person_name", "eq", ("کیان نمونه پور",)),)
    if job:
        filters += (UserFilter("person_job", "eq", (job,)),)
    spec = replace(ReportSpec.from_dict(ready_output()["spec"]), filters=filters)
    output = {"status": "ready", "question": "", "message": "گزارش برای person_name.",
              "spec": spec.to_dict()}
    result, client = interpret(json.dumps(output, ensure_ascii=False), lookup_catalog)
    assert result.spec == spec
    assert result.message == "گزارش برای نام کامل کارمند."
    call = client.calls[0]
    payload = json.loads(call["messages"][1]["content"])
    named = {item["id"]: item for item in payload["catalog"]["datasets"][0]["filters"]}
    assert named["person_name"]["resolves_entity"] is True
    assert named["person_job"]["requires_filter"] == "person_name"
    assert "private_profiles" not in call["messages"][1]["content"]
    assert "private_identity" not in call["messages"][1]["content"]
    assert "private_given" not in call["messages"][1]["content"]
    assert "source_dataset_id" not in call["messages"][1]["content"]
    assert "entire literal name as one value" in call["messages"][0]["content"]


def clarification_output(question):
    return json.dumps({"status": "needs_clarification", "spec": None,
                       "question": question, "message": ""}, ensure_ascii=False)


def named_output():
    output = ready_output()
    output["spec"]["filters"] = [{"filter_id": "person_name", "operator": "eq",
                                 "values": ["کیان نمونه پور"]}]
    output["spec"]["period"]["kind"] = "last_month"
    output["spec"]["period"]["year"] = output["spec"]["period"]["month"] = None
    return json.dumps(output, ensure_ascii=False)


@pytest.mark.parametrize("question", [
    "لطفاً شناسه کارمند کیان نمونه پور را ارائه دهید تا گزارش را بسازم.",
    "آیا شناسه کارمند مشخصی را دارید؟",
    "برای ادامه، آیا می‌خواهید با جست‌وجو بر اساس نام کارمند را پیدا کنم یا شناسه دقیق را ارائه کنید؟",
    "آیا می‌خواهید با اسمش جستجو کنم؟",
    "آیا می خواهید با اسمش جستجو کنم؟",
    "با نام کارمند جستجو کنم؛ تأیید می‌کنید؟",
    "مایلید از طریق جست‌وجوی نام کارمند را پیدا کنم؟",
    "کدام شناسه کارمند؟",
    "شناسه کارمند چیست؟",
    "لطفاً شناسه کارمند را مشخص کنید.",
    "لطفاً شناسه کارمند را ارسال کنید.",
    "Please provide the employee ID.",
    "Please specify the exact employee ID.",
    "Do you have their ID?",
    "Which employee ID should I use?",
    "What is the employee ID?",
    "Shall I look up the employee by name?",
    "Do you want me to search by name?",
    "Would you like me to find the employee by name?",
])
def test_internal_identity_and_lookup_confirmation_corrected_once(lookup_catalog, question):
    messages = (Message("user", "فعالیت‌های ماه قبل کیان نمونه پور را بفرست"),
                Message("assistant", "شناسه کارمند را ارائه دهید."),
                Message("user", "ندارم با اسمش پیداش کن"),
                Message("assistant", "آیا می‌خواهید با اسمش جستجو کنم؟"),
                Message("user", "با اسمش"))
    result, client = interpret([clarification_output(question), named_output()],
                               lookup_catalog, messages=messages)
    assert result.status == "ready" and result.question == ""
    assert result.spec.filters == (UserFilter("person_name", "eq", ("کیان نمونه پور",)),)
    assert result.spec.period.kind == "last_month"
    assert len(client.calls) == 2
    first, corrected = client.calls
    assert first["messages"][1] == corrected["messages"][1]
    assert first["response_format"] == corrected["response_format"]
    assert "Correct the unnecessary entity-lookup clarification" in corrected["messages"][0]["content"]
    assert "assistant questions can be mistaken" in first["messages"][0]["content"]
    payload = json.loads(corrected["messages"][1]["content"])
    assert payload["conversation"] == [{"role": item.role, "text": item.content} for item in messages]
    assert "private_identity" not in corrected["messages"][1]["content"]


@pytest.mark.parametrize("question", [
    "نام و نام خانوادگی کارمند چیست؟",
    "کدام سال میلادی؟",
    "برای شناسه کارمند ۴۲ کدام سال میلادی را مشخص می‌کنید؟",
    "چند کارمند با این نام وجود دارد؛ سمت شغلی چیست؟",
    "کدام گزارش را می‌خواهید؟",
    "Which year should September cover for employee ID 42?",
    "Please provide the year for employee ID 42.",
    "What is the employee's full name?",
    "Which job position distinguishes the employee?",
    "نام کامل کارمند را بگویید؛ شناسه کارمند لازم نیست.",
    "نام کامل کارمند را بگویید و شناسه کارمند لازم نیست.",
    "برای شناسه کارمند ۴۲ کدام سال میلادی را بگویید؟",
    "لطفاً شناسه سفارش را بفرستید.",
    "Please provide the order ID.",
    "آیا نام کامل کارمند را دارید تا جستجو کنم؟",
    "آیا نام و نام خانوادگی را برای جست‌وجو می‌گویید؟",
    "Would you provide the employee's full name so I can search?",
])
def test_real_business_clarifications_not_reinterpreted(lookup_catalog, question):
    result, client = interpret(clarification_output(question), lookup_catalog)
    assert result.status == "needs_clarification" and result.question == question
    assert len(client.calls) == 1


def test_identity_clarification_without_registered_lookup_not_reinterpreted(catalog):
    question = "Please provide the employee ID."
    result, client = interpret(clarification_output(question), catalog)
    assert result.question == question and len(client.calls) == 1


def test_correction_can_still_ask_for_a_real_missing_detail(lookup_catalog):
    result, client = interpret([clarification_output("Please provide the employee ID."),
                               clarification_output("Which year should September cover?")], lookup_catalog)
    assert result.status == "needs_clarification"
    assert result.question == "Which year should September cover?"
    assert len(client.calls) == 2


def test_repeated_identity_question_fails_without_a_third_call(lookup_catalog):
    content = clarification_output("لطفاً شناسه کارمند را ارائه دهید.")
    client = FakeClient(content)
    provider = OpenAIReportInterpreter(LLMConfig("secret"), client=client)
    with pytest.raises(SDKError) as error:
        provider.interpret((Message("user", "فعالیت‌های ماه قبل کیان نمونه پور"),),
                           None, lookup_catalog, date(2026, 10, 6))
    assert error.value.code == "clarification_stalled" and error.value.retryable
    assert "کیان" not in str(error.value) and "secret" not in str(error.value)
    assert len(client.calls) == 2


@pytest.mark.parametrize("second,code", [
    ("not JSON", "invalid_interpretation"),
    (RuntimeError("private secret"), "provider_failed"),
    (json.dumps({"status": "ready", "question": "", "message": "",
                 "spec": {**ready_output()["spec"], "dataset_id": "private_data"}}), "invalid_interpretation"),
    (json.dumps({**ready_output(), "sql": "SELECT private_data"}), "invalid_interpretation"),
])
def test_corrected_output_and_transport_still_fail_closed(lookup_catalog, second, code):
    with pytest.raises(SDKError) as error:
        interpret([clarification_output("Please provide the employee ID."), second], lookup_catalog)
    assert error.value.code == code
    assert "private" not in str(error.value)


def test_correction_uses_remaining_original_timeout(lookup_catalog, monkeypatch):
    ticks = iter((100, 108))
    monkeypatch.setattr("sageql.sdk.provider.time.monotonic", lambda: next(ticks))
    result, client = interpret([clarification_output("Please provide the employee ID."),
                               named_output()], lookup_catalog)
    assert result.status == "ready"
    assert [call["timeout"] for call in client.calls] == [12, 4]
    assert client.options == {"timeout": 12, "max_retries": 0}


def test_expired_correction_deadline_does_not_call_provider_again(lookup_catalog, monkeypatch):
    ticks = iter((100, 112))
    monkeypatch.setattr("sageql.sdk.provider.time.monotonic", lambda: next(ticks))
    client = FakeClient(clarification_output("Please provide the employee ID."))
    provider = OpenAIReportInterpreter(LLMConfig("secret"), client=client, timeout_seconds=12)
    with pytest.raises(SDKError) as error:
        provider.interpret((Message("user", "فعالیت‌های ماه قبل کیان نمونه پور"),),
                           None, lookup_catalog, date(2026, 10, 6))
    assert error.value.code == "request_timeout" and error.value.retryable
    assert len(client.calls) == 1


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
                          messages=(Message("user", "Hey"), Message("user", "Profiles")), language="en")
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
                               messages=(Message("user", "Show my employees' names."),), language="en")
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
