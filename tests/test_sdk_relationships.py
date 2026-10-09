"""Synthetic cross-domain reports, including fan-out and authorization failures."""

from dataclasses import replace
from datetime import date
import json
import sqlite3
from decimal import Decimal

import pytest

from sageql.schema import Column, Table
from sageql.sdk import (
    AccessScope, ActorContext, AggregateFilter, DatasetAccess, DatasetDefinition, DimensionDefinition,
    ExecutionLimits, FilterDefinition, Interpretation, MetricDefinition,
    PeriodSelection, RelatedDimension, RelatedFilter, RelationshipDefinition,
    ReportingCatalog, ReportSpec, RowPolicy, SageQL, SDKError, SQLiteAdapter,
    SQLServerAdapter, SQLiteSessionStore, TimeDefinition, UserFilter, register_relationships,
)
from sageql.sdk.adapters import compile_report, _rows
from sageql.sdk.agents import AgentReportInterpreter, AgentReview
from sageql.sdk.intent import ConceptRef, ReportIntent, canonical_intent, unavailable_intent
from sageql.sdk.lookups import prepare_request
from sageql.sdk.provider import _metadata
from sageql.sdk.semantics import permitted_catalog, validate_catalog


TODAY = date(2026, 10, 9)


def dataset(identifier, names, *, metrics=(), dimensions=(), filters=(), time=None):
    table = Table("private_" + identifier)
    return DatasetDefinition(identifier, identifier, table,
                             tuple(Column(table.key, name, kind) for name, kind in names),
                             metrics, dimensions, filters, time)


def catalog():
    sales = dataset("sales", (("tenant", "int"), ("buyer", "int"), ("product", "int"),
                              ("amount", "float"), ("day", "date")),
                    metrics=(MetricDefinition("revenue", "Revenue", "sum", "amount"),
                             MetricDefinition("orders", "Orders", "count_rows"),
                             MetricDefinition("average", "Average sale", "average", "amount")),
                    dimensions=(DimensionDefinition("buyer", "Buyer", "buyer"),),
                    time=TimeDefinition("day"))
    buyers = dataset("buyers", (("tenant", "int"), ("id", "int"), ("region", "text"), ("active", "bit")),
                     dimensions=(DimensionDefinition("tenant", "Tenant", "tenant"),
                                 DimensionDefinition("identity", "Buyer", "id"),
                                 DimensionDefinition("region", "Region", "region")),
                     filters=(FilterDefinition("region_filter", "Region", "region"),))
    products = dataset("products", (("id", "int"), ("category", "text")),
                       dimensions=(DimensionDefinition("identity", "Product", "id"),
                                   DimensionDefinition("category", "Category", "category")))
    registered = ReportingCatalog((sales, buyers, products))
    relations = (
        RelationshipDefinition("customer", "sales", "buyers", (("tenant", "tenant"), ("buyer", "id")),
                               (RelatedDimension("buyer_region", "Buyer region", "region"),),
                               (RelatedFilter("buyer_region_filter", "Buyer region", "region_filter"),)),
        RelationshipDefinition("product", "sales", "products", (("product", "id"),),
                               (RelatedDimension("product_category", "Product category", "category"),)),
    )
    return register_relationships(registered, relations)


def scope():
    return AccessScope((
        DatasetAccess("sales", policies=(RowPolicy("tenant", "eq", (1,)),)),
        DatasetAccess("buyers", policies=(RowPolicy("tenant", "eq", (1,)), RowPolicy("active", "eq", (True,)))),
        DatasetAccess("products"),
    ))


def spec(**changes):
    return replace(ReportSpec("sales", ("revenue",), dimension_ids=("buyer_region",),
                              period=PeriodSelection("rolling", count=3, unit="month"),
                              order_by="revenue", descending=True), **changes)


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "report.sqlite"
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE private_sales (tenant int, buyer int, product int, amount float, day date);
            CREATE TABLE private_buyers (tenant int, id int, region text, active bit);
            CREATE TABLE private_products (id int, category text);
            INSERT INTO private_sales VALUES
              (1,1,10,10,'2026-07-09'), (1,2,10,20,'2026-09-09'),
              (1,3,20,25,'2026-10-09'), (1,4,20,5,'2026-10-09'),
              (1,5,10,7,'2026-10-09'), (2,1,10,1000,'2026-09-09'),
              (1,1,10,900,'2026-07-08'), (1,1,10,900,'2026-10-10');
            INSERT INTO private_buyers VALUES
              (1,1,'North',1), (1,2,'North',1), (1,3,'South',1),
              (1,4,'Private',0), (2,1,'Other tenant',1);
            INSERT INTO private_products VALUES (10,'Goods'), (20,'Service');
        """)
    return path


def execute(path, selected=None, access=None):
    prepared, lookup = prepare_request(catalog(), selected or spec(), access or scope(), TODAY)
    assert lookup is None
    return SQLiteAdapter(path).execute(prepared, ExecutionLimits())


def test_group_before_top_n_without_fact_fanout(database):
    result = execute(database, spec(limit=1))
    assert result.rows == (("North", 30.0),)
    assert result.truncated
    assert [field.id for field in result.fields] == ["buyer_region", "revenue"]


def test_multiple_relations_metrics_and_missing_policy_bound_attributes(database):
    result = execute(database, spec(metric_ids=("revenue", "orders", "average"),
                                    dimension_ids=("buyer_region", "product_category")))
    assert set(result.rows) == {("North", "Goods", 30.0, 2, 15.0),
                               ("South", "Service", 25.0, 1, 25.0),
                               (None, "Goods", 7.0, 1, 7.0), (None, "Service", 5.0, 1, 5.0)}


def test_related_filters_and_dimension_listing(database):
    condition = (UserFilter("buyer_region_filter", "eq", ("North",)),)
    assert execute(database, spec(filters=condition)).rows == (("North", 30.0),)
    listing = spec(metric_ids=(), period=PeriodSelection("all"), filters=condition, order_by="buyer_region")
    assert execute(database, listing).rows == (("North",),)


def test_related_null_filter_respects_source_policies(database):
    result = execute(database, spec(filters=(UserFilter("buyer_region_filter", "is_null"),)))
    assert result.rows == ((None, 12.0),)


def test_thresholds_filter_final_aggregates_before_top_n(database):
    result = execute(database, spec(aggregate_filters=(AggregateFilter("revenue", "gte", (28,)),), limit=1))
    assert result.rows == (("North", 30.0),) and not result.truncated
    result = execute(database, spec(metric_ids=("revenue", "orders"),
                                    aggregate_filters=(AggregateFilter("orders", "gte", (2,)),)))
    assert result.rows == (("North", 30.0, 2), (None, 12.0, 2))


@pytest.mark.parametrize("condition", [AggregateFilter("unknown", "gt", (1,)),
                                      AggregateFilter("revenue", "gt", ("SQL",)),
                                      AggregateFilter("revenue", "in", ()),
                                      AggregateFilter("revenue", "drop", (1,))])
def test_invalid_aggregate_conditions_are_rejected(condition):
    with pytest.raises(SDKError) as error:
        prepare_request(catalog(), spec(aggregate_filters=(condition,)), scope(), TODAY)
    assert error.value.code == "invalid_spec"


@pytest.mark.parametrize("aggregation,operator,threshold", [("sum", "gte", 25),
                                                         ("average", "gt", 12.5), ("sum", "in", 30)])
def test_decimal_and_integer_aggregate_thresholds_use_numeric_comparison(tmp_path, aggregation, operator, threshold):
    path = tmp_path / "work.sqlite"
    with sqlite3.connect(path) as connection:
        connection.executescript("CREATE TABLE private_work (team text, duration int);"
                                 "INSERT INTO private_work VALUES ('A',10), ('A',20), ('B',5);")
    work = dataset("work", (("team", "text"), ("duration", "int")),
                   metrics=(MetricDefinition("hours", "Hours", aggregation, "duration"),),
                   dimensions=(DimensionDefinition("team", "Team", "team"),))
    selected = ReportSpec("work", ("hours",), ("team",),
                          aggregate_filters=(AggregateFilter("hours", operator, (threshold,)),))
    prepared, _ = prepare_request(ReportingCatalog((work,)), selected, AccessScope((DatasetAccess("work"),)), TODAY)
    result = SQLiteAdapter(path).execute(prepared, ExecutionLimits())
    assert result.rows == (("A", Decimal(15 if aggregation == "average" else 30)),)


@pytest.mark.parametrize("region", ["North", "Conflict"])
def test_duplicates_fail_closed_including_identical_profiles(database, region):
    with sqlite3.connect(database) as connection:
        connection.execute("INSERT INTO private_buyers VALUES (1,1,?,1)", (region,))
    with pytest.raises(SDKError) as error:
        execute(database, spec(limit=1))
    assert error.value.code == "relationship_cardinality"


def test_duplicate_outside_top_n_and_outside_matching_fact_keys_is_detected(database):
    with sqlite3.connect(database) as connection:
        connection.executemany("INSERT INTO private_buyers VALUES (1,99,?,1)", [("A",), ("B",)])
    with pytest.raises(SDKError, match="multiple visible rows"):
        execute(database, spec(limit=1))


def test_denied_duplicate_rows_do_not_affect_report(database):
    with sqlite3.connect(database) as connection:
        connection.executescript("INSERT INTO private_buyers VALUES (1,1,'Hidden',0), (2,1,'Duplicate',1);")
    assert execute(database, spec(limit=1)).rows == (("North", 30.0),)


def test_null_source_keys_never_match_or_trigger_conflict(database):
    with sqlite3.connect(database) as connection:
        connection.executescript("INSERT INTO private_buyers VALUES (1,NULL,'A',1), (1,NULL,'B',1);")
    assert execute(database, spec(limit=1)).rows == (("North", 30.0),)


def test_comparison_preserves_both_source_and_fact_policies(database):
    result = execute(database, spec(comparison=PeriodSelection("month", year=2026, month=9)))
    assert ("base", "North", 30.0) in result.rows
    assert ("comparison", "North", 20.0) in result.rows
    assert not any(row[-1] >= 1000 for row in result.rows)


@pytest.mark.parametrize("access", [
    AccessScope((DatasetAccess("sales"), DatasetAccess("products"))),
    replace(scope(), datasets=(scope().datasets[0], DatasetAccess("buyers", dimension_ids=("tenant", "identity")), scope().datasets[2])),
    replace(scope(), datasets=(scope().datasets[0], DatasetAccess("buyers", dimension_ids=("region",)), scope().datasets[2])),
])
def test_denied_source_or_concept_is_hidden_and_cannot_execute(database, access):
    visible = permitted_catalog(catalog(), access)
    fact = next(item for item in visible.datasets if item.id == "sales")
    assert "buyer_region" not in {item.id for item in fact.dimensions}
    with pytest.raises(SDKError) as error:
        execute(database, access=access)
    assert error.value.code == "access_denied"


def test_source_filter_permission_is_required(database):
    access = replace(scope(), datasets=(scope().datasets[0], replace(scope().datasets[1], filter_ids=()), scope().datasets[2]))
    assert "buyer_region_filter" not in json.dumps(_metadata(permitted_catalog(catalog(), access)))
    with pytest.raises(SDKError) as error:
        execute(database, spec(filters=(UserFilter("buyer_region_filter", "eq", ("North",)),)), access)
    assert error.value.code == "access_denied"


def test_model_payload_contains_no_relationship_keys_policies_or_physical_names():
    visible = permitted_catalog(catalog(), scope())
    payload = json.dumps(_metadata(visible))
    assert "buyer_region" in payload and "product_category" in payload
    for forbidden in ("private_sales", "private_buyers", "key_pairs", "__rel_", '"active"'):
        assert forbidden not in payload
    assert visible.relationships == ()
    validate_catalog(visible)


def test_intent_resolves_registered_equivalence_without_guessing_a_relation():
    visible = permitted_catalog(catalog(), scope())
    requested = ReportIntent(metrics=(ConceptRef("sales", "revenue"),),
                             dimensions=(ConceptRef("buyers", "region"),))
    effective = canonical_intent(requested, visible)
    assert effective.dimensions == (ConceptRef("sales", "buyer_region"),)
    assert unavailable_intent(effective, visible, "en") is None


def test_ambiguous_relationship_roles_never_choose_a_mapping():
    registered = register_relationships(catalog(), (RelationshipDefinition(
        "supplier", "sales", "buyers", (("buyer", "id"),),
        (RelatedDimension("supplier_region", "Supplier region", "region"),)),))
    visible = permitted_catalog(registered, scope())
    requested = ReportIntent(metrics=(ConceptRef("sales", "revenue"),),
                             dimensions=(ConceptRef("buyers", "region"),))
    assert canonical_intent(requested, visible) == requested
    assert unavailable_intent(requested, visible, "en").status == "unsupported"


def test_tsql_ordered_bindings_and_composite_join():
    prepared, _ = prepare_request(catalog(), spec(filters=(UserFilter("buyer_region_filter", "eq", ("North",)),)), scope(), TODAY)
    query = compile_report(prepared, ExecutionLimits(), dialect="tsql")
    assert query.parameters == (1, True, 101, 1, "North", date(2026, 7, 9), date(2026, 10, 10))
    assert "LEFT JOIN r0" in query.sql and "t.[tenant] = r0.[k0]" in query.sql
    assert "COUNT_BIG(*)" in query.sql and "__sageql_relation_guard" in query.sql
    result = _rows(query, [("buyer_region",), ("revenue",), ("__sageql_relation_guard",)], [("North", 30, 0)])
    assert result.rows == (("North", 30),)


def test_adapter_rejects_missing_or_forged_bindings():
    prepared, _ = prepare_request(catalog(), spec(), scope(), TODAY)
    with pytest.raises(SDKError) as error:
        compile_report(replace(prepared, related_sources=()), ExecutionLimits(), dialect="sqlite")
    assert error.value.code == "invalid_spec"
    forged = replace(prepared.related_sources[0], column_pairs=(("__rel_customer_buyer_region", "id"),))
    with pytest.raises(SDKError):
        compile_report(replace(prepared, related_sources=(forged,)), ExecutionLimits(), dialect="sqlite")


def test_schema_drift_on_related_source(database):
    with sqlite3.connect(database) as connection:
        connection.execute("ALTER TABLE private_buyers RENAME COLUMN region TO renamed")
    with pytest.raises(SDKError) as error:
        execute(database)
    assert error.value.code == "schema_drift"


def test_unrelated_reports_do_not_read_or_validate_inactive_sources(database):
    with sqlite3.connect(database) as connection:
        connection.execute("DROP TABLE private_buyers")
    result = execute(database, spec(dimension_ids=()))
    assert result.rows == ((67.0,),)


def test_generic_agent_planning_refinement_and_persistence(database, tmp_path):
    class Backend:
        def __init__(self):
            self.group = "buyer_region"

        def understand(self, messages, current_spec, catalog, today, **kwargs):
            return ReportIntent(metrics=(ConceptRef("sales", "revenue"),),
                                dimensions=(ConceptRef("sales", self.group),),
                                turn_kind="refine" if current_spec else "new", period=spec().period)

        def plan(self, messages, current_spec, catalog, today, **kwargs):
            selected = replace(current_spec, dimension_ids=(self.group,)) if current_spec else spec()
            return Interpretation("ready", selected)

        def review(self, *args, **kwargs):
            return AgentReview(True)

    backend = Backend()
    session_path = tmp_path / "sessions.sqlite"
    engine = SageQL(catalog=catalog(), database=SQLiteAdapter(database),
                    provider=AgentReportInterpreter(backend), policy=lambda actor: scope(),
                    sessions=SQLiteSessionStore(session_path), execution="validated", clock=lambda: TODAY)
    actor = ActorContext("manager")
    session = engine.create_session(actor)
    first = engine.submit(session.session_id, "Rank revenue by region over the last three months", actor, "1", 0)
    assert first.status == "report_ready" and first.report.rows[0] == ("North", 30.0)
    backend.group = "product_category"
    second = engine.submit(session.session_id, "Now by product category", actor, "2", 1)
    assert second.status == "report_ready" and second.report.rows == (("Goods", 37.0), ("Service", 30.0))
    assert engine.get_report(session.session_id, second.report.id, actor) == second.report
    assert engine.submit(session.session_id, "Now by product category", actor, "2", 1) == second
    restarted = SageQL(catalog=catalog(), database=SQLiteAdapter(database),
                       provider=AgentReportInterpreter(backend), policy=lambda actor: scope(),
                       sessions=SQLiteSessionStore(session_path), execution="validated", clock=lambda: TODAY)
    assert restarted.get_report(session.session_id, second.report.id, actor) == second.report


@pytest.mark.parametrize("guard,drift,expected", [(0, False, None), (1, False, "relationship_cardinality"),
                                                (0, True, "schema_drift")])
def test_sqlserver_checks_each_source_and_cleans_up_on_guard_or_schema_failure(guard, drift, expected):
    configured = catalog()
    prepared, _ = prepare_request(configured, spec(dimension_ids=("buyer_region", "product_category")), scope(), TODAY)

    class Connection:
        def __init__(self):
            self.statements = []
            self.description = None
            self.closed = self.rolled_back = self.cancelled = False

        def cursor(self):
            return self

        def execute(self, sql, *parameters):
            self.statements.append((sql, parameters))
            self.metadata = "sys.columns" in sql
            self.current_table = parameters[1] if self.metadata else None
            if not self.metadata:
                self.description = [(name,) for name in ("buyer_region", "product_category", "revenue", "__sageql_relation_guard")]
            return self

        def fetchmany(self, size):
            if not self.metadata:
                return [("North", "Goods", 30.0, guard)]
            source = next(item for item in configured.datasets if item.table.name == self.current_table)
            # SQL Server requires modern text types; SQLite fixtures declare text.
            metadata = [(column.name, "nvarchar" if column.data_type == "text" else column.data_type,
                         column.nullable, "U", 0, 0) for column in source.columns if column.name not in source.related_columns]
            return metadata[:-1] if drift and source.id == "buyers" else metadata

        def rollback(self):
            self.rolled_back = True

        def close(self):
            self.closed = True

        def cancel(self):
            self.cancelled = True

    connection = Connection()
    adapter = SQLServerAdapter(lambda: connection)
    if expected:
        with pytest.raises(SDKError) as error:
            adapter.execute(prepared, ExecutionLimits())
        assert error.value.code == expected
    else:
        result = adapter.execute(prepared, ExecutionLimits())
        assert result.rows == (("North", "Goods", 30.0),)
        assert [args[1] for sql, args in connection.statements if "sys.columns" in sql] == [
            "private_sales", "private_buyers", "private_products"]
    assert connection.closed and connection.rolled_back


def test_source_revocation_during_interpretation_prevents_execution(database):
    current_scope = [scope()]

    class Provider:
        def interpret(self, *args):
            current_scope[0] = replace(scope(), datasets=(scope().datasets[0], scope().datasets[2]))
            return Interpretation("ready", spec())

    class Database:
        def execute(self, *args, **kwargs):
            pytest.fail("Revoked source access must prevent every report query")

    engine = SageQL(catalog=catalog(), database=Database(), provider=Provider(),
                    policy=lambda actor: current_scope[0], execution="validated", clock=lambda: TODAY)
    actor = ActorContext("manager")
    session = engine.create_session(actor)
    reply = engine.submit(session.session_id, "Revenue by region", actor, "1", 0)
    assert reply.error["code"] == "access_denied" and reply.revision == 0


def test_relational_diagnostics_redact_first_policy_parameter(tmp_path):
    from sageql_rahtal.diagnostics import DiagnosticCursor, Trace, _trace

    class Cursor:
        def execute(self, *args):
            return self

    trace = Trace(tmp_path)
    token = _trace.set(trace)
    try:
        DiagnosticCursor(Cursor()).execute("WITH r0 AS (SELECT 1) SELECT TOP (?) 1", 314159, 101)
    finally:
        _trace.reset(token)
    started = next(item for item in trace.data["events"] if item["status"] == "started")
    assert all(item["value"] == "[redacted]" for item in started["parameters"])
    assert "314159" not in json.dumps(trace.data)


def test_registration_rejects_invalid_keys_and_unregistered_imports():
    existing = catalog()
    base = ReportingCatalog(tuple(replace(item, columns=tuple(c for c in item.columns if c.name not in item.related_columns),
                                         dimensions=tuple(d for d in item.dimensions if d.column not in item.related_columns),
                                         filters=tuple(f for f in item.filters if f.column not in item.related_columns), related_columns=())
                                  for item in existing.datasets))
    relation = existing.relationships[0]
    for invalid in (replace(relation, key_pairs=()), replace(relation, key_pairs=(("amount", "id"),)),
                    replace(relation, dimensions=(RelatedDimension("x", "X", "unknown"),)),
                    replace(relation, source_dataset_id="sales")):
        with pytest.raises(SDKError) as error:
            register_relationships(base, (invalid,))
        assert error.value.code == "invalid_catalog"


def test_catalog_rejects_tampered_projection():
    registered = catalog()
    fact = registered.datasets[0]
    tampered = replace(registered, datasets=(replace(fact, related_columns=()), *registered.datasets[1:]))
    with pytest.raises(SDKError):
        validate_catalog(tampered)
