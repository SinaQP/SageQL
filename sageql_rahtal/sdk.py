"""Trusted local Rahtal host configuration for the embedded reporting SDK.

This integration reads the same database/model settings as the diagnostic
pilot, registers only its approved activity and employee-profile columns, and
never discovers or exposes arbitrary tables. It is an administrator's local
demo, not an application-wide employee authorization policy.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import re
import secrets
from typing import Any

from dotenv import dotenv_values

from sageql.conversation import LLMConfig
from sageql.schema import Column, Table
from sageql.sdk import (
    AccessScope, ActorContext, DatasetAccess, DatasetDefinition,
    DimensionDefinition, EntityLookupDefinition, ExecutionLimits, FilterDefinition,
    FullNameFilterDefinition, LookupQualifier, MetricDefinition,
    ReportingCatalog, RowPolicy, SDKError, SQLServerAdapter, SageQL,
    SessionStore, TimeDefinition,
)
from sageql.sdk.agents import OpenAIReportAgent


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LEGACY_ENV = Path("D:/Coding/QuerySmith/rahtal/.env")
DJANGO_ENV = ROOT.parent / "rahtal-be" / ".env"
_TOKEN = re.compile(r"[A-Za-z0-9_-]{32,128}\Z")
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,127}\Z")
_REQUIRED = (
    "RAHTAL_DB_SERVER", "RAHTAL_DB_DATABASE", "RAHTAL_DB_USERNAME",
    "RAHTAL_DB_PASSWORD", "RAHTAL_LLM_API_KEY", "RAHTAL_LLM_BASE_URL",
    "RAHTAL_LLM_MODEL",
)


def rahtal_reporting_catalog(schema: str = "dbo") -> ReportingCatalog:
    """Register existing pilot sources; no join or custom view is required.

    Activity durations are Rahtal's floating-point hours. Employee names are
    resolved through a registered profile name lookup before activity reports.
    Each query still uses one source; profile duplicates cannot multiply totals.
    """
    if not isinstance(schema, str) or not _IDENTIFIER.fullmatch(schema):
        raise ValueError("RAHTAL_DB_SCHEMA must be a simple schema name.")
    activity = Table("functionality_activities", schema)
    person = Table("persons_person", schema)
    activity_columns = tuple(Column(activity.key, name, kind, nullable=name != "id")
                             for name, kind in (
                                 ("id", "int"), ("user_id", "int"),
                                 ("date", "date"), ("time", "float"),
                                 ("is_deleted", "bit"),
                             ))
    person_columns = tuple(Column(person.key, name, kind) for name, kind in (
        ("user_id", "int"), ("first_name", "nvarchar"),
        ("last_name", "nvarchar"), ("job_position", "nvarchar"),
        ("is_deleted", "bit"),
    ))
    return ReportingCatalog((
        DatasetDefinition(
            "activities", "فعالیت‌های کاری کارکنان",
            activity, activity_columns,
            metrics=(
                MetricDefinition("activity_hours", "ساعات فعالیت", "sum", "time", "ساعت"),
                MetricDefinition("average_activity_hours", "میانگین ساعات هر فعالیت", "average", "time", "ساعت"),
                MetricDefinition("activity_count", "تعداد فعالیت‌های ثبت‌شده", "count_rows"),
            ),
            dimensions=(DimensionDefinition("employee_id", "شناسه کارمند", "user_id"),),
            filters=(FilterDefinition("employee_id_filter", "شناسه کارمند", "user_id"),),
            time=TimeDefinition("date", timezone="Asia/Tehran"),
            row_key=("id",), version="rahtal-activities-v1",
        ),
        DatasetDefinition(
            "employees", "مشخصات کارکنان",
            person, person_columns,
            metrics=(MetricDefinition("employee_count", "تعداد پروفایل کارکنان", "count_rows"),),
            dimensions=(
                DimensionDefinition("first_name", "نام", "first_name"),
                DimensionDefinition("last_name", "نام خانوادگی", "last_name"),
                DimensionDefinition("job_position", "سمت شغلی", "job_position"),
                DimensionDefinition("employee_id", "شناسه کارمند", "user_id"),
            ),
            filters=(
                FilterDefinition("first_name_filter", "نام", "first_name"),
                FilterDefinition("last_name_filter", "نام خانوادگی", "last_name"),
                FilterDefinition("job_position_filter", "سمت شغلی", "job_position"),
                FilterDefinition("employee_id_filter", "شناسه کارمند", "user_id"),
                FullNameFilterDefinition("employee_full_name_filter", "نام کامل کارمند", "first_name",
                                         ("eq",), ("first_name", "last_name")),
            ),
            version="rahtal-employees-v2",
        ),
    ), version="rahtal-local-v2", lookups=(EntityLookupDefinition(
        "employee_name_filter", "نام کامل کارمند", "activities", "employee_id_filter",
        "employees", "employee_id", "employee_full_name_filter",
        qualifiers=(LookupQualifier("employee_job_filter", "سمت شغلی", "job_position_filter"),),
    ),))


def find_rahtal_env(env_path: str | Path | None = None) -> Path | None:
    """Choose only the explicit file or established local pilot locations."""
    explicit = env_path if env_path is not None else os.environ.get("RAHTAL_ENV_FILE")
    if explicit is not None:
        path = Path(explicit).expanduser()
        if not path.is_file():
            raise ValueError("The configured Rahtal environment file is unavailable.")
        return path
    return next((path for path in (HERE / ".env", ROOT / ".env", DJANGO_ENV, LEGACY_ENV)
                 if path.is_file()), None)


def _load_settings(env_path: str | Path | None) -> dict[str, str]:
    path = find_rahtal_env(env_path)
    values = {key: value for key, value in (dotenv_values(path).items() if path else ())
              if isinstance(value, str) and value}
    values.update({key: value for key, value in os.environ.items()
                   if key.startswith("RAHTAL_") and value})
    # The reference host's token may be shared with its generic SQL Server mode.
    if os.environ.get("SAGEQL_HOST_TOKEN") and not values.get("RAHTAL_HOST_TOKEN"):
        values["RAHTAL_HOST_TOKEN"] = os.environ["SAGEQL_HOST_TOKEN"]
    # The existing adjacent Rahtal Django project uses DB_* and AVALAI_*
    # settings. Map these documented names locally, without importing Django
    # settings or forwarding its unrelated environment to the interpreter.
    django_aliases = {
        "RAHTAL_DB_SERVER": "DB_HOST", "RAHTAL_DB_DATABASE": "DB_NAME",
        "RAHTAL_DB_USERNAME": "DB_USERNAME", "RAHTAL_DB_PASSWORD": "DB_PASSWORD",
        "RAHTAL_LLM_API_KEY": "AVALAI_API_KEY",
        "RAHTAL_LLM_BASE_URL": "AVALAI_BASE_URL",
    }
    django_mode = any(values.get(alias) for alias in django_aliases.values())
    host_from_django = not values.get("RAHTAL_DB_SERVER") and bool(values.get("DB_HOST"))
    for name, alias in django_aliases.items():
        if not values.get(name) and values.get(alias):
            values[name] = values[alias]
    if host_from_django and values.get("DB_PORT"):
        port = values["DB_PORT"]
        if not re.fullmatch(r"\d{1,5}", port) or not 1 <= int(port) <= 65535:
            raise ValueError("DB_PORT must be a valid SQL Server port.")
        if "," not in values["RAHTAL_DB_SERVER"]:
            values["RAHTAL_DB_SERVER"] += "," + port
    if django_mode:
        values.setdefault("RAHTAL_LLM_MODEL", "gpt-5-nano")
    missing = [key for key in _REQUIRED if not values.get(key, "").strip()]
    if missing:
        raise ValueError("Configure Rahtal settings in its .env or host environment: "
                         + ", ".join(missing))
    values.setdefault("RAHTAL_DB_DRIVER", "ODBC Driver 17 for SQL Server" if django_mode
                      else "ODBC Driver 18 for SQL Server")
    values.setdefault("RAHTAL_DB_SCHEMA", "dbo")
    if not _IDENTIFIER.fullmatch(values["RAHTAL_DB_SCHEMA"]):
        raise ValueError("RAHTAL_DB_SCHEMA must be a simple schema name.")
    return values


def _connect(settings: dict[str, str]) -> Any:
    """Provide a disposable lease with the pilot's finite login timeout."""
    try:
        import pyodbc
    except ImportError:
        raise SDKError("database_unavailable", "Install the sageql[odbc] extra.") from None

    def wrap(value: str) -> str:
        return "{" + value.replace("}", "}}") + "}"

    connection_string = ";".join((
        "DRIVER=" + wrap(settings["RAHTAL_DB_DRIVER"]),
        "SERVER=" + wrap(settings["RAHTAL_DB_SERVER"]),
        "DATABASE=" + wrap(settings["RAHTAL_DB_DATABASE"]),
        "UID=" + wrap(settings["RAHTAL_DB_USERNAME"]),
        "PWD=" + wrap(settings["RAHTAL_DB_PASSWORD"]),
        "ApplicationIntent=ReadOnly", "TrustServerCertificate=yes",
    ))
    try:
        return pyodbc.connect(connection_string, autocommit=False, timeout=5)
    except pyodbc.Error:
        raise SDKError(
            "database_unavailable",
            "I couldn't connect to Rahtal's database. Check the VPN/database connection, then try again.",
            retryable=True,
        ) from None


def create_rahtal_engine(
    env_path: str | Path | None = None, *, sessions: SessionStore | None = None,
    diagnostics_directory: Path | None = None,
) -> tuple[SageQL, ActorContext, str]:
    """Build the explicitly opted-in local SQL Server/model integration.

    Construction sends no model request and executes no query. The returned
    token must protect every HTTP operation in the loopback reference host.
    Identity and catalog are fixed host configuration, never request fields.
    Session persistence is optional and belongs in a host-controlled location;
    it can contain private names/report rows.
    """
    settings = _load_settings(env_path)
    token = settings.get("RAHTAL_HOST_TOKEN") or secrets.token_urlsafe(32)
    if not _TOKEN.fullmatch(token):
        raise ValueError("RAHTAL_HOST_TOKEN must contain 32 to 128 URL-safe characters.")
    subject = settings.get("RAHTAL_HOST_SUBJECT", "rahtal-local-admin")
    if not subject.strip() or len(subject) > 256 or "\x00" in subject:
        raise ValueError("RAHTAL_HOST_SUBJECT must be bounded nonempty text.")
    actor = ActorContext(subject, attributes={"reporting_role": "rahtal-local-admin"})
    scope = AccessScope(tuple(DatasetAccess(dataset_id, policies=(
        RowPolicy("is_deleted", "eq", (False,)),
    )) for dataset_id in ("activities", "employees")), version="rahtal-local-admin-v1")

    def policy(caller: ActorContext) -> AccessScope:
        if caller != actor:
            raise SDKError("access_denied", "Use the authenticated local Rahtal reporting principal.")
        return scope

    config = LLMConfig(settings["RAHTAL_LLM_API_KEY"], settings["RAHTAL_LLM_BASE_URL"],
                       settings["RAHTAL_LLM_MODEL"])
    engine_type, adapter_type = SageQL, SQLServerAdapter
    provider = OpenAIReportAgent(config, timeout_seconds=45)
    if diagnostics_directory is not None:
        from sageql_rahtal.diagnostics import (
            DiagnosticSageQL, DiagnosticSQLServerAdapter, DiagnosticInterpreter,
        )
        engine_type, adapter_type = DiagnosticSageQL, DiagnosticSQLServerAdapter
        provider = DiagnosticInterpreter(provider)
    engine = engine_type(
        catalog=rahtal_reporting_catalog(settings["RAHTAL_DB_SCHEMA"]),
        database=adapter_type(lambda: _connect(settings), max_concurrent_queries=2),
        provider=provider,
        policy=policy, sessions=sessions, execution="validated",
        # Iranian business dates currently use UTC+03:30; these are date-only
        # columns. This clock does not convert persisted timestamps/calendars.
        clock=lambda: datetime.now(timezone(timedelta(hours=3, minutes=30))).date(),
        limits=ExecutionLimits(max_rows=100, query_timeout_seconds=10,
                               request_timeout_seconds=65),
    )
    if diagnostics_directory is not None:
        engine.diagnostics_directory = Path(diagnostics_directory)
    return engine, actor, token
