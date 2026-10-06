"""Bounded report agents use permitted concepts and never execute model SQL."""

from dataclasses import FrozenInstanceError, replace
from datetime import date
from decimal import Decimal
import json
import sqlite3
from types import SimpleNamespace

import pytest

from sageql import Column, LLMConfig, Message, Table
from sageql.sdk import (
    AccessScope, ActorContext, DatasetAccess, DatasetDefinition, DimensionDefinition,
    EntityLookupDefinition, FilterDefinition, FullNameFilterDefinition,
    Interpretation, MetricDefinition, PeriodSelection,
    ReportingCatalog, ReportSpec, RowPolicy, SDKError, SageQL, SQLiteAdapter,
    SQLiteSessionStore, TimeDefinition, UserFilter,
)
from sageql.sdk.agents import AgentReportInterpreter, AgentReview, OpenAIReportAgent
from sageql.sdk.semantics import permitted_catalog


TODAY = date(2026, 10, 6)
ACTOR = ActorContext("sales-reader", "7")
MESSAGES = (Message("user", "فروش روزانه سپتامبر ۲۰۲۶ را نمایش بده"),)


def catalog():
    table = Table("private_sales_source")
    return ReportingCatalog((DatasetDefinition(
        "sales", "فروش", table,
        tuple(Column(table.key, name, kind) for name, kind in (
            ("private_tenant", "int"), ("private_sale_date", "date"),
            ("private_amount", "decimal"), ("private_category", "text"),
            ("private_deleted", "int"),
        )),
        (MetricDefinition("revenue", "مبلغ فروش", "sum", "private_amount", "ریال"),),
        (DimensionDefinition("category", "گروه کالا", "private_category"),),
        (FilterDefinition("category_filter", "گروه کالا", "private_category"),),
        TimeDefinition("private_sale_date"), row_key=("private_tenant",),
    ),))


def spec(**changes):
    return replace(ReportSpec(
        "sales", ("revenue",), period=PeriodSelection("month", year=2026, month=9),
        time_grain="day", chart="table",
    ), **changes)


def ready(report=None):
    return Interpretation("ready", spec() if report is None else report,
                          message="گزارش فروش روزانه.")


class Backend:
    """Script decisions while recording exactly what crosses each stage."""

    def __init__(self, plans, reviews):
        self.plans = iter(plans)
        self.reviews = iter(reviews)
        self.calls = []

    def plan(self, messages, current_spec, allowed, today, *, feedback, timeout_seconds):
        self.calls.append({"stage": "plan", "messages": messages, "current_spec": current_spec,
                           "catalog": allowed, "today": today, "feedback": feedback,
                           "timeout_seconds": timeout_seconds})
        answer = next(self.plans)
        if isinstance(answer, Exception):
            raise answer
        return answer() if callable(answer) else answer

    def review(self, messages, current_spec, allowed, today, decision, *, timeout_seconds):
        self.calls.append({"stage": "review", "messages": messages, "current_spec": current_spec,
                           "catalog": allowed, "today": today, "decision": decision,
                           "timeout_seconds": timeout_seconds})
        answer = next(self.reviews)
        if isinstance(answer, Exception):
            raise answer
        return answer() if callable(answer) else answer


def interpret(backend, *, messages=MESSAGES, current=None, **options):
    return AgentReportInterpreter(backend, **options).interpret(messages, current, catalog(), TODAY)


def test_agents_plan_and_review_generic_registered_business_concepts():
    decision = ready()
    backend = Backend([decision], [AgentReview(True)])

    assert interpret(backend) == decision

    assert [call["stage"] for call in backend.calls] == ["plan", "review"]
    assert backend.calls[0]["feedback"] == ()
    assert backend.calls[1]["decision"] == decision
    for call in backend.calls:
        assert call["messages"] == MESSAGES and call["today"] == TODAY
        assert call["current_spec"] is None and call["catalog"] == catalog()
        assert 0 < call["timeout_seconds"] <= 30


@pytest.mark.parametrize("question", [
    "می‌توانم برای شروع سراغ گزارش فروش بروم؟",
    "Would you prefer that I construct the supported report first?",
    "Soll ich den registrierten Bericht erstellen?",
])
def test_review_can_replace_unnecessary_questions_without_phrase_matching(question):
    feedback = "The requested period and measure are already present; produce the report."
    backend = Backend(
        [Interpretation("needs_clarification", question=question), ready()],
        [AgentReview(False, feedback), AgentReview(True)],
    )

    result = interpret(backend)

    assert result == ready()
    assert [call["stage"] for call in backend.calls] == ["plan", "review", "plan", "review"]
    assert backend.calls[2]["feedback"] == (feedback,)
    assert all(call["messages"] == MESSAGES for call in backend.calls)


@pytest.mark.parametrize("decision", [
    Interpretation("needs_clarification", question="سپتامبر کدام سال؟"),
    Interpretation("unsupported", message="محاسبه سود در مفاهیم مجاز ثبت نشده است."),
])
def test_review_approved_missing_detail_or_unsupported_request_remains_incomplete(decision):
    backend = Backend([decision], [AgentReview(True)])
    assert interpret(backend) == decision
    assert len(backend.calls) == 2


@pytest.mark.parametrize("invalid,error_code", [
    (ready(spec(period=PeriodSelection("range", "private-date-value", "2026-10-01"))), "invalid_spec"),
    (ready(spec(chart="kpi")), "unsupported"),
])
def test_semantic_spec_error_is_repaired_with_code_only_feedback_before_review(invalid, error_code):
    backend = Backend([invalid, ready()], [AgentReview(True)])

    assert interpret(backend) == ready()

    assert [call["stage"] for call in backend.calls] == ["plan", "plan", "review"]
    feedback = backend.calls[1]["feedback"]
    assert isinstance(feedback, tuple) and len(feedback) == 1
    assert feedback == ("specification_validation: " + error_code,)
    assert "private-date-value" not in feedback[0]
    assert "private_" not in feedback[0]


@pytest.mark.parametrize("invalid", [
    None, {"status": "ready", "spec": "SELECT secret"},
    Interpretation("run_sql", message="SELECT secret"),
    Interpretation("ready"),
    Interpretation("ready", spec(), question="Which year?"),
    Interpretation("ready", spec(), question="   "),
    Interpretation("needs_clarification", spec(), question="Which year?"),
    Interpretation("needs_clarification"),
    Interpretation("unsupported", message=""),
    Interpretation("unsupported", question="   ", message="Unavailable calculation."),
    ready(spec(dataset_id="unregistered_private_source")),
    ready(spec(metric_ids=("private_metric",))),
    ready(spec(dimension_ids=("private_tenant",))),
    ready(spec(filters=(UserFilter("unknown", "eq", ("private-value",)),))),
])
def test_invalid_planner_objects_or_concepts_fail_without_review_or_replan(invalid):
    backend = Backend([invalid], [])

    with pytest.raises(SDKError) as error:
        interpret(backend)

    assert error.value.code == "invalid_interpretation"
    assert "secret" not in str(error.value) and "private" not in str(error.value)
    assert [call["stage"] for call in backend.calls] == ["plan"]


@pytest.mark.parametrize("invalid", [
    None, {"approved": True, "feedback": ""},
    AgentReview(1), AgentReview(True, "change the report"), AgentReview(True, "   "),
    AgentReview(False), AgentReview(False, "   "),
    AgentReview(False, "x" * 2001), AgentReview(False, 42),
])
def test_invalid_reviewer_outputs_fail_without_replan(invalid):
    backend = Backend([ready()], [invalid])

    with pytest.raises(SDKError) as error:
        interpret(backend)

    assert error.value.code == "invalid_interpretation"
    assert len(backend.calls) == 2


def test_review_contract_is_immutable():
    review = AgentReview(False, "Use the supported measure.")
    with pytest.raises(FrozenInstanceError):
        review.approved = True


def test_revision_budget_ends_rejection_without_extra_planning():
    backend = Backend([ready(), ready()], [AgentReview(False, "Check the intent again.")] * 2)

    with pytest.raises(SDKError) as error:
        interpret(backend, max_revisions=1)

    assert error.value.code == "agent_exhausted"
    assert error.value.retryable
    assert [call["stage"] for call in backend.calls] == ["plan", "review", "plan", "review"]


def test_zero_revision_budget_still_reviews_once_and_rejects():
    backend = Backend([ready()], [AgentReview(False, "Use the requested grouping.")])
    with pytest.raises(SDKError) as error:
        interpret(backend, max_revisions=0)
    assert error.value.code == "agent_exhausted" and len(backend.calls) == 2


def test_all_stages_share_one_original_timeout(monkeypatch):
    ticks = [100.0]
    monkeypatch.setattr("sageql.sdk.agents.time.monotonic", lambda: ticks[0])

    def planned():
        ticks[0] += 8
        return ready()

    def rejected():
        ticks[0] += 1
        return AgentReview(False, "Use the intended grouping.")

    def revised():
        ticks[0] += 1
        return ready()

    backend = Backend([planned, revised], [rejected, AgentReview(True)])
    assert interpret(backend, timeout_seconds=12) == ready()
    assert [call["timeout_seconds"] for call in backend.calls] == [12, 4, 3, 2]


def test_expired_planning_deadline_does_not_start_review(monkeypatch):
    ticks = [100.0]
    monkeypatch.setattr("sageql.sdk.agents.time.monotonic", lambda: ticks[0])

    def delayed():
        ticks[0] += 12
        return ready()

    backend = Backend([delayed], [])
    with pytest.raises(SDKError) as error:
        interpret(backend, timeout_seconds=12)
    assert error.value.code == "request_timeout" and error.value.retryable
    assert len(backend.calls) == 1


def test_expired_review_deadline_does_not_publish_an_approved_decision(monkeypatch):
    ticks = [100.0]
    monkeypatch.setattr("sageql.sdk.agents.time.monotonic", lambda: ticks[0])

    def delayed_review():
        ticks[0] += 12
        return AgentReview(True)

    backend = Backend([ready()], [delayed_review])
    with pytest.raises(SDKError) as error:
        interpret(backend, timeout_seconds=12)
    assert error.value.code == "request_timeout" and error.value.retryable
    assert len(backend.calls) == 2


@pytest.mark.parametrize("stage", ["plan", "review"])
def test_unexpected_backend_failure_is_sanitized_and_not_retried(stage):
    failure = RuntimeError("private database password and model output")
    backend = Backend([failure if stage == "plan" else ready()],
                      [failure] if stage == "review" else [])
    with pytest.raises(SDKError) as error:
        interpret(backend)
    assert error.value.code == "provider_failed" and error.value.retryable
    assert "private" not in str(error.value)
    assert len(backend.calls) == (1 if stage == "plan" else 2)


def test_safe_backend_sdk_error_keeps_its_code_without_retries():
    failure = SDKError("provider_unavailable", "Configured model is unavailable.", retryable=True)
    backend = Backend([failure], [])
    with pytest.raises(SDKError) as error:
        interpret(backend)
    assert error.value.code == failure.code and error.value.retryable
    assert len(backend.calls) == 1


@pytest.mark.parametrize("stage", ["plan", "review"])
@pytest.mark.parametrize("safe_exception", [False, True])
def test_expired_stage_error_returns_shared_timeout_before_provider_failure(
    monkeypatch, stage, safe_exception,
):
    ticks = [100.0]
    monkeypatch.setattr("sageql.sdk.agents.time.monotonic", lambda: ticks[0])

    def failed():
        ticks[0] += 12
        if safe_exception:
            raise SDKError("provider_failed", "The configured provider failed.", retryable=True)
        raise RuntimeError("private endpoint key and response")

    backend = Backend([failed if stage == "plan" else ready()],
                      [failed] if stage == "review" else [])
    with pytest.raises(SDKError) as error:
        interpret(backend, timeout_seconds=12)
    assert error.value.code == "request_timeout" and error.value.retryable
    assert "private" not in str(error.value)
    assert len(backend.calls) == (1 if stage == "plan" else 2)


@pytest.mark.parametrize("options", [
    {"timeout_seconds": True}, {"timeout_seconds": 0}, {"timeout_seconds": float("nan")},
    {"timeout_seconds": float("inf")}, {"timeout_seconds": 181},
    {"max_revisions": True}, {"max_revisions": -1}, {"max_revisions": 1.5},
    {"max_revisions": 4},
])
def test_agent_runtime_bounds_reject_invalid_configuration(options):
    with pytest.raises(ValueError):
        AgentReportInterpreter(Backend([], []), **options)


class FakeClient:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.calls = []
        self.options = None
        self.chat = SimpleNamespace(completions=self)

    def with_options(self, **options):
        self.options = options
        return self

    def create(self, **options):
        self.calls.append(options)
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        content = response if isinstance(response, str) else json.dumps(response, ensure_ascii=False)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def plan_json(decision=None):
    decision = ready() if decision is None else decision
    return {"status": decision.status, "spec": decision.spec.to_dict() if decision.spec else None,
            "question": decision.question, "message": decision.message}


def remote(*responses, **options):
    client = FakeClient(*responses)
    provider = OpenAIReportAgent(
        LLMConfig("private-api-key", "https://example.test/v1", "configured-model"),
        client=client, **options,
    )
    return provider, client


def test_remote_agent_uses_strict_planner_reviewer_shapes_and_permitted_payloads():
    provider, client = remote(plan_json(), {"approved": True, "feedback": ""},
                              timeout_seconds=12, max_output_tokens=3072)
    assert provider.interpret(MESSAGES, None, catalog(), TODAY) == ready()

    assert client.options == {"timeout": 12, "max_retries": 0}
    assert len(client.calls) == 2
    plan, review = [json.loads(call["messages"][1]["content"]) for call in client.calls]
    assert plan["feedback"] == []
    assert review["candidate"] == plan_json()
    for call, payload in zip(client.calls, (plan, review)):
        assert call["model"] == "configured-model" and call["max_completion_tokens"] == 3072
        assert call["response_format"]["json_schema"]["strict"] is True
        assert 0 < call["timeout"] <= 12
        assert payload["conversation"] == [{"role": "user", "text": MESSAGES[0].content}]
        assert payload["today"] == TODAY.isoformat() and payload["current_spec"] is None
        serialized = json.dumps(payload, ensure_ascii=False)
        assert "مبلغ فروش" in serialized and "گروه کالا" in serialized
        for hidden in ("private_api", "private-api-key", "private_sales_source", "private_tenant",
                       "private_amount", "private_sale_date", "private_category", "private_deleted",
                       "row_key", "policies"):
            assert hidden not in serialized
        assert "rows" not in payload and "results" not in payload
    review_schema = client.calls[1]["response_format"]["json_schema"]["schema"]
    assert set(review_schema["properties"]) == {"approved", "feedback"}
    assert review_schema["additionalProperties"] is False


def test_remote_agent_replans_from_semantic_review_with_unchanged_original_context():
    incomplete = Interpretation("unsupported", message="این درخواست پشتیبانی نمی‌شود.")
    feedback = "Registered revenue supports this request; produce its daily table."
    provider, client = remote(
        plan_json(incomplete), {"approved": False, "feedback": feedback},
        plan_json(), {"approved": True, "feedback": ""},
    )

    assert provider.interpret(MESSAGES, None, catalog(), TODAY) == ready()

    payloads = [json.loads(call["messages"][1]["content"]) for call in client.calls]
    assert payloads[2]["feedback"] == [feedback]
    for payload in payloads:
        assert payload["catalog"] == payloads[0]["catalog"]
        assert payload["conversation"] == payloads[0]["conversation"]


@pytest.mark.parametrize("response", [
    "not JSON", "[]",
    '{"approved":true,"feedback":"","sql":"SELECT secret"}',
    '{"approved":true,"feedback":"","approved":false}',
    '{"approved":1,"feedback":""}',
    '{"approved":true,"feedback":"private correction"}',
    '{"approved":true,"feedback":"   "}',
    '{"approved":false,"feedback":""}',
    '{"approved":false,"feedback":NaN}',
])
def test_remote_reviewer_malformed_output_fails_closed_without_replan(response):
    provider, client = remote(plan_json(), response)
    with pytest.raises(SDKError) as error:
        provider.interpret(MESSAGES, None, catalog(), TODAY)
    assert error.value.code == "invalid_interpretation"
    assert "secret" not in str(error.value) and "private" not in str(error.value)
    assert len(client.calls) == 2


def test_remote_planner_model_sql_never_reaches_review():
    provider, client = remote({**plan_json(), "sql": "SELECT private_source"})
    with pytest.raises(SDKError) as error:
        provider.interpret(MESSAGES, None, catalog(), TODAY)
    assert error.value.code == "invalid_interpretation"
    assert len(client.calls) == 1 and "private_source" not in str(error.value)


def test_remote_reviewer_failure_is_sanitized_without_transport_retry():
    provider, client = remote(plan_json(), RuntimeError("private endpoint key and response"))
    with pytest.raises(SDKError) as error:
        provider.interpret(MESSAGES, None, catalog(), TODAY)
    assert error.value.code == "provider_failed" and error.value.retryable
    assert "private" not in str(error.value) and len(client.calls) == 2


def policy(actor):
    return AccessScope((DatasetAccess("sales", policies=(
        RowPolicy("private_tenant", "eq", (int(actor.tenant_id),)),
        RowPolicy("private_deleted", "eq", (0,)),
    )),), version="sales-policy-v1")


class CountingAdapter:
    def __init__(self, path):
        self.adapter = SQLiteAdapter(path)
        self.calls = []

    def execute(self, report, limits, *, cancel=None):
        self.calls.append(report)
        return self.adapter.execute(report, limits, cancel=cancel)


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "synthetic-sales.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE private_sales_source (private_tenant INTEGER NOT NULL, private_sale_date DATE, "
            "private_amount DECIMAL, private_category TEXT, private_deleted INTEGER)"
        )
        connection.executemany("INSERT INTO private_sales_source VALUES (?, ?, ?, ?, ?)", [
            (7, "2026-09-02", 12.5, "books", 0), (7, "2026-09-02", 2, "books", 0),
            (8, "2026-09-02", 900, "other-tenant", 0),
            (7, "2026-09-02", 800, "deleted", 1),
            (7, "2026-08-02", 700, "outside-period", 0),
        ])
    return path


def engine(database, provider, **options):
    return SageQL(catalog=catalog(), database=CountingAdapter(database), provider=provider,
                  policy=options.pop("policy", policy), clock=lambda: TODAY,
                  execution=options.pop("execution", "validated"), **options)


def test_agent_report_executes_only_registered_policy_bound_query_and_retry_is_cached(database):
    provider, client = remote(plan_json(), {"approved": True, "feedback": ""})
    sdk = engine(database, provider)
    session = sdk.create_session(ACTOR)

    reply = sdk.submit(session.session_id, MESSAGES[0].content, ACTOR, "sales-report", 0)

    assert reply.status == "report_ready", reply.to_dict()
    assert reply.report.rows == ((date(2026, 9, 2), Decimal("14.5")),)
    assert len(client.calls) == 2 and len(sdk.database.calls) == 1
    assert sdk.database.calls[0].access.policies == policy(ACTOR).datasets[0].policies
    retry = sdk.submit(session.session_id, MESSAGES[0].content, ACTOR, "sales-report", 0)
    assert retry.to_dict() == reply.to_dict()
    assert len(client.calls) == 2 and len(sdk.database.calls) == 1
    for call in client.calls:
        payload = json.loads(call["messages"][1]["content"])
        assert "14.5" not in json.dumps(payload) and "other-tenant" not in json.dumps(payload)
        assert "policies" not in payload and "rows" not in payload


def test_agent_approval_does_not_enable_host_disabled_execution(database):
    backend = Backend([ready()], [AgentReview(True)])
    sdk = engine(database, AgentReportInterpreter(backend), execution="disabled")
    session = sdk.create_session(ACTOR)

    reply = sdk.submit(session.session_id, "فروش روزانه سپتامبر ۲۰۲۶", ACTOR, "no-execution", 0)

    assert reply.error["code"] == "execution_disabled"
    assert sdk.database.calls == []


def test_access_revoked_during_agent_review_blocks_execution(database):
    current = [policy(ACTOR)]

    def revoked():
        current[0] = replace(current[0], version="revoked")
        return AgentReview(True)

    backend = Backend([ready()], [revoked])
    sdk = engine(database, AgentReportInterpreter(backend), policy=lambda actor: current[0])
    session = sdk.create_session(ACTOR)

    reply = sdk.submit(session.session_id, "فروش سپتامبر ۲۰۲۶", ACTOR, "revocation", 0)

    assert reply.error["code"] == "access_denied"
    assert sdk.database.calls == [] and len(backend.calls) == 2


def count_registration():
    registered = replace(catalog().datasets[0],
                         metrics=(MetricDefinition("sales_count", "تعداد فروش", "count_rows"),),
                         time=None)
    scope = replace(policy(ACTOR), datasets=(replace(
        policy(ACTOR).datasets[0], metric_ids=("sales_count",), dimension_ids=(), filter_ids=(),
    ),))
    return ReportingCatalog((registered,)), scope


def test_permitted_timeless_count_only_projection_is_valid_without_hidden_columns():
    registered, scope = count_registration()
    visible = permitted_catalog(registered, scope)
    assert visible.datasets[0].columns == ()
    assert visible.datasets[0].dimensions == () and visible.datasets[0].filters == ()
    decision = ready(ReportSpec("sales", ("sales_count",)))
    provider, client = remote(plan_json(decision), {"approved": True, "feedback": ""})

    assert provider.interpret(MESSAGES, None, visible, TODAY) == decision

    for call in client.calls:
        serialized = call["messages"][1]["content"]
        assert "sales_count" in serialized and "private_" not in serialized
        assert "category" not in serialized and "policies" not in serialized


def test_agent_count_only_report_retains_real_host_policies_and_hides_denied_concepts(database):
    registered, scope = count_registration()
    decision = ready(ReportSpec("sales", ("sales_count",)))
    provider, client = remote(plan_json(decision), {"approved": True, "feedback": ""})
    sdk = SageQL(catalog=registered, database=CountingAdapter(database), provider=provider,
                 policy=lambda actor: scope, clock=lambda: TODAY, execution="validated")
    session = sdk.create_session(ACTOR)

    reply = sdk.submit(session.session_id, "تعداد فروش‌ها", ACTOR, "count", 0)

    assert reply.status == "report_ready", reply.to_dict()
    assert reply.report.rows == ((3,),)
    assert len(sdk.database.calls) == 1 and len(client.calls) == 2
    assert sdk.database.calls[0].access.policies == scope.datasets[0].policies
    for call in client.calls:
        serialized = call["messages"][1]["content"]
        assert "private_" not in serialized and "category" not in serialized
        payload = json.loads(serialized)
        assert "rows" not in payload and "results" not in payload and "policies" not in payload


def test_saved_agent_report_refines_after_restart_with_frozen_period(database, tmp_path):
    store = tmp_path / "report-sessions.sqlite"
    initial = spec(period=PeriodSelection("last_month"))
    backend = Backend([ready(initial)], [AgentReview(True)])
    sdk = engine(database, AgentReportInterpreter(backend), sessions=SQLiteSessionStore(store))
    session = sdk.create_session(ACTOR)
    first = sdk.submit(session.session_id, "فروش ماه قبل", ACTOR, "first", 0)
    assert first.status == "report_ready"

    grouped = spec(dimension_ids=("category",), time_grain="none")
    backend = Backend([ready(grouped)], [AgentReview(True)])
    resumed = engine(database, AgentReportInterpreter(backend), sessions=SQLiteSessionStore(store))
    assert resumed.get_report(session.session_id, first.report.id, ACTOR) == first.report
    second = resumed.submit(session.session_id, "بر اساس گروه کالا", ACTOR, "grouped", 1)

    assert second.status == "report_ready"
    assert second.report.rows == (("books", Decimal("14.5")),)
    assert backend.calls[0]["current_spec"].period == PeriodSelection(
        "range", "2026-09-01", "2026-10-01"
    )
    assert backend.calls[1]["current_spec"] == backend.calls[0]["current_spec"]
    assert all("14.5" not in str(call["messages"]) for call in backend.calls)


def typed_filter_catalog(column):
    registration = catalog()
    dataset = registration.datasets[0]
    return replace(registration, datasets=(replace(
        dataset, filters=(*dataset.filters,
                          FilterDefinition("typed_filter", "Minimum selection", column, ("gte",))),
    ),))


@pytest.mark.parametrize("column,value", [
    ("private_amount", Decimal("3.00")),
    ("private_sale_date", date(2026, 9, 2)),
])
def test_custom_backend_plan_preserves_supported_sdk_typed_filter_scalars(column, value):
    decision = ready(spec(filters=(UserFilter("typed_filter", "gte", (value,)),)))
    backend = Backend([decision], [AgentReview(True)])
    provider = AgentReportInterpreter(backend)

    result = provider.interpret(MESSAGES, None, typed_filter_catalog(column), TODAY)

    assert result is decision
    assert type(result.spec.filters[0].values[0]) is type(value)
    assert backend.calls[1]["decision"] is decision


@pytest.mark.parametrize("column,value", [
    ("private_amount", Decimal("3.00")),
    ("private_sale_date", date(2026, 9, 2)),
])
@pytest.mark.parametrize("agent_kind", ["custom_backend", "openai_transport"])
def test_agent_refines_typed_filter_report_saved_by_previous_provider(
    database, tmp_path, column, value, agent_kind,
):
    registration = typed_filter_catalog(column)
    requested = spec(filters=(UserFilter("typed_filter", "gte", (value,)),))
    store = tmp_path / "typed-filter-sessions.sqlite"

    class PreviousProvider:
        def interpret(self, messages, current_spec, allowed, today):
            return ready(requested)

    original = SageQL(
        catalog=registration, database=CountingAdapter(database), provider=PreviousProvider(),
        policy=policy, sessions=SQLiteSessionStore(store), clock=lambda: TODAY,
        execution="validated",
    )
    session = original.create_session(ACTOR)
    first = original.submit(session.session_id, "Minimum selection for September 2026", ACTOR, "first", 0)
    assert first.status == "report_ready", first.to_dict()

    frozen_period = PeriodSelection("range", "2026-09-01", "2026-10-01")
    grouped = replace(requested, dimension_ids=("category",), time_grain="none", period=frozen_period)
    if agent_kind == "custom_backend":
        backend = Backend([ready(grouped)], [AgentReview(True)])
        provider = AgentReportInterpreter(backend)
    else:
        provider, client = remote(plan_json(ready(grouped)), {"approved": True, "feedback": ""})
    resumed = SageQL(
        catalog=registration, database=CountingAdapter(database), provider=provider,
        policy=policy, sessions=SQLiteSessionStore(store), clock=lambda: TODAY,
        execution="validated",
    )

    second = resumed.submit(session.session_id, "Group the report by category", ACTOR, "grouped", 1)

    assert second.status == "report_ready", second.to_dict()
    assert second.revision == 2
    expected_amount = Decimal("12.5") if isinstance(value, Decimal) else Decimal("14.5")
    assert second.report.rows == (("books", expected_amount),)
    assert len(resumed.database.calls) == 1
    if agent_kind == "custom_backend":
        for call in backend.calls:
            current = call["current_spec"]
            assert current.period == frozen_period
            assert current.filters[0].values == (value,)
            assert type(current.filters[0].values[0]) is type(value)
    else:
        assert len(client.calls) == 2
        for call in client.calls:
            payload = json.loads(call["messages"][1]["content"])
            assert payload["current_spec"]["period"] == grouped.to_dict()["period"]
            assert payload["current_spec"]["filters"][0]["values"] == [str(value)]
            assert "private_" not in call["messages"][1]["content"]


def test_remote_agent_name_lookup_and_refinement_keep_identity_and_rows_local(tmp_path):
    path = tmp_path / "synthetic-name-reports.sqlite"
    person_name = "کیان نمونه پور"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE private_orders (private_tenant INTEGER, "
                           "private_deleted INTEGER, private_person INTEGER, "
                           "private_day DATE, private_value DECIMAL)")
        connection.execute("CREATE TABLE private_people (private_tenant INTEGER, "
                           "private_deleted INTEGER, private_identity INTEGER, "
                           "private_given TEXT, private_surname TEXT)")
        connection.executemany("INSERT INTO private_people VALUES (?, ?, ?, ?, ?)", [
            (7, 0, 101, "کیان", "نمونه پور"), (7, 0, 101, "کیان", "نمونه پور"),
            (8, 0, 202, "کیان", "نمونه پور"), (7, 1, 303, "کیان", "نمونه پور"),
        ])
        connection.executemany("INSERT INTO private_orders VALUES (?, ?, ?, ?, ?)", [
            (7, 0, 101, "2026-09-02", 4), (7, 0, 101, "2026-09-02", 2.5),
            (8, 0, 101, "2026-09-02", 900), (7, 1, 101, "2026-09-02", 800),
            (7, 0, 404, "2026-09-02", 700), (7, 0, 101, "2026-08-02", 600),
        ])
    target_table, source_table = Table("private_orders"), Table("private_people")
    target = DatasetDefinition(
        "orders", "فروش", target_table,
        tuple(Column(target_table.key, name, kind) for name, kind in (
            ("private_tenant", "int"), ("private_deleted", "int"),
            ("private_person", "int"), ("private_day", "date"), ("private_value", "decimal"),
        )),
        (MetricDefinition("revenue", "مبلغ فروش", "sum", "private_value"),),
        filters=(FilterDefinition("person_filter", "کارمند", "private_person"),),
        time=TimeDefinition("private_day"),
    )
    source = DatasetDefinition(
        "people", "کارکنان", source_table,
        tuple(Column(source_table.key, name, kind) for name, kind in (
            ("private_tenant", "int"), ("private_deleted", "int"),
            ("private_identity", "int"), ("private_given", "text"), ("private_surname", "text"),
        )), metrics=(), dimensions=(DimensionDefinition("person", "کارمند", "private_identity"),),
        filters=(FullNameFilterDefinition(
            "full_name", "نام کامل", "private_given", ("eq",), ("private_given", "private_surname"),
        ),),
    )
    registered = ReportingCatalog((target, source), lookups=(EntityLookupDefinition(
        "person_name", "نام کامل کارمند", "orders", "person_filter", "people", "person", "full_name",
    ),))
    scope = AccessScope(tuple(DatasetAccess(dataset.id, policies=(
        RowPolicy("private_tenant", "eq", (7,)), RowPolicy("private_deleted", "eq", (0,)),
    )) for dataset in registered.datasets))
    named_spec = ReportSpec(
        "orders", ("revenue",), filters=(UserFilter("person_name", "eq", (person_name,)),),
        period=PeriodSelection("month", year=2026, month=9), time_grain="day",
    )
    total_spec = replace(named_spec, time_grain="none")
    provider, client = remote(
        plan_json(ready(named_spec)), {"approved": True, "feedback": ""},
        plan_json(ready(total_spec)), {"approved": True, "feedback": ""},
    )
    sdk = SageQL(catalog=registered, database=CountingAdapter(path), provider=provider,
                 policy=lambda actor: scope, clock=lambda: TODAY, execution="validated")
    session = sdk.create_session(ACTOR)

    first = sdk.submit(session.session_id, f"فروش روزانه {person_name} در سپتامبر ۲۰۲۶",
                       ACTOR, "named", 0)
    assert first.status == "report_ready", first.to_dict()
    assert first.report.rows == ((date(2026, 9, 2), Decimal("6.5")),)
    second = sdk.submit(session.session_id, "مجموع همان فروش‌ها را نمایش بده", ACTOR, "total", 1)

    assert second.status == "report_ready", second.to_dict()
    assert second.report.rows == ((Decimal("6.5"),),)
    assert [report.dataset.id for report in sdk.database.calls] == ["people", "orders"] * 2
    by_dataset = {access.dataset_id: access for access in scope.datasets}
    for index, report in enumerate(sdk.database.calls):
        assert report.access.policies == by_dataset[report.dataset.id].policies
        if index % 2 == 0:
            assert report.spec.dimension_ids == ("person",) and report.spec.limit == 2
            assert report.spec.filters == (UserFilter("full_name", "eq", (person_name,)),)
        else:
            assert report.spec.filters == (UserFilter("person_filter", "eq", (101,)),)
    assert len(client.calls) == 4
    for call in client.calls:
        serialized = call["messages"][1]["content"]
        payload = json.loads(serialized)
        assert person_name in serialized
        assert "private_" not in serialized and "101" not in serialized and "6.5" not in serialized
        assert "source_id_dimension_id" not in serialized and "policies" not in serialized
        assert "rows" not in payload and "results" not in payload
    for call in client.calls[2:]:
        context = json.loads(call["messages"][1]["content"])["current_spec"]
        assert context["filters"] == [{"filter_id": "person_name", "operator": "eq", "values": [person_name]}]
        assert context["period"]["kind"] == "range"
