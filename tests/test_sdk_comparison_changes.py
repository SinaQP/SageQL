"""Fixed comparison changes: real compilers, synthetic rows, fake model calls."""

from dataclasses import replace
from datetime import date
from decimal import Decimal, Inexact, ROUND_UP, localcontext
import json
import sqlite3
from types import SimpleNamespace

import pytest

from sageql import LLMConfig
from sageql.sdk import (
    AccessScope, ActorContext, AdapterResult, AggregateFilter, ConceptRef,
    DatasetAccess, ExecutionLimits, Interpretation, OpenAIReportAgent,
    PeriodSelection, ReportIntent, ReportSpec, RowPolicy, SDKError, SageQL,
    SQLiteAdapter, SQLiteSessionStore,
)
from sageql.sdk.adapters import compile_report
from sageql.sdk.comparisons import calculate_change, comparison_evidence_context
from sageql.sdk.lookups import prepare_request
from sageql.sdk.provider import _check_spec, _format
# The private Rahtal host supplies this catalog; it is not published.
pytest.importorskip("sageql_rahtal")
from sageql_rahtal.sdk import rahtal_reporting_catalog  # noqa: E402
from sageql import Message


TODAY = date(2026, 10, 11)
ACTOR = ActorContext("synthetic-manager")
QUESTION = (
    "مقایسه عملکرد ماهانه: حجم فعالیت سازمان در شهریور ۱۴۰۵ نسبت به مرداد چقدر "
    "تغییر کرده؟ هم از نظر مجموع ساعات کاری و هم تعداد فعالیت‌ها، درصد افزایش یا کاهش را نشان بده."
)
SPEC = ReportSpec(
    "activities", ("activity_hours", "activity_count"),
    period=PeriodSelection("jalali_month", year=1405, month=6),
    comparison=PeriodSelection("jalali_month", year=1405, month=5),
    comparison_calculation="change",
)
SCOPE = AccessScope((DatasetAccess("activities", policies=(RowPolicy("is_deleted", "eq", (False,)),)),))


@pytest.mark.parametrize("current, reference, absolute, percent, status", [
    (30, 20, 10, 50, "increase"), (15, 20, -5, -25, "decrease"),
    (20, 20, 0, 0, "unchanged"), (0, 20, -20, -100, "decrease"),
    (10, 0, 10, None, "zero_baseline"), (0, 0, 0, None, "zero_baseline"),
    (None, 20, None, None, "missing_value"), (10, None, None, None, "missing_value"),
    (10, -5, 15, None, "negative_baseline"),
    (Decimal("0.3"), Decimal("0.2"), Decimal("0.1"), 50, "increase"),
    (Decimal("12345678901234567890.123"), Decimal("12345678901234567890.122"), Decimal(".001"), None, "increase"),
])
def test_fixed_change_arithmetic_and_reference_edge_cases(current, reference, absolute, percent, status):
    with localcontext() as context:
        # Host precision, rounding and traps must not alter SDK arithmetic.
        context.prec = 2
        context.rounding = ROUND_UP
        context.traps[Inexact] = True
        result = calculate_change(current, reference)
    assert result[0] == absolute and result[2] == status
    if status == "increase" and percent is None:
        assert result[1] > 0
    else:
        assert result[1] == percent


@pytest.mark.parametrize("value", [True, "10", float("inf"), float("nan"), Decimal("NaN"), Decimal("1E10000"), 2**2000])
def test_invalid_comparison_values_fail_with_a_safe_error(value):
    with pytest.raises(SDKError) as error:
        calculate_change(value, 20)
    assert error.value.code == "adapter_failed"


@pytest.mark.parametrize("changes", [
    {"comparison_calculation": "current / previous"}, {"comparison_calculation": []},
    {"comparison": None}, {"dimension_ids": ("employee_id",)}, {"time_grain": "day"},
    {"aggregate_filters": (AggregateFilter("activity_hours", "gt", (0,)),)},
    {"limit": 1}, {"chart": "bar"},
])
def test_unsupported_formulas_or_grains_cannot_reach_compilation(changes):
    with pytest.raises(SDKError):
        prepare_request(rahtal_reporting_catalog(), replace(SPEC, **changes), SCOPE, TODAY)
    if "comparison_calculation" in changes:
        with pytest.raises(ValueError):
            _check_spec(replace(SPEC, **changes), rahtal_reporting_catalog())


def test_legacy_specification_defaults_and_strict_model_schema():
    old = SPEC.to_dict()
    del old["comparison_calculation"]
    assert ReportSpec.from_dict(old).comparison_calculation == "none"
    del old["aggregate_filters"]
    assert ReportSpec.from_dict(old).aggregate_filters == ()
    old["formula"] = "x/y"
    with pytest.raises(SDKError):
        ReportSpec.from_dict(old)
    schema = _format(rahtal_reporting_catalog())["json_schema"]["schema"]["properties"]["spec"]["anyOf"][0]
    assert "comparison_calculation" in schema["required"]
    assert schema["properties"]["comparison_calculation"]["enum"] == ["none", "change", "decrease"]


def test_percentage_evidence_repairs_wrong_monthly_grain_and_cannot_be_dropped():
    wrong = ReportIntent(comparison=SPEC.comparison, comparison_specified=True,
                         time_grain="jalali_month", comparison_calculation="none")
    checked = comparison_evidence_context(wrong, (Message("user", QUESTION),), None)
    assert checked.comparison_calculation == "change" and checked.time_grain == "none"
    grouped = comparison_evidence_context(wrong, (Message("user", "درصد تغییر را روزانه نشان بده"),), None)
    assert grouped.time_grain == "jalali_month"  # Preserve explicit unsupported breakdown.


def test_refinement_preserves_calculation_and_explicit_removal_is_honored():
    effective = ReportIntent(turn_kind="refine", comparison=SPEC.comparison, comparison_specified=True)
    messages = (Message("user", "همان گزارش با تعداد فعالیت‌ها"),)
    assert comparison_evidence_context(effective, messages, SPEC).comparison_calculation == "change"
    removed = replace(effective, comparison_calculation="none")
    assert comparison_evidence_context(removed, messages, SPEC).comparison_calculation == "none"
    assert comparison_evidence_context(effective, (Message("user", "درصد تغییر را حذف کن"),), SPEC).comparison_calculation == "none"


def test_non_numeric_aggregates_are_rejected():
    from sageql.sdk import MetricDefinition
    catalog = rahtal_reporting_catalog()
    source = replace(catalog.datasets[0], metrics=(*catalog.datasets[0].metrics,
                     MetricDefinition("first_day", "نخستین تاریخ", "minimum", "date")))
    catalog = replace(catalog, datasets=(source, *catalog.datasets[1:]))
    with pytest.raises(SDKError) as error:
        prepare_request(catalog, replace(SPEC, metric_ids=("first_day",)), SCOPE, TODAY)
    assert error.value.code == "unsupported"


class Client:
    def __init__(self, *plans, turn="new"):
        intent = ReportIntent(metrics=tuple(ConceptRef("activities", key) for key in SPEC.metric_ids),
                              period=SPEC.period, comparison=SPEC.comparison, comparison_specified=True,
                              comparison_calculation="change", time_grain="none", turn_kind=turn)
        self.responses = iter((intent.to_dict(), *(
            {"status": "ready", "spec": item.to_dict(), "question": "", "message": ""} for item in plans
        ), {"approved": True, "feedback": ""}))
        self.calls = []
        self.chat = SimpleNamespace(completions=self)

    def with_options(self, **options):
        return self

    def create(self, **options):
        self.calls.append(options)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(next(self.responses))))])


class Adapter(SQLiteAdapter):
    def __init__(self, path):
        super().__init__(path)
        self.calls = []
        self.alter = lambda result: result

    def execute(self, request, limits, *, cancel=None):
        self.calls.append(request)
        return self.alter(super().execute(request, limits, cancel=cancel))


def engine_for(tmp_path, *plans):
    path = tmp_path / "monthly.sqlite"
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE functionality_activities (
                id int NOT NULL, user_id int, date date, time float, is_deleted bit, title_id bigint);
            INSERT INTO functionality_activities VALUES
                (1,1,'2026-07-23',10,0,NULL), (2,2,'2026-08-22',10,0,NULL),
                (3,1,'2026-08-23',5,0,NULL), (4,2,'2026-09-22',10,0,NULL),
                (5,1,'2026-09-01',15,0,NULL), (6,1,'2026-09-01',999,1,NULL),
                (7,1,'2026-09-23',888,0,NULL), (8,1,'2026-07-22',777,0,NULL);
        """)
    client = Client(*(plans or (SPEC,)))
    adapter = Adapter(path)
    engine = SageQL(catalog=rahtal_reporting_catalog("main"), database=adapter,
                    provider=OpenAIReportAgent(LLMConfig("fake", "https://example.test/v1", "fake"), client=client),
                    policy=lambda actor: SCOPE, execution="validated", clock=lambda: TODAY,
                    sessions=SQLiteSessionStore(tmp_path / "sessions.sqlite"))
    return engine, client, adapter


def test_both_period_totals_changes_persistence_and_cached_retry(tmp_path):
    engine, client, adapter = engine_for(tmp_path)
    session = engine.create_session(ACTOR)
    reply = engine.submit(session.session_id, QUESTION, ACTOR, "monthly", 0)
    assert reply.status == "report_ready" and reply.error is None
    assert reply.report.rows == (
        ("مجموع ساعات فعالیت (ساعت)", 20.0, 30.0, 10.0, Decimal(50), "افزایش"),
        ("تعداد فعالیت‌های ثبت‌شده", 2, 3, Decimal(1), Decimal(50), "افزایش"),
    )
    assert tuple(field.id for field in reply.report.fields) == (
        "metric_label", "comparison_value", "base_value", "absolute_change", "percent_change", "change_status")
    assert reply.report.provenance["percentage_reference"] == "comparison"
    assert reply.report.fields[1].label == "مرداد 1405" and reply.report.fields[2].label == "شهریور 1405"
    query = compile_report(adapter.calls[0], ExecutionLimits(), dialect="tsql")
    assert "UNION ALL" in query.sql and query.sql.count("is_deleted") == 2
    assert "JOIN" not in query.sql and "/" not in query.sql
    assert Decimal(engine.get_report(session.session_id, reply.report.id, ACTOR).to_dict()["rows"][0][4]) == 50
    cached = engine.submit(session.session_id, QUESTION, ACTOR, "monthly", 0)
    assert cached.to_dict() == reply.to_dict() and len(adapter.calls) == 1
    state = engine.sessions.get(session.session_id, (ACTOR.subject, ACTOR.tenant_id))
    assert ReportSpec.from_dict(state["current_spec"]).comparison_calculation == "change"
    assert len(client.calls) == 3
    model_text = json.dumps(client.calls, ensure_ascii=False)
    assert "functionality_activities" not in model_text and "change_statuses" not in model_text


def test_percentage_request_cannot_silently_return_only_period_totals(tmp_path):
    engine, client, adapter = engine_for(tmp_path, replace(SPEC, comparison_calculation="none"), SPEC)
    session = engine.create_session(ACTOR)
    reply = engine.submit(session.session_id, QUESTION, ACTOR, "monthly", 0)
    assert reply.status == "report_ready" and len(adapter.calls) == 1 and len(client.calls) == 4
    payload = json.loads(client.calls[2]["messages"][1]["content"])
    assert payload["feedback"] == ["intent_validation: comparison_calculation_mismatch"]


def test_persisted_comparison_refinement_keeps_both_dates_and_calculation(tmp_path):
    engine, _, adapter = engine_for(tmp_path)
    session = engine.create_session(ACTOR)
    first = engine.submit(session.session_id, QUESTION, ACTOR, "first", 0)
    client = Client(SPEC, turn="refine")
    engine.provider = OpenAIReportAgent(LLMConfig("fake", "https://example.test/v1", "fake"), client=client)
    second = engine.submit(session.session_id, "همین گزارش را دوباره تهیه کن", ACTOR, "refine", first.revision)
    assert second.status == "report_ready" and second.report.rows == first.report.rows
    assert len(adapter.calls) == 2
    current = json.loads(client.calls[0]["messages"][1]["content"])["current_spec"]
    assert current["comparison_calculation"] == "change"
    assert current["period"]["month"] == 6 and current["comparison"]["month"] == 5
    assert "change_statuses" not in json.dumps(client.calls)


@pytest.mark.parametrize("reference, expected_status", [(0, "مبنای صفر"), (None, "دادهٔ کافی")])
def test_zero_or_null_reference_is_presented_without_a_fabricated_percent(tmp_path, reference, expected_status):
    engine, _, adapter = engine_for(tmp_path)
    adapter.alter = lambda result: replace(result, rows=tuple(
        (row[0], reference, row[2]) if row[0] == "comparison" else row for row in result.rows))
    session = engine.create_session(ACTOR)
    reply = engine.submit(session.session_id, QUESTION, ACTOR, "edge", 0)
    assert reply.status == "report_ready"
    row = reply.report.rows[0]
    assert row[1] is reference and row[4] is None and expected_status in row[5]


@pytest.mark.parametrize("alter", [
    lambda result: replace(result, truncated=True),
    lambda result: replace(result, rows=result.rows[:1]),
    lambda result: replace(result, rows=(result.rows[0], result.rows[0])),
    lambda result: replace(result, rows=(("unknown", *result.rows[0][1:]), result.rows[1])),
    lambda result: replace(result, rows=(("base", "private-invalid-value", 3), result.rows[1])),
])
def test_incomplete_or_invalid_period_results_fail_before_persistence(tmp_path, alter):
    engine, _, adapter = engine_for(tmp_path)
    adapter.alter = alter
    session = engine.create_session(ACTOR)
    reply = engine.submit(session.session_id, QUESTION, ACTOR, "bad", 0)
    assert reply.status == "failed" and reply.error["code"] == "adapter_failed"
    assert reply.report is None and "private-invalid-value" not in json.dumps(reply.to_dict())
    state = engine.sessions.get(session.session_id, (ACTOR.subject, ACTOR.tenant_id))
    assert state["current_spec"] is None and not state["reports"]
