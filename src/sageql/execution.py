"""Bounded read-only execution of validated SQLite report queries."""

import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from sageql.context import ResolvedContext
from sageql.discovery import QuerySpace
from sageql.planning import QueryPlan
from sageql.report_validation import RequiredFilter, validate_report_query
from sageql.sql_generation import SQLQuery


class QueryExecutionError(Exception):
    """The report query could not be executed safely."""


@dataclass(frozen=True)
class QueryResult:
    columns: tuple[str, ...]
    rows: tuple[tuple[object, ...], ...]
    truncated: bool


_ALLOWED_FUNCTIONS = {
    "strftime", "date", "printf", "sum", "count", "avg", "min", "max",
}


def _readonly_uri(path: str | Path) -> str:
    try:
        resolved = Path(path).resolve(strict=True)
        if not resolved.is_file():
            raise OSError
        return resolved.as_uri() + "?mode=ro"
    except (OSError, TypeError, ValueError) as exc:
        raise QueryExecutionError("SQLite database file is unavailable") from exc


def _identifier(value: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise QueryExecutionError("invalid SQLite schema name")
    return '"' + value.replace('"', '""') + '"'


def execute_sqlite_report(
    database_path: str | Path,
    query: SQLQuery,
    plan: QueryPlan,
    context: ResolvedContext,
    space: QuerySpace,
    *,
    attached_schemas: Mapping[str, str | Path] | None = None,
    required_filters: tuple[RequiredFilter, ...] = (),
    max_rows: int = 500,
    timeout_seconds: float = 5.0,
    max_vm_steps: int = 1_000_000,
) -> QueryResult:
    """Run a validated SELECT on read-only SQLite files with access limits.

    This function never accepts an existing read-write connection. Schema
    aliases must be mapped explicitly to read-only database files.
    """
    if (not isinstance(max_rows, int) or isinstance(max_rows, bool) or not 1 <= max_rows <= 10_000
            or not isinstance(timeout_seconds, (int, float)) or not 0 < timeout_seconds <= 60
            or not isinstance(max_vm_steps, int) or isinstance(max_vm_steps, bool)
            or not 1_000 <= max_vm_steps <= 100_000_000):
        raise QueryExecutionError("invalid execution limits")
    validation = validate_report_query(
        query, plan, context, space, required_filters=required_filters
    )
    if not validation.valid:
        raise QueryExecutionError("query did not pass validation: " + " ".join(validation.issues))

    attachments = dict(attached_schemas or {})
    needed_schemas = {table.schema for table in (plan.base_table, *(join.to_table for join in plan.joins))
                      if table.schema}
    if (set(attachments) != needed_schemas
            or any(name.casefold() in {"main", "temp"} for name in attachments)
            or len({name.casefold() for name in attachments}) != len(attachments)):
        raise QueryExecutionError("provide one read-only SQLite file for each selected schema")
    main_uri = _readonly_uri(database_path)
    attach_uris = {name: _readonly_uri(path) for name, path in attachments.items()}

    allowed_tables = {
        (table.schema or "main", table.name) for table in space.tables
    }
    allowed_columns = {
        (column.table.rpartition(".")[0] or "main",
         column.table.rpartition(".")[2] or column.table,
         column.name)
        for column in space.columns
    }
    deadline = time.monotonic() + timeout_seconds
    steps = 0
    interrupted = False

    def authorizer(action, arg1, arg2, db_name, source):
        if action == sqlite3.SQLITE_SELECT:
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_FUNCTION:
            return sqlite3.SQLITE_OK if (arg2 or "").casefold() in _ALLOWED_FUNCTIONS else sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_READ:
            table = (db_name, arg1)
            if table not in allowed_tables:
                return sqlite3.SQLITE_DENY
            if arg2 and (db_name, arg1, arg2) not in allowed_columns:
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY

    def progress():
        nonlocal steps, interrupted
        steps += 1_000
        if steps > max_vm_steps or time.monotonic() >= deadline:
            interrupted = True
            return 1
        return 0

    try:
        with closing(sqlite3.connect(main_uri, uri=True, timeout=1.0)) as connection:
            for name, uri in attach_uris.items():
                connection.execute(f"ATTACH DATABASE ? AS {_identifier(name)}", (uri,))
            connection.execute("PRAGMA query_only = ON")
            connection.execute("PRAGMA trusted_schema = OFF")
            connection.set_authorizer(authorizer)
            connection.set_progress_handler(progress, 1_000)
            with closing(connection.execute(query.sql, dict(query.parameters))) as cursor:
                columns = tuple(item[0] for item in cursor.description or ())
                fetched = cursor.fetchmany(max_rows + 1)
            return QueryResult(columns, tuple(tuple(row) for row in fetched[:max_rows]),
                               len(fetched) > max_rows)
    except sqlite3.Error as exc:
        if interrupted:
            raise QueryExecutionError("query exceeded its time or work limit") from exc
        raise QueryExecutionError("SQLite report query failed") from exc
