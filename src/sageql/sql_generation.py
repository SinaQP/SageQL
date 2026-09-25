"""Deterministic SQLite rendering of a validated logical query plan."""

from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Mapping

from sageql.errors import InvalidSQL
from sageql.planning import QueryPlan
from sageql.schema import Column, Table
from sageql.validation import validate_sql


class SQLGenerationError(Exception):
    """A logical plan cannot be represented safely as supported SQLite SQL."""


@dataclass(frozen=True)
class SQLQuery:
    sql: str
    parameters: Mapping[str, str]
    required_parameters: tuple[str, ...]

    @property
    def fully_bound(self) -> bool:
        return not self.required_parameters


_FILTER_OPERATORS = {
    "eq": "=", "neq": "!=", "gt": ">", "gte": ">=", "lt": "<", "lte": "<=",
}
_AGGREGATIONS = {
    "sum": "SUM", "count_distinct": "COUNT", "average": "AVG",
    "minimum": "MIN", "maximum": "MAX",
}


def _identifier(value: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise SQLGenerationError("plan contains an invalid SQL identifier")
    return '"' + value.replace('"', '""') + '"'


def _table_sql(table: Table) -> str:
    if not isinstance(table, Table):
        raise SQLGenerationError("plan contains an invalid table")
    return f"{_identifier(table.schema)}.{_identifier(table.name)}" if table.schema else _identifier(table.name)


def _column_sql(column: Column, aliases: dict[str, str]) -> str:
    if not isinstance(column, Column) or column.table not in aliases:
        raise SQLGenerationError("plan references a column outside its joined tables")
    return f"{aliases[column.table]}.{_identifier(column.name)}"


def _bounds(value: tuple[str, str] | None, label: str) -> tuple[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, tuple) or len(value) != 2:
        raise SQLGenerationError(f"{label} bounds must be a (start, end) tuple")
    try:
        start, end = (date.fromisoformat(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise SQLGenerationError(f"{label} bounds must be ISO dates") from exc
    if end <= start:
        raise SQLGenerationError(f"{label} end must follow its start")
    return start.isoformat(), end.isoformat()


def _time_bucket(column: str, grain: str) -> str:
    if grain == "day":
        return f"date({column})"
    if grain == "week":
        return f"date({column}, 'weekday 0', '-6 days')"
    if grain == "month":
        return f"strftime('%Y-%m-01', {column})"
    if grain == "quarter":
        month_index = f"((CAST(strftime('%m', {column}) AS INTEGER) - 1) / 3) * 3"
        return f"date({column}, 'start of year', printf('+%d months', {month_index}))"
    if grain == "year":
        return f"strftime('%Y-01-01', {column})"
    raise SQLGenerationError("plan has an unsupported time grain")


def generate_sql_from_plan(
    plan: QueryPlan,
    *,
    period_bounds: tuple[str, str] | None = None,
    comparison_bounds: tuple[str, str] | None = None,
) -> SQLQuery:
    """Render one read-only SQLite SELECT with named bind parameters.

    Bounds are inclusive start and exclusive end. Missing date bounds remain
    named placeholders and are listed in ``required_parameters``.
    """
    if not isinstance(plan, QueryPlan):
        raise SQLGenerationError("a validated query plan is required")
    primary = _bounds(period_bounds, "time period")
    comparison = _bounds(comparison_bounds, "comparison period")
    has_period = plan.time_period.casefold() != "all available data"
    if primary and not has_period:
        raise SQLGenerationError("time bounds were supplied for all available data")
    if comparison and not plan.comparison_period:
        raise SQLGenerationError("comparison bounds were supplied without a comparison period")
    if plan.comparison_period and (not has_period or plan.time_column is None):
        raise SQLGenerationError("comparison requires a time column and bounded base period")
    if (has_period or plan.time_grain != "none") and plan.time_column is None:
        raise SQLGenerationError("time operation has no time column")
    if not plan.measures and not plan.dimensions and plan.time_grain == "none":
        raise SQLGenerationError("plan has no report fields to select")

    aliases = {plan.base_table.key: "t0"}
    from_sql = f"FROM {_table_sql(plan.base_table)} AS t0"
    for index, join in enumerate(plan.joins, start=1):
        if join.join_type not in {"inner", "left"}:
            raise SQLGenerationError("plan contains an unsupported join type")
        relation = join.relation
        new_table = join.to_table.key
        endpoints = {relation.child_table, relation.parent_table}
        if (new_table in aliases or new_table not in endpoints or len(endpoints & aliases.keys()) != 1
                or len(relation.child_columns) != len(relation.parent_columns)
                or not relation.child_columns):
            raise SQLGenerationError("plan contains a disconnected join")
        new_alias = f"t{index}"
        aliases[new_table] = new_alias
        pairs = [
            f"{aliases[relation.child_table]}.{_identifier(child)} = "
            f"{aliases[relation.parent_table]}.{_identifier(parent)}"
            for child, parent in zip(relation.child_columns, relation.parent_columns)
        ]
        from_sql += (
            f"\n{join.join_type.upper()} JOIN {_table_sql(join.to_table)} "
            f"AS {new_alias} ON " + " AND ".join(pairs)
        )

    select: list[str] = []
    group_by: list[str] = []
    if plan.time_grain != "none":
        bucket = _time_bucket(_column_sql(plan.time_column, aliases), plan.time_grain)
        select.append(f"{bucket} AS \"time_bucket\"")
        group_by.append(bucket)
    for index, dimension in enumerate(plan.dimensions, start=1):
        expression = _column_sql(dimension, aliases)
        select.append(f"{expression} AS {_identifier(f'dimension_{index}')}")
        group_by.append(expression)
    for index, measure in enumerate(plan.measures, start=1):
        if measure.aggregation == "count_rows" and measure.column is None:
            expression = "COUNT(*)"
        elif measure.aggregation == "count_distinct" and measure.column is not None:
            expression = f"COUNT(DISTINCT {_column_sql(measure.column, aliases)})"
        elif measure.aggregation in _AGGREGATIONS and measure.column is not None:
            expression = f"{_AGGREGATIONS[measure.aggregation]}({_column_sql(measure.column, aliases)})"
        else:
            raise SQLGenerationError("plan contains an unsupported measure")
        select.append(f"{expression} AS {_identifier(f'metric_{index}')}")

    parameters: dict[str, str] = {}
    required: list[str] = []
    common_where: list[str] = []
    for index, condition in enumerate(plan.filters):
        column = _column_sql(condition.column, aliases)
        operator = condition.operator
        if operator in {"is_null", "is_not_null"}:
            if condition.values:
                raise SQLGenerationError("null filter cannot have values")
            common_where.append(f"{column} IS {'NOT ' if operator == 'is_not_null' else ''}NULL")
            continue
        if (not condition.values or operator not in {*_FILTER_OPERATORS, "in"}
                or (operator != "in" and len(condition.values) != 1)):
            raise SQLGenerationError("plan contains an invalid filter")
        placeholders = []
        for value_index, value in enumerate(condition.values):
            if not isinstance(value, str):
                raise SQLGenerationError("filter values must be strings")
            name = f"filter_{index}_{value_index}"
            parameters[name] = value
            placeholders.append(f":{name}")
        if operator == "in":
            common_where.append(f"{column} IN ({', '.join(placeholders)})")
        else:
            common_where.append(f"{column} {_FILTER_OPERATORS[operator]} {placeholders[0]}")

    def branch(label: str, bounds: tuple[str, str] | None, start_name: str, end_name: str) -> str:
        fields = list(select)
        if plan.comparison_period:
            fields.insert(0, f"'{label}' AS \"period_label\"")
        where = list(common_where)
        if has_period:
            time_column = _column_sql(plan.time_column, aliases)
            where.append(f"{time_column} >= :{start_name}")
            where.append(f"{time_column} < :{end_name}")
            if bounds is None:
                required.extend((start_name, end_name))
            else:
                parameters[start_name], parameters[end_name] = bounds
        statement = "SELECT " + ", ".join(fields) + "\n" + from_sql
        if where:
            statement += "\nWHERE " + " AND ".join(where)
        if group_by:
            statement += "\nGROUP BY " + ", ".join(group_by)
        return statement

    sql = branch("base", primary, "period_start", "period_end")
    if plan.comparison_period:
        sql += "\nUNION ALL\n" + branch(
            "comparison", comparison, "comparison_start", "comparison_end"
        )
    order_by = []
    if plan.comparison_period:
        order_by.append('"period_label"')
    if plan.time_grain != "none":
        order_by.append('"time_bucket"')
    order_by.extend(_identifier(f"dimension_{index}") for index in range(1, len(plan.dimensions) + 1))
    if order_by:
        sql += "\nORDER BY " + ", ".join(order_by)
    try:
        validate_sql(sql)
    except InvalidSQL as exc:
        raise SQLGenerationError("generated SQL did not pass read-only validation") from exc
    return SQLQuery(sql, MappingProxyType(parameters), tuple(required))
