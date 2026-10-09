"""Independent intent gates on real synthetic report/session paths; no network."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
import json
import sqlite3
from types import SimpleNamespace

import pytest

from sageql import Column, LLMConfig, Message, Table
from sageql.sdk import (
    AccessScope, ActorContext, AggregateFilter, ConceptRef, DatasetAccess, DatasetDefinition,
    DimensionDefinition, EntityLabelDimension, FilterDefinition, Interpretation,
    MetricDefinition, OpenAIReportAgent, PeriodSelection, ReportingCatalog,
    ReportIntent, ReportSpec, RowPolicy, SDKError, SageQL, SQLiteAdapter,
    SQLiteSessionStore, TimeDefinition, UserFilter,
)
from sageql.sdk.agents import AgentReportInterpreter, AgentReview
from sageql.sdk.intent import check_intent, intent_feedback
from sageql.sdk.semantics import permitted_catalog


TODAY = date(2026, 10, 8)
ACTOR = ActorContext("intent-test", "7")


def catalog():
    work, people = Table("synthetic_work_rows"), Table("synthetic_profile_rows")
    return ReportingCatalog((
        DatasetDefinition("activities", "فعالیت‌ها", work, tuple(
            Column(work.key, name, kind) for name, kind in (
                ("worker_key", "int"), ("work_day", "date"), ("duration", "decimal"),
                ("unit_name", "text"), ("policy_tenant", "int"))),
            metrics=(MetricDefinition("hours", "ساعات فعالیت", "sum", "duration"),),
            dimensions=(DimensionDefinition("worker", "شناسه کارمند", "worker_key"),
                        DimensionDefinition("unit", "واحد کاری", "unit_name"),
                        EntityLabelDimension("worker_name", "نام کارمند", "worker_key",
                                             "employees", "identity", "identity_filter", ("display",))),
            time=TimeDefinition("work_day")),
        DatasetDefinition("employees", "کارکنان", people, tuple(
            Column(people.key, name, kind) for name, kind in (
                ("profile_key", "int"), ("profile_display", "text"),
                ("profile_position", "text"), ("policy_tenant", "int"))),
            metrics=(MetricDefinition("people", "تعداد کارکنان", "count_rows"),),
            dimensions=(DimensionDefinition("identity", "شناسه", "profile_key"),
                        DimensionDefinition("display", "نام", "profile_display"),
                        DimensionDefinition("job_position", "سمت شغلی", "profile_position")),
            filters=(FilterDefinition("identity_filter", "شناسه", "profile_key"),)),
    ))


def scope():
    return AccessScope(tuple(DatasetAccess(item, policies=(
        RowPolicy("policy_tenant", "eq", (7,)),
    )) for item in ("activities", "employees")))


def spec(**changes):
    return replace(ReportSpec("activities", ("hours",), ("worker_name",),
                              period=PeriodSelection("last_month"), chart="bar",
                              order_by="hours", descending=True), **changes)


def intent(request=None, *, missing=(), turn_kind="new", **changes):
    request = spec() if request is None else request
    return replace(ReportIntent(
        metrics=tuple(ConceptRef(request.dataset_id, key) for key in request.metric_ids),
        dimensions=tuple(ConceptRef(request.dataset_id, key) for key in request.dimension_ids),
        missing=missing, turn_kind=turn_kind,
        period=None if {"period", "year", "calendar"}.intersection(missing) else request.period,
    ), **changes)


def planned(request=None, *, question=None):
    return {"status": "needs_clarification" if question else "ready",
            "spec": None if question else (request or spec()).to_dict(),
            "question": question or "", "message": ""}


APPROVED = {"approved": True, "feedback": ""}


class Client:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.calls = []
        self.chat = SimpleNamespace(completions=self)

    def with_options(self, **kwargs):
        return self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        if isinstance(response, ReportIntent):
            response = response.to_dict()
        raw = response if isinstance(response, str) else json.dumps(response, ensure_ascii=False)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=raw))])


def provider(*responses, **options):
    client = Client(*responses)
    agent = OpenAIReportAgent(LLMConfig("fake-key", "https://example.test", "test"),
                              client=client, **options)
    return agent, client


class Adapter:
    def __init__(self, path):
        self.inner = SQLiteAdapter(path)
        self.calls = []

    def execute(self, request, limits, *, cancel=None):
        self.calls.append(request)
        return self.inner.execute(request, limits, cancel=cancel)


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "synthetic.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE synthetic_work_rows (worker_key INT, work_day DATE, duration DECIMAL, unit_name TEXT, policy_tenant INT)")
        connection.execute("CREATE TABLE synthetic_profile_rows (profile_key INT, profile_display TEXT, profile_position TEXT, policy_tenant INT)")
        connection.executemany("INSERT INTO synthetic_work_rows VALUES (?, ?, ?, ?, ?)", [
            (11, "2026-09-02", 4, "A", 7), (12, "2026-09-03", 3, "A", 7),
            (13, "2026-09-04", 2, "B", 7), (14, "2026-09-02", 900, "A", 8),
        ])
        connection.executemany("INSERT INTO synthetic_profile_rows VALUES (?, ?, ?, ?)", [
            (11, "Synthetic Alpha", "Role A", 7), (12, "Synthetic Beta", "Role A", 7),
            (13, "Synthetic Gamma", "Role B", 7), (14, "Other tenant", "Role A", 8),
        ])
    return path


def engine(database, agent, **kwargs):
    return SageQL(catalog=catalog(), database=Adapter(database), provider=agent,
                  policy=lambda _: scope(), clock=lambda: TODAY, execution="validated", **kwargs)


def test_full_conversation_blocks_unavailable_grouping_and_old_confirmation_without_reads(database):
    original = spec(chart="table")
    cross = intent(turn_kind="refine", dimensions=(ConceptRef("employees", "job_position"),))
    agent, client = provider(
        intent(original), planned(original), APPROVED,
        intent(turn_kind="refine", chart="bar"), planned(), APPROVED,
        cross, cross, replace(cross, turn_kind="answer"),
    )
    sdk = engine(database, agent)
    session = sdk.create_session(ACTOR)
    texts = (
        "گزارش عملکرد ماه گشته کارکنان منو بیار", "نمودار ستونی نشون بده اینا رو",
        "میتونی جمع کارکرد های رو بر اساس مقعیت شغلی برام بیار",
        "نه میخوام بر اساس موقعیت شغلی جمع ببنیدی بیاریشون", "اره همینکار کن",
    )
    replies = []
    for index, text in enumerate(texts):
        replies.append(sdk.submit(session.session_id, text, ACTOR, str(index), index))
    assert [reply.status for reply in replies] == ["report_ready", "report_ready"] + ["unsupported"] * 3
    assert len(sdk.database.calls) == 4  # Two aggregates plus their scoped labels.
    assert all("سمت شغلی" in reply.text and "ساعات فعالیت" in reply.text for reply in replies[2:])
    assert all(reply.report is None and reply.clarification is None for reply in replies[2:])
    assert len(client.calls) == 9
    assert sdk.get_report(session.session_id, replies[1].report.id, ACTOR).id == replies[1].report.id
    retry = sdk.submit(session.session_id, texts[-1], ACTOR, "4", 4)
    assert retry.to_dict() == replies[-1].to_dict() and len(client.calls) == 9


def test_supported_regrouping_cannot_reuse_previous_groups_even_with_approving_reviewer(database):
    grouped = spec(dimension_ids=("unit",))
    agent, client = provider(intent(grouped, turn_kind="refine"), planned(), planned(grouped), APPROVED)
    sdk = engine(database, agent)
    session = sdk.create_session(ACTOR)
    reply = sdk.submit(session.session_id, "جمع ساعات را به تفکیک واحد بده", ACTOR, "group", 0)
    assert reply.status == "report_ready", reply.to_dict()
    assert reply.report.rows == (("A", 7), ("B", 2))
    assert len(sdk.database.calls) == 1
    payloads = [json.loads(call["messages"][1]["content"]) for call in client.calls]
    assert payloads[2]["feedback"] == ["intent_validation: report_mismatch"]
    assert payloads[1]["intent"] == payloads[2]["intent"] == payloads[3]["intent"]
    assert "candidate" not in payloads[2]


def test_bar_refinement_retains_display_label_of_same_registered_identity(database):
    repeated_identity = intent(
        spec(dimension_ids=("worker", "worker_name")), turn_kind="refine", chart="bar")
    agent, client = provider(repeated_identity, planned(), APPROVED)
    sdk = engine(database, agent)
    session = sdk.create_session(ACTOR)
    reply = sdk.submit(session.session_id, "همان کارکنان را ستونی نمایش بده", ACTOR, "bar", 0)
    assert reply.status == "report_ready", reply.to_dict()
    assert [row[1] for row in reply.report.rows] == [4, 3, 2]
    assert reply.report.fields[0].id == "worker_name"
    planned_intent = json.loads(client.calls[1]["messages"][1]["content"])["intent"]
    assert planned_intent["dimensions"] == [{"dataset_id": "activities", "concept_id": "worker_name"}]
    assert "worker_key" not in json.dumps(planned_intent)


def test_bar_refinement_cannot_drop_a_different_grouping_column(database):
    two_groups = intent(spec(dimension_ids=("unit", "worker_name")), chart="bar")
    agent, _ = provider(two_groups, planned(), planned())
    sdk = engine(database, agent)
    session = sdk.create_session(ACTOR)
    reply = sdk.submit(session.session_id, "ستونی به تفکیک واحد و کارمند", ACTOR, "bar", 0)
    assert reply.error["code"] == "intent_mismatch" and sdk.database.calls == []


@pytest.mark.parametrize("wrong", [
    planned(), planned(spec(dimension_ids=())),
    planned(spec(dimension_ids=("unit",), chart="table")),
    planned(question="اجازه می‌دهید اطلاعات را ترکیب کنم؟"),
])
def test_bad_grouping_or_technical_question_cannot_execute_even_if_reviewer_would_approve(database, wrong):
    agent, client = provider(intent(spec(dimension_ids=("unit",)), chart="bar"), wrong, wrong, APPROVED)
    sdk = engine(database, agent)
    session = sdk.create_session(ACTOR)
    reply = sdk.submit(session.session_id, "ستونی به تفکیک واحد", ACTOR, "wrong", 0)
    assert reply.error["code"] == "intent_mismatch" and not reply.error["retryable"]
    assert reply.revision == 0 and sdk.database.calls == []
    assert len(client.calls) == 3  # Neither invalid candidate reaches the reviewer.


def test_unnecessary_question_is_replanned_into_supported_report(database):
    agent, client = provider(intent(), planned(question="تأیید می‌کنید؟"), planned(), APPROVED)
    sdk = engine(database, agent)
    session = sdk.create_session(ACTOR)
    reply = sdk.submit(session.session_id, "ساعات کارکنان در ماه قبل", ACTOR, "yes", 0)
    assert reply.status == "report_ready"
    assert json.loads(client.calls[2]["messages"][1]["content"])["feedback"] == [
        "intent_validation: unnecessary_clarification"]


def test_fresh_dated_total_with_omitted_period_gets_necessary_clarification(database):
    requested = spec(dimension_ids=("unit",), chart="table")
    agent, client = provider(intent(requested, period=None),
                             planned(question="ساعات کدام بازه زمانی را می‌خواهید؟"), APPROVED)
    sdk = engine(database, agent)
    session = sdk.create_session(ACTOR)
    reply = sdk.submit(session.session_id, "به تفکیک واحد بگو هرکدام چقدر کار کردند", ACTOR, "period", 0)
    assert reply.status == "needs_clarification" and sdk.database.calls == []
    effective = json.loads(client.calls[1]["messages"][1]["content"])["intent"]
    assert effective["missing"] == ["period"] and effective["period"] is None


def test_fresh_dated_aggregate_cannot_silently_use_all_dates(database):
    requested = spec(dimension_ids=("unit",), chart="table")
    agent, client = provider(intent(requested, period=None),
                             planned(replace(requested, period=PeriodSelection("all"))),
                             planned(question="کدام بازه زمانی؟"), APPROVED)
    sdk = engine(database, agent)
    session = sdk.create_session(ACTOR)
    reply = sdk.submit(session.session_id, "ساعات را به تفکیک واحد بگو", ACTOR, "no-all", 0)
    assert reply.status == "needs_clarification" and sdk.database.calls == []
    assert json.loads(client.calls[2]["messages"][1]["content"])["feedback"] == [
        "intent_validation: missing_information"]


def test_regrouping_without_new_dates_preserves_current_period(database):
    requested = spec(dimension_ids=("unit",), chart="table")
    agent, client = provider(intent(requested, period=None, turn_kind="refine"), planned(requested), APPROVED)
    assert agent.interpret((Message("user", "حالا به تفکیک واحد بگو"),), spec(),
                           permitted_catalog(catalog(), scope()), TODAY).spec == requested
    effective = json.loads(client.calls[1]["messages"][1]["content"])["intent"]
    assert effective["period"] == spec().to_dict()["period"] and effective["missing"] == []


def test_new_request_does_not_inherit_unrelated_current_period():
    requested = spec(dimension_ids=("unit",), chart="table")
    agent, _ = provider(intent(requested, period=None, turn_kind="new"),
                        planned(question="بازه گزارش جدید چیست؟"), APPROVED)
    assert agent.interpret((Message("user", "گزارش جدید ساعات واحدها"),), spec(),
                           permitted_catalog(catalog(), scope()), TODAY).status == "needs_clarification"


def test_structured_period_drift_is_repaired_without_querying_wrong_dates(database):
    requested = spec(dimension_ids=("unit",))
    wrong = replace(requested, period=PeriodSelection("all"))
    agent, client = provider(intent(requested), planned(wrong), planned(requested), APPROVED)
    sdk = engine(database, agent)
    session = sdk.create_session(ACTOR)
    reply = sdk.submit(session.session_id, "ساعات ماه قبل به تفکیک واحد", ACTOR, "dates", 0)
    assert reply.status == "report_ready" and len(sdk.database.calls) == 1
    assert json.loads(client.calls[2]["messages"][1]["content"])["feedback"] == [
        "intent_validation: period_mismatch"]


def test_rolling_period_and_equivalent_explicit_bounds_match():
    requested = spec(period=PeriodSelection("rolling", count=3, unit="month"))
    equivalent = replace(requested, period=PeriodSelection("range", start="2026-07-08", end="2026-10-09"))
    agent, _ = provider(intent(requested), planned(equivalent), APPROVED)
    assert agent.interpret((Message("user", "سه ماه گذشته"),), None,
                           permitted_catalog(catalog(), scope()), TODAY).spec == equivalent


def test_unspecified_period_does_not_require_dates_for_dimension_listing():
    requested = ReportSpec("activities", (), dimension_ids=("unit",))
    agent, _ = provider(intent(requested, period=None), planned(requested), APPROVED)
    assert agent.interpret((Message("user", "واحدها را فهرست کن"),), None,
                           permitted_catalog(catalog(), scope()), TODAY).spec == requested


def test_paraphrased_repeated_missing_detail_stops_after_persistent_restart(database, tmp_path):
    path = tmp_path / "sessions.sqlite"
    first_agent, _ = provider(intent(missing=("year",)), planned(question="کدام سال؟"), APPROVED)
    sdk = engine(database, first_agent, sessions=SQLiteSessionStore(path))
    session = sdk.create_session(ACTOR)
    first = sdk.submit(session.session_id, "ساعات ماه سپتامبر", ACTOR, "first", 0)
    assert first.status == "needs_clarification"
    second_agent, client = provider(intent(missing=("year",), turn_kind="answer"),
                                    planned(question="لطفاً سال گزارش را مشخص کنید؟"), APPROVED)
    resumed = engine(database, second_agent, sessions=SQLiteSessionStore(path))
    reply = resumed.submit(session.session_id, "۲۰۲۶", ACTOR, "year", 1)
    assert reply.error["code"] == "clarification_stalled" and not reply.error["retryable"]
    assert reply.revision == 1 and resumed.database.calls == []
    assert resumed.get_session(session.session_id, ACTOR)["clarification"] == first.text
    retry = resumed.submit(session.session_id, "۲۰۲۶", ACTOR, "year", 1)
    assert retry.to_dict() == reply.to_dict() and len(client.calls) == 3


def test_successive_missing_details_and_new_request_with_same_slot_remain_allowed(database):
    agent, _ = provider(
        intent(missing=("year",)), planned(question="کدام سال؟"), APPROVED,
        intent(missing=("calendar",), turn_kind="answer"), planned(question="کدام تقویم؟"), APPROVED,
        intent(missing=("calendar",), turn_kind="new"), planned(question="برای گزارش جدید کدام تقویم؟"), APPROVED,
        intent(turn_kind="answer"), planned(), APPROVED,
    )
    sdk = engine(database, agent)
    session = sdk.create_session(ACTOR)
    for index, text in enumerate(("سپتامبر", "۲۰۲۶", "گزارش جدیدی برای تقویم نامشخص", "میلادی")):
        reply = sdk.submit(session.session_id, text, ACTOR, str(index), index)
        assert reply.status == ("report_ready" if index == 3 else "needs_clarification"), reply.to_dict()
    assert sdk.sessions.get(session.session_id, (ACTOR.subject, ACTOR.tenant_id))["pending_clarification_key"] is None


def test_upgrade_handles_old_pending_unsupported_technical_confirmation(database):
    legacy = SimpleNamespace(interpret=lambda *args: Interpretation(
        "needs_clarification", question="برای جمع ساعات بر اساس سمت، منابع را ترکیب کنم؟"))
    sdk = engine(database, legacy)
    session = sdk.create_session(ACTOR)
    assert sdk.submit(session.session_id, "ساعات بر اساس سمت", ACTOR, "old", 0).status == "needs_clarification"
    cross = intent(turn_kind="answer", dimensions=(ConceptRef("employees", "job_position"),))
    sdk.provider, client = provider(cross)
    reply = sdk.submit(session.session_id, "اره همینکار کن", ACTOR, "answer", 1)
    assert reply.status == "unsupported" and sdk.database.calls == [] and len(client.calls) == 1
    assert sdk.get_session(session.session_id, ACTOR)["clarification"] is None


def test_alternating_clarification_cycle_is_also_blocked(database):
    agent, _ = provider(
        intent(missing=("year",)), planned(question="کدام سال؟"), APPROVED,
        intent(missing=("calendar",), turn_kind="answer"), planned(question="کدام تقویم؟"), APPROVED,
        intent(missing=("year",), turn_kind="answer"), planned(question="سال گزارش را بگویید؟"), APPROVED,
    )
    sdk = engine(database, agent)
    session = sdk.create_session(ACTOR)
    for index, text in enumerate(("سپتامبر", "۲۰۲۶", "میلادی")):
        reply = sdk.submit(session.session_id, text, ACTOR, str(index), index)
    assert reply.error["code"] == "clarification_stalled" and reply.revision == 2
    assert sdk.database.calls == []


def test_count_only_permitted_catalog_works_through_all_three_stages():
    table = Table("synthetic_count")
    registered = ReportingCatalog((DatasetDefinition(
        "counts", "شمارش", table, (Column(table.key, "policy_only", "int"),),
        metrics=(MetricDefinition("count", "تعداد", "count_rows"),)),))
    visible = permitted_catalog(registered, AccessScope((DatasetAccess("counts"),)))
    request = ReportSpec("counts", ("count",))
    agent, client = provider(ReportIntent(metrics=(ConceptRef("counts", "count"),)), planned(request), APPROVED)
    assert agent.interpret((Message("user", "تعداد را بگو"),), None, visible, TODAY).spec == request
    assert len(client.calls) == 3


@pytest.mark.parametrize("value", [
    ReportIntent(), intent(metrics=(ConceptRef("unknown", "hours"),)),
    intent(dimensions=(ConceptRef("activities", "job_position"),)),
    intent(missing=("permission_to_join",)), intent(missing=("year", "year")),
    intent(turn_kind="run_sql"), intent(chart="pie"), intent(time_grain="jalali_month"),
    intent(metrics=(ConceptRef("activities", "hours"),) * 2),
    intent(unsupported_reason="x" * 2001), intent(missing=["year"]),
    intent(period="all"), intent(period=PeriodSelection("unsupported")),
    intent(period=PeriodSelection("rolling", count=True, unit="month")),
    intent(period=PeriodSelection("range", start="2026-07-01", end="invalid")),
])
def test_invalid_intent_fails_closed(value):
    with pytest.raises(SDKError) as error:
        check_intent(value, catalog(), today=TODAY)
    assert error.value.code == "invalid_interpretation"


def test_public_intent_serialization_cannot_mutate_frozen_references():
    value = intent()
    payload = value.to_dict()
    payload["metrics"][0]["concept_id"] = "changed"
    assert value.metrics[0].concept_id == "hours"


@pytest.mark.parametrize("raw", [
    "", "{}", "null", '{"metrics":[],"metrics":[]}',
    json.dumps({**intent().to_dict(), "sql": "SELECT anything"}),
    json.dumps({**intent().to_dict(), "metrics": [{"dataset_id": "employees", "concept_id": "hours"}]}),
    json.dumps({**intent().to_dict(), "missing": None}),
    json.dumps({**intent().to_dict(), "dimensions": [None]}),
    json.dumps({**intent().to_dict(), "period": {"kind": "all"}}),
    json.dumps({**intent().to_dict(), "period": {**intent().to_dict()["period"], "sql": "SELECT anything"}}),
])
def test_malformed_intent_has_no_planning_review_or_execution(raw):
    agent, client = provider(raw)
    with pytest.raises(SDKError) as error:
        agent.interpret((Message("user", "report"),), None, permitted_catalog(catalog(), scope()), TODAY)
    assert error.value.code == "invalid_interpretation" and len(client.calls) == 1


def test_all_three_remote_stages_use_only_permitted_business_context():
    agent, client = provider(intent(), planned(), APPROVED)
    agent.interpret((Message("user", "ساعات کارکنان ماه گذشته"),), spec(),
                    permitted_catalog(catalog(), scope()), TODAY)
    assert [call["response_format"]["json_schema"]["name"] for call in client.calls] == [
        "sageql_report_intent", "sageql_report_interpretation", "sageql_report_review"]
    for call in client.calls:
        payload = json.loads(call["messages"][1]["content"])
        assert "rows" not in payload and "results" not in payload
        assert call["response_format"]["json_schema"]["strict"]
        for forbidden in ("synthetic_", "worker_key", "profile_key", "policy_tenant", "fake-key", "Synthetic Alpha"):
            assert forbidden not in call["messages"][1]["content"]
        assert "ONE registered fact dataset" in call["messages"][0]["content"]


def test_intent_stage_consumes_same_deadline_as_plan_and_review(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("sageql.sdk.agents.time.monotonic", lambda: clock[0])

    class Backend:
        budgets = []

        def understand(self, *args, timeout_seconds):
            self.budgets.append(timeout_seconds)
            clock[0] += 4
            return intent()

        def plan(self, *args, timeout_seconds, **kwargs):
            self.budgets.append(timeout_seconds)
            clock[0] += 3
            return Interpretation("ready", spec())

        def review(self, *args, timeout_seconds, **kwargs):
            self.budgets.append(timeout_seconds)
            return AgentReview(True)

    backend = Backend()
    result = AgentReportInterpreter(backend, timeout_seconds=12).interpret(
        (Message("user", "report"),), None, permitted_catalog(catalog(), scope()), TODAY)
    assert result.status == "ready" and backend.budgets == [12, 8, 5]


def test_intent_timeout_never_starts_planning(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("sageql.sdk.agents.time.monotonic", lambda: clock[0])
    backend = SimpleNamespace(plan=lambda *a, **k: pytest.fail("expired planning"),
                              review=lambda *a, **k: pytest.fail("expired review"))

    def understand(*args, **kwargs):
        clock[0] += 12
        return intent()

    backend.understand = understand
    with pytest.raises(SDKError) as error:
        AgentReportInterpreter(backend, timeout_seconds=12).interpret(
            (Message("user", "report"),), None, permitted_catalog(catalog(), scope()), TODAY)
    assert error.value.code == "request_timeout"


def test_intent_transport_failure_is_sanitized_without_retry():
    agent, client = provider(RuntimeError("private endpoint secret"))
    with pytest.raises(SDKError) as error:
        agent.interpret((Message("user", "report"),), None, permitted_catalog(catalog(), scope()), TODAY)
    assert error.value.code == "provider_failed" and "private" not in str(error.value)
    assert len(client.calls) == 1


def managerial_catalog():
    registered = catalog()
    work = replace(registered.datasets[0],
                   metrics=(*registered.datasets[0].metrics,
                            MetricDefinition("activity_count", "تعداد فعالیت‌ها", "count_rows")),
                   filters=(FilterDefinition("unit_filter", "واحد کاری", "unit_name"),))
    return replace(registered, datasets=(work, registered.datasets[1]))


def managerial_spec(**changes):
    return spec(chart="table", metric_ids=("hours", "activity_count"), dimension_ids=("worker_name", "unit"),
                period=PeriodSelection("jalali_month", year=1405, month=6),
                comparison=PeriodSelection("jalali_month", year=1405, month=5),
                filters=(UserFilter("unit_filter", "eq", ("A",)),),
                aggregate_filters=(AggregateFilter("hours", "gt", (2,)),),
                limit=10, **changes)


def controlled_intent(request):
    return intent(request, comparison=request.comparison, comparison_specified=True,
                  filters=request.filters, aggregate_filters=request.aggregate_filters,
                  order_by=request.order_by, ordering_specified=True,
                  descending=request.descending, limit=request.limit)


@pytest.mark.parametrize("changes,feedback", [
    ({"comparison": None}, "comparison_mismatch"),
    ({"comparison": PeriodSelection("jalali_month", year=1405, month=4)}, "comparison_mismatch"),
    ({"filters": ()}, "filter_mismatch"),
    ({"filters": (UserFilter("unit_filter", "eq", ("B",)),)}, "filter_mismatch"),
    ({"aggregate_filters": ()}, "aggregate_filter_mismatch"),
    ({"aggregate_filters": (AggregateFilter("hours", "gte", (2,)),)}, "aggregate_filter_mismatch"),
    ({"order_by": None}, "ordering_mismatch"),
    ({"order_by": "activity_count"}, "ordering_mismatch"),
    ({"descending": False}, "ordering_mismatch"),
    ({"limit": 100}, "limit_mismatch"),
    ({"metric_ids": ("hours",)}, "report_mismatch"),
    ({"dimension_ids": ("worker_name",)}, "report_mismatch"),
])
def test_managerial_controls_are_repaired_before_an_approving_reviewer(changes, feedback):
    requested = managerial_spec()
    wrong = replace(requested, **changes)
    agent, client = provider(controlled_intent(requested), planned(wrong), planned(requested), APPROVED)
    decision = agent.interpret((Message("user", "مقایسه شهریور و مرداد ۱۴۰۵ به تفکیک واحد؛ فقط جمع ساعات بیشتر از ۲"),),
                               None, permitted_catalog(managerial_catalog(), scope()), TODAY)
    assert decision.spec == requested
    payloads = [json.loads(call["messages"][1]["content"]) for call in client.calls]
    assert payloads[2]["feedback"] == ["intent_validation: " + feedback]
    assert len(client.calls) == 4  # Intent, rejected plan, repaired plan, one review.
    assert payloads[3]["candidate"]["spec"] == requested.to_dict()


def test_explicit_control_removal_cannot_preserve_old_comparison_filters_or_ordering():
    previous = managerial_spec()
    requested = replace(previous, comparison=None, filters=(), aggregate_filters=(),
                        order_by=None, descending=False)
    agent, client = provider(replace(controlled_intent(requested), turn_kind="refine"),
                             planned(previous), planned(requested), APPROVED)
    assert agent.interpret((Message("user", "مقایسه و فیلتر و مرتب‌سازی را حذف کن"),), previous,
                           permitted_catalog(managerial_catalog(), scope()), TODAY).spec == requested
    assert json.loads(client.calls[2]["messages"][1]["content"])["feedback"] == [
        "intent_validation: comparison_mismatch"]


def test_legacy_optional_controls_do_not_constrain_an_unspecified_request():
    requested = managerial_spec()
    assert intent_feedback(intent(requested), Interpretation("ready", requested), today=TODAY) is None


@pytest.mark.parametrize("changes", [
    {"comparison": None}, {"filters": ()}, {"aggregate_filters": ()},
    {"descending": False}, {"limit": 100},
])
def test_exhausted_managerial_control_repair_cannot_execute(database, changes):
    requested = managerial_spec()
    wrong = replace(requested, **changes)
    agent, client = provider(controlled_intent(requested), planned(wrong), planned(wrong), APPROVED)
    sdk = SageQL(catalog=managerial_catalog(), database=Adapter(database), provider=agent,
                 policy=lambda _: scope(), clock=lambda: TODAY, execution="validated")
    session = sdk.create_session(ACTOR)
    reply = sdk.submit(session.session_id, "مقایسه ساعات واحدها، با شرط جمع ساعات", ACTOR, "controls", 0)
    assert reply.error["code"] == "intent_mismatch" and not reply.error["retryable"]
    assert reply.revision == 0 and sdk.database.calls == [] and len(client.calls) == 3


@pytest.mark.parametrize("changes,feedback", [
    ({"comparison": PeriodSelection("jalali_month", year=1405, month=5)}, "comparison_mismatch"),
    ({"filters": (UserFilter("unit_filter", "eq", ("A",)),)}, "filter_mismatch"),
    ({"aggregate_filters": (AggregateFilter("hours", "gt", (2,)),)}, "aggregate_filter_mismatch"),
    ({"order_by": "hours"}, "ordering_mismatch"),
])
def test_explicit_empty_controls_reject_injected_or_preserved_old_controls(changes, feedback):
    requested = replace(managerial_spec(), comparison=None, filters=(), aggregate_filters=(),
                        order_by=None, descending=False)
    assert intent_feedback(controlled_intent(requested), Interpretation("ready", replace(requested, **changes)),
                           today=TODAY, catalog=managerial_catalog()) == "intent_validation: " + feedback


def test_equivalent_predicate_order_in_members_and_numeric_encodings_do_not_require_repair():
    requested = replace(managerial_spec(), filters=(UserFilter("unit_filter", "in", ("A", "B")),),
                        aggregate_filters=(AggregateFilter("hours", "gt", (Decimal("2.00"),)),
                                           AggregateFilter("hours", "lt", (10,))))
    equivalent = replace(requested, filters=(UserFilter("unit_filter", "in", ("B", "A", "A")),),
                         aggregate_filters=(AggregateFilter("hours", "lt", ("10.0",)),
                                            AggregateFilter("hours", "gt", (2,))))
    agent, client = provider(controlled_intent(requested), planned(equivalent), APPROVED)
    assert agent.interpret((Message("user", "واحدهای A و B با جمع ساعات بین دو آستانه"),), None,
                           permitted_catalog(managerial_catalog(), scope()), TODAY).spec == equivalent
    assert len(client.calls) == 3


def test_invalid_candidate_numeric_threshold_yields_safe_fixed_feedback_before_review():
    requested = managerial_spec()
    wrong = replace(requested, aggregate_filters=(AggregateFilter("hours", "gt", ("not-a-number",)),))
    agent, client = provider(controlled_intent(requested), planned(wrong), planned(requested), APPROVED)
    assert agent.interpret((Message("user", "جمع ساعات بیشتر از دو"),), None,
                           permitted_catalog(managerial_catalog(), scope()), TODAY).spec == requested
    assert json.loads(client.calls[2]["messages"][1]["content"])["feedback"] == [
        "intent_validation: aggregate_filter_mismatch"]


@pytest.mark.parametrize("changes", [
    {"comparison": "month"}, {"comparison_specified": "true"},
    {"comparison": PeriodSelection("jalali_month", year=1405, month=5), "comparison_specified": False},
    {"comparison": PeriodSelection("all")},
    {"comparison": PeriodSelection("jalali_month", year=1405, month=13)},
    {"ordering_specified": 1}, {"order_by": "hours", "ordering_specified": False},
    {"order_by": "unregistered"}, {"descending": "true"},
    {"limit": True}, {"limit": 0}, {"limit": 10001},
    {"filters": []}, {"filters": (UserFilter("unknown", "eq", ("A",)),)},
    {"filters": (UserFilter("unit_filter", "like", ("A",)),)},
    {"filters": (UserFilter("unit_filter", "eq", ()),)},
    {"filters": (UserFilter("unit_filter", "eq", ("A", "B")),)},
    {"filters": (UserFilter("unit_filter", "eq", ["A"]),)},
    {"filters": (UserFilter("unit_filter", "eq", ("x" * 1001,)),)},
    {"filters": (UserFilter("unit_filter", "eq", ({"sql": "untrusted"},)),)},
    {"filters": (UserFilter("unit_filter", "eq", ("A",)),) * 2},
    {"aggregate_filters": []},
    {"aggregate_filters": (AggregateFilter("people", "gt", (2,)),)},
    {"aggregate_filters": (AggregateFilter("hours", "unknown", (2,)),)},
    {"aggregate_filters": (AggregateFilter("hours", "gt", (True,)),)},
    {"aggregate_filters": (AggregateFilter("hours", "gt", (float("nan"),)),)},
    {"aggregate_filters": (AggregateFilter("hours", "gt", ("not-numeric",)),)},
    {"aggregate_filters": (AggregateFilter("hours", "gt", (2,)),) * 2},
])
def test_invalid_managerial_intent_controls_fail_closed(changes):
    with pytest.raises(SDKError) as error:
        check_intent(replace(controlled_intent(managerial_spec()), **changes), managerial_catalog(), today=TODAY)
    assert error.value.code == "invalid_interpretation"


@pytest.mark.parametrize("key,value", [
    ("filters", {}), ("filters", [{"filter_id": "unit_filter", "operator": "eq", "values": "A"}]),
    ("aggregate_filters", [{"metric_id": "hours", "operator": "gt", "values": [2], "sql": "SELECT"}]),
    ("comparison", {"kind": "jalali_month", "year": 1405, "month": 5}),
])
def test_malformed_live_control_response_never_starts_planning(key, value):
    payload = {**controlled_intent(managerial_spec()).to_dict(), key: value}
    agent, client = provider(payload)
    with pytest.raises(SDKError) as error:
        agent.interpret((Message("user", "گزارش"),), None,
                        permitted_catalog(managerial_catalog(), scope()), TODAY)
    assert error.value.code == "invalid_interpretation" and len(client.calls) == 1


def test_live_intent_schema_requires_bounded_effective_controls_and_explains_jalali_comparison():
    requested = managerial_spec()
    agent, client = provider(controlled_intent(requested), planned(requested), APPROVED)
    agent.interpret((Message("user", "شهریور ۱۴۰۵ را با مرداد ۱۴۰۵ مقایسه کن"),), None,
                    permitted_catalog(managerial_catalog(), scope()), TODAY)
    schema = client.calls[0]["response_format"]["json_schema"]["schema"]
    required = {"comparison", "comparison_specified", "filters", "aggregate_filters", "order_by",
                "ordering_specified", "descending", "limit"}
    assert required <= set(schema["required"])
    for key in ("filters", "aggregate_filters"):
        definition = schema["properties"][key]["anyOf"][0]
        assert definition["maxItems"] == 32
        assert definition["items"]["properties"]["values"]["maxItems"] == 100
        assert definition["items"]["additionalProperties"] is False
    for call in client.calls:
        assert "Comparing TWO explicit Jalali months is supported" in call["messages"][0]["content"]


def test_hallucinated_unsupported_jalali_comparison_is_reconsidered_by_planner_and_reviewer():
    requested = managerial_spec()
    misunderstood = replace(controlled_intent(requested), unsupported_reason="مقایسه دو ماه شمسی پشتیبانی نمی‌شود")
    agent, client = provider(misunderstood, planned(requested), APPROVED)
    assert agent.interpret((Message("user", "شهریور ۱۴۰۵ را با مرداد ۱۴۰۵ مقایسه کن"),), None,
                           permitted_catalog(managerial_catalog(), scope()), TODAY).spec == requested
    assert len(client.calls) == 3


def test_actual_unregistered_operation_still_returns_reviewed_unsupported():
    unsupported = ReportIntent(unsupported_reason="تفاضل محاسباتی پشتیبانی نمی‌شود")
    candidate = {"status": "unsupported", "spec": None, "question": "", "message": unsupported.unsupported_reason}
    agent, client = provider(unsupported, candidate, APPROVED)
    assert agent.interpret((Message("user", "درصد رشد را محاسبه کن"),), None,
                           permitted_catalog(managerial_catalog(), scope()), TODAY).status == "unsupported"
    assert len(client.calls) == 3
