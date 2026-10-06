"""Name-based activity reports use policy-bound reads without joins or row leakage."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
import json
import sqlite3
from threading import Event
from types import SimpleNamespace

import pytest

from sageql import Column, Table
from sageql.conversation import LLMConfig
from sageql.sdk import (
    AccessScope, ActorContext, AdapterResult, DatasetAccess, DatasetDefinition,
    DimensionDefinition, EntityLookupDefinition, ExecutionLimits, FilterDefinition,
    FullNameFilterDefinition, Interpretation, LookupQualifier, MetricDefinition,
    PeriodSelection, ReportField, ReportingCatalog, ReportSpec, RowPolicy, SDKError,
    SageQL, SQLiteAdapter, SQLiteSessionStore, TimeDefinition, UserFilter,
)
from sageql.sdk.adapters import compile_report
from sageql.sdk.lookups import prepare_request
from sageql.sdk.provider import OpenAIReportInterpreter, _format, _metadata
from sageql.sdk.semantics import permitted_catalog, validate_catalog


ACTOR = ActorContext("synthetic-user", "1")
NAME = "کیان نمونه پور"


def catalog():
    activity, profile = Table("activity"), Table("profile")
    return ReportingCatalog((
        DatasetDefinition("activities", "فعالیت‌ها", activity,
            tuple(Column(activity.key, name, kind) for name, kind in (
                ("tenant", "int"), ("deleted", "int"), ("person_id", "int"),
                ("date", "date"), ("hours", "decimal"))),
            metrics=(MetricDefinition("hours", "ساعات فعالیت", "sum", "hours", "ساعت"),
                     MetricDefinition("count", "تعداد فعالیت‌ها", "count_rows")),
            filters=(FilterDefinition("person_filter", "کارمند", "person_id"),),
            time=TimeDefinition("date")),
        DatasetDefinition("profiles", "کارکنان", profile,
            tuple(Column(profile.key, name, kind) for name, kind in (
                ("tenant", "int"), ("deleted", "int"), ("person_id", "int"),
                ("given", "nvarchar"), ("surname", "nvarchar"), ("job", "nvarchar"))),
            metrics=(), dimensions=(DimensionDefinition("person", "کارمند", "person_id"),),
            filters=(FullNameFilterDefinition("full_name", "نام کامل", "given", ("eq",), ("given", "surname")),
                     FilterDefinition("job", "سمت", "job"))),
    ), lookups=(EntityLookupDefinition("person_name", "نام کامل کارمند", "activities", "person_filter",
                                      "profiles", "person", "full_name",
                                      (LookupQualifier("person_job", "سمت شغلی", "job"),)),))


def scope():
    return AccessScope(tuple(DatasetAccess(identifier, policies=(
        RowPolicy("tenant", "eq", (1,)), RowPolicy("deleted", "eq", (0,)),
    )) for identifier in ("activities", "profiles")))


def request(name=NAME, job=None):
    conditions = [UserFilter("person_name", "eq", (name,))]
    if job is not None:
        conditions.append(UserFilter("person_job", "eq", (job,)))
    return ReportSpec("activities", ("hours", "count"), filters=tuple(conditions),
                      period=PeriodSelection("last_month"), time_grain="day")


class Provider:
    def __init__(self, *decisions):
        self.decisions = iter(decisions)
        self.calls = []

    def interpret(self, messages, current, allowed, today):
        self.calls.append((messages, current, allowed, today))
        return next(self.decisions)


class Adapter:
    def __init__(self, path):
        self.database = SQLiteAdapter(path)
        self.calls = []
        self.after_read = lambda: None

    def execute(self, report, limits, *, cancel=None):
        self.calls.append(report)
        result = self.database.execute(report, limits, cancel=cancel)
        self.after_read()
        return result


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "names.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE profile (tenant INT, deleted INT, person_id INT, given NVARCHAR, surname NVARCHAR, job NVARCHAR)")
        connection.execute("CREATE TABLE activity (tenant INT, deleted INT, person_id INT, date DATE, hours DECIMAL)")
        connection.executemany("INSERT INTO profile VALUES (?, ?, ?, ?, ?, ?)", [
            (1, 0, 101, "کیان", "نمونه‌پور", "مهندس"),
            (1, 0, 101, "کیان", "نمونه‌پور", "مهندس"),  # Duplicate profiles, same identity.
            (2, 0, 202, "کیان", "نمونه‌پور", "مهندس"),
            (1, 1, 303, "کیان", "نمونه‌پور", "مهندس"),
            (1, 0, 404, "کارمند", "آزمایشی", "مدیر"),
        ])
        connection.executemany("INSERT INTO activity VALUES (?, ?, ?, ?, ?)", [
            (1, 0, 101, "2026-09-02", 4), (1, 0, 101, "2026-09-02", 2.5),
            (1, 0, 101, "2026-08-02", 9), (1, 0, 404, "2026-09-02", 99),
            (2, 0, 101, "2026-09-02", 999), (1, 1, 101, "2026-09-02", 888),
        ])
    return path


def engine(database, provider, *, policies=None, **options):
    return SageQL(catalog=catalog(), database=Adapter(database), provider=provider,
                  policy=policies or (lambda actor: scope()), execution=options.pop("execution", "validated"),
                  clock=lambda: date(2026, 10, 6), **options)


class SequencedClient:
    """Exercise the real interpreter boundary without a network connection."""

    def __init__(self, *responses):
        self.responses = iter(responses)
        self.calls = []
        self.chat = SimpleNamespace(completions=self)

    def with_options(self, **options):
        return self

    def create(self, **options):
        self.calls.append(options)
        content = json.dumps(next(self.responses), ensure_ascii=False)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def remote_provider(*responses):
    client = SequencedClient(*responses)
    provider = OpenAIReportInterpreter(LLMConfig("synthetic-key", "https://example.test/v1", "fake-model"),
                                       client=client, timeout_seconds=12)
    return provider, client


def clarification_output(question):
    return {"status": "needs_clarification", "spec": None, "question": question, "message": ""}


def ready_output(spec):
    return {"status": "ready", "spec": spec.to_dict(), "question": "", "message": "گزارش فعالیت آماده است."}


def assert_private_model_payloads(client):
    payloads = [json.loads(call["messages"][1]["content"]) for call in client.calls]
    for payload in payloads:
        serialized = json.dumps(payload, ensure_ascii=False)
        assert NAME in serialized
        assert "101" not in serialized and "6.5" not in serialized
        assert "person_id" not in serialized and "synthetic-key" not in serialized
        assert "rows" not in payload and "results" not in payload
        assert payload["current_spec"] is None
    return payloads


@pytest.mark.parametrize("question", [
    f"لطفاً شناسه کارمند {NAME} را ارائه دهید تا گزارش فعالیت‌های ماه قبل را بسازم.",
    f"آیا می‌خواهید با جست‌وجو بر اساس نام «{NAME}» شناسه کارمند را پیدا کنم؟",
])
def test_real_interpreter_repairs_name_lookup_clarification_before_bounded_reads(database, question):
    provider, client = remote_provider(clarification_output(question), ready_output(request()))
    sdk = engine(database, provider)
    session = sdk.create_session(ACTOR)
    origin = f"فعالیت‌های ماه قبل {NAME} را بفرست"

    reply = sdk.submit(session.session_id, origin, ACTOR, "named", 0)

    assert reply.status == "report_ready", reply.to_dict()
    assert reply.revision == 1 and reply.session_id == session.session_id
    assert reply.report.rows == ((date(2026, 9, 2), Decimal("6.5"), 2),)
    assert reply.report.provenance["filters"] == [
        {"filter_id": "person_name", "operator": "eq", "values": [NAME]},
    ]
    assert [item.dataset.id for item in sdk.database.calls] == ["profiles", "activities"]
    assert sdk.database.calls[0].spec.filters == (UserFilter("full_name", "eq", (NAME,)),)
    assert sdk.database.calls[1].spec.filters == (UserFilter("person_filter", "eq", (101,)),)
    assert len(client.calls) == 2
    payloads = assert_private_model_payloads(client)
    assert payloads[0] == payloads[1]

    repeated = sdk.submit(session.session_id, origin, ACTOR, "named", 0)
    assert repeated.to_dict() == reply.to_dict()
    assert len(client.calls) == 2 and len(sdk.database.calls) == 2


def test_real_interpreter_repeated_identity_question_fails_without_database_reads(database):
    provider, client = remote_provider(
        clarification_output(f"شناسه کارمند {NAME} چیست؟"),
        clarification_output(f"آیا می‌خواهید با نام {NAME} شناسه کارمند را جست‌وجو کنم؟"),
    )
    sdk = engine(database, provider)
    session = sdk.create_session(ACTOR)

    reply = sdk.submit(session.session_id, f"فعالیت‌های ماه قبل {NAME} را بفرست", ACTOR, "stalled", 0)

    assert reply.status == "failed", reply.to_dict()
    assert reply.error == {"code": "clarification_stalled", "retryable": True}
    assert reply.revision == 0 and reply.report is None and reply.clarification is None
    assert "شناسه کارمند" not in reply.text and "آیا می‌خواهید" not in reply.text
    assert any("\u0600" <= character <= "\u06ff" for character in reply.text)
    assert len(client.calls) == 2 and sdk.database.calls == []
    payloads = assert_private_model_payloads(client)
    assert payloads[0] == payloads[1]
    assert sdk.get_session(session.session_id, ACTOR)["clarification"] is None


def test_real_interpreter_repairs_lookup_after_year_answer_in_same_session(database):
    requested = replace(request(), period=PeriodSelection("month", year=2026, month=9))
    provider, client = remote_provider(
        clarification_output("گزارش سپتامبر کدام سال را می‌خواهید؟"),
        clarification_output(f"لطفاً شناسه کارمند {NAME} را بفرستید."),
        ready_output(requested),
    )
    sdk = engine(database, provider)
    session = sdk.create_session(ACTOR)
    origin = f"فعالیت‌های روزانه {NAME} در سپتامبر را بفرست"

    first = sdk.submit(session.session_id, origin, ACTOR, "month", 0)

    assert first.status == "needs_clarification" and first.revision == 1
    assert len(client.calls) == 1 and sdk.database.calls == []

    reply = sdk.submit(session.session_id, "۲۰۲۶", ACTOR, "year", 1)

    assert reply.status == "report_ready", reply.to_dict()
    assert reply.session_id == session.session_id and reply.revision == 2
    assert reply.report.rows == ((date(2026, 9, 2), Decimal("6.5"), 2),)
    assert reply.report.provenance["period_start"] == "2026-09-01"
    assert reply.report.provenance["period_end_exclusive"] == "2026-10-01"
    assert len(client.calls) == 3
    assert [item.dataset.id for item in sdk.database.calls] == ["profiles", "activities"]
    payloads = assert_private_model_payloads(client)
    assert payloads[1] == payloads[2]
    conversation = payloads[2]["conversation"]
    assert {"role": "user", "text": origin} in conversation
    assert {"role": "assistant", "text": first.clarification} in conversation
    assert conversation[-1] == {"role": "user", "text": "۲۰۲۶"}
    assert sdk.get_session(session.session_id, ACTOR)["clarification"] is None


@pytest.mark.parametrize("name", [NAME, "كيان نمونه پور", "کیان نمونه‌پور", "کیان\tنمونه\u00a0پور"])
def test_unique_name_resolves_locally_and_duplicate_profiles_do_not_multiply_totals(database, name):
    provider = Provider(Interpretation("ready", request(name)))
    sdk = engine(database, provider)
    session = sdk.create_session(ACTOR)
    reply = sdk.submit(session.session_id, "اطلاعات فعالیت روزانه این کارمند در ماه گذشته", ACTOR, "first", 0)
    assert reply.status == "report_ready"
    assert reply.report.rows == ((date(2026, 9, 2), Decimal("6.5"), 2),)
    assert [item.dataset.id for item in sdk.database.calls] == ["profiles", "activities"]
    assert sdk.database.calls[1].spec.filters == (UserFilter("person_filter", "eq", (101,)),)
    assert reply.report.provenance["filters"] == [{"filter_id": "person_name", "operator": "eq", "values": [name]}]
    for report in sdk.database.calls:
        query = compile_report(report, sdk.limits, dialect="tsql")
        assert "JOIN" not in query.sql
        assert "tenant" in query.sql and "deleted" in query.sql
        assert name not in query.sql
    assert "101" not in str(provider.calls)


def test_ambiguous_name_asks_for_job_and_answer_preserves_original_request(database):
    with sqlite3.connect(database) as connection:
        connection.execute("INSERT INTO profile VALUES (?, ?, ?, ?, ?, ?)", (1, 0, 505, "کیان", "نمونه پور", "مدیر"))
    provider = Provider(Interpretation("ready", request()), Interpretation("ready", request(job="مهندس")))
    sdk = engine(database, provider)
    session = sdk.create_session(ACTOR)
    origin = f"تمام اطلاعات فعالیت‌های روزانه {NAME} در ماه گذشته"
    first = sdk.submit(session.session_id, origin, ACTOR, "first", 0)
    assert first.status == "needs_clarification"
    assert "سمت شغلی" in first.text
    assert len(sdk.database.calls) == 1 and first.report is None
    assert "101" not in first.text and "505" not in first.text
    second = sdk.submit(session.session_id, "مهندس", ACTOR, "job", 1)
    assert second.status == "report_ready"
    assert second.report.rows == ((date(2026, 9, 2), Decimal("6.5"), 2),)
    assert provider.calls[1][0][0].content == origin
    assert len(sdk.database.calls) == 3


def test_missing_name_asks_for_correction_without_reading_activities(database):
    sdk = engine(database, Provider(Interpretation("ready", request("نام پیدا نشده"))))
    session = sdk.create_session(ACTOR)
    reply = sdk.submit(session.session_id, "گزارش این شخص", ACTOR, "first", 0)
    assert reply.status == "needs_clarification"
    assert "املای دیگری" in reply.text and reply.report is None
    assert len(sdk.database.calls) == 1


def test_lookup_refinements_and_retries_keep_names_but_never_forward_resolved_ids(database, tmp_path):
    store = SQLiteSessionStore(tmp_path / "sessions.sqlite")
    provider = Provider(Interpretation("ready", request()))
    sdk = engine(database, provider, sessions=store)
    session = sdk.create_session(ACTOR)
    first = sdk.submit(session.session_id, f"گزارش {NAME}", ACTOR, "first", 0)
    assert first.status == "report_ready"
    replay = sdk.submit(session.session_id, f"گزارش {NAME}", ACTOR, "first", 0)
    assert replay.to_dict() == first.to_dict() and len(sdk.database.calls) == 2
    provider = Provider(Interpretation("ready", replace(request(), time_grain="none", chart="table")))
    resumed = engine(database, provider, sessions=SQLiteSessionStore(tmp_path / "sessions.sqlite"))
    assert resumed.get_report(session.session_id, first.report.id, ACTOR) == first.report
    refinement = resumed.submit(session.session_id, "مجموع را بده", ACTOR, "total", 1)
    assert refinement.report.rows == ((Decimal("6.5"), 2),)
    assert provider.calls[0][1].filters == request().filters
    assert provider.calls[0][1].period.kind == "range"
    assert "101" not in str(provider.calls)


@pytest.mark.parametrize("result", [
    AdapterResult((ReportField("wrong", "Wrong", "integer"),), ((101,),), False),
    AdapterResult((ReportField("person", "Person", "integer"),), ((True,),), False),
    AdapterResult((ReportField("person", "Person", "integer"),), ((101, 202),), False),
])
def test_malformed_lookup_rows_never_enter_target_execution(database, result):
    sdk = engine(database, Provider(Interpretation("ready", request())))
    calls = []
    def execute(report, limits, *, cancel=None):
        calls.append(report.dataset.id)
        return result
    sdk.database.execute = execute
    session = sdk.create_session(ACTOR)
    reply = sdk.submit(session.session_id, "گزارش این شخص", ACTOR, "first", 0)
    assert reply.report is None and reply.error is not None
    assert calls == ["profiles"]


def test_denied_qualifier_is_not_exposed_and_cannot_be_used(database):
    access = replace(scope(), datasets=(scope().datasets[0],
                     replace(scope().datasets[1], filter_ids=("full_name",))))
    visible = permitted_catalog(catalog(), access)
    assert len(visible.lookups) == 1 and visible.lookups[0].qualifiers == ()
    assert "person_job" not in str(_metadata(visible))
    sdk = engine(database, Provider(Interpretation("ready", request(job="مهندس"))), policies=lambda actor: access)
    session = sdk.create_session(ACTOR)
    reply = sdk.submit(session.session_id, "گزارش این شخص", ACTOR, "first", 0)
    assert reply.error["code"] == "access_denied" and sdk.database.calls == []


@pytest.mark.parametrize("denial", ["source", "identity", "name", "target"])
def test_lookup_metadata_and_execution_require_current_source_and_target_access(database, denial):
    access = scope()
    if denial == "source":
        access = replace(access, datasets=(access.datasets[0],))
    elif denial == "identity":
        access = replace(access, datasets=(access.datasets[0], replace(access.datasets[1], dimension_ids=())))
    elif denial == "name":
        access = replace(access, datasets=(access.datasets[0], replace(access.datasets[1], filter_ids=("job",))))
    else:
        access = replace(access, datasets=(replace(access.datasets[0], filter_ids=()), access.datasets[1]))
    visible = permitted_catalog(catalog(), access)
    assert visible.lookups == ()
    assert "person_name" not in str(_metadata(visible))
    sdk = engine(database, Provider(Interpretation("ready", request())), policies=lambda actor: access)
    session = sdk.create_session(ACTOR)
    reply = sdk.submit(session.session_id, "گزارش این شخص", ACTOR, "first", 0)
    assert reply.error["code"] == "access_denied"
    assert sdk.database.calls == []


def test_scope_change_after_lookup_blocks_target_execution_and_saved_report(database):
    current = [scope()]
    sdk = engine(database, Provider(Interpretation("ready", request())), policies=lambda actor: current[0])
    sdk.database.after_read = lambda: current.__setitem__(0, replace(scope(), version="revoked"))
    session = sdk.create_session(ACTOR)
    reply = sdk.submit(session.session_id, "گزارش این شخص", ACTOR, "first", 0)
    assert reply.error["code"] == "access_denied"
    assert len(sdk.database.calls) == 1 and reply.report is None


def test_cancellation_after_lookup_does_not_execute_target(database):
    cancelled = Event()
    sdk = engine(database, Provider(Interpretation("ready", request())))
    sdk.database.after_read = cancelled.set
    session = sdk.create_session(ACTOR)
    reply = sdk.submit(session.session_id, "گزارش این شخص", ACTOR, "first", 0, cancel=cancelled)
    assert reply.error["code"] == "cancelled" and len(sdk.database.calls) == 1


def test_execution_disabled_stops_lookup_before_any_database_access(database):
    sdk = engine(database, Provider(Interpretation("ready", request())), execution="disabled")
    session = sdk.create_session(ACTOR)
    reply = sdk.submit(session.session_id, "گزارش این شخص", ACTOR, "first", 0)
    assert reply.error["code"] == "execution_disabled"
    assert sdk.database.calls == []


def test_truncated_lookup_never_chooses_first_identity(database):
    sdk = engine(database, Provider(Interpretation("ready", request())), limits=ExecutionLimits(max_rows=1))
    with sqlite3.connect(database) as connection:
        connection.execute("INSERT INTO profile VALUES (?, ?, ?, ?, ?, ?)", (1, 0, 505, "کیان", "نمونه پور", "مدیر"))
    session = sdk.create_session(ACTOR)
    reply = sdk.submit(session.session_id, "گزارش این شخص", ACTOR, "first", 0)
    assert reply.status == "needs_clarification" and len(sdk.database.calls) == 1


@pytest.mark.parametrize("conditions", [
    (UserFilter("person_job", "eq", ("مهندس",)),),
    (UserFilter("person_name", "in", (NAME,)),),
    (UserFilter("person_name", "eq", (NAME,)), UserFilter("person_name", "eq", (NAME,))),
    (UserFilter("person_name", "eq", (NAME,)), UserFilter("person_filter", "eq", (101,))),
    (UserFilter("person_name", "eq", ("\u200c\u00a0",)),),
])
def test_invalid_lookup_requests_fail_before_any_read(database, conditions):
    sdk = engine(database, Provider(Interpretation("ready", replace(request(), filters=conditions))))
    session = sdk.create_session(ACTOR)
    reply = sdk.submit(session.session_id, "گزارش این شخص", ACTOR, "first", 0)
    assert reply.error["code"] == "invalid_spec" and sdk.database.calls == []


@pytest.mark.parametrize("changes", [
    {"source_dataset_id": "missing"}, {"target_filter_id": "missing"},
    {"source_id_dimension_id": "missing"}, {"id": "person_filter"},
    {"qualifiers": (LookupQualifier("person_job", "سمت", "missing"),)},
])
def test_invalid_host_registration_fails_closed(changes):
    registered = catalog()
    with pytest.raises(SDKError) as error:
        validate_catalog(replace(registered, lookups=(replace(registered.lookups[0], **changes),)))
    assert error.value.code == "invalid_catalog"


def test_lookup_names_are_bound_and_metadata_omits_physical_mapping_and_policies():
    registered = catalog()
    visible = permitted_catalog(registered, scope())
    payload = _metadata(visible)
    filters = payload["datasets"][0]["filters"]
    assert next(item for item in filters if item["id"] == "person_name")["resolves_entity"] is True
    assert next(item for item in filters if item["id"] == "person_job")["requires_filter"] == "person_name"
    rendered = json.dumps(payload, ensure_ascii=False)
    assert "source_id_dimension_id" not in rendered and "name_columns" not in rendered
    assert "tenant" not in rendered and "deleted" not in rendered
    schema = _format(visible)["json_schema"]["schema"]["properties"]["spec"]["anyOf"][0]
    assert "person_name" in schema["properties"]["filters"]["items"]["properties"]["filter_id"]["enum"]
    prepared, lookup = prepare_request(registered, request("x'; DROP TABLE profile; --"), scope(), date(2026, 10, 6))
    for dialect in ("sqlite", "tsql"):
        query = compile_report(lookup.source, ExecutionLimits(), dialect=dialect)
        assert "DROP TABLE" not in query.sql
        assert any(isinstance(item, str) and "DROP" in item for item in query.parameters)
        assert "JOIN" not in query.sql
