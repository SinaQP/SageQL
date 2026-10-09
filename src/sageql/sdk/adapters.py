"""Deterministic, bounded adapters for registered reporting sources.

SQL Server uses a host-supplied, dedicated connection factory. The factory must
set a finite login timeout and return a disposable connection (or a pool lease
whose close() discards/reset its state); it must not return an application
transaction. This adapter owns cursor closure, rollback and connection closure.
Only this module's canonical SELECTs execute; no API accepts SQL text. Queries
have driver timeouts and cooperative cancel/deadline checks. A faulty ODBC driver
or a factory ignoring its login timeout cannot be forcibly stopped in Python.

SQLite is an offline reference, with a read-only file connection, an authorizer
and a VM work budget. It supports ordinary tables in the main schema only.
Its numeric affinity does not provide SQL Server's fixed-point decimal accuracy.
Both adapters reject unregistered joins, arbitrary expressions and objects.
"""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import math
from pathlib import Path
import re
import sqlite3
from threading import BoundedSemaphore, Event, Thread
import time
from typing import Any, Callable

from sageql.errors import InvalidSQL
from sageql.sdk.models import (
    AdapterResult, EntityLabelDimension, ExecutionLimits, FullNameFilterDefinition, ReportField, SDKError, ValidatedReport,
)
from sageql.sdk.names import NAME_REPLACEMENTS, normalize_name
from sageql.sdk.semantics import column_type, validate_report
from sageql.validation import validate_sql


@dataclass(frozen=True)
class CompiledReport:
    """Developer diagnostic only; execution always recompiles the specification."""

    sql: str
    parameters: tuple[object, ...]
    fields: tuple[ReportField, ...]
    limit: int
    guarded: bool = False


def _quote(value: str, dialect: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise SDKError("invalid_catalog", "Registered identifier is invalid.")
    if dialect == "tsql":
        return "[" + value.replace("]", "]]") + "]"
    return '"' + value.replace('"', '""') + '"'


def _revalidate(report: ValidatedReport) -> None:
    if not isinstance(report, ValidatedReport):
        raise SDKError("invalid_spec", "A validated report specification is required.")
    canonical = validate_report(report.dataset, report.spec, report.access, today=report.as_of)
    from dataclasses import replace
    from sageql.sdk.relationships import validate_bound_relationships
    validate_bound_relationships(report)
    if canonical != replace(report, related_sources=()):
        raise SDKError("invalid_spec", "Resolved report differs from its validated specification.")


def _parameter(value: object, family: str, dialect: str) -> object:
    """Preserve typed ODBC bindings; adapt only the SQLite driver boundary."""
    if family == "decimal" and value is not None:
        value = value if isinstance(value, Decimal) else Decimal(str(value))
    elif family == "number" and value is not None:
        value = float(value)
    elif family == "date" and value is not None:
        value = value if type(value) is date else date.fromisoformat(value)
    if dialect == "sqlite":
        if isinstance(value, Decimal):
            return str(value)
        if type(value) is date:
            return value.isoformat()
    return value


def _bucket(expression: str, grain: str, dialect: str) -> str:
    if dialect == "tsql":
        if grain == "day":
            return f"CAST({expression} AS date)"
        if grain == "week":
            # Positive modulo also works for dates earlier than the Monday epoch.
            return (f"DATEADD(day, -((DATEDIFF(day, '19000101', {expression}) % 7 + 7) % 7), "
                    f"CAST({expression} AS date))")
        if grain == "month":
            return f"DATEFROMPARTS(YEAR({expression}), MONTH({expression}), 1)"
        if grain == "quarter":
            return f"DATEFROMPARTS(YEAR({expression}), ((DATEPART(quarter, {expression}) - 1) * 3) + 1, 1)"
        if grain == "year":
            return f"DATEFROMPARTS(YEAR({expression}), 1, 1)"
    else:
        if grain == "day":
            return f"date({expression})"
        if grain == "week":
            return f"date({expression}, '-' || ((CAST(strftime('%w', {expression}) AS INTEGER) + 6) % 7) || ' days')"
        if grain == "month":
            return f"date({expression}, 'start of month')"
        if grain == "quarter":
            return (f"printf('%04d-%02d-01', CAST(strftime('%Y', {expression}) AS INTEGER), "
                    f"((CAST(strftime('%m', {expression}) AS INTEGER) - 1) / 3) * 3 + 1)")
        if grain == "year":
            return f"date({expression}, 'start of year')"
    raise SDKError("unsupported", "This time grouping is unsupported.")


def compile_report(
    report: ValidatedReport, limits: ExecutionLimits, *, dialect: str,
) -> CompiledReport:
    """Revalidate and render SQL plus ordered typed parameters from trusted IDs."""
    if dialect not in {"tsql", "sqlite"}:
        raise SDKError("unsupported", "This database dialect is unsupported.")
    if not isinstance(limits, ExecutionLimits):
        raise SDKError("invalid_limits", "Explicit execution limits are required.")
    _revalidate(report)
    dataset, spec = report.dataset, report.spec
    dimension_listing = not spec.metric_ids
    if dialect == "sqlite" and (dataset.table.schema not in {"", "main"}
                                 or dataset.table.kind.upper() != "TABLE"):
        raise SDKError("unsupported", "SQLite reference reports require a table in the main schema.")
    columns = {column.name: column for column in dataset.columns}
    metrics = {item.id: item for item in dataset.metrics}
    dimensions = {item.id: item for item in dataset.dimensions}
    filters = {item.id: item for item in dataset.filters}
    fields: list[ReportField] = []
    group: list[str] = []
    selections: list[str] = []
    related_expressions = {}
    for index, bound in enumerate(report.related_sources):
        for field_index, (local, _) in enumerate(bound.column_pairs):
            related_expressions[local] = f"r{index}." + _quote(f"v{field_index}", dialect)

    def col(name: str) -> str:
        if name in related_expressions:
            return related_expressions[name]
        return "t." + _quote(name, dialect)

    if report.comparison_period:
        fields.append(ReportField("period_label", "Period", "text"))
    if spec.time_grain != "none":
        expression = _bucket(col(dataset.time.column), spec.time_grain, dialect)
        selections.append(expression + " AS " + _quote("time_bucket", dialect))
        group.append(expression)
        fields.append(ReportField("time_bucket", "Date", "date"))
    for identifier in spec.dimension_ids:
        dimension = dimensions[identifier]
        expression = col(dimension.column)
        selections.append(expression + " AS " + _quote(identifier, dialect))
        group.append(expression)
        fields.append(ReportField(identifier, dimension.label, column_type(columns[dimension.column].data_type)))
    aggregates = {"sum": "SUM", "average": "AVG", "minimum": "MIN", "maximum": "MAX"}
    for identifier in spec.metric_ids:
        metric = metrics[identifier]
        family = column_type(columns[metric.column].data_type) if metric.column else "integer"
        output_type = family
        if metric.aggregation == "count_rows":
            expression = "COUNT_BIG(*)" if dialect == "tsql" else "COUNT(*)"
            output_type = "integer"
        elif metric.aggregation == "count_distinct":
            function = "COUNT_BIG" if dialect == "tsql" else "COUNT"
            expression = f"{function}(DISTINCT {col(metric.column)})"
            output_type = "integer"
        else:
            argument = col(metric.column)
            if metric.aggregation in {"sum", "average"} and family == "integer":
                output_type = "decimal"
                if dialect == "tsql":
                    scale = 6 if metric.aggregation == "average" else 0
                    argument = f"CAST({argument} AS decimal(38,{scale}))"
            expression = f"{aggregates[metric.aggregation]}({argument})"
        selections.append(expression + " AS " + _quote(identifier, dialect))
        fields.append(ReportField(identifier, metric.label, output_type, metric.unit))
    table = _quote(dataset.table.name, dialect)
    schema = dataset.table.schema or ("dbo" if dialect == "tsql" else "")
    if schema:
        table = _quote(schema, dialect) + "." + table
    limit = min(spec.limit, limits.max_rows)
    parameters: list[object] = [limit + 1] if dialect == "tsql" else []

    def bind(value: object, family: str) -> str:
        parameters.append(_parameter(value, family, dialect))
        return "?"

    operators = {"eq": "=", "neq": "<>", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}

    ctes = []
    joins = []
    guards = []
    for index, bound in enumerate(report.related_sources):
        source = bound.source
        if dialect == "sqlite" and (source.table.schema not in {"", "main"}
                                      or source.table.kind != "TABLE"):
            raise SDKError("unsupported", "SQLite related sources require main-schema tables.")
        source_columns = {item.name: item for item in source.columns}
        keys = ["s." + _quote(remote, dialect) for _, remote in bound.definition.key_pairs]
        projected = [expression + " AS " + _quote(f"k{i}", dialect) for i, expression in enumerate(keys)]
        for i, (_, remote) in enumerate(bound.column_pairs):
            expression = "s." + _quote(remote, dialect)
            if column_type(source_columns[remote].data_type) == "boolean" and dialect == "tsql":
                expression = f"CAST({expression} AS int)"
            projected.append(f"MIN({expression}) AS " + _quote(f"v{i}", dialect))
        count = "COUNT_BIG(*)" if dialect == "tsql" else "COUNT(*)"
        projected.append(count + " AS " + _quote("__count", dialect))
        predicates = [expression + " IS NOT NULL" for expression in keys]
        for policy in bound.access.policies:
            expression = "s." + _quote(policy.column, dialect)
            family = column_type(source_columns[policy.column].data_type)
            if policy.operator in {"is_null", "is_not_null"}:
                predicates.append(expression + (" IS NULL" if policy.operator == "is_null" else " IS NOT NULL"))
            elif policy.operator == "in":
                predicates.append(expression + " IN (" + ", ".join(bind(value, family) for value in policy.values) + ")")
            else:
                predicates.append(expression + " " + operators[policy.operator] + " " + bind(policy.values[0], family))
        source_table = _quote(source.table.name, dialect)
        source_schema = source.table.schema or ("dbo" if dialect == "tsql" else "")
        if source_schema:
            source_table = _quote(source_schema, dialect) + "." + source_table
        ctes.append(f"r{index} AS (SELECT " + ", ".join(projected) + " FROM " + source_table
                    + " AS s WHERE " + " AND ".join(predicates) + " GROUP BY " + ", ".join(keys) + ")")
        join_keys = [col(local) + f" = r{index}." + _quote(f"k{i}", dialect)
                     for i, (local, _) in enumerate(bound.definition.key_pairs)]
        joins.append(f"LEFT JOIN r{index} ON " + " AND ".join(join_keys))
        guards.append(f"EXISTS (SELECT 1 FROM r{index} WHERE " + _quote("__count", dialect) + " > 1)")

    def condition(name: str, operator: str, values: tuple[object, ...]) -> str:
        expression = col(name)
        family = column_type(columns[name].data_type)
        if operator in {"is_null", "is_not_null"}:
            return expression + (" IS NULL" if operator == "is_null" else " IS NOT NULL")
        if operator == "in":
            return expression + " IN (" + ", ".join(bind(value, family) for value in values) + ")"
        return expression + " " + operators[operator] + " " + bind(values[0], family)

    def branch(label: str, period: Any) -> str:
        predicates = [condition(item.column, item.operator, item.values) for item in report.access.policies]
        for item in spec.filters:
            definition = filters[item.filter_id]
            if isinstance(definition, FullNameFilterDefinition):
                # Host-declared columns and fixed operations only. No names or
                # model expressions enter SQL text; the normalized name is bound.
                prefix = "N" if dialect == "tsql" else ""
                parts = [f"COALESCE({col(name)}, {prefix}'')" for name in definition.name_columns]
                if dialect == "tsql":
                    parts = [part + " COLLATE Latin1_General_100_BIN2" for part in parts]
                expression = "(" + (" + " if dialect == "tsql" else " || ").join(parts) + ")"
                for original, replacement in NAME_REPLACEMENTS:
                    expression = f"REPLACE({expression}, {prefix}'{original}', {prefix}'{replacement}')"
                expression += " COLLATE " + ("Latin1_General_100_BIN2" if dialect == "tsql" else "BINARY")
                predicates.append(expression + " = " + bind(normalize_name(item.values[0]), "text"))
            else:
                predicates.append(condition(definition.column, item.operator, item.values))
        if period.start is not None:
            expression = col(dataset.time.column)
            predicates += [expression + " >= " + bind(period.start, "date"),
                           expression + " < " + bind(period.end, "date")]
        selected = list(selections)
        if report.comparison_period:
            selected.insert(0, f"'{label}' AS " + _quote("period_label", dialect))
        sql = ("SELECT DISTINCT " if dimension_listing else "SELECT ") + ", ".join(selected) + "\nFROM " + table + " AS t"
        if joins:
            sql += "\n" + "\n".join(joins)
        if predicates:
            sql += "\nWHERE " + " AND ".join(predicates)
        if group and not dimension_listing:
            sql += "\nGROUP BY " + ", ".join(group)
        return sql

    body = branch("base", report.period)
    if report.comparison_period:
        body += "\nUNION ALL\n" + branch("comparison", report.comparison_period)
    # The cap applies to the entire result, including comparison branches.
    projection = ", ".join(_quote(item.id, dialect) for item in fields)
    if guards:
        projection += ", CASE WHEN " + " OR ".join(guards) + " THEN 1 ELSE 0 END AS " + _quote("__sageql_relation_guard", dialect)
    sql = ("SELECT TOP (?) " if dialect == "tsql" else "SELECT ") + projection
    sql += "\nFROM (\n" + body + "\n) AS report"
    aggregate_predicates = []
    for item in spec.aggregate_filters:
        expression = _quote(item.metric_id, dialect)
        family = next(field.type for field in fields if field.id == item.metric_id)

        def aggregate_bind(value):
            placeholder = bind(value, family)
            # Aggregate expressions have no SQLite column affinity. Decimal
            # driver strings need an explicit numeric cast for comparisons.
            return f"CAST({placeholder} AS NUMERIC)" if dialect == "sqlite" and family == "decimal" else placeholder

        if item.operator in {"is_null", "is_not_null"}:
            aggregate_predicates.append(expression + (" IS NULL" if item.operator == "is_null" else " IS NOT NULL"))
        elif item.operator == "in":
            aggregate_predicates.append(expression + " IN (" + ", ".join(aggregate_bind(value) for value in item.values) + ")")
        else:
            aggregate_predicates.append(expression + " " + operators[item.operator] + " " + aggregate_bind(item.values[0]))
    if aggregate_predicates:
        sql += "\nWHERE " + " AND ".join(aggregate_predicates)
    order: list[str] = []
    if spec.order_by:
        order.append(_quote(spec.order_by, dialect) + (" DESC" if spec.descending else " ASC"))
    tie_dimensions = list(spec.dimension_ids)
    if spec.order_by in spec.metric_ids:
        # A display-column reorder must not change tied entity top-N groups.
        # Labels still sort by their underlying identity before enrichment.
        tie_dimensions.sort(key=lambda key: not isinstance(dimensions[key], EntityLabelDimension))
    selected_ids = {item.id for item in fields}
    tie_ids = [key for key in ("period_label", "time_bucket", *tie_dimensions)
               if key in selected_ids and key != spec.order_by]
    order += [_quote(key, dialect) + " ASC" for key in tie_ids]
    if order:
        sql += "\nORDER BY " + ", ".join(order)
    if dialect == "sqlite":
        sql += "\nLIMIT ?"
        parameters.append(limit + 1)
    if ctes:
        sql = "WITH " + ",\n".join(ctes) + "\n" + sql
        # CTE policies precede SQL Server's TOP placeholder in textual bind order.
        if dialect == "tsql":
            source_parameters = sum(len(policy.values) for bound in report.related_sources
                                    for policy in bound.access.policies)
            parameters = [*parameters[1:1 + source_parameters], parameters[0], *parameters[1 + source_parameters:]]
    # Conservative portable budgets leave room for ODBC's prepared-call
    # bookkeeping and SQLite builds with the older 999-variable default.
    if len(parameters) > (2_000 if dialect == "tsql" else 900):
        raise SDKError("unsupported", "Report exceeds this adapter's parameter budget.")
    try:
        validate_sql(sql, dialect=dialect)
    except InvalidSQL:
        raise SDKError("invalid_query", "Compiled report did not pass SQL validation.") from None
    return CompiledReport(sql, tuple(parameters), tuple(fields), limit, bool(guards))


def _rows(query: CompiledReport, description: Any, fetched: Any) -> AdapterResult:
    if query.guarded:
        if (tuple(item[0] for item in description or ()) != (*[field.id for field in query.fields], "__sageql_relation_guard")
                or any(len(row) != len(query.fields) + 1 or type(row[-1]) not in (int, bool)
                       or row[-1] not in (0, 1) for row in fetched)):
            raise SDKError("execution_failed", "Database returned invalid related report fields.")
        if any(row[-1] for row in fetched):
            raise SDKError("relationship_cardinality", "Related source has multiple visible rows for a registered key.")
        description = description[:-1]
        fetched = [row[:-1] for row in fetched]
    if tuple(item[0] for item in description or ()) != tuple(field.id for field in query.fields):
        raise SDKError("execution_failed", "Database returned unexpected report fields.")
    normalized = []
    for row in fetched[:query.limit]:
        if len(row) != len(query.fields):
            raise SDKError("execution_failed", "Database returned an invalid report row.")
        values = []
        for field, value in zip(query.fields, row):
            try:
                if value is None:
                    pass
                elif field.type == "decimal":
                    if isinstance(value, bool) or not isinstance(value, (Decimal, int, float, str)):
                        raise ValueError
                    value = value if isinstance(value, Decimal) else Decimal(str(value))
                    if not value.is_finite():
                        raise ValueError
                elif field.type == "date":
                    if type(value) is str:
                        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                            raise ValueError
                        value = date.fromisoformat(value)
                    if type(value) is not date:
                        raise ValueError
                elif field.type == "integer":
                    if type(value) is not int:
                        raise ValueError
                elif field.type == "boolean":
                    if type(value) is int and value in (0, 1):
                        value = bool(value)
                    if type(value) is not bool:
                        raise ValueError
                elif field.type == "number":
                    if type(value) not in (int, float) or not math.isfinite(value):
                        raise ValueError
                elif field.type == "text":
                    if type(value) is not str or len(value) > 1_000_000:
                        raise ValueError
                elif field.type == "datetime":
                    if not isinstance(value, datetime):
                        raise ValueError
                else:
                    raise ValueError
            except (ValueError, TypeError, InvalidOperation):
                raise SDKError("serialization_failed", "Database returned an unsupported report value.") from None
            values.append(value)
        normalized.append(tuple(values))
    return AdapterResult(query.fields, tuple(normalized), len(fetched) > query.limit)


def _check_deadline(deadline: float, cancel: Event | None) -> None:
    if cancel is not None and not isinstance(cancel, Event):
        raise SDKError("invalid_input", "Cancellation must use a threading event.")
    if cancel is not None and cancel.is_set():
        raise SDKError("cancelled", "Report request was cancelled.", retryable=True)
    if time.monotonic() >= deadline:
        raise SDKError("query_timeout", "Report exceeded its execution time limit.", retryable=True)


def _cleanup(connection: Any, cursor: Any) -> bool:
    failed = False
    for owner, method in ((cursor, "close"), (connection, "rollback"), (connection, "close")):
        if owner is not None:
            try:
                getattr(owner, method)()
            except Exception:
                failed = True
    return failed


class SQLServerAdapter:
    """Explicit SQL Server adapter; no ODBC dialect inference or model SQL.

    The factory must provide a finite login timeout. This instance admits a
    bounded number of concurrent checkouts and never changes shared connection
    state. Each checkout must be dedicated to this report until close().
    """

    def __init__(self, connection_factory: Callable[[], Any], *, max_concurrent_queries: int = 4):
        if not callable(connection_factory) or type(max_concurrent_queries) is not int or not 1 <= max_concurrent_queries <= 100:
            raise ValueError("a connection factory and bounded concurrency are required")
        self._connect = connection_factory
        self._slots = BoundedSemaphore(max_concurrent_queries)

    def _verify_schema(self, cursor: Any, report: ValidatedReport) -> None:
        for dataset in (report.dataset, *(bound.source for bound in report.related_sources)):
            self._verify_dataset(cursor, dataset)

    def _verify_dataset(self, cursor: Any, dataset) -> None:
        physical_columns = tuple(column for column in dataset.columns if column.name not in dataset.related_columns)
        names = tuple(column.name for column in physical_columns)
        sql = (
            "SELECT c.name, ty.name, c.is_nullable, o.type, c.precision, c.scale "
            "FROM sys.columns AS c "
            "JOIN sys.objects AS o ON o.object_id = c.object_id "
            "JOIN sys.schemas AS s ON s.schema_id = o.schema_id "
            "JOIN sys.types AS ty ON ty.user_type_id = c.user_type_id "
            "WHERE s.name = ? AND o.name = ? AND o.type IN ('U', 'V') AND c.name IN ("
            + ", ".join("?" for _ in names) + ")"
        )
        cursor.execute(sql, dataset.table.schema or "dbo", dataset.table.name, *names)
        actual = cursor.fetchmany(len(names) + 1)
        by_name = {row[0]: row for row in actual}
        if len(actual) != len(names) or len(by_name) != len(names):
            raise SDKError("schema_drift", "Registered database schema is unavailable or has changed.")
        for column in physical_columns:
            row = by_name.get(column.name)
            if row is not None and isinstance(row[1], str) and row[1].strip().casefold() in {"text", "ntext"}:
                raise SDKError("unsupported", "SQL Server reporting requires modern text column types.")
            try:
                compatible = row is not None and column_type(row[1]) == column_type(column.data_type)
                expected_kind = "V" if dataset.table.kind.upper() == "VIEW" else "U"
                compatible = compatible and row[3].strip() == expected_kind
                compatible = compatible and (column.nullable or not bool(row[2]))
                if column.name in dataset.row_key:
                    compatible = compatible and not bool(row[2])
                declared = re.fullmatch(r"\s*(?:decimal|numeric)\s*\(\s*(\d+)\s*(?:,\s*(\d+)\s*)?\)\s*", column.data_type, re.I)
                if declared:
                    expected_precision = (int(declared[1]), int(declared[2] or 0))
                    compatible = compatible and (int(row[4]), int(row[5])) == expected_precision
            except (SDKError, TypeError, ValueError, AttributeError, IndexError):
                compatible = False
            if not compatible:
                raise SDKError("schema_drift", "Registered database schema is unavailable or has changed.")

    def execute(
        self, report: ValidatedReport, limits: ExecutionLimits, *, cancel: Event | None = None,
    ) -> AdapterResult:
        query = compile_report(report, limits, dialect="tsql")
        deadline = time.monotonic() + min(limits.query_timeout_seconds, limits.request_timeout_seconds)
        _check_deadline(deadline, cancel)
        if not self._slots.acquire(blocking=False):
            raise SDKError("database_busy", "Report database is busy; retry shortly.", retryable=True)
        connection = cursor = watcher = None
        done = Event()
        error = result = None
        try:
            connection = self._connect()
            _check_deadline(deadline, cancel)
            connection.timeout = max(1, math.ceil(deadline - time.monotonic()))
            cursor = connection.cursor()

            def watch() -> None:
                while not done.wait(0.01):
                    if (cancel is not None and cancel.is_set()) or time.monotonic() >= deadline:
                        try:
                            cursor.cancel()
                        except Exception:
                            pass
                        return

            watcher = Thread(target=watch, daemon=True, name="sageql-report-deadline")
            watcher.start()
            self._verify_schema(cursor, report)
            _check_deadline(deadline, cancel)
            # Recheck the specification after metadata verification, immediately
            # before issuing the canonical report query.
            if query != compile_report(report, limits, dialect="tsql"):
                raise SDKError("invalid_query", "Report changed during validation.")
            cursor.execute(query.sql, *query.parameters)
            fetched = cursor.fetchmany(query.limit + 1)
            _check_deadline(deadline, cancel)
            result = _rows(query, cursor.description, fetched)
        except SDKError as exc:
            error = exc
        except Exception:
            try:
                _check_deadline(deadline, cancel)
            except SDKError as exc:
                error = exc
            if error is None:
                if connection is None:
                    error = SDKError("database_unavailable", "The reporting database could not be reached. Check its connection and try again.", retryable=True)
                else:
                    error = SDKError("execution_failed", "SQL Server report execution failed.", retryable=True)
        finally:
            done.set()
            if watcher is not None:
                watcher.join(timeout=0.1)
            if error is not None and cursor is not None:
                try:
                    cursor.cancel()
                except Exception:
                    pass
            cleanup_failed = _cleanup(connection, cursor)
            self._slots.release()
        if error is not None:
            raise error from None
        if cleanup_failed:
            raise SDKError("execution_failed", "Report connection cleanup failed.", retryable=True)
        return result


class SQLiteAdapter:
    """Offline read-only table adapter with row, time and VM work bounds."""

    def __init__(self, database_path: str | Path, *, max_vm_steps: int = 1_000_000):
        if type(max_vm_steps) is not int or not 1_000 <= max_vm_steps <= 100_000_000:
            raise ValueError("max_vm_steps must be from 1000 to 100000000")
        self._path = database_path
        self._max_vm_steps = max_vm_steps

    def execute(
        self, report: ValidatedReport, limits: ExecutionLimits, *, cancel: Event | None = None,
    ) -> AdapterResult:
        query = compile_report(report, limits, dialect="sqlite")
        deadline = time.monotonic() + min(limits.query_timeout_seconds, limits.request_timeout_seconds)
        _check_deadline(deadline, cancel)
        try:
            path = Path(self._path).resolve(strict=True)
            if not path.is_file():
                raise OSError
        except (OSError, TypeError, ValueError):
            raise SDKError("database_unavailable", "SQLite reporting database is unavailable.") from None
        connection = cursor = None
        steps = 0
        work_exceeded = False
        error = result = None
        dataset = report.dataset
        datasets = (dataset, *(bound.source for bound in report.related_sources))
        allowed = {}
        for source_dataset in datasets:
            allowed.setdefault(source_dataset.table.name, set()).update(
                column.name for column in source_dataset.columns if column.name not in source_dataset.related_columns)

        def authorizer(action: int, arg1: Any, arg2: Any, db_name: Any, source: Any) -> int:
            if action == sqlite3.SQLITE_SELECT:
                return sqlite3.SQLITE_OK
            if action == sqlite3.SQLITE_READ:
                return (sqlite3.SQLITE_OK if db_name == "main" and arg1 in allowed
                        and (not arg2 or arg2 in allowed[arg1]) else sqlite3.SQLITE_DENY)
            if action == sqlite3.SQLITE_FUNCTION:
                return (sqlite3.SQLITE_OK if (arg2 or "").casefold() in
                        {"sum", "avg", "min", "max", "count", "date", "strftime", "printf", "replace", "coalesce"}
                        else sqlite3.SQLITE_DENY)
            return sqlite3.SQLITE_DENY

        def progress() -> int:
            nonlocal steps, work_exceeded
            steps += 1_000
            work_exceeded = steps > self._max_vm_steps
            return int(work_exceeded or time.monotonic() >= deadline or (cancel is not None and cancel.is_set()))

        try:
            connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True,
                                         timeout=max(0.001, min(1.0, deadline - time.monotonic())))
            connection.execute("PRAGMA query_only = ON").close()
            connection.execute("PRAGMA trusted_schema = OFF").close()
            for source_dataset in datasets:
                _verify_sqlite_dataset(connection, source_dataset)
            connection.set_authorizer(authorizer)
            connection.set_progress_handler(progress, 1_000)
            _check_deadline(deadline, cancel)
            if query != compile_report(report, limits, dialect="sqlite"):
                raise SDKError("invalid_query", "Report changed during validation.")
            cursor = connection.execute(query.sql, query.parameters)
            fetched = cursor.fetchmany(query.limit + 1)
            _check_deadline(deadline, cancel)
            result = _rows(query, cursor.description, fetched)
        except SDKError as exc:
            error = exc
        except sqlite3.Error:
            try:
                _check_deadline(deadline, cancel)
            except SDKError as exc:
                error = exc
            if error is None:
                error = (SDKError("query_work_limit", "Report exceeded its database work limit.", retryable=True)
                         if work_exceeded else SDKError("execution_failed", "SQLite report execution failed.", retryable=True))
        finally:
            cleanup_failed = _cleanup(connection, cursor)
        if error is not None:
            raise error from None
        if cleanup_failed:
            raise SDKError("execution_failed", "Report connection cleanup failed.", retryable=True)
        return result


def _verify_sqlite_dataset(connection, dataset):
    with closing(connection.execute("SELECT type FROM sqlite_schema WHERE name = ?", (dataset.table.name,))) as metadata_cursor:
        actual = metadata_cursor.fetchall()
    if actual != [("table",)]:
        raise SDKError("schema_drift", "Registered SQLite table is unavailable or has changed.")
    with closing(connection.execute("PRAGMA table_info(" + _quote(dataset.table.name, "sqlite") + ")")) as metadata_cursor:
        metadata = metadata_cursor.fetchall()
    by_name = {row[1]: row for row in metadata}
    primary_key_columns = [row for row in metadata if row[5]]
    for column in dataset.columns:
        if column.name in dataset.related_columns:
            continue
        row = by_name.get(column.name)
        try:
            compatible = row is not None and column_type(row[2]) == column_type(column.data_type)
            # Only a single INTEGER PRIMARY KEY is an implicit non-null
            # rowid alias; ordinary SQLite primary keys can contain null.
            nonnull = (bool(row[3]) or (len(primary_key_columns) == 1 and bool(row[5])
                                      and row[2].strip().casefold() == "integer")) if row else False
            compatible = compatible and (column.nullable or nonnull)
            if column.name in dataset.row_key:
                compatible = compatible and nonnull
        except (SDKError, TypeError, ValueError, AttributeError, IndexError):
            compatible = False
        if not compatible:
            raise SDKError("schema_drift", "Registered SQLite schema is unavailable or has changed.")
