import sqlite3
from dataclasses import replace

import pytest

from sageql import (
    PlanProposal, ProposedFilter, ProposedJoin, ProposedMeasure, QuerySpace,
    ResolvedContext, SQLGenerationError, QueryPlan, Table, catalog_from_dict, create_query_plan,
    generate_sql_from_plan,
)
from sageql.planning import PlannedMeasure


def _plan(*, filter_value=None):
    catalog = catalog_from_dict({
        "tables": [
            {"schema": "sales", "name": "orders", "columns": [
                {"name": "region_id", "data_type": "integer"},
                {"name": "amount", "data_type": "decimal"},
                {"name": "order_date", "data_type": "date"},
                {"name": "status", "data_type": "text"},
            ]},
            {"schema": "sales", "name": "regions", "columns": [
                {"name": "region_id", "data_type": "integer"},
                {"name": "name", "data_type": "text"},
            ]},
        ],
        "relations": [{"name": "fk_region", "child_table": "sales.orders",
                       "child_columns": ["region_id"], "parent_table": "sales.regions",
                       "parent_columns": ["region_id"]}],
    })
    space = QuerySpace(catalog.tables, catalog.columns, catalog.relations, ())
    filters = ("status is complete",) if filter_value is not None else ()
    context = ResolvedContext("monthly 2025", ("region",), ("total amount",), filters, "")

    class Provider:
        def propose_query_plan(self, understanding, resolved, candidates):
            tables = {table.key: key for key, table in candidates.tables.items()}
            columns = {column.key: key for key, column in candidates.columns.items()}
            return PlanProposal(
                tables["sales.orders"],
                (ProposedJoin(next(iter(candidates.relations)), tables["sales.regions"], "left"),),
                columns["sales.orders.order_date"], "month",
                (columns["sales.regions.name"],),
                (ProposedMeasure("total amount", "sum", columns["sales.orders.amount"]),),
                (ProposedFilter("status is complete", columns["sales.orders.status"],
                                "eq", (filter_value,)),) if filter_value is not None else (),
            )

    return create_query_plan("Monthly total amount by region for 2025", context, space, Provider())


def _database():
    connection = sqlite3.connect(":memory:")
    connection.execute("ATTACH DATABASE ':memory:' AS sales")
    connection.execute("CREATE TABLE sales.orders (region_id INTEGER, amount DECIMAL, order_date DATE, status TEXT)")
    connection.execute("CREATE TABLE sales.regions (region_id INTEGER, name TEXT)")
    connection.executemany("INSERT INTO sales.regions VALUES (?, ?)", [(1, "North"), (2, "South")])
    connection.executemany("INSERT INTO sales.orders VALUES (?, ?, ?, ?)", [
        (1, 10, "2025-01-15", "complete"),
        (1, 20, "2025-01-20", "complete"),
        (2, 7, "2025-02-03", "pending"),
        (1, 99, "2024-12-31", "complete"),
    ])
    return connection


def test_generated_sql_returns_expected_rows_on_synthetic_sqlite():
    query = generate_sql_from_plan(_plan(), period_bounds=("2025-01-01", "2026-01-01"))
    assert query.fully_bound
    assert "LEFT JOIN" in query.sql
    assert 'ORDER BY "time_bucket", "dimension_1"' in query.sql
    assert ":period_start" in query.sql
    assert "2025-01-01" not in query.sql
    with _database() as connection:
        rows = connection.execute(query.sql, dict(query.parameters)).fetchall()
    assert rows == [("2025-01-01", "North", 30), ("2025-02-01", "South", 7)]


def test_missing_dates_are_explicit_bindings():
    query = generate_sql_from_plan(_plan())
    assert not query.fully_bound
    assert query.required_parameters == ("period_start", "period_end")
    assert dict(query.parameters) == {}


def test_filter_value_is_bound_not_interpolated():
    malicious = "complete' OR 1=1 --"
    query = generate_sql_from_plan(_plan(filter_value=malicious),
                                   period_bounds=("2025-01-01", "2026-01-01"))
    assert malicious not in query.sql
    assert query.parameters["filter_0_0"] == malicious
    with _database() as connection:
        rows = connection.execute(query.sql, dict(query.parameters)).fetchall()
    assert rows == []


def test_comparison_generates_both_periods_without_calculating_delta():
    plan = replace(_plan(), comparison_period="2024")
    query = generate_sql_from_plan(
        plan, period_bounds=("2025-01-01", "2026-01-01"),
        comparison_bounds=("2024-01-01", "2025-01-01"),
    )
    assert query.fully_bound
    assert "UNION ALL" in query.sql
    with _database() as connection:
        rows = connection.execute(query.sql, dict(query.parameters)).fetchall()
    assert ("base", "2025-01-01", "North", 30) in rows
    assert ("comparison", "2024-12-01", "North", 99) in rows


def test_quarter_bucket_uses_calendar_quarters():
    plan = replace(_plan(), time_grain="quarter")
    query = generate_sql_from_plan(plan, period_bounds=("2025-01-01", "2026-01-01"))
    with _database() as connection:
        rows = connection.execute(query.sql, dict(query.parameters)).fetchall()
    assert rows == [("2025-01-01", "North", 30), ("2025-01-01", "South", 7)]


@pytest.mark.parametrize("bounds", [
    ("2025-01-01", "2025-01-01"),
    ("2026-01-01", "2025-01-01"),
    ("next year", "2026-01-01"),
])
def test_rejects_invalid_date_bounds(bounds):
    with pytest.raises(SQLGenerationError):
        generate_sql_from_plan(_plan(), period_bounds=bounds)


def test_rejects_disconnected_join_even_for_manually_built_plan():
    plan = _plan()
    bad_join = replace(plan.joins[0], join_type="cross")
    with pytest.raises(SQLGenerationError, match="join type"):
        generate_sql_from_plan(replace(plan, joins=(bad_join,)))


def test_untrusted_identifier_is_quoted_as_one_name():
    plan = QueryPlan(
        Table('orders"; DROP TABLE users;--'), (), None, "all available data", "none", (),
        (PlannedMeasure("number of orders", "count_rows", None),), (), "", "Count orders"
    )
    query = generate_sql_from_plan(plan)
    assert 'FROM "orders""; DROP TABLE users;--" AS t0' in query.sql
    assert query.sql.startswith('SELECT COUNT(*) AS "metric_1"')
