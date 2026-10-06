"""Product behavior tests: real synthetic reports, sessions and trusted scope."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
import json
import sqlite3
from threading import Event

import pytest

from sageql import Column, Table
from sageql.sdk import (
    AccessScope, ActorContext, DatasetAccess, DatasetDefinition, DimensionDefinition,
    ExecutionLimits, FilterDefinition, InMemorySessionStore, Interpretation, MetricDefinition,
    PeriodSelection, ReportingCatalog, ReportSpec, RowPolicy, SDKError, SageQL,
    SQLiteAdapter, SQLiteSessionStore, TimeDefinition, UserFilter,
)


def catalog():
    table = Table("activities")
    return ReportingCatalog((DatasetDefinition(
        "activities", "Activities", table,
        tuple(Column(table.key, name, kind) for name, kind in (
            ("id", "int"), ("tenant_id", "int"), ("employee", "text"),
            ("activity_date", "date"), ("hours", "decimal"), ("is_deleted", "int"),
        )),
        (MetricDefinition("activity_hours", "Activity hours", "sum", "hours", "hours"),),
        (DimensionDefinition("employee", "Employee", "employee"),),
        (FilterDefinition("employee_filter", "Employee", "employee"),),
        TimeDefinition("activity_date"), row_key=("id",),
    ),))


ACTOR = ActorContext("user-1", "1")


def policy(actor):
    if not actor.tenant_id:
        raise SDKError("access_denied", "Tenant identity is required.")
    return AccessScope((DatasetAccess("activities", policies=(
        RowPolicy("tenant_id", "eq", (int(actor.tenant_id),)),
        RowPolicy("is_deleted", "eq", (0,)),
    )),))


def spec(**changes):
    return replace(ReportSpec("activities", ("activity_hours",), period=PeriodSelection("month", year=2026, month=9),
                              time_grain="day", chart="line"), **changes)


class Provider:
    def __init__(self, *answers):
        self.answers = iter(answers)
        self.calls = []

    def interpret(self, messages, current_spec, allowed, today):
        self.calls.append((messages, current_spec, allowed, today))
        answer = next(self.answers)
        if isinstance(answer, Exception):
            raise answer
        return answer(messages, current_spec) if callable(answer) else answer


class CountingAdapter:
    def __init__(self, adapter):
        self.adapter = adapter
        self.calls = 0
        self.fail = False

    def execute(self, report, limits, *, cancel=None):
        self.calls += 1
        if self.fail:
            raise RuntimeError("secret database password and private row")
        return self.adapter.execute(report, limits, cancel=cancel)


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "reports.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE activities (id INTEGER PRIMARY KEY, tenant_id INTEGER, "
                           "employee TEXT, activity_date DATE, hours DECIMAL, is_deleted INTEGER)")
        connection.executemany("INSERT INTO activities VALUES (?, ?, ?, ?, ?, ?)", [
            (1, 1, "Alice", "2026-09-01", 10, 0),
            (2, 1, "Bob", "2026-09-01", 2.5, 0),
            (3, 1, "Alice", "2026-09-02", 3, 0),
            (4, 2, "Private other tenant", "2026-09-01", 999, 0),
            (5, 1, "Deleted employee", "2026-09-01", 111, 1),
            (6, 1, "Alice", "2026-08-01", 50, 0),
        ])
    return path


def engine(database, provider, **options):
    return SageQL(catalog=catalog(), database=CountingAdapter(SQLiteAdapter(database)),
                  provider=provider, policy=policy, clock=lambda: date(2026, 10, 5),
                  execution="validated", **options)


def test_first_report_enforces_scope_and_lossless_frontend_contract(database):
    provider = Provider(Interpretation("ready", spec()))
    sdk = engine(database, provider)
    session = sdk.create_session(ACTOR)
    reply = sdk.submit(session.session_id, "Show daily hours for September 2026", ACTOR, "r1", 0)
    assert reply.status == "report_ready"
    assert reply.report.rows == ((date(2026, 9, 1), Decimal("12.5")), (date(2026, 9, 2), Decimal("3")))
    payload = json.loads(json.dumps(reply.to_dict(), allow_nan=False))
    assert payload["report"]["fields"][1]["unit"] == "hours"
    assert payload["report"]["rows"][0][1] == "12.5"
    assert payload["report"]["visualization"] == {"kind": "line", "x": "time_bucket", "y": "activity_hours"}
    assert payload["report"]["provenance"]["period_end_exclusive"] == "2026-10-01"
    assert "tenant_id" not in repr(provider.calls[0][2])
    assert "is_deleted" not in repr(provider.calls[0][2])
    assert "Private other tenant" not in json.dumps(payload)


def test_persian_clarification_unicode_filter_persistence_and_retry(database, tmp_path):
    name = "علي‌۱۲"
    with sqlite3.connect(database) as connection:
        connection.executemany("INSERT INTO activities VALUES (?, ?, ?, ?, ?, ?)", [
            (7, 1, name, "2026-09-01", 2.5, 0),
            (8, 1, "علی‌۱۲", "2026-09-01", 20, 0),
            (9, 2, name, "2026-09-01", 999, 0),
        ])
    dataset = replace(catalog().datasets[0], label="فعالیت‌ها",
                      metrics=(MetricDefinition("activity_hours", "ساعات فعالیت", "sum", "hours", "ساعت"),),
                      dimensions=(DimensionDefinition("employee", "کارمند", "employee"),))
    fa_catalog = ReportingCatalog((dataset,))
    filtered = spec(dimension_ids=("employee",), time_grain="none", chart="table",
                    filters=(UserFilter("employee_filter", "eq", (name,)),))
    provider = Provider(Interpretation("needs_clarification", question="کدام سال میلادی را می‌خواهید؟"),
                        Interpretation("ready", spec()), Interpretation("ready", filtered))
    store = SQLiteSessionStore(tmp_path / "persian-sessions.sqlite")
    def configured(provider):
        return SageQL(catalog=fa_catalog, database=SQLiteAdapter(database), provider=provider,
                      policy=policy, sessions=store, execution="validated", clock=lambda: date(2026, 10, 5))
    sdk = configured(provider)
    session = sdk.create_session(ACTOR)
    assert session.text == "چه گزارشی می‌خواهید تهیه کنید؟"
    question = sdk.submit(session.session_id, "ساعات فعالیت روزانه در سپتامبر", ACTOR, "question", 0)
    assert question.clarification == "کدام سال میلادی را می‌خواهید؟"
    daily = sdk.submit(session.session_id, "۲۰۲۶", ACTOR, "year", 1)
    assert daily.report.title == "ساعات فعالیت به تفکیک روز"
    assert daily.report.fields[0].label == "تاریخ"
    request = f"فقط {name} را به تفکیک کارمند نشان بده"
    reply = sdk.submit(session.session_id, request, ACTOR, "refine", 2)
    assert reply.report.title == "ساعات فعالیت به تفکیک کارمند"
    assert reply.report.rows == ((name, Decimal("2.5")),)
    assert reply.to_dict()["report"]["rows"] == [[name, "2.5"]]
    resumed_provider = Provider()
    resumed = configured(resumed_provider)
    assert resumed.get_report(session.session_id, reply.report.id, ACTOR) == reply.report
    assert resumed.submit(session.session_id, request, ACTOR, "refine", 2).to_dict() == reply.to_dict()
    assert resumed_provider.calls == []


def test_english_opt_in_keeps_titles_headers_and_errors(database):
    sdk = engine(database, Provider(Interpretation("ready", spec())), language="en")
    session = sdk.create_session(ACTOR)
    assert session.text == "What report would you like to create?"
    reply = sdk.submit(session.session_id, "daily hours", ACTOR, "r1", 0)
    assert reply.report.title == "Activity hours by day"
    assert reply.report.fields[0].label == "Date"
    denied = sdk.submit(session.session_id, "", ACTOR, "r2", 1)
    assert denied.error["code"] == "invalid_input"
    assert denied.text == "Provide a bounded message, request ID and session revision."
    persian = engine(database, Provider())
    fa_session = persian.create_session(ACTOR)
    assert "متن پرسش" in persian.submit(fa_session.session_id, "", ACTOR, "r1", 0).text
    with pytest.raises(ValueError, match="language"):
        engine(database, Provider(), language="unknown")


def test_distinct_employee_listing_and_activity_followup_use_same_authorized_session(database):
    requested = ReportSpec("activities", (), dimension_ids=("employee",))
    provider = Provider(Interpretation("ready", requested), Interpretation("ready", spec()))
    sdk = engine(database, provider)
    session = sdk.create_session(ACTOR)
    listed = sdk.submit(session.session_id, "Show employee names", ACTOR, "names", 0)
    assert listed.status == "report_ready"
    assert listed.report.title == "Activities: Employee"
    assert listed.report.rows == (("Alice",), ("Bob",))
    assert listed.report.visualization == {"kind": "table"}
    assert listed.report.provenance["report_kind"] == "listing"
    assert listed.report.provenance["metrics"] == []
    retry = sdk.submit(session.session_id, "Show employee names", ACTOR, "names", 0)
    assert retry.to_dict() == listed.to_dict() and sdk.database.calls == 1
    daily = sdk.submit(session.session_id, "Now daily hours for September 2026", ACTOR, "daily", 1)
    assert daily.status == "report_ready" and daily.report.visualization["kind"] == "line"
    assert provider.calls[1][1] == requested


def test_duplicate_request_returns_same_report_without_new_calls(database):
    provider = Provider(Interpretation("ready", spec()))
    sdk = engine(database, provider)
    session = sdk.create_session(ACTOR)
    first = sdk.submit(session.session_id, "daily hours September 2026", ACTOR, "r1", 0)
    again = sdk.submit(session.session_id, "daily hours September 2026", ACTOR, "r1", 0)
    assert again.to_dict() == first.to_dict()
    assert again.report.rows == first.report.rows
    assert sdk.get_report(session.session_id, first.report.id, ACTOR).rows == first.report.rows
    assert len(provider.calls) == sdk.database.calls == 1
    conflict = sdk.submit(session.session_id, "different question", ACTOR, "r1", 0)
    assert conflict.error["code"] == "request_conflict"
    stale = sdk.submit(session.session_id, "a new question", ACTOR, "r2", 0)
    assert stale.error["code"] == "revision_conflict"
    assert sdk.database.calls == 1


def test_pending_clarification_survives_restart_and_preserves_original_question(database, tmp_path):
    store_path = tmp_path / "sessions.sqlite"
    sdk = engine(database, Provider(Interpretation("needs_clarification", question="Which year?")),
                 sessions=SQLiteSessionStore(store_path))
    session = sdk.create_session(ACTOR)
    pending = sdk.submit(session.session_id, "daily hours for September", ACTOR, "r1", 0)
    assert pending.status == "needs_clarification"
    assert sdk.database.calls == 0
    provider = Provider(Interpretation("ready", spec()))
    restarted = engine(database, provider, sessions=SQLiteSessionStore(store_path))
    assert restarted.get_session(session.session_id, ACTOR)["clarification"] == "Which year?"
    reply = restarted.submit(session.session_id, "2026", ACTOR, "r2", 1)
    assert reply.status == "report_ready"
    assert [item.content for item in provider.calls[0][0]] == [
        "daily hours for September", "Which year?", "2026",
    ]


def test_completed_report_refines_after_restart_without_re_resolving_relative_period(database, tmp_path):
    store_path = tmp_path / "sessions.sqlite"
    sdk = engine(database, Provider(Interpretation("ready", spec(period=PeriodSelection("last_month")))),
                 sessions=SQLiteSessionStore(store_path))
    session = sdk.create_session(ACTOR)
    first = sdk.submit(session.session_id, "hours last month", ACTOR, "r1", 0)
    assert first.status == "report_ready"

    def refine(messages, current):
        assert current.period == PeriodSelection("range", "2026-09-01", "2026-10-01")
        return Interpretation("ready", replace(current, dimension_ids=("employee",), time_grain="none", chart="bar"))

    provider = Provider(refine)
    restarted = SageQL(catalog=catalog(), database=SQLiteAdapter(database), provider=provider,
                      policy=policy, sessions=SQLiteSessionStore(store_path),
                      clock=lambda: date(2026, 11, 5), execution="validated")
    second = restarted.submit(session.session_id, "group by employee instead", ACTOR, "r2", 1)
    assert second.status == "report_ready"
    assert second.report.rows == (("Alice", Decimal("13")), ("Bob", Decimal("2.5")))
    assert restarted.get_report(session.session_id, first.report.id, ACTOR).to_dict() == first.report.to_dict()
    assert "12.5" not in str(provider.calls[0][0])  # Result rows are never model context.


def test_failed_provider_and_adapter_preserve_last_successful_report(database):
    provider = Provider(Interpretation("ready", spec()), RuntimeError("secret API key"),
                        Interpretation("ready", spec(dimension_ids=("employee",), chart="table")))
    sdk = engine(database, provider)
    session = sdk.create_session(ACTOR)
    first = sdk.submit(session.session_id, "daily hours", ACTOR, "r1", 0)
    failed = sdk.submit(session.session_id, "group by employee", ACTOR, "r2", 1)
    assert failed.status == "failed" and failed.revision == 1
    assert "secret" not in json.dumps(failed.to_dict())
    sdk.database.fail = True
    failed_query = sdk.submit(session.session_id, "group by employee", ACTOR, "r3", 1)
    assert failed_query.status == "failed" and failed_query.revision == 1
    assert "secret" not in json.dumps(failed_query.to_dict())
    assert sdk.get_session(session.session_id, ACTOR)["last_report_id"] == first.report.id
    assert sdk.get_report(session.session_id, first.report.id, ACTOR).to_dict() == first.report.to_dict()
    state = sdk.sessions.get(session.session_id, (ACTOR.subject, ACTOR.tenant_id))
    assert [item["content"] for item in state["messages"]] == ["daily hours", first.text]


def test_sessions_and_reports_are_owned_and_scope_revocation_blocks_reuse(database):
    sdk = engine(database, Provider(Interpretation("ready", spec())))
    session = sdk.create_session(ACTOR)
    other = ActorContext("user-2", "1")
    denied = sdk.submit(session.session_id, "show hours", other, "r1", 0)
    assert denied.error["code"] == "access_denied"
    assert sdk.database.calls == 0
    first = sdk.submit(session.session_id, "daily hours", ACTOR, "r1", 0)
    with pytest.raises(SDKError, match="unavailable"):
        sdk.get_report(session.session_id, first.report.id, other)
    sdk._policy = lambda actor: AccessScope((DatasetAccess("activities", policies=(
        RowPolicy("tenant_id", "eq", (2,)), RowPolicy("is_deleted", "eq", (0,)),
    )),), version="2")
    denied_cache = sdk.submit(session.session_id, "daily hours", ACTOR, "r1", 0)
    assert denied_cache.error["code"] == "access_denied"
    with pytest.raises(SDKError, match="unavailable"):
        sdk.get_report(session.session_id, first.report.id, ACTOR)


def test_access_changes_during_model_call_block_execution(database):
    changed = False

    def scoped(actor):
        return replace(policy(actor), version="2" if changed else "1")

    def interpret(messages, current):
        nonlocal changed
        changed = True
        return Interpretation("ready", spec())

    sdk = SageQL(catalog=catalog(), database=CountingAdapter(SQLiteAdapter(database)),
                 provider=Provider(interpret), policy=scoped, execution="validated")
    session = sdk.create_session(ACTOR)
    result = sdk.submit(session.session_id, "hours", ACTOR, "r1", 0)
    assert result.error["code"] == "access_denied"
    assert sdk.database.calls == 0


def test_denied_metric_and_unknown_policy_fail_before_database_and_remote_calls(database):
    sdk = engine(database, Provider(Interpretation("ready", spec(metric_ids=("private_salary",)))))
    session = sdk.create_session(ACTOR)
    result = sdk.submit(session.session_id, "show salary", ACTOR, "r1", 0)
    assert result.status == "blocked"
    assert sdk.database.calls == 0
    sdk._policy = lambda actor: AccessScope((DatasetAccess("activities", policies=(RowPolicy("missing", "eq", (1,)),)),))
    with pytest.raises(SDKError):
        sdk.create_session(ACTOR)


def test_execution_requires_explicit_host_opt_in(database):
    sdk = SageQL(catalog=catalog(), database=CountingAdapter(SQLiteAdapter(database)),
                 provider=Provider(Interpretation("ready", spec())), policy=policy)
    session = sdk.create_session(ACTOR)
    reply = sdk.submit(session.session_id, "hours", ACTOR, "r1", 0)
    assert reply.error["code"] == "execution_disabled"
    assert sdk.database.calls == 0


def test_precancelled_request_does_not_call_provider_or_adapter(database):
    provider = Provider()
    sdk = engine(database, provider)
    session = sdk.create_session(ACTOR)
    cancel = Event()
    cancel.set()
    reply = sdk.submit(session.session_id, "hours", ACTOR, "r1", 0, cancel=cancel)
    assert reply.error["code"] == "cancelled"
    assert provider.calls == [] and sdk.database.calls == 0


def test_malformed_cancel_is_rejected_before_threads_or_remote_calls(database):
    provider = Provider()
    sdk = engine(database, provider)
    session = sdk.create_session(ACTOR)
    reply = sdk.submit(session.session_id, "hours", ACTOR, "r1", 0, cancel=object())
    assert reply.error["code"] == "invalid_input"
    assert provider.calls == [] and sdk.database.calls == 0


def test_empty_and_truncated_reports_are_explicit(database):
    provider = Provider(Interpretation("ready", spec(period=PeriodSelection("year", year=2000))),
                        Interpretation("ready", spec(limit=1)))
    sdk = engine(database, provider)
    session = sdk.create_session(ACTOR)
    empty = sdk.submit(session.session_id, "hours in 2000", ACTOR, "r1", 0)
    assert empty.report.rows == ()
    assert empty.report.provenance["completeness"] == "empty"
    truncated = sdk.submit(session.session_id, "September hours", ACTOR, "r2", 1)
    assert len(truncated.report.rows) == 1
    assert truncated.report.truncated
    assert truncated.report.provenance["completeness"] == "truncated"


def test_decimal_user_filter_survives_saved_spec_roundtrip(database, tmp_path):
    original = catalog()
    dataset = replace(original.datasets[0], filters=(*original.datasets[0].filters,
                                                   FilterDefinition("min_hours", "Minimum hours", "hours", ("gte",))))
    registration = replace(original, datasets=(dataset,))
    requested = spec(filters=(UserFilter("min_hours", "gte", (Decimal("3.00"),)),))
    provider = Provider(Interpretation("ready", requested))
    sdk = SageQL(catalog=registration, database=SQLiteAdapter(database), provider=provider,
                 policy=policy, sessions=SQLiteSessionStore(tmp_path / "state.sqlite"),
                 execution="validated", clock=lambda: date(2026, 10, 5))
    session = sdk.create_session(ACTOR)
    first = sdk.submit(session.session_id, "at least three hours", ACTOR, "r1", 0)
    assert first.status == "report_ready"
    assert sdk.get_report(session.session_id, first.report.id, ACTOR).to_dict() == first.report.to_dict()


def test_short_history_budget_includes_latest_message(database):
    provider = Provider(Interpretation("needs_clarification", question="Which period?"),
                        Interpretation("ready", spec()))
    sdk = engine(database, provider, limits=ExecutionLimits(max_history_messages=3))
    session = sdk.create_session(ACTOR)
    sdk.submit(session.session_id, "hours", ACTOR, "r1", 0)
    reply = sdk.submit(session.session_id, "September 2026", ACTOR, "r2", 1)
    assert reply.status == "report_ready"
    assert len(provider.calls[1][0]) == 3


def test_minimum_history_retains_original_request_across_clarifications(database):
    provider = Provider(Interpretation("needs_clarification", question="Which year?"),
                        Interpretation("needs_clarification", question="Table or chart?"),
                        Interpretation("ready", spec()))
    sdk = engine(database, provider, limits=ExecutionLimits(max_history_messages=3))
    session = sdk.create_session(ACTOR)
    sdk.submit(session.session_id, "daily hours for September", ACTOR, "r1", 0)
    sdk.submit(session.session_id, "2026", ACTOR, "r2", 1)
    sdk.submit(session.session_id, "line chart", ACTOR, "r3", 2)
    messages = provider.calls[2][0]
    assert "daily hours for September" in messages[0].content
    assert "Which year?" in messages[0].content and "2026" in messages[0].content
    assert [item.content for item in messages[1:]] == ["Table or chart?", "line chart"]


@pytest.mark.parametrize("size", [0, 1, 2, 41, True])
def test_history_limits_fit_provider_and_clarification_contract(size):
    with pytest.raises(ValueError):
        ExecutionLimits(max_history_messages=size)


@pytest.mark.parametrize("decision", [
    Interpretation("needs_clarification", question="Which employee should be included?"),
    Interpretation("unsupported", message="The previous reporting vocabulary cannot answer this question."),
])
def test_access_revoked_during_nonexecution_interpretation_never_publishes_a_turn(database, decision):
    changed = False

    def scoped(actor):
        return replace(policy(actor), version="revoked" if changed else "initial")

    def interpret(messages, current):
        nonlocal changed
        changed = True
        return decision

    sdk = SageQL(catalog=catalog(), database=CountingAdapter(SQLiteAdapter(database)),
                 provider=Provider(interpret), policy=scoped, execution="validated")
    session = sdk.create_session(ACTOR)
    reply = sdk.submit(session.session_id, "show employee activity", ACTOR, "r1", 0)

    assert reply.error["code"] == "access_denied"
    assert reply.revision == 0
    assert reply.clarification is None and reply.report is None
    assert sdk.database.calls == 0
    state = sdk.sessions.get(session.session_id, (ACTOR.subject, ACTOR.tenant_id))
    assert state["messages"] == []
    assert state["pending_question"] is None
    assert state["revision"] == 0


def test_provider_failure_recovers_from_claim_even_if_session_reads_are_unavailable(database):
    class UnavailableReads(InMemorySessionStore):
        def get(self, session_id, owner):
            raise SDKError("storage_failed", "Session reads are unavailable.", retryable=True)

    store = UnavailableReads()
    sdk = engine(database, Provider(RuntimeError("secret endpoint credential")), sessions=store)
    session = sdk.create_session(ACTOR)
    reply = sdk.submit(session.session_id, "daily hours", ACTOR, "r1", 0)

    assert reply.status == "failed"
    assert reply.error["code"] == "provider_failed"
    assert reply.revision == 0
    assert "secret" not in json.dumps(reply.to_dict())
    # A provider failure needs only its original claimed snapshot for recovery.
    state = InMemorySessionStore.get(store, session.session_id, (ACTOR.subject, ACTOR.tenant_id))
    assert state["messages"] == [] and state["inflight"] is None
    assert state["receipts"]["r1"]["reply"]["error"]["code"] == "provider_failed"


def test_unexpected_store_completion_error_returns_safe_retryable_reply(database):
    class BrokenCompletion(InMemorySessionStore):
        def complete(self, claim, state, reply):
            raise RuntimeError("secret driver connection string")

    sdk = engine(database, Provider(Interpretation("ready", spec())), sessions=BrokenCompletion())
    session = sdk.create_session(ACTOR)
    reply = sdk.submit(session.session_id, "daily hours", ACTOR, "r1", 0)

    assert reply.status == "failed"
    assert reply.error["retryable"] is True
    assert reply.report is None and reply.revision == 0
    assert "secret" not in json.dumps(reply.to_dict())


def test_store_claim_failure_is_sanitized_before_provider_call(database):
    class BrokenClaim(InMemorySessionStore):
        def claim(self, *args, **kwargs):
            raise RuntimeError("secret database credential")

    provider = Provider()
    sdk = engine(database, provider, sessions=BrokenClaim())
    session = sdk.create_session(ACTOR)
    reply = sdk.submit(session.session_id, "hours", ACTOR, "r1", 0)
    assert reply.error["code"] == "storage_failed"
    assert "secret" not in json.dumps(reply.to_dict()) and provider.calls == []


def test_corrupt_cached_reply_returns_safe_error_without_reexecuting(database):
    class CorruptReply(InMemorySessionStore):
        def claim(self, *args, **kwargs):
            return replace(super().claim(*args, **kwargs), cached_reply={"bad": "secret"})

    provider = Provider()
    sdk = engine(database, provider, sessions=CorruptReply())
    session = sdk.create_session(ACTOR)
    reply = sdk.submit(session.session_id, "hours", ACTOR, "r1", 0)
    assert reply.error["code"] == "storage_failed"
    assert "secret" not in json.dumps(reply.to_dict()) and provider.calls == []


def test_non_utc_date_configuration_requires_an_explicit_business_clock(database):
    original = catalog()
    registration = replace(original, datasets=(replace(original.datasets[0],
                                                       time=TimeDefinition("activity_date", timezone="Asia/Tehran")),))
    with pytest.raises((SDKError, ValueError), match="[Cc]lock"):
        SageQL(catalog=registration, database=SQLiteAdapter(database), provider=Provider(),
               policy=policy, execution="validated")

    provider = Provider(Interpretation("ready", spec(period=PeriodSelection("today"))))
    sdk = SageQL(catalog=registration, database=SQLiteAdapter(database), provider=provider,
                 policy=policy, execution="validated", clock=lambda: date(2026, 9, 1))
    session = sdk.create_session(ACTOR)
    reply = sdk.submit(session.session_id, "daily hours today", ACTOR, "r1", 0)

    assert reply.status == "report_ready"
    assert provider.calls[0][3] == date(2026, 9, 1)
    assert reply.report.provenance["period_start"] == "2026-09-01"
    assert reply.report.rows == ((date(2026, 9, 1), Decimal("12.5")),)
