"""Request-local consistent reads; no model SQL, configuration changes or retries."""
from contextlib import contextmanager
import math
from pathlib import Path
import sqlite3
from sqlite3 import SQLITE_OK
import sys
from threading import Event, Thread, get_ident
import time

from sageql.sdk.adapters import (
    _check_deadline, _cleanup, _rows, _sqlite_authorizer, _verify_sqlite_dataset, compile_report,
)
from sageql.sdk.models import ExecutionLimits, SDKError


# Only the current connection/database's capability is inspected. No physical
# identifiers, host identity or row data are selected or returned to a model.
SQL_SERVER_SNAPSHOT_STATE = (
    "SELECT s.transaction_isolation_level, d.snapshot_isolation_state "
    "FROM sys.dm_exec_sessions AS s CROSS JOIN sys.databases AS d "
    "WHERE s.session_id = @@SPID AND d.database_id = DB_ID()"
)


def unavailable():
    return SDKError("unsupported", "The requested snapshot consistency is unavailable.",
                    stage="database_execution", reason="consistency_unavailable", field="read_consistency")


def _limits(limits, cancel):
    if not isinstance(limits, ExecutionLimits):
        raise SDKError("invalid_input", "Execution limits are required.")
    deadline = time.monotonic() + limits.request_timeout_seconds
    _check_deadline(deadline, cancel)
    return deadline


def _trusted_sqlite_authorizer(*unused):
    # Python 3.10 cannot disable an authorizer with None. Only fixed metadata
    # statements/rollback run under this callback; canonical business SELECTs
    # always install the registered-source allowlist. mode=ro/query_only persist.
    return SQLITE_OK


class _ReadScope:
    def __init__(self, connection, limits, cancel, deadline):
        self.connection = connection
        self.limits = limits
        self.cancel = cancel
        self.deadline = deadline
        self.thread = get_ident()
        self.closed = self.failed = False

    def check(self):
        if self.closed or self.failed or get_ident() != self.thread:
            raise SDKError("execution_failed", "Report read scope is closed, failed or used from another thread.",
                           retryable=True, stage="database_execution", reason="read_scope")
        _check_deadline(self.deadline, self.cancel)

    @contextmanager
    def guard(self, limits, cancel):
        try:
            self.check()
            if limits != self.limits or (cancel is not None and cancel is not self.cancel):
                raise SDKError("invalid_input", "Read scope limits and cancellation cannot be replaced.")
            yield
        except BaseException:
            self.failed = True
            raise


class _SQLServerScope(_ReadScope):
    def __init__(self, adapter, *args):
        super().__init__(*args)
        self.adapter = adapter

    def statement(self, operation):
        deadline = min(self.deadline, time.monotonic() + self.limits.query_timeout_seconds)
        cursor = watcher = None
        done = Event()
        cleanup_failed = False
        try:
            self.check()
            if getattr(self.connection, "autocommit", None) is not False:
                raise unavailable()
            self.connection.timeout = max(1, math.ceil(deadline - time.monotonic()))
            cursor = self.connection.cursor()

            def watch():
                while not done.wait(0.01):
                    if (self.cancel is not None and self.cancel.is_set()) or time.monotonic() >= deadline:
                        try:
                            cursor.cancel()
                        except Exception:
                            pass
                        return

            watcher = Thread(target=watch, daemon=True, name="sageql-snapshot-deadline")
            watcher.start()
            result = operation(cursor, deadline)
            _check_deadline(deadline, self.cancel)
        except SDKError:
            raise
        except Exception:
            _check_deadline(deadline, self.cancel)
            raise SDKError("execution_failed", "SQL Server report execution failed.", retryable=True,
                           stage="database_execution", reason="query_failed") from None
        finally:
            failed = sys.exc_info()[0] is not None
            done.set()
            if watcher is not None and watcher.ident is not None:
                watcher.join(timeout=0.1)
                cleanup_failed = watcher.is_alive()
            if failed and cursor is not None:
                try:
                    cursor.cancel()
                except Exception:
                    pass
            cleanup_failed = _cleanup(None, cursor) or cleanup_failed
        if cleanup_failed:
            raise SDKError("execution_failed", "Report cursor cleanup failed.", retryable=True,
                           stage="database_execution", reason="cleanup")
        return result

    def verify(self):
        def inspect(cursor, deadline):
            cursor.execute(SQL_SERVER_SNAPSHOT_STATE)
            rows = cursor.fetchmany(2)
            try:
                state = tuple(rows[0]) if len(rows) == 1 else ()
            except (TypeError, IndexError):
                state = ()
            if state != (5, 1) or any(type(value) is not int for value in state):
                raise unavailable()
        self.statement(inspect)

    def execute(self, report, limits, *, cancel=None):
        with self.guard(limits, cancel):
            query = compile_report(report, limits, dialect="tsql")

            def query_rows(cursor, deadline):
                self.adapter._verify_schema(cursor, report)
                _check_deadline(deadline, self.cancel)
                if query != compile_report(report, limits, dialect="tsql"):
                    raise SDKError("invalid_query", "Report changed during validation.")
                _check_deadline(deadline, self.cancel)
                cursor.execute(query.sql, *query.parameters)
                return _rows(query, cursor.description, cursor.fetchmany(query.limit + 1))
            return self.statement(query_rows)


@contextmanager
def sql_server_read_scope(adapter, limits, *, cancel=None):
    deadline = _limits(limits, cancel)
    if adapter._snapshot_connect is None:
        raise unavailable()
    if not adapter._slots.acquire(blocking=False):
        raise SDKError("database_busy", "Report database is busy; retry shortly.", retryable=True)
    connection = scope = None
    try:
        try:
            connection = adapter._snapshot_connect()
        except Exception:
            raise SDKError("database_unavailable", "The reporting database could not be reached.", retryable=True,
                           stage="database_connection", reason="unavailable") from None
        scope = _SQLServerScope(adapter, connection, limits, cancel, deadline)
        scope.verify()
        yield scope
        scope.check()
    finally:
        failed = sys.exc_info()[0] is not None
        if scope is not None:
            scope.closed = True
        cleanup_failed = _cleanup(connection, None)
        adapter._slots.release()
        if cleanup_failed and not failed:
            raise SDKError("execution_failed", "Report connection cleanup failed.", retryable=True,
                           stage="database_execution", reason="cleanup")


class _SQLiteScope(_ReadScope):
    def __init__(self, adapter, *args):
        super().__init__(*args)
        self.adapter = adapter
        self.steps = 0
        self.work_exceeded = False
        self.query_deadline = self.deadline

    def progress(self):
        self.steps += 1000
        self.work_exceeded = self.steps > self.adapter._max_vm_steps
        return int(self.work_exceeded or time.monotonic() >= self.query_deadline
                   or (self.cancel is not None and self.cancel.is_set()))

    def execute(self, report, limits, *, cancel=None):
        with self.guard(limits, cancel):
            query = compile_report(report, limits, dialect="sqlite")
            self.query_deadline = min(self.deadline, time.monotonic() + limits.query_timeout_seconds)
            cursor = None
            try:
                if not self.connection.in_transaction:
                    raise SDKError("execution_failed", "Report read transaction is unavailable.", retryable=True)
                # Schema inspection is trusted fixed SQL; business SELECTs retain
                # the same per-report allowlist as ordinary adapter execution.
                self.connection.set_authorizer(_trusted_sqlite_authorizer)
                self.connection.set_progress_handler(self.progress, 1000)
                for dataset in (report.dataset, *(b.source for b in report.related_sources)):
                    _verify_sqlite_dataset(self.connection, dataset)
                self.connection.set_authorizer(_sqlite_authorizer(report))
                _check_deadline(self.query_deadline, self.cancel)
                if query != compile_report(report, limits, dialect="sqlite"):
                    raise SDKError("invalid_query", "Report changed during validation.")
                cursor = self.connection.execute(query.sql, query.parameters)
                result = _rows(query, cursor.description, cursor.fetchmany(query.limit + 1))
                _check_deadline(self.query_deadline, self.cancel)
            except SDKError:
                raise
            except Exception:
                _check_deadline(self.query_deadline, self.cancel)
                raise SDKError("query_work_limit" if self.work_exceeded else "execution_failed",
                               "SQLite report execution failed.", retryable=True) from None
            finally:
                failed = sys.exc_info()[0] is not None
                cleanup_failed = _cleanup(None, cursor)
            if cleanup_failed and not failed:
                raise SDKError("execution_failed", "Report cursor cleanup failed.", retryable=True)
            return result


@contextmanager
def sqlite_read_scope(adapter, limits, *, cancel=None):
    deadline = _limits(limits, cancel)
    try:
        path = Path(adapter._path).resolve(strict=True)
        if not path.is_file():
            raise OSError
    except (OSError, TypeError, ValueError):
        raise SDKError("database_unavailable", "SQLite reporting database is unavailable.") from None
    connection = scope = None
    try:
        try:
            connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True,
                timeout=max(0.001, min(1.0, limits.query_timeout_seconds, deadline-time.monotonic())))
            connection.execute("PRAGMA query_only = ON").close()
            connection.execute("PRAGMA trusted_schema = OFF").close()
            connection.execute("BEGIN").close()
        except sqlite3.Error:
            _check_deadline(deadline, cancel)
            raise SDKError("execution_failed", "SQLite read transaction is unavailable.", retryable=True) from None
        scope = _SQLiteScope(adapter, connection, limits, cancel, deadline)
        yield scope
        scope.check()
    finally:
        failed = sys.exc_info()[0] is not None
        if scope is not None:
            scope.closed = True
        cleanup_failed = False
        if connection is not None:
            for clear in (lambda: connection.set_authorizer(_trusted_sqlite_authorizer),
                          lambda: connection.set_progress_handler(None, 0)):
                try:
                    clear()
                except Exception:
                    cleanup_failed = True
        cleanup_failed = _cleanup(connection, None) or cleanup_failed
        if cleanup_failed and not failed:
            raise SDKError("execution_failed", "Report connection cleanup failed.", retryable=True)
