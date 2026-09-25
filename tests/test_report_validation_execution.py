import sqlite3
from contextlib import closing
from dataclasses import replace

import pytest

from sageql import (
    Column, QueryExecutionError, QueryPlan, QuerySpace, QueryValidationError,
    RequiredFilter, ResolvedContext, SQLQuery, Table, execute_sqlite_report,
    generate_sql_from_plan, prepare_report_query, validate_report_query,
)
from sageql.planning import PlannedFilter, PlannedJoin, PlannedMeasure
from sageql.schema import Relation


def _case(*, with_filter=False):
    table = Table("orders")
    region = Column("orders", "region", "text")
    status = Column("orders", "status", "text")
    space = QuerySpace((table,), (region, status), (), ())
    context = ResolvedContext(
        "all available data", ("region",), ("order count",),
        ("status active",) if with_filter else (), "",
    )
    filters = (PlannedFilter("status active", status, "eq", ("active",)),) if with_filter else ()
    plan = QueryPlan(
        table, (), None, "all available data", "none", (region,),
        (PlannedMeasure("order count", "count_rows", None),), filters, "",
        "Count orders by region, all available data",
    )
    query = generate_sql_from_plan(plan)
    return query, plan, context, space


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "orders.sqlite"
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("CREATE TABLE orders (region TEXT, status TEXT)")
        connection.executemany("INSERT INTO orders VALUES (?, ?)", [
            ("North", "active"), ("North", "inactive"),
            ("South", "active"), ("West", "active"),
        ])
        connection.commit()
    return path


def test_validation_and_read_only_execution(database):
    query, plan, context, space = _case(with_filter=True)
    required = (RequiredFilter("orders.status", "eq", ("active",)),)
    validation = validate_report_query(query, plan, context, space, required_filters=required)
    assert validation.valid
    assert any("SELECT-only" in item for item in validation.checks_passed)
    result = execute_sqlite_report(
        database, query, plan, context, space, required_filters=required
    )
    assert result.columns == ("dimension_1", "metric_1")
    assert result.rows == (("North", 1), ("South", 1), ("West", 1))
    assert not result.truncated
    with closing(sqlite3.connect(database)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM orders").fetchone() == (4,)


def test_rejects_select_from_unapproved_table(database):
    query, plan, context, space = _case()
    tampered = replace(query, sql="SELECT * FROM sqlite_master")
    assert not validate_report_query(tampered, plan, context, space).valid
    with pytest.raises(QueryExecutionError, match="validation"):
        execute_sqlite_report(database, tampered, plan, context, space)


def test_rejects_write_and_multiple_statements(database):
    query, plan, context, space = _case()
    for sql in ("DELETE FROM orders", query.sql + "; DROP TABLE orders"):
        tampered = replace(query, sql=sql)
        assert not validate_report_query(tampered, plan, context, space).valid
        with pytest.raises(QueryExecutionError, match="validation"):
            execute_sqlite_report(database, tampered, plan, context, space)


def test_rejects_missing_required_filter(database):
    query, plan, context, space = _case()
    required = (RequiredFilter("orders.status", "eq", ("active",)),)
    validation = validate_report_query(query, plan, context, space, required_filters=required)
    assert not validation.valid
    assert any("required filters" in item for item in validation.issues)
    with pytest.raises(QueryValidationError):
        prepare_report_query(plan, context, space, required_filters=required)
    with pytest.raises(QueryExecutionError, match="required filters"):
        execute_sqlite_report(database, query, plan, context, space, required_filters=required)


def test_rejects_mismatched_interpretation_and_bind_values(database):
    query, plan, context, space = _case(with_filter=True)
    wrong_context = replace(context, metrics=("revenue",))
    assert not validate_report_query(query, plan, wrong_context, space).valid
    changed = replace(query, parameters={"filter_0_0": "inactive"})
    assert not validate_report_query(changed, plan, context, space).valid
    with pytest.raises(QueryExecutionError):
        execute_sqlite_report(database, changed, plan, context, space)


def test_rejects_explicit_aggregation_conflict():
    query, plan, context, space = _case()
    changed_plan = replace(plan, measures=(PlannedMeasure("order count", "maximum",
                                                         Column("orders", "region", "text")),))
    changed_query = generate_sql_from_plan(changed_plan)
    result = validate_report_query(changed_query, changed_plan, context, space)
    assert not result.valid
    assert any("aggregation conflicts" in item for item in result.issues)


def test_rejects_named_entity_outside_selected_space():
    query, plan, context, space = _case()
    changed = replace(context, entities=("private.customers",))
    result = validate_report_query(query, plan, changed, space)
    assert not result.valid
    assert any("named entity" in item for item in result.issues)


def test_rejects_resolved_time_that_drops_explicit_year():
    query, plan, context, space = _case()
    plan = replace(plan, request_understanding="Count orders by region in 2025")
    result = validate_report_query(query, plan, context, space)
    assert not result.valid
    assert any("explicit year" in item for item in result.issues)


def test_validator_blocks_unrepaired_inner_join_for_all_base_rows():
    query, plan, context, space = _case()
    region_table = Table("regions")
    region_id = Column("regions", "id", "integer")
    order_region = Column("orders", "region_id", "integer")
    relation = Relation("fk_region", "orders", ("region_id",), "regions", ("id",))
    space = replace(space, tables=(*space.tables, region_table),
                    columns=(*space.columns, region_id, order_region), relations=(relation,))
    plan = replace(plan,
                   joins=(PlannedJoin(relation, region_table, "inner"),),
                   request_understanding="Count all orders by region")
    query = generate_sql_from_plan(plan)
    result = validate_report_query(query, plan, context, space)
    assert not result.valid
    assert any("discard rows" in item for item in result.issues)


def test_repair_discards_invalid_sql_and_regenerates():
    query, plan, context, space = _case()
    malicious = SQLQuery("SELECT * FROM sqlite_master", {}, ())
    prepared = prepare_report_query(plan, context, space, candidate=malicious)
    assert prepared.repaired
    assert prepared.validation.valid
    assert prepared.query.sql == query.sql


def test_repair_honors_new_date_bounds_over_valid_candidate():
    query, plan, context, space = _case()
    time_column = Column("orders", "created_at", "date")
    plan = replace(plan, time_period="2025", time_column=time_column)
    context = replace(context, time_period="2025")
    space = replace(space, columns=(*space.columns, time_column))
    old = generate_sql_from_plan(plan, period_bounds=("2024-01-01", "2025-01-01"))
    prepared = prepare_report_query(
        plan, context, space, candidate=old,
        period_bounds=("2025-01-01", "2026-01-01"),
    )
    assert prepared.repaired
    assert prepared.query.parameters["period_start"] == "2025-01-01"


def test_result_limit_reports_truncation(database):
    query, plan, context, space = _case()
    result = execute_sqlite_report(database, query, plan, context, space, max_rows=1)
    assert len(result.rows) == 1
    assert result.truncated


def test_unresolved_date_bindings_block_execution(database):
    query, plan, context, space = _case()
    timed = replace(plan, time_period="2025", time_column=Column("orders", "created_at", "date"))
    timed_space = replace(space, columns=(*space.columns, timed.time_column))
    timed_context = replace(context, time_period="2025")
    unbound = generate_sql_from_plan(timed)
    assert not validate_report_query(unbound, timed, timed_context, timed_space).valid
    with pytest.raises(QueryExecutionError, match="date bindings"):
        execute_sqlite_report(database, unbound, timed, timed_context, timed_space)


def test_work_limit_interrupts_large_query(database):
    with closing(sqlite3.connect(database)) as connection:
        connection.executemany("INSERT INTO orders VALUES (?, ?)",
                               ((f"Region {index}", "active") for index in range(10_000)))
        connection.commit()
    query, plan, context, space = _case()
    with pytest.raises(QueryExecutionError, match="time or work limit"):
        execute_sqlite_report(database, query, plan, context, space, max_vm_steps=1_000)


def test_database_must_exist_and_is_never_created(tmp_path):
    path = tmp_path / "missing.sqlite"
    query, plan, context, space = _case()
    with pytest.raises(QueryExecutionError, match="unavailable"):
        execute_sqlite_report(path, query, plan, context, space)
    assert not path.exists()
