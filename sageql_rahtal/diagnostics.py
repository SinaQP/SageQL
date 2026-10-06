"""Local test-host diagnostics; never forwarded to the interpreter.

Only deterministic SQL may include physical identifiers in these explicitly
requested local traces. Messages, returned rows, credentials and scalar filter
values are excluded. The host keeps traces under ignored private state.
"""

from contextvars import ContextVar
from datetime import date, datetime, timezone
import json
from pathlib import Path
import time
from uuid import uuid4

from sageql.sdk import SageQL, SQLServerAdapter
from sageql.sdk.adapters import compile_report
from sageql.sdk.models import Interpretation, SDKError


_trace = ContextVar("rahtal_trace", default=None)


class Trace:
    def __init__(self, directory: Path):
        self.started = time.monotonic()
        self.path = directory / (uuid4().hex + ".json")
        self.data = {"id": self.path.stem, "started_at": datetime.now(timezone.utc).isoformat(),
                     "events": [], "saved": False}

    def event(self, stage, status, **details):
        elapsed = round((time.monotonic() - self.started) * 1000)
        if status != "started":
            previous = next((item for item in reversed(self.data["events"])
                             if item["stage"] == stage and item["status"] == "started"), None)
            if previous:
                details["duration_ms"] = elapsed - previous["elapsed_ms"]
        self.data["events"].append({"stage": stage, "status": status,
                                    "elapsed_ms": elapsed,
                                    **details})
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.data["saved"] = True
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(self.path)
        except OSError:
            # Diagnostics must never cause a successful report to fail/reexecute.
            self.data["saved"] = False


def event(stage, status, **details):
    trace = _trace.get()
    if trace is not None:
        trace.event(stage, status, **details)


class DiagnosticSageQL(SageQL):
    def submit_with_diagnostics(self, *args, **kwargs):
        trace = Trace(self.diagnostics_directory)
        token = _trace.set(trace)
        try:
            event("request", "started", note="Checking input, access, session revision and retry receipt.")
            reply = self.submit(*args, **kwargs)
            ran_provider = any(item["stage"] == "interpretation" for item in trace.data["events"])
            if not ran_provider and reply.error is None:
                event("retry", "cached", note="Saved reply reused; no model or database query ran on this attempt.")
            details = {"revision": reply.revision, "reply_status": reply.status}
            if reply.error:
                details["error"] = reply.error
                details["note"] = "Check the last started stage; no raw provider/driver errors are logged."
            elif reply.report is not None:
                details.update(row_count=len(reply.report.rows), truncated=reply.report.truncated)
                if not reply.report.rows:
                    details["note"] = (
                        "The validated SELECT returned zero rows, not a resource-not-found error. "
                        "Inspect the selected dataset, user filters, date bounds and mandatory policies. "
                        "This trace cannot determine which condition excluded rows; no unfiltered probe was run."
                    )
            elif reply.status == "needs_clarification":
                details["note"] = "A clarification is needed; no report SQL was executed."
            event("request", "failed" if reply.error else "complete", **details)
            payload = reply.to_dict()
            payload["diagnostics"] = trace.data
            return payload
        finally:
            _trace.reset(token)


class DiagnosticInterpreter:
    def __init__(self, provider):
        self.provider = provider

    def interpret(self, messages, current, catalog, today):
        event("interpretation", "started", message_count=len(messages),
              refinement=current is not None, datasets=[item.id for item in catalog.datasets])
        try:
            decision = self.provider.interpret(messages, current, catalog, today)
        except Exception:
            event("interpretation", "failed", note="Interpreter failed; raw model/transport details excluded.")
            raise
        status = decision.status if isinstance(decision, Interpretation) else "invalid"
        # Do not log model text or the unvalidated specification.
        event("interpretation", "complete", decision=status if status in
              {"ready", "unsupported", "needs_clarification"} else "invalid")
        if status == "ready":
            event("validation", "started", note="Checking registered concepts, types, dates and current policies.")
        return decision


class DiagnosticCursor:
    def __init__(self, cursor):
        self.cursor = cursor
        self.report_query = False

    def __getattr__(self, name):
        return getattr(self.cursor, name)

    def execute(self, sql, *parameters):
        # Both statements still originate exclusively in the original adapter.
        metadata = "FROM sys.columns AS c" in sql
        if not metadata:
            self.report_query = True
            event("sql_execution", "started", sql=sql, parameters=[
                {"position": index, "type": type(value).__name__,
                 "value": value.isoformat() if type(value) is date else
                 value if type(value) is bool or index == 1 else "[redacted]"}
                for index, value in enumerate(parameters, 1)
            ], note="Bound parameters are in placeholder order. Personal/filter values are redacted.")
        else:
            event("metadata_sql", "started", sql=sql,
                  parameter_count=len(parameters), note="Registered metadata lookup; identifier binds omitted.")
        result = self.cursor.execute(sql, *parameters)
        if self.report_query:
            event("sql_execution", "complete")
        else:
            event("metadata_sql", "complete")
        return result

    def fetchmany(self, size):
        if self.report_query:
            event("fetch", "started", max_rows=size)
        rows = self.cursor.fetchmany(size)
        if self.report_query:
            event("fetch", "complete", fetched_row_count=len(rows))
        return rows


class DiagnosticConnection:
    def __init__(self, connection):
        self.connection = connection

    def __getattr__(self, name):
        return getattr(self.connection, name)

    @property
    def timeout(self):
        return self.connection.timeout

    @timeout.setter
    def timeout(self, value):
        self.connection.timeout = value

    def cursor(self):
        return DiagnosticCursor(self.connection.cursor())

    def rollback(self):
        event("rollback", "started")
        self.connection.rollback()
        event("rollback", "complete")

    def close(self):
        event("connection_close", "started")
        self.connection.close()
        event("connection_close", "complete")


class DiagnosticSQLServerAdapter(SQLServerAdapter):
    def __init__(self, connection_factory, **kwargs):
        def connect():
            event("connection", "started")
            connection = connection_factory()
            event("connection", "complete")
            return DiagnosticConnection(connection)
        super().__init__(connect, **kwargs)

    def _verify_schema(self, cursor, report):
        event("metadata", "started", dataset=report.dataset.id)
        super()._verify_schema(cursor, report)
        event("metadata", "complete", note="Registered columns and SQL types match the live source.")

    def execute(self, report, limits, *, cancel=None):
        event("database", "started")
        spec = report.spec
        event("validation", "complete", dataset=report.dataset.id,
              metrics=list(spec.metric_ids), dimensions=list(spec.dimension_ids),
              filters=[{"id": item.filter_id, "operator": item.operator,
                        "value_count": len(item.values), "values": "[redacted]"} for item in spec.filters],
              policies=[{"column": item.column, "operator": item.operator,
                         "values": [value if type(value) is bool else "[redacted]" for value in item.values]}
                        for item in report.access.policies],
              period={"start": report.period.start.isoformat() if report.period.start else None,
                      "end_exclusive": report.period.end.isoformat() if report.period.end else None},
              comparison={"start": report.comparison_period.start.isoformat(),
                          "end_exclusive": report.comparison_period.end.isoformat()}
                         if report.comparison_period else None,
              time_grain=spec.time_grain, order_by=spec.order_by, descending=spec.descending,
              chart=spec.chart, limit=min(spec.limit, limits.max_rows))
        event("compilation", "started")
        query = compile_report(report, limits, dialect="tsql")
        event("compilation", "complete", sql=query.sql,
              note="Deterministic SQL compiled; execution has not yet started.")
        try:
            result = super().execute(report, limits, cancel=cancel)
        except SDKError as exc:
            event("database", "failed", error_code=exc.code, retryable=exc.retryable)
            raise
        event("database", "complete", row_count=len(result.rows), truncated=result.truncated,
              note="Query, result decoding and connection cleanup completed. Result rows are not logged.")
        return result
