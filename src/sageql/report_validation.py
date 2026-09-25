"""Validate generated report SQL against its plan before execution."""

from dataclasses import dataclass
import re
from typing import Iterable

from sageql.context import ResolvedContext
from sageql.discovery import QuerySpace
from sageql.errors import InvalidSQL
from sageql.planning import QueryPlan, _requires_all_base_rows, review_query_plan
from sageql.schema import SchemaCatalog
from sageql.sql_generation import SQLGenerationError, SQLQuery, generate_sql_from_plan
from sageql.validation import validate_sql


class QueryValidationError(Exception):
    """The report query failed validation and cannot be executed."""


@dataclass(frozen=True)
class RequiredFilter:
    column_key: str
    operator: str
    values: tuple[str, ...]


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    checks_passed: tuple[str, ...]
    issues: tuple[str, ...]
    review_items: tuple[str, ...]


@dataclass(frozen=True)
class PreparedQuery:
    query: SQLQuery
    validation: ValidationResult
    repaired: bool


def _bounds_from_query(query: SQLQuery, start: str, end: str) -> tuple[str, str] | None:
    values = query.parameters
    if start in values and end in values:
        return values[start], values[end]
    return None


def validate_report_query(
    query: SQLQuery,
    plan: QueryPlan,
    context: ResolvedContext,
    space: QuerySpace,
    *,
    required_filters: Iterable[RequiredFilter] = (),
) -> ValidationResult:
    """Check SQL shape, schema scope, plan match, binds, and required filters.

    Semantic review items are reported separately. They cannot be proved by
    SQL syntax checks or a user-supplied catalog.
    """
    issues: list[str] = []
    checks: list[str] = []
    if not isinstance(query, SQLQuery) or not isinstance(plan, QueryPlan):
        return ValidationResult(False, (), ("A generated SQL query and plan are required.",), ())
    if not isinstance(context, ResolvedContext) or not isinstance(space, QuerySpace):
        return ValidationResult(False, (), ("Resolved context and selected query space are required.",), ())
    allowed_columns: set[str] = set()
    try:
        validate_sql(query.sql)
        checks.append("One syntactically valid SELECT-only SQLite statement.")
    except InvalidSQL:
        issues.append("SQL is invalid or contains a disallowed statement.")

    try:
        SchemaCatalog(space.tables, space.columns, space.relations, space.definitions)
        allowed_tables = {table.key: table for table in space.tables}
        allowed_column_map = {column.key: column for column in space.columns}
        allowed_columns = set(allowed_column_map)
        allowed_relations = {relation.name: relation for relation in space.relations}
        referenced_tables = (plan.base_table, *(join.to_table for join in plan.joins))
        referenced_columns = (
            plan.time_column, *plan.dimensions,
            *(measure.column for measure in plan.measures),
            *(condition.column for condition in plan.filters),
        )
        if any(table.key not in allowed_tables or table != allowed_tables[table.key]
               for table in referenced_tables):
            raise ValueError("table outside selected query space")
        if any(column is not None and (column.key not in allowed_column_map
                                      or column != allowed_column_map[column.key])
               for column in referenced_columns):
            raise ValueError("column outside selected query space")
        if any(join.relation.name not in allowed_relations
               or join.relation != allowed_relations[join.relation.name]
               for join in plan.joins):
            raise ValueError("relation outside selected query space")
        for join in plan.joins:
            if any(f"{join.relation.child_table}.{name}" not in allowed_columns
                   for name in join.relation.child_columns):
                raise ValueError("join key outside selected query space")
            if any(f"{join.relation.parent_table}.{name}" not in allowed_columns
                   for name in join.relation.parent_columns):
                raise ValueError("join key outside selected query space")
        checks.append("Plan tables, columns, and joins are in the selected query space.")
    except (ValueError, TypeError, AttributeError):
        issues.append("Plan references tables, columns, or joins outside the selected query space.")

    if (plan.time_period != context.time_period
            or plan.comparison_period != context.comparison_period
            or {measure.source_metric for measure in plan.measures} != set(context.metrics)
            or len(plan.measures) != len(context.metrics)
            or {condition.source_filter for condition in plan.filters} != set(context.filters)
            or len(plan.filters) != len(context.filters)):
        issues.append("Plan does not match the resolved time, metrics, or filters.")
    else:
        checks.append("Plan covers the resolved time, metrics, and filters.")
    explicit_years = set(re.findall(r"\b(?:19|20)\d{2}\b", plan.request_understanding))
    if len(explicit_years) == 1 and next(iter(explicit_years)) not in context.time_period:
        issues.append("Resolved time period omits the report's explicit year.")
    if (_requires_all_base_rows(plan.request_understanding, plan.base_table)
            and not context.filters
            and any(join.join_type == "inner" for join in plan.joins)):
        issues.append("Inner join can discard rows explicitly requested as all base rows.")

    known_entities = {table.key for table in space.tables} | allowed_columns
    named_entities = {item for item in context.entities
                      if re.fullmatch(r"[A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)+", item)}
    exact_entities = named_entities & known_entities
    used_entities = {table.key for table in (plan.base_table, *(join.to_table for join in plan.joins))}
    used_entities.update(column.key for column in plan.dimensions)
    if named_entities - known_entities:
        issues.append("An explicitly named entity is outside the selected query space.")
    elif not exact_entities <= used_entities:
        issues.append("Plan omits an explicitly named table or grouping column.")
    elif len(plan.measures) == 1:
        phrase = plan.request_understanding.casefold()
        explicit_aggregations = (
            (r"\bcount\s+distinct\b", "count_distinct"),
            (r"\bsum\b", "sum"),
            (r"\b(?:average|mean)\b", "average"),
            (r"\b(?:minimum|lowest)\b", "minimum"),
            (r"\b(?:maximum|highest)\b", "maximum"),
            (r"\bcount\b", "count_rows"),
        )
        requested = next((aggregate for pattern, aggregate in explicit_aggregations
                          if re.search(pattern, phrase)), None)
        if requested and plan.measures[0].aggregation != requested:
            issues.append("Plan aggregation conflicts with the explicit report request.")
        else:
            checks.append("Explicit report entities and aggregation do not conflict with the plan.")

    try:
        required = tuple(required_filters)
        if any(not isinstance(item, RequiredFilter) or item.column_key not in allowed_columns
               for item in required):
            raise ValueError("invalid required filter")
        actual = {(item.column.key, item.operator, item.values) for item in plan.filters}
        if any((item.column_key, item.operator, item.values) not in actual for item in required):
            issues.append("One or more required filters are missing from the plan.")
        else:
            checks.append("All caller-required filters are present.")
    except (ValueError, TypeError, NameError):
        issues.append("Required filters are invalid or outside the selected query space.")

    if query.required_parameters:
        issues.append("Exact date bindings are required before execution.")
    elif not isinstance(query.parameters, dict) and not hasattr(query.parameters, "items"):
        issues.append("Query bind parameters are invalid.")
    else:
        try:
            canonical = generate_sql_from_plan(
                plan,
                period_bounds=_bounds_from_query(query, "period_start", "period_end"),
                comparison_bounds=_bounds_from_query(query, "comparison_start", "comparison_end"),
            )
            if (query.sql != canonical.sql
                    or dict(query.parameters) != dict(canonical.parameters)
                    or query.required_parameters != canonical.required_parameters):
                issues.append("SQL or bind values differ from the validated plan.")
            else:
                checks.append("SQL and bind values exactly match the structured plan.")
        except (SQLGenerationError, TypeError, ValueError):
            issues.append("The structured plan cannot produce this SQL safely.")

    try:
        review = review_query_plan(plan, context, space).review_items
    except (TypeError, AttributeError, ValueError):
        issues.append("Plan cannot be reviewed safely.")
        review = ()
    return ValidationResult(not issues, tuple(checks), tuple(issues), review)


def prepare_report_query(
    plan: QueryPlan,
    context: ResolvedContext,
    space: QuerySpace,
    *,
    period_bounds: tuple[str, str] | None = None,
    comparison_bounds: tuple[str, str] | None = None,
    required_filters: Iterable[RequiredFilter] = (),
    candidate: SQLQuery | None = None,
) -> PreparedQuery:
    """Validate a candidate, or discard and regenerate it once from the plan."""
    filters = tuple(required_filters)
    repaired = False
    if candidate is not None:
        first = validate_report_query(candidate, plan, context, space, required_filters=filters)
        bounds_match = True
        if first.valid and (period_bounds is not None or comparison_bounds is not None):
            try:
                expected = generate_sql_from_plan(
                    plan, period_bounds=period_bounds, comparison_bounds=comparison_bounds
                )
                bounds_match = (
                    candidate.sql == expected.sql
                    and dict(candidate.parameters) == dict(expected.parameters)
                )
            except SQLGenerationError:
                bounds_match = False
        if first.valid and bounds_match:
            return PreparedQuery(candidate, first, False)
        repaired = True
    try:
        generated = generate_sql_from_plan(
            plan, period_bounds=period_bounds, comparison_bounds=comparison_bounds
        )
    except SQLGenerationError as exc:
        raise QueryValidationError("query cannot be generated from this plan") from exc
    result = validate_report_query(generated, plan, context, space, required_filters=filters)
    if not result.valid:
        raise QueryValidationError("query failed validation: " + " ".join(result.issues))
    return PreparedQuery(generated, result, repaired)
