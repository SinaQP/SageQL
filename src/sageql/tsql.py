"""Narrow SQL Server adapter for validated SageQL report plans.

The caller supplies an allowlisted query space and a database connection.
This adapter renders SQL itself; it never executes text returned by a model.
"""

from dataclasses import dataclass
from datetime import date
import re
from typing import Any, Callable, Mapping

from sageql.context import ResolvedContext
from sageql.discovery import QuerySpace
from sageql.errors import InvalidSQL
from sageql.planning import QueryPlan
from sageql.report_validation import RequiredFilter
from sageql.schema import Column, SchemaCatalog
from sageql.validation import validate_sql


class TSQLReportError(Exception):
    """A SQL Server report cannot be generated, validated, or executed safely."""


@dataclass(frozen=True)
class TSQLQuery:
    sql: str
    parameter_names: tuple[str, ...]
    parameters: tuple[object, ...]


@dataclass(frozen=True)
class TSQLResult:
    columns: tuple[str, ...]
    rows: tuple[tuple[object, ...], ...]
    truncated: bool


def _id(value: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise TSQLReportError("invalid identifier")
    return "[" + value.replace("]", "]]" ) + "]"


def _col(column: Column, aliases: Mapping[str, str]) -> str:
    if column.table not in aliases:
        raise TSQLReportError("column is outside joined tables")
    return aliases[column.table] + "." + _id(column.name)


def _bucket(expression: str, grain: str) -> str:
    if grain == "day":
        return f"CAST({expression} AS date)"
    if grain == "week":
        return f"DATEADD(day, -(DATEDIFF(day, '19000101', {expression}) % 7), CAST({expression} AS date))"
    if grain == "month":
        return f"DATEFROMPARTS(YEAR({expression}), MONTH({expression}), 1)"
    if grain == "quarter":
        return f"DATEFROMPARTS(YEAR({expression}), ((DATEPART(quarter, {expression}) - 1) * 3) + 1, 1)"
    if grain == "year":
        return f"DATEFROMPARTS(YEAR({expression}), 1, 1)"
    raise TSQLReportError("unsupported time grain")


def _bounds(bounds: tuple[str, str] | None, label: str) -> tuple[str, str]:
    if not isinstance(bounds, tuple) or len(bounds) != 2:
        raise TSQLReportError(f"{label} needs explicit ISO start and exclusive end dates")
    try:
        start, end = (date.fromisoformat(value) for value in bounds)
    except (ValueError, TypeError) as exc:
        raise TSQLReportError(f"{label} needs ISO dates") from exc
    if start >= end:
        raise TSQLReportError(f"{label} end must follow start")
    return start.isoformat(), end.isoformat()


def render_tsql_report(
    plan: QueryPlan,
    *,
    policy_columns: Mapping[str, str],
    period_bounds: tuple[str, str] | None = None,
    comparison_bounds: tuple[str, str] | None = None,
) -> TSQLQuery:
    """Render one parameterized T-SQL SELECT from a validated logical plan.

    Policy columns map table keys to their soft-delete bit column. Base-table
    policy goes in WHERE; joined-table policy goes in ON to preserve LEFT JOINs.
    """
    if not isinstance(plan, QueryPlan) or not plan.measures and not plan.dimensions and plan.time_grain == "none":
        raise TSQLReportError("a report plan with fields is required")
    if plan.comparison_period and (plan.time_column is None or plan.time_period.casefold() == "all available data"):
        raise TSQLReportError("comparison needs a bounded time period")
    if (plan.time_period.casefold() != "all available data" or plan.time_grain != "none") and plan.time_column is None:
        raise TSQLReportError("time operation needs a time column")
    if plan.time_period.casefold() == "all available data" and period_bounds is not None:
        raise TSQLReportError("unexpected period bounds")
    if not plan.comparison_period and comparison_bounds is not None:
        raise TSQLReportError("unexpected comparison bounds")

    aliases = {plan.base_table.key: "t0"}
    parameters: list[object] = []
    names: list[str] = []

    def bind(name: str, value: object) -> str:
        names.append(name)
        parameters.append(value)
        return "?"

    def table_name(table) -> str:
        return f"{_id(table.schema)}.{_id(table.name)}" if table.schema else _id(table.name)

    from_sql = f"FROM {table_name(plan.base_table)} AS t0"
    for index, join in enumerate(plan.joins, 1):
        if join.join_type not in {"inner", "left"}:
            raise TSQLReportError("unsupported join type")
        relation = join.relation
        endpoints = {relation.child_table, relation.parent_table}
        if (join.to_table.key in aliases or join.to_table.key not in endpoints
                or len(endpoints & aliases.keys()) != 1):
            raise TSQLReportError("disconnected join")
        alias = f"t{index}"
        aliases[join.to_table.key] = alias
        pairs = [f"{aliases[relation.child_table]}.{_id(child)} = {aliases[relation.parent_table]}.{_id(parent)}"
                 for child, parent in zip(relation.child_columns, relation.parent_columns)]
        if not pairs:
            raise TSQLReportError("join has no keys")
        if join.to_table.key in policy_columns:
            pairs.append(f"{alias}.{_id(policy_columns[join.to_table.key])} = 0")
        from_sql += f"\n{join.join_type.upper()} JOIN {table_name(join.to_table)} AS {alias} ON " + " AND ".join(pairs)

    select: list[str] = []
    group: list[str] = []
    if plan.time_grain != "none":
        bucket = _bucket(_col(plan.time_column, aliases), plan.time_grain)
        select.append(f"{bucket} AS [time_bucket]")
        group.append(bucket)
    for index, column in enumerate(plan.dimensions, 1):
        expression = _col(column, aliases)
        select.append(f"{expression} AS {_id(f'dimension_{index}')}")
        group.append(expression)
    aggregates = {"sum": "SUM", "average": "AVG", "minimum": "MIN", "maximum": "MAX"}
    for index, measure in enumerate(plan.measures, 1):
        if measure.aggregation == "count_rows" and measure.column is None:
            expression = "COUNT_BIG(*)"
        elif measure.aggregation == "count_distinct" and measure.column is not None:
            expression = f"COUNT(DISTINCT {_col(measure.column, aliases)})"
        elif measure.aggregation in aggregates and measure.column is not None:
            expression = f"{aggregates[measure.aggregation]}({_col(measure.column, aliases)})"
        else:
            raise TSQLReportError("unsupported measure")
        select.append(f"{expression} AS {_id(f'metric_{index}')}")

    common: list[str] = []
    if plan.base_table.key in policy_columns:
        common.append(f"t0.{_id(policy_columns[plan.base_table.key])} = 0")
    ops = {"eq": "=", "neq": "!=", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}
    for index, condition in enumerate(plan.filters):
        expression = _col(condition.column, aliases)
        if condition.operator in {"is_null", "is_not_null"} and not condition.values:
            common.append(f"{expression} IS {'NOT ' if condition.operator == 'is_not_null' else ''}NULL")
        elif condition.operator == "in" and condition.values:
            marks = [bind(f"filter_{index}_{i}", value) for i, value in enumerate(condition.values)]
            common.append(f"{expression} IN ({', '.join(marks)})")
        elif condition.operator in ops and len(condition.values) == 1:
            common.append(f"{expression} {ops[condition.operator]} {bind(f'filter_{index}_0', condition.values[0])}")
        else:
            raise TSQLReportError("invalid plan filter")

    def branch(label: str, bounds: tuple[str, str] | None) -> str:
        fields = ([f"'{label}' AS [period_label]"] if plan.comparison_period else []) + select
        where = list(common)
        if label == "comparison":
            for index, condition in enumerate(plan.filters):
                if condition.operator not in {"is_null", "is_not_null"}:
                    for value_index, value in enumerate(condition.values):
                        bind(f"filter_{index}_{value_index}", value)
        if plan.time_period.casefold() != "all available data":
            start, end = _bounds(bounds, label)
            expression = _col(plan.time_column, aliases)
            where += [f"{expression} >= {bind(label + '_start', start)}",
                      f"{expression} < {bind(label + '_end', end)}"]
        result = "SELECT " + ", ".join(fields) + "\n" + from_sql
        if where:
            result += "\nWHERE " + " AND ".join(where)
        if group:
            result += "\nGROUP BY " + ", ".join(group)
        return result

    sql = branch("base", period_bounds)
    if plan.comparison_period:
        sql += "\nUNION ALL\n" + branch("comparison", comparison_bounds)
    order = (["[period_label]"] if plan.comparison_period else [])
    if plan.time_grain != "none":
        order.append("[time_bucket]")
    order += [_id(f"dimension_{i}") for i in range(1, len(plan.dimensions) + 1)]
    if order:
        sql += "\nORDER BY " + ", ".join(order)
    try:
        validate_sql(sql, dialect="tsql")
    except InvalidSQL as exc:
        raise TSQLReportError("generated T-SQL did not parse as one SELECT") from exc
    return TSQLQuery(sql, tuple(names), tuple(parameters))


def validate_tsql_report(
    query: TSQLQuery, plan: QueryPlan, context: ResolvedContext, space: QuerySpace,
    *, policy_columns: Mapping[str, str], period_bounds: tuple[str, str] | None = None,
    comparison_bounds: tuple[str, str] | None = None,
    required_filters: tuple[RequiredFilter, ...] = (),
) -> tuple[str, ...]:
    """Recheck syntax, scope, interpretation and exact deterministic SQL/binds."""
    if not isinstance(query, TSQLQuery) or not isinstance(plan, QueryPlan):
        raise TSQLReportError("query and plan are required")
    if not isinstance(context, ResolvedContext) or not isinstance(space, QuerySpace):
        raise TSQLReportError("context and query space are required")
    catalog = SchemaCatalog(space.tables, space.columns, space.relations, space.definitions)
    tables = {table.key: table for table in catalog.tables}
    columns = {column.key: column for column in catalog.columns}
    relations = {relation.name: relation for relation in catalog.relations}
    referenced_tables = (plan.base_table, *(join.to_table for join in plan.joins))
    referenced_columns = (plan.time_column, *plan.dimensions, *(measure.column for measure in plan.measures),
                          *(condition.column for condition in plan.filters))
    if (any(table.key not in tables or tables[table.key] != table for table in referenced_tables)
            or any(column is not None and (column.key not in columns or columns[column.key] != column)
                   for column in referenced_columns)
            or any(join.relation.name not in relations or relations[join.relation.name] != join.relation
                   for join in plan.joins)):
        raise TSQLReportError("plan references an object outside selected query space")
    if (plan.time_period != context.time_period or plan.comparison_period != context.comparison_period
            or {m.source_metric for m in plan.measures} != set(context.metrics)
            or len(plan.measures) != len(context.metrics)
            or {f.source_filter for f in plan.filters} != set(context.filters)
            or len(plan.filters) != len(context.filters)):
        raise TSQLReportError("plan does not match resolved report context")
    explicit_years = set(re.findall(r"\b(?:19|20)\d{2}\b", plan.request_understanding))
    if len(explicit_years) == 1 and next(iter(explicit_years)) not in context.time_period:
        raise TSQLReportError("resolved time period omits the request's explicit year")
    if len(plan.measures) == 1:
        text = plan.request_understanding.casefold()
        requested = next((aggregation for pattern, aggregation in (
            (r"\bcount\s+distinct\b", "count_distinct"),
            (r"\b(?:sum|summed)\b", "sum"),
            (r"\b(?:average|mean)\b", "average"),
            (r"\b(?:minimum|lowest)\b", "minimum"),
            (r"\b(?:maximum|highest)\b", "maximum"),
            (r"\bcount\b", "count_rows"),
        ) if re.search(pattern, text)), None)
        if requested and plan.measures[0].aggregation != requested:
            raise TSQLReportError("plan aggregation conflicts with the explicit request")
    for table_key, column_name in policy_columns.items():
        if table_key in {table.key for table in referenced_tables} and f"{table_key}.{column_name}" not in columns:
            raise TSQLReportError("required policy column is outside selected query space")
    actual = {(f.column.key, f.operator, f.values) for f in plan.filters}
    if any((f.column_key, f.operator, f.values) not in actual for f in required_filters):
        raise TSQLReportError("required report filter is absent")
    try:
        validate_sql(query.sql, dialect="tsql")
    except InvalidSQL as exc:
        raise TSQLReportError("query is not one SELECT") from exc
    expected = render_tsql_report(plan, policy_columns=policy_columns,
                                  period_bounds=period_bounds, comparison_bounds=comparison_bounds)
    if query != expected:
        raise TSQLReportError("SQL or bind values differ from the validated plan")
    return ("One parsed SELECT statement.", "All plan objects are in the selected query space.",
            "Plan matches resolved metrics, filters, and periods.",
            "Explicit year and aggregation do not conflict with the plan.",
            "Required soft-delete policies are in generated SQL.",
            "SQL and ordered bind values exactly match the plan.")


def execute_tsql_report(
    connect: Callable[[], Any], query: TSQLQuery, plan: QueryPlan,
    context: ResolvedContext, space: QuerySpace,
    *, policy_columns: Mapping[str, str], period_bounds: tuple[str, str] | None = None,
    comparison_bounds: tuple[str, str] | None = None, max_rows: int = 100,
    timeout_seconds: int = 10,
) -> TSQLResult:
    """Execute validated SQL through a caller-owned ODBC connection factory."""
    if not 1 <= max_rows <= 1000 or not 1 <= timeout_seconds <= 60:
        raise TSQLReportError("invalid execution limits")
    validate_tsql_report(query, plan, context, space, policy_columns=policy_columns,
                         period_bounds=period_bounds, comparison_bounds=comparison_bounds)
    connection = None
    try:
        connection = connect()
        connection.timeout = timeout_seconds
        cursor = connection.cursor()
        cursor.execute(query.sql, *query.parameters)
        columns = tuple(item[0] for item in cursor.description)
        rows = cursor.fetchmany(max_rows + 1)
        return TSQLResult(columns, tuple(tuple(row) for row in rows[:max_rows]), len(rows) > max_rows)
    except TSQLReportError:
        raise
    except Exception:
        raise TSQLReportError("SQL Server report execution failed; check local connection and database permissions") from None
    finally:
        if connection is not None:
            try:
                connection.rollback()
            finally:
                connection.close()
