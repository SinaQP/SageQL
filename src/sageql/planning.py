"""Turn a resolved report request into validated logical database operations."""

import re
from dataclasses import dataclass
from typing import Any, Protocol

from sageql.context import ResolvedContext
from sageql.discovery import QuerySpace
from sageql.schema import Column, Definition, Relation, SchemaCatalog, Table


class PlanningError(Exception):
    """A proposed operation plan is incomplete or contradicts the query space."""


@dataclass(frozen=True)
class PlanCandidates:
    tables: dict[str, Table]
    columns: dict[str, Column]
    relations: dict[str, Relation]
    definitions: tuple[Definition, ...]


@dataclass(frozen=True)
class ProposedJoin:
    relation_id: str
    to_table_id: str
    join_type: str


@dataclass(frozen=True)
class ProposedMeasure:
    source_metric: str
    aggregation: str
    column_id: str


@dataclass(frozen=True)
class ProposedFilter:
    source_filter: str
    column_id: str
    operator: str
    values: tuple[str, ...]


@dataclass(frozen=True)
class PlanProposal:
    base_table_id: str
    joins: tuple[ProposedJoin, ...]
    time_column_id: str
    time_grain: str
    dimensions: tuple[str, ...]
    measures: tuple[ProposedMeasure, ...]
    filters: tuple[ProposedFilter, ...]


@dataclass(frozen=True)
class PlannedJoin:
    relation: Relation
    to_table: Table
    join_type: str


@dataclass(frozen=True)
class PlannedMeasure:
    source_metric: str
    aggregation: str
    column: Column | None


@dataclass(frozen=True)
class PlannedFilter:
    source_filter: str
    column: Column
    operator: str
    values: tuple[str, ...]


@dataclass(frozen=True)
class QueryPlan:
    base_table: Table
    joins: tuple[PlannedJoin, ...]
    time_column: Column | None
    time_period: str
    time_grain: str
    dimensions: tuple[Column, ...]
    measures: tuple[PlannedMeasure, ...]
    filters: tuple[PlannedFilter, ...]
    comparison_period: str
    request_understanding: str
    repairs: tuple[str, ...] = ()

    def operations(self) -> list[dict[str, Any]]:
        """Return ordered, JSON-shaped logical operations; these are not SQL."""
        operations: list[dict[str, Any]] = [{"operation": "scan", "table": self.base_table.key}]
        for join in self.joins:
            operations.append({
                "operation": "join",
                "table": join.to_table.key,
                "relation": join.relation.name,
                "type": join.join_type,
                "child_keys": [f"{join.relation.child_table}.{name}" for name in join.relation.child_columns],
                "parent_keys": [f"{join.relation.parent_table}.{name}" for name in join.relation.parent_columns],
            })
        if self.time_column is not None and self.time_period.casefold() != "all available data":
            operations.append({
                "operation": "filter_time",
                "column": self.time_column.key,
                "period_phrase": self.time_period,
            })
        for condition in self.filters:
            operations.append({
                "operation": "filter",
                "column": condition.column.key,
                "operator": condition.operator,
                "values": list(condition.values),
                "source_phrase": condition.source_filter,
            })
        if self.measures or self.dimensions or self.time_grain != "none":
            operations.append({
                "operation": "aggregate",
                "time_grain": self.time_grain,
                "time_column": self.time_column.key if self.time_column else "",
                "group_by": [column.key for column in self.dimensions],
                "measures": [
                    {"source_metric": measure.source_metric, "function": measure.aggregation,
                     "column": measure.column.key if measure.column else ""}
                    for measure in self.measures
                ],
            })
        if self.comparison_period:
            operations.append({
                "operation": "compare_periods",
                "base_period_phrase": self.time_period,
                "comparison_period_phrase": self.comparison_period,
            })
        return operations


@dataclass(frozen=True)
class PlanQuality:
    checks_passed: tuple[str, ...]
    review_items: tuple[str, ...]

    @property
    def structurally_valid(self) -> bool:
        return True  # Constructed only after strict validation.


class PlanningProvider(Protocol):
    def propose_query_plan(
        self, understanding: str, context: ResolvedContext, candidates: PlanCandidates
    ) -> PlanProposal:
        """Choose logical operations using only the provided candidate IDs."""


_AGGREGATIONS = {"sum", "count_rows", "count_distinct", "average", "minimum", "maximum"}
_GRAINS = {"none", "day", "week", "month", "quarter", "year"}
_OPERATORS = {"eq", "neq", "gt", "gte", "lt", "lte", "in", "is_null", "is_not_null"}
_NUMERIC_TYPES = ("int", "decimal", "numeric", "number", "float", "double", "real", "money")
_TIME_TYPES = ("date", "time", "timestamp")


def _requires_all_base_rows(understanding: str, base: Table) -> bool:
    return bool(re.search(
        rf"\b(?:all|every)\s+{re.escape(base.name)}\b|\ball\s+rows\b",
        understanding, re.IGNORECASE,
    ))


def _unique(values: tuple[str, ...], label: str) -> None:
    if any(not isinstance(value, str) for value in values):
        raise PlanningError(f"invalid {label} in query plan")
    if len(values) != len(set(values)):
        raise PlanningError(f"duplicate {label} in query plan")


def _require_id(key: str, items: dict[str, Any], label: str) -> Any:
    if not isinstance(key, str) or key not in items:
        raise PlanningError(f"query plan references an unknown {label}")
    return items[key]


def _check_column_type(column: Column, expected: str) -> None:
    data_type = column.data_type.casefold()
    if data_type == "unknown":
        return
    hints = _TIME_TYPES if expected == "time" else _NUMERIC_TYPES
    if not any(hint in data_type for hint in hints):
        raise PlanningError(f"query plan uses a non-{expected} column for {expected} operation")


def create_query_plan(
    understanding: str,
    context: ResolvedContext,
    space: QuerySpace,
    provider: PlanningProvider,
) -> QueryPlan:
    """Request a model plan, then validate every operation against the query space."""
    if not understanding.strip() or not isinstance(space, QuerySpace):
        raise ValueError("an understanding and query space are required")
    try:
        SchemaCatalog(space.tables, space.columns, space.relations, space.definitions)
    except ValueError as exc:
        raise PlanningError("selected query space is inconsistent") from exc
    candidates = PlanCandidates(
        {f"t{i}": table for i, table in enumerate(space.tables)},
        {f"c{i}": column for i, column in enumerate(space.columns)},
        {f"r{i}": relation for i, relation in enumerate(space.relations)},
        space.definitions,
    )
    try:
        proposal = provider.propose_query_plan(understanding, context, candidates)
    except PlanningError:
        raise
    except Exception as exc:
        raise PlanningError("query planning provider failed") from exc
    if not isinstance(proposal, PlanProposal):
        raise PlanningError("query planning provider returned an invalid proposal")

    base = _require_id(proposal.base_table_id, candidates.tables, "base table")
    joined = {base.key}
    joins: list[PlannedJoin] = []
    if not isinstance(proposal.joins, tuple) or len(proposal.joins) > 20:
        raise PlanningError("invalid join list")
    for item in proposal.joins:
        if (not isinstance(item, ProposedJoin) or not isinstance(item.join_type, str)
                or item.join_type not in {"inner", "left"}):
            raise PlanningError("invalid join operation")
        relation = _require_id(item.relation_id, candidates.relations, "relation")
        to_table = _require_id(item.to_table_id, candidates.tables, "join table")
        endpoints = {relation.child_table, relation.parent_table}
        if to_table.key in joined or to_table.key not in endpoints or len(endpoints & joined) != 1:
            raise PlanningError("join does not extend the connected table path")
        joined.add(to_table.key)
        joins.append(PlannedJoin(relation, to_table, item.join_type))

    if not isinstance(proposal.time_grain, str) or proposal.time_grain not in _GRAINS:
        raise PlanningError("invalid time grain")
    for phrase, expected_grain in (
        (r"\bdaily\b", "day"), (r"\bweekly\b", "week"),
        (r"\bmonthly\b", "month"), (r"\bquarterly\b", "quarter"),
        (r"\byearly\b|\bannually\b", "year"),
    ):
        if re.search(phrase, understanding + " " + context.time_period, re.IGNORECASE):
            if proposal.time_grain != expected_grain:
                raise PlanningError("time grain conflicts with the report request")
            break
    time_column = None
    if not isinstance(proposal.time_column_id, str):
        raise PlanningError("invalid time column")
    if proposal.time_column_id:
        time_column = _require_id(proposal.time_column_id, candidates.columns, "time column")
        _check_column_type(time_column, "time")
    if (context.time_period.casefold() != "all available data" or proposal.time_grain != "none") and time_column is None:
        raise PlanningError("a time column is required for this report")

    if not isinstance(proposal.dimensions, tuple):
        raise PlanningError("invalid dimension list")
    _unique(proposal.dimensions, "dimensions")
    dimensions = tuple(_require_id(key, candidates.columns, "dimension") for key in proposal.dimensions)

    if not isinstance(proposal.measures, tuple):
        raise PlanningError("invalid measure list")
    measures: list[PlannedMeasure] = []
    for item in proposal.measures:
        if (not isinstance(item, ProposedMeasure) or not isinstance(item.aggregation, str)
                or item.aggregation not in _AGGREGATIONS
                or not isinstance(item.source_metric, str)
                or not isinstance(item.column_id, str)):
            raise PlanningError("invalid measure operation")
        if item.source_metric not in context.metrics:
            raise PlanningError("measure does not match a resolved metric")
        if item.aggregation == "count_rows":
            if item.column_id:
                raise PlanningError("count_rows must not specify a column")
            column = None
        else:
            column = _require_id(item.column_id, candidates.columns, "measure column")
            if item.aggregation in {"sum", "average"}:
                _check_column_type(column, "numeric")
        measures.append(PlannedMeasure(item.source_metric, item.aggregation, column))
    _unique(tuple(item.source_metric for item in measures), "metrics")
    if {item.source_metric for item in measures} != set(context.metrics):
        raise PlanningError("query plan does not map every resolved metric")

    if not isinstance(proposal.filters, tuple):
        raise PlanningError("invalid filter list")
    filters: list[PlannedFilter] = []
    for item in proposal.filters:
        if (not isinstance(item, ProposedFilter) or not isinstance(item.operator, str)
                or item.operator not in _OPERATORS
                or not isinstance(item.source_filter, str)):
            raise PlanningError("invalid filter operation")
        if item.source_filter not in context.filters:
            raise PlanningError("filter does not match a resolved filter")
        column = _require_id(item.column_id, candidates.columns, "filter column")
        if not isinstance(item.values, tuple) or any(not isinstance(value, str) or not value.strip()
                                                      for value in item.values):
            raise PlanningError("invalid filter values")
        expected_values = 0 if item.operator in {"is_null", "is_not_null"} else 1
        if (expected_values == 0 and item.values) or (
            expected_values == 1 and (not item.values or (item.operator != "in" and len(item.values) != 1))
        ):
            raise PlanningError("filter values do not match the operator")
        if len(item.values) > 20 or any(len(value) > 200 for value in item.values):
            raise PlanningError("filter values are too large")
        filters.append(PlannedFilter(item.source_filter, column, item.operator, item.values))
    _unique(tuple(item.source_filter for item in filters), "filters")
    if {item.source_filter for item in filters} != set(context.filters):
        raise PlanningError("query plan does not map every resolved filter")

    referenced_columns = (
        (*dimensions, time_column, *(item.column for item in measures), *(item.column for item in filters))
    )
    if any(column is not None and column.table not in joined for column in referenced_columns):
        raise PlanningError("query plan uses a column from an unjoined table")
    repairs: list[str] = []
    if _requires_all_base_rows(understanding, base) and any(
        join.join_type == "inner" for join in joins
    ):
        joins = [PlannedJoin(join.relation, join.to_table, "left")
                 if join.join_type == "inner" else join for join in joins]
        repairs.append("Changed inner joins to left joins to preserve all requested base rows.")
    return QueryPlan(
        base, tuple(joins), time_column, context.time_period, proposal.time_grain,
        dimensions, tuple(measures), tuple(filters), context.comparison_period, understanding,
        tuple(repairs),
    )


def review_query_plan(plan: QueryPlan, context: ResolvedContext, space: QuerySpace) -> PlanQuality:
    """Explain verified structure and what still needs semantic review."""
    checks = (
        "All tables, columns, and relations exist in the selected query space.",
        "Every join extends one connected path from the source table.",
        "Every resolved metric and filter is mapped exactly once.",
    )
    review: list[str] = []
    review.extend(plan.repairs)
    if plan.time_column is not None and plan.time_period.casefold() != "all available data":
        review.append(
            f"Confirm exact date boundaries and timezone for time phrase '{plan.time_period}' before execution."
        )
    if plan.time_grain != "none":
        review.append("Confirm the calendar and timezone used for time grouping.")
    if plan.time_column is not None and plan.time_column.data_type.casefold() == "unknown":
        review.append("Confirm that the selected time column has a temporal data type.")
    if plan.comparison_period:
        review.append("Define comparison-period alignment and the comparison calculation before SQL.")
    if plan.joins and plan.measures:
        review.append("Confirm join cardinality does not multiply rows used by aggregates.")
    for measure in plan.measures:
        if measure.column is not None and measure.column.data_type.casefold() == "unknown":
            review.append(f"Confirm the data type used for metric '{measure.source_metric}'.")
        has_definition = any(definition.term.casefold() in measure.source_metric.casefold()
                             for definition in space.definitions)
        explicit_formula = (
            measure.column is not None
            and any(
                measure.column.key.casefold() in phrase.casefold()
                and measure.aggregation in phrase.casefold()
                for phrase in (measure.source_metric, plan.request_understanding)
            )
        )
        if not has_definition and not explicit_formula:
            review.append(f"Confirm the business formula for metric '{measure.source_metric}'.")
    for condition in plan.filters:
        if any(join.join_type == "left" and join.to_table.key == condition.column.table
               for join in plan.joins):
            review.append(
                f"Confirm filter '{condition.source_filter}' should exclude unmatched left-join rows."
            )
        if any(value.casefold() not in condition.source_filter.casefold() for value in condition.values):
            review.append(f"Confirm inferred filter values for '{condition.source_filter}'.")
        review.append(f"Check that filter values for '{condition.source_filter}' exist in the database.")
    if re.search(r"\ball\s+\w+", plan.request_understanding, re.IGNORECASE) and any(
        join.join_type == "inner" for join in plan.joins
    ):
        review.append("Confirm that inner joins do not discard requested rows.")
    return PlanQuality(checks, tuple(dict.fromkeys(review)))
