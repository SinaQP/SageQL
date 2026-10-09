"""Registered display dimensions preserve identity rankings without joining data."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
import json
import sqlite3
from threading import Event
from types import SimpleNamespace

import pytest

from sageql import Column, LLMConfig, Table
from sageql.sdk import (
    AccessScope, ActorContext, DatasetAccess, DatasetDefinition,
    DimensionDefinition, EntityLabelDimension, EntityLookupDefinition, ExecutionLimits,
    FilterDefinition, FullNameFilterDefinition,
    Interpretation, MetricDefinition, OpenAIReportAgent, PeriodSelection,
    ReportingCatalog, ReportSpec, RowPolicy, SDKError, SageQL, SQLiteAdapter,
    SQLiteSessionStore, TimeDefinition, UserFilter,
)
from sageql.sdk.adapters import compile_report
from sageql.sdk.lookups import prepare_request
from sageql.sdk.provider import _metadata
from sageql.sdk.semantics import permitted_catalog, validate_catalog


ACTOR = ActorContext("reader", "7")
TODAY = date(2026, 10, 7)


def catalog():
    orders, people = Table("private_orders"), Table("private_people")
    return ReportingCatalog((
        DatasetDefinition("orders", "فروش", orders,
            tuple(Column(orders.key, name, kind) for name, kind in (
                ("tenant", "int"), ("deleted", "int"), ("person_key", "int"),
                ("day", "date"), ("amount", "decimal"))),
            metrics=(MetricDefinition("revenue", "مبلغ فروش", "sum", "amount"),),
            dimensions=(DimensionDefinition("person", "شناسه فروشنده", "person_key"),
                        EntityLabelDimension("person_name", "نام فروشنده", "person_key",
                                             "people", "identity", "identity_filter", ("given", "surname"))),
            time=TimeDefinition("day")),
        DatasetDefinition("people", "فروشندگان", people,
            tuple(Column(people.key, name, kind) for name, kind in (
                ("tenant", "int"), ("deleted", "int"), ("identity_key", "int"),
                ("first", "text"), ("last", "text"))), metrics=(),
            dimensions=(DimensionDefinition("identity", "شناسه", "identity_key"),
                        DimensionDefinition("given", "نام", "first"),
                        DimensionDefinition("surname", "نام خانوادگی", "last")),
            filters=(FilterDefinition("identity_filter", "شناسه", "identity_key"),)),
    ))


def scope():
    return AccessScope(tuple(DatasetAccess(identifier, policies=(
        RowPolicy("tenant", "eq", (7,)), RowPolicy("deleted", "eq", (0,)),
    )) for identifier in ("orders", "people")))


def spec(**changes):
    return replace(ReportSpec("orders", ("revenue",), ("person_name",),
                              period=PeriodSelection("last_month"), chart="bar",
                              order_by="revenue", descending=True, limit=2), **changes)


class Provider:
    def __init__(self, *specs):
        self.specs = iter(specs)
        self.calls = []

    def interpret(self, messages, current, allowed, today):
        self.calls.append((messages, current, allowed))
        return Interpretation("ready", next(self.specs))


class Adapter:
    def __init__(self, path):
        self.inner = SQLiteAdapter(path)
        self.calls = []
        self.after = lambda report: None

    def execute(self, report, limits, *, cancel=None):
        self.calls.append(report)
        result = self.inner.execute(report, limits, cancel=cancel)
        self.after(report)
        return result


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "synthetic.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE private_orders (tenant INT, deleted INT, person_key INT, day DATE, amount DECIMAL)")
        connection.execute("CREATE TABLE private_people (tenant INT, deleted INT, identity_key INT, first TEXT, last TEXT)")
        connection.executemany("INSERT INTO private_orders VALUES (?, ?, ?, ?, ?)", [
            (7, 0, 101, "2026-09-02", 4), (7, 0, 101, "2026-09-03", 8),
            (7, 0, 202, "2026-09-02", 10), (7, 0, 303, "2026-09-02", 6),
            (7, 0, 404, "2026-09-02", 5), (7, 0, 505, "2026-09-02", 4),
            (7, 0, None, "2026-09-02", 3),
            (8, 0, 101, "2026-09-02", 900), (7, 1, 101, "2026-09-02", 800),
            (7, 0, 101, "2026-08-02", 700),
        ])
        connection.executemany("INSERT INTO private_people VALUES (?, ?, ?, ?, ?)", [
            (7, 0, 101, "کیان", "نمونه"), (7, 0, 101, "کیان", "نمونه"),
            (7, 0, 202, "کیان", "نمونه"),  # Same name, distinct ranked identities.
            (8, 0, 101, "Other", "tenant"), (7, 1, 101, "Deleted", "profile"),
            (8, 0, 303, "Forbidden", "profile"), (7, 1, 404, "Deleted", "profile"),
            (7, 0, 505, None, "  "),
        ])
    return path


def engine(database, provider=None, **options):
    return SageQL(catalog=options.pop("catalog", catalog()), database=Adapter(database),
                  provider=provider or Provider(spec()), policy=options.pop("policy", lambda actor: scope()),
                  clock=lambda: TODAY, execution=options.pop("execution", "validated"), **options)


def submit(sdk, message="فروش فروشندگان ماه قبل با نام", request="first", revision=0, session=None, **options):
    session = session or sdk.create_session(ACTOR).session_id
    return sdk.submit(session, message, ACTOR, request, revision, **options)


def test_top_n_keeps_totals_rank_and_separate_identities_with_the_same_name(database):
    sdk = engine(database)
    reply = submit(sdk)
    assert reply.status == "report_ready", reply.to_dict()
    assert reply.report.rows == (("کیان نمونه", Decimal(12)), ("کیان نمونه", Decimal(10)))
    assert reply.report.fields[0].type == "text" and reply.report.fields[0].id == "person_name"
    assert reply.report.visualization == {"kind": "bar", "x": "person_name", "y": "revenue"}
    assert [report.dataset.id for report in sdk.database.calls] == ["orders", "people"]
    source = sdk.database.calls[1]
    assert source.spec.filters[0].values == (101, 202)
    assert source.spec.dimension_ids == ("identity", "given", "surname")
    assert all(report.access.policies == scope().datasets[i].policies
               for i, report in enumerate(sdk.database.calls))
    def scalar_values(value):
        if isinstance(value, dict):
            for item in value.values():
                yield from scalar_values(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                yield from scalar_values(item)
        else:
            yield value

    # Opaque random report/session IDs may legitimately contain the digits 101.
    # Check actual values for a leaked resolved identity, not UUID substrings.
    assert all(value != 101 and value != "101"
               for value in scalar_values(reply.report.to_dict()))


def test_metric_rank_ties_preserve_identity_selection_when_display_dimensions_change(database):
    registered = catalog()
    work = replace(registered.datasets[0], dimensions=(
        *registered.datasets[0].dimensions,
        DimensionDefinition("category", "دسته", "deleted"),
    ))
    registered = replace(registered, datasets=(work, registered.datasets[1]))
    # Opposite category/identity order exposes selection drift in tied top-N.
    with sqlite3.connect(database) as connection:
        connection.execute("DELETE FROM private_orders")
        connection.executemany("INSERT INTO private_orders VALUES (?, ?, ?, ?, ?)", [
            (7, 0, 101, "2026-09-02", 10),
            (7, 1, 202, "2026-09-02", 10),
            (7, 0, 303, "2026-09-02", 10),
        ])
    unrestricted_category = AccessScope((
        DatasetAccess("orders", policies=(RowPolicy("tenant", "eq", (7,)),)),
        scope().datasets[1],
    ))
    ordered = spec(dimension_ids=("person_name", "category"), chart="table", limit=2)
    reversed_columns = replace(ordered, dimension_ids=tuple(reversed(ordered.dimension_ids)))
    named = replace(ordered, dimension_ids=("person_name",), chart="bar")
    sdk = engine(database, Provider(ordered, reversed_columns, named), catalog=registered,
                 policy=lambda _: unrestricted_category)
    session = sdk.create_session(ACTOR).session_id
    first = submit(sdk, session=session)
    second = submit(sdk, session=session, request="reorder", revision=1)
    third = submit(sdk, session=session, request="chart", revision=2)
    assert [reply.status for reply in (first, second, third)] == ["report_ready"] * 3
    identity_filters = [request.spec.filters[0].values for request in sdk.database.calls
                        if request.dataset.id == "people"]
    assert identity_filters == [(101, 202)] * 3
    assert second.report.rows == tuple((row[1], row[0], row[2]) for row in first.report.rows)
    for request in sdk.database.calls:
        if request.dataset.id != "orders":
            continue
        query = compile_report(request, ExecutionLimits(), dialect="tsql")
        assert "ORDER BY [revenue] DESC, [person_name] ASC" in query.sql


def test_missing_null_blank_and_policy_denied_profiles_do_not_leak_ids_or_trigger_probes(database):
    sdk = engine(database, Provider(spec(limit=10)))
    reply = submit(sdk)
    assert reply.status == "report_ready"
    assert [row[0] for row in reply.report.rows] == ["کیان نمونه"] * 2 + ["نام در دسترس نیست"] * 4
    assert [row[1] for row in reply.report.rows] == list(map(Decimal, [12, 10, 6, 5, 4, 3]))
    assert reply.report.provenance["entity_labels"]["unavailable_rows"] == 4
    assert sdk.database.calls[1].spec.filters[0].values == (101, 202, 303, 404, 505)
    assert len(sdk.database.calls) == 2


def test_conflicting_profiles_fail_without_overwriting_previous_report(database):
    sdk = engine(database, Provider(spec(dimension_ids=("person",)), spec()))
    first = submit(sdk)
    with sqlite3.connect(database) as connection:
        connection.execute("INSERT INTO private_people VALUES (7, 0, 101, 'Conflicting', 'Name')")
    second = submit(sdk, session=first.session_id, request="names", revision=1)
    assert second.error == {"code": "entity_label_conflict", "retryable": False}
    assert "Conflicting" not in second.text and second.revision == 1
    assert sdk.get_report(first.session_id, first.report.id, ACTOR) == first.report


@pytest.mark.parametrize("denial", ["source", "identity", "given", "surname", "filter", "target"])
def test_denied_mapping_is_hidden_and_rejected_before_any_read(database, denial):
    access = scope()
    target, source = access.datasets
    if denial == "source":
        access = replace(access, datasets=(target,))
    else:
        if denial == "filter":
            source = replace(source, filter_ids=())
        elif denial == "target":
            target = replace(target, dimension_ids=("person",))
        else:
            source = replace(source, dimension_ids=tuple(
                item.id for item in catalog().datasets[1].dimensions if item.id != denial))
        access = replace(access, datasets=(target, source))
    visible = permitted_catalog(catalog(), access)
    assert "person_name" not in {item.id for item in visible.datasets[0].dimensions}
    sdk = engine(database, policy=lambda actor: access)
    reply = submit(sdk)
    assert reply.error["code"] == "access_denied" and sdk.database.calls == []


@pytest.mark.parametrize("stage", ["orders", "people"])
def test_access_revocation_between_reads_discards_report(database, stage):
    current = [scope()]
    sdk = engine(database, policy=lambda actor: current[0])
    def revoke(report):
        if report.dataset.id == stage:
            current[0] = replace(current[0], version="revoked")
    sdk.database.after = revoke
    reply = submit(sdk)
    assert reply.error["code"] == "access_denied" and reply.report is None
    assert len(sdk.database.calls) == (1 if stage == "orders" else 2)


def test_execution_disabled_never_runs_report_or_label_lookup(database):
    sdk = engine(database, execution="disabled")
    assert submit(sdk).error["code"] == "execution_disabled"
    assert sdk.database.calls == []


def test_cancellation_after_label_read_discards_partial_artifact(database):
    cancelled = Event()
    sdk = engine(database)
    sdk.database.after = lambda report: cancelled.set() if report.dataset.id == "people" else None
    reply = submit(sdk, cancel=cancelled)
    assert reply.error["code"] == "cancelled" and reply.report is None


def test_empty_result_does_not_read_profiles_and_still_has_text_schema(database):
    sdk = engine(database, Provider(spec(period=PeriodSelection("year", year=2025))))
    reply = submit(sdk)
    assert reply.status == "report_ready" and reply.report.rows == ()
    assert reply.report.fields[0].type == "text" and len(sdk.database.calls) == 1


def test_persistence_refinement_and_cached_retry_keep_names_out_of_model_context(database, tmp_path):
    store = tmp_path / "sessions.sqlite"
    sdk = engine(database, sessions=SQLiteSessionStore(store))
    first = submit(sdk)
    assert first.status == "report_ready"
    provider = Provider(spec(chart="table", limit=3))
    resumed = engine(database, provider, sessions=SQLiteSessionStore(store))
    assert resumed.get_report(first.session_id, first.report.id, ACTOR) == first.report
    second = submit(resumed, message="سه نفر را به صورت جدول نشان بده", session=first.session_id,
                    request="refine", revision=1)
    assert second.status == "report_ready"
    current = provider.calls[0][1]
    assert current.dimension_ids == ("person_name",) and current.limit == 2
    assert current.period == PeriodSelection("range", "2026-09-01", "2026-10-01")
    assert "کیان" not in str(provider.calls) and "101" not in str(provider.calls)
    retry = submit(resumed, message="سه نفر را به صورت جدول نشان بده", session=first.session_id,
                   request="refine", revision=1)
    assert retry.to_dict() == second.to_dict()
    assert len(resumed.database.calls) == 2 and len(provider.calls) == 1


def test_label_reads_batch_only_returned_identities(database):
    with sqlite3.connect(database) as connection:
        connection.executemany("INSERT INTO private_orders VALUES (7, 0, ?, '2026-09-02', 1)",
                               [(i,) for i in range(1000, 1201)])
    sdk = engine(database, Provider(spec(limit=1000)))
    reply = submit(sdk)
    assert reply.status == "report_ready" and len(reply.report.rows) == 207
    batches = [report.spec.filters[0].values for report in sdk.database.calls[1:]]
    assert list(map(len, batches)) == [100, 100, 6]
    assert len(set(key for batch in batches for key in batch)) == 206


@pytest.mark.parametrize("corruption", ["truncated", "shape", "foreign_id", "wrong_type", "label_type"])
def test_incomplete_or_invalid_label_results_fail_closed(database, corruption):
    sdk = engine(database)
    original = sdk.database.execute
    def execute(report, limits, *, cancel=None):
        result = original(report, limits, cancel=cancel)
        if report.dataset.id != "people":
            return result
        if corruption == "truncated":
            return replace(result, truncated=True)
        if corruption == "shape":
            return replace(result, fields=result.fields[:-1])
        identity = 999 if corruption == "foreign_id" else "101" if corruption == "wrong_type" else 101
        return replace(result, rows=((identity, 42 if corruption == "label_type" else "Name", "Surname"),))
    sdk.database.execute = execute
    reply = submit(sdk)
    assert reply.error["code"] == "entity_label_failed" and reply.report is None


def test_actual_source_truncation_never_picks_an_arbitrary_profile(database):
    with sqlite3.connect(database) as connection:
        connection.execute("INSERT INTO private_people VALUES (7, 0, 101, 'Conflicting', 'Name')")
    sdk = engine(database, limits=ExecutionLimits(max_rows=2))
    assert submit(sdk).error["code"] == "entity_label_failed"


@pytest.mark.parametrize("change", [
    {"source_dataset_id": "missing"}, {"source_dataset_id": "orders"},
    {"source_id_dimension_id": "given"}, {"source_id_filter_id": "missing"},
    {"source_label_dimension_ids": ()}, {"source_label_dimension_ids": ("identity",)},
    {"source_label_dimension_ids": ("given", "given")},
])
def test_bad_host_mappings_are_rejected(change):
    registration = catalog()
    target, source = registration.datasets
    target = replace(target, dimensions=(target.dimensions[0], replace(target.dimensions[1], **change)))
    with pytest.raises(SDKError) as error:
        validate_catalog(replace(registration, datasets=(target, source)))
    assert error.value.code == "invalid_catalog"


def test_label_sorting_and_multiple_enrichments_are_rejected_before_execution(database):
    sdk = engine(database, Provider(spec(order_by="person_name")))
    assert submit(sdk).error["code"] == "unsupported" and sdk.database.calls == []
    registration = catalog()
    target, source = registration.datasets
    target = replace(target, dimensions=(*target.dimensions, replace(target.dimensions[1], id="other_name")))
    sdk = engine(database, Provider(spec(dimension_ids=("person_name", "other_name"), chart="table")),
                 catalog=replace(registration, datasets=(target, source)))
    assert submit(sdk).error["code"] == "unsupported" and sdk.database.calls == []


def test_text_identities_can_be_labeled_without_numeric_coercion(database):
    registration = catalog()
    target, source = registration.datasets
    target = replace(target, columns=tuple(replace(column, data_type="text")
                     if column.name == "person_key" else column for column in target.columns))
    source = replace(source, columns=tuple(replace(column, data_type="text")
                     if column.name == "identity_key" else column for column in source.columns))
    path = database.parent / "text-identities.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE private_orders (tenant INT, deleted INT, person_key TEXT, day DATE, amount DECIMAL)")
        connection.execute("CREATE TABLE private_people (tenant INT, deleted INT, identity_key TEXT, first TEXT, last TEXT)")
        connection.execute("INSERT INTO private_orders VALUES (7, 0, '001', '2026-09-02', 12)")
        connection.execute("INSERT INTO private_people VALUES (7, 0, '001', 'Test', 'Person')")
    sdk = engine(path, catalog=replace(registration, datasets=(target, source)), language="en")
    reply = submit(sdk)
    assert reply.status == "report_ready" and reply.report.rows == (("Test Person", Decimal(12)),)
    assert sdk.database.calls[1].spec.filters[0].values == ("001",)


def test_name_filter_and_display_labels_use_independent_policy_bound_reads(database):
    registration = catalog()
    target, source = registration.datasets
    target = replace(target, filters=(FilterDefinition("person_filter", "فروشنده", "person_key"),))
    source = replace(source, filters=(*source.filters, FullNameFilterDefinition(
        "full_name", "نام کامل", "first", ("eq",), ("first", "last"))))
    registration = replace(registration, datasets=(target, source), lookups=(EntityLookupDefinition(
        "person_name_filter", "نام فروشنده", "orders", "person_filter", "people", "identity", "full_name"),))
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE private_people SET first='Other' WHERE identity_key=202")
    request = spec(filters=(UserFilter("person_name_filter", "eq", ("کیان نمونه",)),))
    sdk = engine(database, Provider(request), catalog=registration)
    reply = submit(sdk)
    assert reply.status == "report_ready" and reply.report.rows == (("کیان نمونه", Decimal(12)),)
    assert [report.dataset.id for report in sdk.database.calls] == ["people", "orders", "people"]
    assert reply.report.provenance["filters"] == [
        {"filter_id": "person_name_filter", "operator": "eq", "values": ["کیان نمونه"]}]
    assert "101" not in json.dumps(reply.report.to_dict())


def test_sql_server_compilation_still_groups_and_limits_identities_without_joins():
    prepared, _ = prepare_request(catalog(), spec(), scope(), TODAY)
    query = compile_report(prepared, ExecutionLimits(), dialect="tsql")
    assert "GROUP BY t.[person_key]" in query.sql
    assert "ORDER BY [revenue] DESC, [person_name] ASC" in query.sql
    assert "TOP (?)" in query.sql and query.parameters[0] == 3
    assert "JOIN" not in query.sql.upper() and "private_people" not in query.sql
    assert query.fields[0].type == "integer"  # Internal adapter result, enriched locally.


class Client:
    def __init__(self, *decisions):
        self.responses = iter(decisions)
        self.calls = []
        self.chat = SimpleNamespace(completions=self)

    def with_options(self, **options):
        return self

    def create(self, **options):
        self.calls.append(options)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content=json.dumps(next(self.responses), ensure_ascii=False)))])


def decision(request):
    return {"status": "ready", "spec": request.to_dict(), "question": "", "message": ""}


def intent(request, *, missing=(), turn_kind="new"):
    from sageql.sdk import ConceptRef, ReportIntent
    return ReportIntent(
        metrics=tuple(ConceptRef(request.dataset_id, key) for key in request.metric_ids),
        dimensions=tuple(ConceptRef(request.dataset_id, key) for key in request.dimension_ids),
        missing=missing, turn_kind=turn_kind,
        period=None if {"period", "year", "calendar"}.intersection(missing) else request.period,
    ).to_dict()


def test_agent_replays_id_report_name_refinement_and_short_confirmation_without_losing_rank(database):
    original = spec(dimension_ids=("person",), limit=10)
    named = spec(limit=10)
    client = Client(intent(original), decision(original), {"approved": True, "feedback": ""},
                    intent(named, turn_kind="refine"),
                    {"status": "needs_clarification", "spec": None,
                     "question": "نام به جای شناسه نمایش داده شود؟", "message": ""},
                    decision(named), {"approved": True, "feedback": ""},
                    intent(named, turn_kind="answer"),
                    decision(named), {"approved": True, "feedback": ""})
    provider = OpenAIReportAgent(LLMConfig("fake-key", "https://example.test", "test"), client=client)
    sdk = engine(database, provider)
    first = submit(sdk, message="۱۰ فروشنده با بیشترین فروش در ماه قبل")
    second = submit(sdk, message="با اسم بگو شناسه بدردم نمیخوره", session=first.session_id,
                    request="names", revision=1)
    third = submit(sdk, message="اره اره", session=first.session_id, request="yes", revision=2)
    assert [reply.status for reply in (first, second, third)] == ["report_ready"] * 3
    assert second.report.rows == third.report.rows
    assert [row[1] for row in second.report.rows] == [row[1] for row in first.report.rows]
    assert len(client.calls) == 10
    for call in client.calls:
        content = call["messages"][1]["content"]
        payload = json.loads(content)
        assert "کیان" not in content and "101" not in content and "private_" not in content
        assert "source_id_filter_id" not in content and "source_label_dimension_ids" not in content
        assert "rows" not in payload and "policies" not in payload
    for call in client.calls[3:7]:
        current = json.loads(call["messages"][1]["content"])["current_spec"]
        assert current["limit"] == 10 and current["order_by"] == "revenue" and current["descending"]


def test_existing_pending_confirmation_remains_interpretable_with_registered_capability(database):
    original, named = spec(dimension_ids=("person",)), spec()
    client = Client(intent(named, turn_kind="answer"),
                    decision(named), {"approved": True, "feedback": ""})
    sdk = engine(database, Provider(original))
    first = submit(sdk)
    # Simulate a question persisted by an older provider before the upgrade.
    sdk.provider = SimpleNamespace(interpret=lambda *args: Interpretation(
        "needs_clarification", question="نام کامل را به جای شناسه نمایش دهم؟"))
    question = submit(sdk, message="نام‌ها را نمایش بده", session=first.session_id, request="names", revision=1)
    assert question.status == "needs_clarification"
    sdk.provider = OpenAIReportAgent(LLMConfig("fake-key", "https://example.test", "test"), client=client)
    reply = submit(sdk, message="بله حتماً", session=first.session_id, request="yes", revision=2)
    assert reply.status == "report_ready" and reply.report.rows[0][0] == "کیان نمونه"
    conversation = json.loads(client.calls[0]["messages"][1]["content"])["conversation"]
    assert [item["text"] for item in conversation][-3:] == ["نام‌ها را نمایش بده", question.text, "بله حتماً"]


@pytest.mark.parametrize("message", ["۱۰ تا از بهترین فروشنده‌ها را بگو", "Who are our top ten sellers?"])
def test_ambiguous_ranking_review_can_ask_for_criterion_and_period_before_any_read(database, message):
    question = "بهترین را بر اساس چه معیاری و برای چه بازه‌ای می‌خواهید؟"
    client = Client(intent(spec(), missing=("measure", "period")), decision(spec()),
                    {"status": "needs_clarification", "spec": None, "question": question, "message": ""},
                    {"approved": True, "feedback": ""},
                    intent(spec(), turn_kind="answer"),
                    decision(spec()), {"approved": True, "feedback": ""})
    provider = OpenAIReportAgent(LLMConfig("fake-key", "https://example.test", "test"), client=client)
    sdk = engine(database, provider)
    first = submit(sdk, message=message)
    assert first.status == "needs_clarification" and sdk.database.calls == []
    second = submit(sdk, message="بیشترین مبلغ فروش در ماه قبل", session=first.session_id,
                    request="criterion", revision=1)
    assert second.status == "report_ready"
    conversation = json.loads(client.calls[4]["messages"][1]["content"])["conversation"]
    assert [item["text"] for item in conversation] == [message, question, "بیشترین مبلغ فروش در ماه قبل"]


def test_provider_capability_exposes_only_business_dimension_and_no_source_mapping():
    metadata = _metadata(permitted_catalog(catalog(), scope()))
    label = next(item for item in metadata["datasets"][0]["dimensions"] if item["id"] == "person_name")
    assert label == {"id": "person_name", "label": "نام فروشنده", "type": "text",
                     "entity_label": True, "sortable": False}
    assert "person_key" not in json.dumps(metadata) and "source_dataset_id" not in json.dumps(metadata)
