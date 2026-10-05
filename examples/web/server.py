"""Local reference host for the SageQL reporting SDK.

Run ``python examples/web/server.py --demo`` for synthetic, offline data.
Use ``--rahtal`` for the existing Rahtal database and model configuration.
Use ``--sqlserver`` for another explicitly registered SQL Server reporting view.
This loopback-only sample is an integration reference, not a production identity
provider. A production application supplies its own authenticated ActorContext.
"""

from __future__ import annotations

import argparse
from contextlib import closing
from dataclasses import replace
from datetime import date
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import sys
from tempfile import TemporaryDirectory
from threading import BoundedSemaphore
from typing import Any
from urllib.parse import urlsplit

from sageql.conversation import LLMConfig, Message
from sageql.schema import Column, Table
from sageql.sdk import (
    AccessScope, ActorContext, DatasetAccess, DatasetDefinition, DimensionDefinition,
    ExecutionLimits, FilterDefinition, Interpretation, MetricDefinition,
    PeriodSelection, ReportingCatalog, ReportSpec, RowPolicy, SDKError, TimeDefinition,
)
from sageql.sdk.adapters import SQLServerAdapter, SQLiteAdapter
from sageql.sdk.engine import SageQL
from sageql.sdk.provider import OpenAIReportInterpreter


_MONTHS = {name: index for index, name in enumerate((
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
), 1)}
_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{32,128}\Z")
_IDENTIFIER_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,127}\Z")
_MAX_BODY_BYTES = 16_384


class WorkspaceHTTPServer(ThreadingHTTPServer):
    """Keep one workspace owner per port, including on Windows."""

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            # Windows SO_REUSEADDR can let two listeners share a port. Their
            # different tokens then make authentication depend on the listener.
            self.allow_reuse_address = False
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def reporting_catalog(*, schema: str = "", table_name: str = "activities",
                      table_kind: str = "TABLE") -> ReportingCatalog:
    """Register one explicitly supported reporting table/view and business metric."""
    table = Table(table_name, schema, table_kind)
    columns = tuple(Column(table.key, name, kind) for name, kind in (
        ("id", "int"), ("tenant_id", "int"), ("employee", "nvarchar"),
        ("activity_date", "date"), ("hours", "decimal"), ("is_deleted", "int"),
    ))
    return ReportingCatalog((DatasetDefinition(
        "activities", "Activity reporting", table, columns,
        metrics=(MetricDefinition("activity_hours", "Activity hours", "sum", "hours", "hours"),),
        dimensions=(DimensionDefinition("employee", "Employee", "employee"),),
        filters=(FilterDefinition("employee_filter", "Employee", "employee"),),
        time=TimeDefinition("activity_date"), row_key=("id",),
    ),))


def activity_policy(actor: ActorContext) -> AccessScope:
    """The host supplies identity; conversations and request JSON never select it."""
    if not actor.tenant_id.isdigit():
        raise SDKError("access_denied", "Authenticated reporting tenant is required.")
    return AccessScope((DatasetAccess("activities", policies=(
        RowPolicy("tenant_id", "eq", (int(actor.tenant_id),)),
        RowPolicy("is_deleted", "eq", (0,)),
    )),), version="activity-policy-v1")


class DemoInterpreter:
    """A deliberately small deterministic interpreter for the offline example.

    This is not a substitute for the configured model interpreter. It recognizes
    a few documented activity-hour questions to exercise the real engine, policy,
    SQL compiler, adapter, sessions, and frontend without credentials.
    """

    def interpret(self, messages: tuple[Message, ...], current_spec: ReportSpec | None,
                  catalog: ReportingCatalog, today: date) -> Interpretation:
        latest = messages[-1].content.strip().lower()
        history = " ".join(item.content.lower() for item in messages if item.role == "user")
        if re.search(r"\b(sql|delete|drop|password|credential|tenant|bypass|ignore restrictions|profit|sales|average|median|percentage|compare)\b", latest):
            return Interpretation("unsupported", message="This workspace supports approved activity-hour reports only.")
        if current_spec is None and not re.search(r"\b(hour|hours|activity|activities)\b", history):
            return Interpretation("unsupported", message="Try asking for daily activity hours for September 2026.")
        spec = current_spec or ReportSpec("activities", ("activity_hours",))
        # The original question remains available while a clarification answer
        # supplies only the missing year or period.
        context = latest if current_spec is not None else history
        if (current_spec is not None and len(messages) > 2 and messages[-2].role == "assistant"
                and "which year" in messages[-2].content.lower()):
            previous = next((item.content.lower() for item in reversed(messages[:-1])
                             if item.role == "user"), "")
            context = previous + " " + latest
        month_matches = list(re.finditer(r"\b(" + "|".join(_MONTHS) + r")\b", context))
        month = _MONTHS[month_matches[-1].group(1)] if month_matches else None
        year_match = re.search(r"\b(20\d{2}|19\d{2})\b", context)
        year = int(year_match.group(1)) if year_match else None
        period = None
        if month is not None:
            if year is None:
                return Interpretation("needs_clarification", question="Which year should September cover?" if month == 9
                                      else "Which year should that month cover?")
            period = PeriodSelection("month", year=year, month=month)
        elif re.search(r"\ball (available )?(data|dates|time)|all time\b", context):
            period = PeriodSelection("all")
        else:
            for phrase, kind in (("last month", "last_month"), ("this month", "this_month"),
                                 ("last year", "last_year"), ("this year", "this_year"),
                                 ("last week", "last_week"), ("this week", "this_week"),
                                 ("yesterday", "yesterday"), ("today", "today")):
                if phrase in context:
                    period = PeriodSelection(kind)
                    break
            if period is None and year is not None:
                period = PeriodSelection("year", year=year)
        if period is None and current_spec is None:
            return Interpretation("needs_clarification", question="Which period should the report cover? You can also ask for all available data.")
        if period is not None:
            spec = replace(spec, period=period)
        if re.search(r"\b(by|group.*by) employee\b", context):
            spec = replace(spec, dimension_ids=("employee",), time_grain="none", chart="bar")
        elif re.search(r"\b(daily|by day|each day|per day)\b", context):
            spec = replace(spec, dimension_ids=(), time_grain="day", chart="line")
        elif re.search(r"\b(monthly|by month|each month|per month)\b", context):
            spec = replace(spec, dimension_ids=(), time_grain="month", chart="line")
        elif re.search(r"\b(total|ungrouped|one number)\b", latest):
            spec = replace(spec, dimension_ids=(), time_grain="none", chart="kpi")
        if "table" in latest:
            spec = replace(spec, chart="table")
        if "line chart" in latest:
            if spec.time_grain == "none":
                return Interpretation("needs_clarification", question="Should the line chart group activity hours by day or month?")
            spec = replace(spec, chart="line")
        if re.search(r"\b(only|filter|where|excluding|except)\b", latest):
            return Interpretation("unsupported", message="The offline demo supports period and grouping refinements. Use the configured model for employee filters.")
        if current_spec is not None and not re.search(
            r"\b(employee|daily|day|monthly|month|year|today|yesterday|week|total|table|chart|hours|activity)\b", latest,
        ) and month is None:
            return Interpretation("unsupported", message="Try grouping the report by employee or asking for a different month.")
        return Interpretation("ready", spec, message="Approved activity-hour report.")


def seed_demo(path: Path) -> None:
    """Synthetic values only; excluded tenant/deleted rows test mandatory policies."""
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute("CREATE TABLE activities (id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, "
                           "employee TEXT, activity_date DATE NOT NULL, hours DECIMAL NOT NULL, is_deleted INTEGER NOT NULL)")
        rows = []
        next_id = 1
        for day in range(1, 16):
            for employee, hours in (("Alex", 5 + day % 4 * .25), ("Sam", 3 + day % 3 * .5)):
                rows.append((next_id, 1, employee, f"2026-09-{day:02d}", hours, 0))
                next_id += 1
        rows.extend(((next_id, 2, "Other tenant", "2026-09-01", 9999, 0),
                     (next_id + 1, 1, "Deleted activity", "2026-09-01", 8888, 1)))
        connection.executemany("INSERT INTO activities VALUES (?, ?, ?, ?, ?, ?)", rows)


def create_demo_engine(path: Path) -> SageQL:
    seed_demo(path)
    return SageQL(catalog=reporting_catalog(), database=SQLiteAdapter(path),
                  provider=DemoInterpreter(), policy=activity_policy,
                  clock=lambda: date(2026, 10, 5), execution="validated",
                  limits=ExecutionLimits(max_rows=100, query_timeout_seconds=5,
                                         request_timeout_seconds=10))


def create_sqlserver_engine() -> tuple[SageQL, ActorContext, str]:
    """Read trusted process configuration only after explicit --sqlserver opt-in."""
    def required(name: str, *fallbacks: str) -> str:
        value = next((os.environ[key] for key in (name, *fallbacks)
                      if os.environ.get(key, "").strip()), "")
        if not value.strip():
            raise ValueError(f"Configure {name} in the host process before starting SQL Server mode.")
        return value

    connection_string = required("SAGEQL_SQLSERVER_CONNECTION_STRING")
    token = required("SAGEQL_HOST_TOKEN")
    if not _TOKEN_PATTERN.fullmatch(token):
        raise ValueError("SAGEQL_HOST_TOKEN must contain 32 to 128 URL-safe letters, digits, '-' or '_'.")
    actor = ActorContext(required("SAGEQL_HOST_SUBJECT"), required("SAGEQL_HOST_TENANT_ID"))
    activity_policy(actor)
    table_name = os.environ.get("SAGEQL_REPORT_TABLE", "sageql_activities_view")
    schema = os.environ.get("SAGEQL_REPORT_SCHEMA", "dbo")
    table_kind = os.environ.get("SAGEQL_REPORT_KIND", "VIEW").upper()
    if table_kind not in ("TABLE", "VIEW"):
        raise ValueError("SAGEQL_REPORT_KIND must be TABLE or VIEW.")
    if not _IDENTIFIER_PATTERN.fullmatch(table_name) or not _IDENTIFIER_PATTERN.fullmatch(schema):
        raise ValueError("Reporting schema and table must be explicitly registered simple identifiers.")
    config = LLMConfig(required("SAGEQL_API_KEY", "LLM_API_KEY", "OPENAI_API_KEY"),
                       os.environ.get("SAGEQL_BASE_URL") or os.environ.get("LLM_BASE_URL") or "https://api.openai.com/v1",
                       os.environ.get("SAGEQL_MODEL") or os.environ.get("LLM_MODEL") or "gpt-5-nano")
    try:
        import pyodbc
    except ImportError as exc:
        raise ValueError("Install the sageql[odbc,openai] extras for SQL Server mode.") from exc

    def connect():
        # Every checkout belongs to the adapter, which performs its own schema
        # verification, bounded execution, rollback, and resource cleanup.
        return pyodbc.connect(connection_string, autocommit=False, timeout=5)

    engine = SageQL(catalog=reporting_catalog(schema=schema, table_name=table_name, table_kind=table_kind),
                    database=SQLServerAdapter(connect),
                    provider=OpenAIReportInterpreter(config, timeout_seconds=25),
                    policy=activity_policy, execution="validated",
                    limits=ExecutionLimits(max_rows=100, query_timeout_seconds=10,
                                           request_timeout_seconds=40))
    return engine, actor, token


def _json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _bad_constant(value):
    raise ValueError("invalid JSON constant")


def handler_for(engine: SageQL, actor: ActorContext, *, mode: str, token: str = ""):
    """Build a host handler with identity and catalog entirely outside HTTP input."""
    if mode not in ("demo", "sqlserver", "rahtal") or (mode != "demo" and not _TOKEN_PATTERN.fullmatch(token)):
        raise ValueError("An explicit demo or authenticated SQL Server mode is required.")
    page = Path(__file__).with_name("index.html").read_bytes()
    budget = BoundedSemaphore(8)

    class Handler(BaseHTTPRequestHandler):
        server_version = "SageQLReference"

        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, format, *args):
            # The reference host does not log conversations or credentials.
            pass

        def _write(self, code: int, payload: Any, *, cookie: str | None = None):
            raw = payload if isinstance(payload, bytes) else json.dumps(payload, allow_nan=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8" if isinstance(payload, bytes)
                             else "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                             "style-src 'self' 'unsafe-inline'; img-src 'self'; connect-src 'self'; "
                             "frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            if cookie:
                self.send_header("Set-Cookie", cookie)
            self.end_headers()
            self.wfile.write(raw)

        def _error(self, code: int, machine_code: str, message: str):
            self._write(code, {"error": {"code": machine_code, "message": message}})

        def _trusted_origin(self) -> bool:
            port = self.server.server_port
            hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
            if self.headers.get("Host") not in hosts:
                self._error(403, "invalid_host", "Use the local reporting application address.")
                return False
            origin = self.headers.get("Origin")
            if origin and origin not in {"http://" + host for host in hosts}:
                self._error(403, "invalid_origin", "Cross-origin requests are not supported.")
                return False
            return True

        def _authenticated(self) -> bool:
            if mode == "demo":
                return True
            auth = self.headers.get("Authorization", "")
            supplied = auth[7:] if auth.startswith("Bearer ") else ""
            if not supplied:
                cookies = SimpleCookie()
                try:
                    cookies.load(self.headers.get("Cookie", ""))
                    if "sageql_host_token" in cookies:
                        supplied = cookies["sageql_host_token"].value
                except Exception:
                    supplied = ""
            if not hmac.compare_digest(supplied.encode("utf-8"), token.encode("utf-8")):
                self._error(401, "authentication_required", "Sign in with your host workspace access token.")
                return False
            return True

        def _read(self) -> dict[str, Any]:
            if self.headers.get("Transfer-Encoding") is not None:
                raise SDKError("invalid_request", "Chunked request bodies are not supported.")
            if self.headers.get_content_type() != "application/json":
                raise SDKError("invalid_request", "Send a JSON request body.")
            if len(self.headers.get_all("Content-Length", [])) != 1:
                raise SDKError("invalid_request", "Provide exactly one request body length.")
            length = self.headers.get("Content-Length", "")
            if not length.isdigit() or not 0 < int(length) <= _MAX_BODY_BYTES:
                raise SDKError("request_too_large", "Request body must be at most 16384 bytes.")
            raw = self.rfile.read(int(length))
            if len(raw) != int(length):
                raise SDKError("invalid_request", "Request body was incomplete.")
            try:
                data = json.loads(raw.decode("utf-8"), object_pairs_hook=_json_object,
                                  parse_constant=_bad_constant)
            except (ValueError, UnicodeError, RecursionError) as exc:
                raise SDKError("invalid_request", "Send a valid JSON object.") from exc
            if not isinstance(data, dict):
                raise SDKError("invalid_request", "Send a JSON object.")
            return data

        def do_GET(self):
            if not self._trusted_origin():
                return
            parsed = urlsplit(self.path)
            if parsed.query or parsed.fragment:
                self._error(400, "invalid_request", "Query parameters are not supported.")
                return
            if parsed.path == "/":
                self._write(200, page)
                return
            if parsed.path == "/config":
                self._write(200, {"mode": mode, "requires_auth": mode != "demo"})
                return
            if not self._authenticated():
                return
            try:
                match = re.fullmatch(r"/report-sessions/([a-f0-9]{32})", parsed.path)
                if match:
                    self._write(200, engine.get_session(match.group(1), actor))
                    return
                # Session ID is necessary to establish report ownership. The
                # browser never supplies an actor, tenant, policy, or connection.
                match = re.fullmatch(r"/report-sessions/([a-f0-9]{32})/reports/([a-f0-9]{32})", parsed.path)
                if match:
                    self._write(200, engine.get_report(match.group(1), match.group(2), actor).to_dict())
                    return
                self._error(404, "not_found", "Resource is unavailable.")
            except SDKError as exc:
                self._error(403 if exc.code == "access_denied" else 400, exc.code, str(exc))
            except Exception:
                self._error(500, "request_failed", "The host request could not complete.")

        def do_POST(self):
            if not self._trusted_origin():
                return
            if not budget.acquire(blocking=False):
                self._error(503, "host_busy", "The workspace is busy; retry shortly.")
                return
            try:
                parsed = urlsplit(self.path)
                if parsed.query or parsed.fragment:
                    raise SDKError("invalid_request", "Query parameters are not supported.")
                if parsed.path == "/auth" and mode != "demo":
                    data = self._read()
                    supplied = data.get("token")
                    if (set(data) != {"token"} or not isinstance(supplied, str)
                            or not hmac.compare_digest(supplied.encode("utf-8"), token.encode("utf-8"))):
                        self._error(401, "authentication_required", "The workspace access token is invalid.")
                        return
                    self._write(200, {"authenticated": True}, cookie=
                                f"sageql_host_token={token}; HttpOnly; SameSite=Strict; Path=/")
                    return
                if not self._authenticated():
                    return
                data = self._read()
                if parsed.path == "/report-sessions":
                    if data:
                        raise SDKError("invalid_request", "Session creation does not accept identity or configuration.")
                    self._write(201, engine.create_session(actor).to_dict())
                    return
                match = re.fullmatch(r"/report-sessions/([a-f0-9]{32})/messages", parsed.path)
                if match:
                    if set(data) != {"message", "request_id", "expected_revision"}:
                        raise SDKError("invalid_request", "Send only message, request_id, and expected_revision.")
                    reply = engine.submit(match.group(1), data["message"], actor,
                                          data["request_id"], data["expected_revision"])
                    self._write(200, reply.to_dict())
                    return
                self._error(404, "not_found", "Resource is unavailable.")
            except SDKError as exc:
                self._error(413 if exc.code == "request_too_large" else 400, exc.code, str(exc))
            except Exception:
                self._error(500, "request_failed", "The host request could not complete.")
            finally:
                budget.release()

    return Handler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--demo", action="store_true", help="Synthetic SQLite data and offline interpreter")
    mode.add_argument("--rahtal", action="store_true", help="Existing Rahtal SQL Server data and configured real model")
    mode.add_argument("--sqlserver", action="store_true", help="Explicit trusted SQL Server/model environment")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--env-file", type=Path, help="Explicit local host configuration file (Rahtal or SQL Server mode)")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("port must be from 1 to 65535")
    if args.env_file is not None:
        if args.demo:
            parser.error("--env-file is only available with --rahtal or --sqlserver")
        if not args.env_file.is_file():
            parser.error("--env-file must name an existing local file")
        if args.sqlserver:
            from dotenv import load_dotenv
            # Rahtal loads its own selected keys without injecting Django secrets
            # into the environment of the generic host.
            load_dotenv(dotenv_path=args.env_file, override=False)
    with TemporaryDirectory(prefix="sageql-web-demo-") as directory:
        server = None
        token_file = None
        try:
            if args.demo:
                engine = create_demo_engine(Path(directory) / "activities.sqlite")
                actor, token, selected = ActorContext("demo", "1"), "", "demo"
            elif args.rahtal:
                root = Path(__file__).resolve().parents[2]
                sys.path.insert(0, str(root))
                from sageql_rahtal.sdk import create_rahtal_engine
                private_state = root / ".venv" / "rahtal-web"
                private_state.mkdir(parents=True, exist_ok=True)
                from sageql.sdk import SQLiteSessionStore
                engine, actor, token = create_rahtal_engine(
                    args.env_file, sessions=SQLiteSessionStore(private_state / "sessions.sqlite"))
                token_file = private_state / "host-token.txt"
                selected = "rahtal"
            else:
                engine, actor, token = create_sqlserver_engine()
                selected = "sqlserver"
            server = WorkspaceHTTPServer(("127.0.0.1", args.port), handler_for(engine, actor, mode=selected, token=token))
            if token_file is not None:
                # A failed bind must leave a running workspace's token intact.
                token_file.write_text(token, encoding="utf-8")
                print(f"Local workspace access token saved to: {token_file}")
        except (ValueError, SDKError, OSError) as exc:
            if server is not None:
                server.server_close()
            parser.exit(2, f"Could not start reference host: {exc}\n")
        print(f"SageQL {selected} reference host: http://127.0.0.1:{args.port}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
