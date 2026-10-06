"""Rahtal frontend setup and approved SQL execution, entirely offline."""

from datetime import date
import sys
from types import SimpleNamespace

import pytest

from sageql.sdk import ActorContext, Interpretation, PeriodSelection, ReportSpec, SDKError, UserFilter
from sageql.sdk.provider import _metadata
from sageql.sdk.semantics import permitted_catalog, validate_catalog
from sageql.sdk.sessions import SQLiteSessionStore
from sageql_rahtal import sdk
from sageql_rahtal.catalog import daily_performance_catalog


@pytest.fixture(autouse=True)
def isolated_configuration(monkeypatch):
    for name in tuple(sdk.os.environ):
        if name.startswith("RAHTAL_") or name == "SAGEQL_HOST_TOKEN":
            monkeypatch.delenv(name)


def settings_file(tmp_path, *, django=False, extra=""):
    path = tmp_path / ".env"
    if django:
        source = ("DB_HOST=test-server\nDB_NAME=test-db\nDB_USERNAME=test-login\n"
                  "DB_PASSWORD=fake-password\nAVALAI_API_KEY=fake-api-key\n"
                  "AVALAI_BASE_URL=https://example.test/v1\n")
    else:
        source = ("RAHTAL_DB_SERVER=test-server\nRAHTAL_DB_DATABASE=test-db\n"
                  "RAHTAL_DB_USERNAME=test-login\nRAHTAL_DB_PASSWORD=fake-password\n"
                  "RAHTAL_LLM_API_KEY=fake-api-key\n"
                  "RAHTAL_LLM_BASE_URL=https://example.test/v1\nRAHTAL_LLM_MODEL=test-model\n")
    path.write_text(source + extra, encoding="utf-8")
    return path


def test_catalog_uses_only_existing_approved_sources_and_columns():
    catalog = sdk.rahtal_reporting_catalog()
    validate_catalog(catalog)
    approved = {column.key: column.data_type for column in daily_performance_catalog().columns}
    assert {dataset.table.name for dataset in catalog.datasets} == {
        "functionality_activities", "persons_person",
    }
    for dataset in catalog.datasets:
        assert dataset.table.kind == "TABLE"
        assert all(approved[column.key] == column.data_type for column in dataset.columns)
    activities, employees = catalog.datasets
    assert activities.time.column == "date"
    assert activities.row_key == ("id",)
    assert employees.time is None
    assert employees.row_key == ()  # Profile-to-user uniqueness has not been assumed.
    assert {item.id for item in employees.dimensions} == {
        "first_name", "last_name", "job_position", "employee_id",
    }
    assert {item.id for item in activities.dimensions} == {"employee_id"}
    with pytest.raises(ValueError):
        sdk.rahtal_reporting_catalog("dbo; DROP TABLE something")


def test_existing_django_env_aliases_port_and_declared_driver(tmp_path):
    settings = sdk._load_settings(settings_file(tmp_path, django=True, extra="DB_PORT=1444\n"))
    assert settings["RAHTAL_DB_SERVER"] == "test-server,1444"
    assert settings["RAHTAL_DB_DATABASE"] == "test-db"
    assert settings["RAHTAL_DB_USERNAME"] == "test-login"
    assert settings["RAHTAL_LLM_BASE_URL"] == "https://example.test/v1"
    assert settings["RAHTAL_LLM_MODEL"] == "gpt-5-nano"
    assert settings["RAHTAL_DB_DRIVER"] == "ODBC Driver 17 for SQL Server"


def test_process_rahtal_settings_override_django_aliases_and_port(tmp_path, monkeypatch):
    path = settings_file(tmp_path, django=True, extra="DB_PORT=1444\n")
    monkeypatch.setenv("RAHTAL_DB_SERVER", "host-from-process")
    monkeypatch.setenv("RAHTAL_DB_DRIVER", "Explicit test driver")
    monkeypatch.setenv("RAHTAL_LLM_MODEL", "explicit-test-model")
    monkeypatch.setenv("SAGEQL_HOST_TOKEN", "z" * 40)
    settings = sdk._load_settings(path)
    assert settings["RAHTAL_DB_SERVER"] == "host-from-process"
    assert settings["RAHTAL_DB_DRIVER"] == "Explicit test driver"
    assert settings["RAHTAL_LLM_MODEL"] == "explicit-test-model"
    assert settings["RAHTAL_HOST_TOKEN"] == "z" * 40


@pytest.mark.parametrize("port", ["0", "65536", "bad;password=fake", "-1"])
def test_invalid_django_port_is_rejected_without_echoing_value(tmp_path, port):
    path = settings_file(tmp_path, django=True, extra="DB_PORT=" + port + "\n")
    with pytest.raises(ValueError, match="DB_PORT must be a valid SQL Server port") as error:
        sdk._load_settings(path)
    assert "password=fake" not in str(error.value)


def test_pilot_configuration_preserves_driver_and_required_model(tmp_path):
    settings = sdk._load_settings(settings_file(tmp_path))
    assert settings["RAHTAL_DB_DRIVER"] == "ODBC Driver 18 for SQL Server"
    assert settings["RAHTAL_LLM_MODEL"] == "test-model"
    path = tmp_path / "incomplete.env"
    path.write_text("RAHTAL_DB_PASSWORD=private-test-value\n", encoding="utf-8")
    with pytest.raises(ValueError) as error:
        sdk._load_settings(path)
    assert "RAHTAL_DB_SERVER" in str(error.value)
    assert "private-test-value" not in str(error.value)


def test_env_discovery_uses_known_paths_and_explicit_path_wins(tmp_path, monkeypatch):
    local = tmp_path / "local"
    root = tmp_path / "project"
    local.mkdir()
    root.mkdir()
    django = tmp_path / "django.env"
    legacy = tmp_path / "legacy.env"
    monkeypatch.setattr(sdk, "HERE", local)
    monkeypatch.setattr(sdk, "ROOT", root)
    monkeypatch.setattr(sdk, "DJANGO_ENV", django)
    monkeypatch.setattr(sdk, "LEGACY_ENV", legacy)
    assert sdk.find_rahtal_env() is None
    legacy.write_text("", encoding="utf-8")
    assert sdk.find_rahtal_env() == legacy
    django.write_text("", encoding="utf-8")
    assert sdk.find_rahtal_env() == django
    root.joinpath(".env").write_text("", encoding="utf-8")
    assert sdk.find_rahtal_env() == root / ".env"
    local.joinpath(".env").write_text("", encoding="utf-8")
    assert sdk.find_rahtal_env() == local / ".env"
    assert sdk.find_rahtal_env(legacy) == legacy
    monkeypatch.setenv("RAHTAL_ENV_FILE", str(django))
    assert sdk.find_rahtal_env() == django
    with pytest.raises(ValueError, match="unavailable"):
        sdk.find_rahtal_env(tmp_path / "missing.env")


class Provider:
    def __init__(self, responses=()):
        self.responses = iter(responses)
        self.calls = []

    def interpret(self, messages, current_spec, catalog, today):
        self.calls.append((messages, current_spec, catalog, today))
        return next(self.responses)


def configured_engine(tmp_path, monkeypatch, responses=(), *, extra="", sessions=None, diagnostics=False):
    provider = Provider(responses)
    configs = []

    def make_provider(config, **options):
        configs.append((config, options))
        return provider

    monkeypatch.setattr(sdk, "OpenAIReportAgent", make_provider)
    engine, actor, token = sdk.create_rahtal_engine(
        settings_file(tmp_path, extra=extra), sessions=sessions,
        diagnostics_directory=tmp_path / "diagnostics" if diagnostics else None)
    return engine, actor, token, provider, configs


def test_setup_does_not_call_database_or_model_and_host_identity_is_fixed(tmp_path, monkeypatch):
    monkeypatch.setattr(sdk, "_connect", lambda settings: pytest.fail("startup must not open database"))
    store = SQLiteSessionStore(tmp_path / "sessions.sqlite")
    engine, actor, token, provider, configs = configured_engine(tmp_path, monkeypatch, sessions=store)
    assert provider.calls == []
    assert sdk._TOKEN.fullmatch(token)
    assert actor.subject == "rahtal-local-admin"
    assert actor.tenant_id == ""
    assert actor.attributes == {"reporting_role": "rahtal-local-admin"}
    assert engine.sessions is store
    assert engine.execution == "validated"
    assert engine.limits.max_rows == 100
    assert configs[0][0].model == "test-model"
    assert configs[0][1]["timeout_seconds"] == 45
    session = engine.create_session(actor)
    assert session.status == "session_ready"
    for wrong in (ActorContext("browser-user"), ActorContext(actor.subject),
                  ActorContext(actor.subject, "other", actor.attributes)):
        with pytest.raises(SDKError, match="authenticated local"):
            engine.create_session(wrong)
    scope = engine._scope(actor)
    assert all(access.policies[0].values == (False,) for access in scope.datasets)
    metadata = _metadata(permitted_catalog(engine.catalog, scope))
    serialized = str(metadata)
    assert "first_name" in serialized
    assert "fake-password" not in serialized
    assert "fake-api-key" not in serialized
    assert "persons_person" not in serialized
    assert "is_deleted" not in serialized


def test_explicit_token_is_validated_and_not_derived_from_credentials(tmp_path, monkeypatch):
    _, actor, token, _, _ = configured_engine(tmp_path, monkeypatch,
        extra="RAHTAL_HOST_TOKEN=" + "t" * 40 + "\nRAHTAL_HOST_SUBJECT=operator\n")
    assert token == "t" * 40
    assert actor.subject == "operator"
    with pytest.raises(ValueError, match="RAHTAL_HOST_TOKEN"):
        configured_engine(tmp_path, monkeypatch, extra="RAHTAL_HOST_TOKEN=short\n")


def test_connection_factory_has_finite_login_and_odbc_escaped_credentials(tmp_path, monkeypatch):
    captured = []
    lease = object()

    def connect(connection_string, **options):
        captured.append((connection_string, options))
        return lease

    monkeypatch.setitem(sys.modules, "pyodbc", SimpleNamespace(connect=connect))
    settings = sdk._load_settings(settings_file(tmp_path))
    settings["RAHTAL_DB_PASSWORD"] = "fake};UID=attacker"
    assert sdk._connect(settings) is lease
    string, options = captured[0]
    assert "PWD={fake}};UID=attacker}" in string
    assert "ApplicationIntent=ReadOnly" in string
    assert options == {"autocommit": False, "timeout": 5}


def test_unreachable_rahtal_reports_connection_failure_without_claiming_query_failure(tmp_path, monkeypatch):
    class DriverError(Exception):
        pass

    attempts = []

    def connect(*args, **kwargs):
        attempts.append(True)
        if len(attempts) == 1:
            raise DriverError("08001", "private-host;PWD=secret; login timeout")
        return connection

    monkeypatch.setitem(sys.modules, "pyodbc", SimpleNamespace(connect=connect, Error=DriverError))
    listing = ReportSpec("employees", (), dimension_ids=("first_name", "last_name"))
    engine, actor, _, _, _ = configured_engine(tmp_path, monkeypatch,
        (Interpretation("ready", listing), Interpretation("ready", listing)))
    connection = FakeConnection(engine.catalog.datasets[1], ("first_name", "last_name"),
                                (("Test", "Employee"),))
    session = engine.create_session(actor)
    reply = engine.submit(session.session_id, "Send me employee names", actor, "names", 0)
    assert reply.status == "failed"
    assert reply.error == {"code": "database_unavailable", "retryable": True}
    assert "اتصال به پایگاه داده برقرار نشد" in reply.text
    assert "VPN" in reply.text
    assert "SQL Server report execution failed" not in reply.text
    assert "private-host" not in reply.text and "secret" not in reply.text
    assert reply.report is None and reply.revision == 0
    assert connection.statements == []
    repeated = engine.submit(session.session_id, "Send me employee names", actor, "names", 0)
    assert repeated.to_dict() == reply.to_dict() and len(attempts) == 1
    recovered = engine.submit(session.session_id, "Send me employee names", actor, "names-retry", 0)
    assert recovered.status == "report_ready"
    assert [field.label for field in recovered.report.fields] == ["نام", "نام خانوادگی"]
    assert len(connection.statements) == 2  # Metadata check, then the bounded report.
    assert connection.closed and connection.rolled_back


class FakeConnection:
    def __init__(self, dataset, fields, rows):
        self.metadata = [(column.name, column.data_type, column.nullable, "U", 0, 0)
                         for column in dataset.columns]
        self.rows = rows
        self.fields = fields
        self.statements = []
        self.closed = self.rolled_back = self.cursor_closed = False
        self.timeout = 0
        self.phase = "metadata"
        self.description = None

    def cursor(self):
        return self

    def execute(self, sql, *parameters):
        self.statements.append((sql, parameters))
        self.phase = "metadata" if "sys.columns" in sql else "report"
        if self.phase == "report":
            self.description = [(field,) for field in self.fields]
        return self

    def fetchmany(self, size):
        return (self.metadata if self.phase == "metadata" else self.rows)[:size]

    def cancel(self):
        pass

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_employee_names_use_existing_profiles_with_mandatory_soft_delete(tmp_path, monkeypatch):
    listing = ReportSpec("employees", (), dimension_ids=("first_name", "last_name"),
                         order_by="last_name")
    engine, actor, _, provider, _ = configured_engine(tmp_path, monkeypatch,
        (Interpretation("ready", listing),))
    connection = FakeConnection(engine.catalog.datasets[1], ("first_name", "last_name"),
                                (("Test", "Employee"),))
    monkeypatch.setattr(sdk, "_connect", lambda settings: connection)
    session = engine.create_session(actor)
    reply = engine.submit(session.session_id, "Send my employees' names", actor, "names", 0)
    assert reply.status == "report_ready", reply.to_dict()
    assert reply.report.rows == (("Test", "Employee"),)
    assert [field.id for field in reply.report.fields] == ["first_name", "last_name"]
    query, parameters = connection.statements[1]
    assert "SELECT DISTINCT" in query
    assert "[dbo].[persons_person]" in query
    assert "t.[is_deleted] = ?" in query
    assert "functionality_activities" not in query
    assert parameters == (101, False)
    assert connection.closed and connection.rolled_back
    assert provider.calls[0][1] is None


@pytest.mark.parametrize("diagnostics", [False, True])
def test_activity_report_resolves_full_name_with_two_bounded_sqlserver_reads(tmp_path, monkeypatch, diagnostics):
    name = "کارمند نمونه پور"
    daily = ReportSpec("activities", ("activity_hours", "activity_count", "average_activity_hours"),
                       filters=(UserFilter("employee_name_filter", "eq", (name,)),),
                       period=PeriodSelection("last_month"), time_grain="day")
    engine, actor, _, provider, _ = configured_engine(tmp_path, monkeypatch,
        (Interpretation("ready", daily),), diagnostics=diagnostics)
    engine._clock = lambda: date(2026, 10, 6)
    profiles = FakeConnection(engine.catalog.datasets[1], ("employee_id",), ((27,),))
    activities = FakeConnection(engine.catalog.datasets[0],
                                ("time_bucket", "activity_hours", "activity_count", "average_activity_hours"),
                                ((date(2026, 9, 2), 6.5, 2, 3.25),))
    connections = iter((profiles, activities))
    monkeypatch.setattr(sdk, "_connect", lambda settings: next(connections))
    session = engine.create_session(actor)
    message = f"تمام اطلاعات فعالیت‌های روزانه {name} در ماه گذشته"
    if diagnostics:
        payload = engine.submit_with_diagnostics(session.session_id, message, actor, "named", 0)
        assert payload["status"] == "report_ready"
        import json
        trace = payload["diagnostics"]
        serialized = json.dumps(trace, ensure_ascii=False)
        assert name not in serialized and name.replace(" ", "") not in serialized
        query_events = [item for item in trace["events"] if item["stage"] == "sql_execution" and item["status"] == "started"]
        assert len(query_events) == 2
        assert all(item["parameters"][2]["value"] == "[redacted]" for item in query_events)
    else:
        reply = engine.submit(session.session_id, message, actor, "named", 0)
        assert reply.status == "report_ready", reply.to_dict()
        assert reply.report.rows == ((date(2026, 9, 2), 6.5, 2, 3.25),)
    name_sql, name_binds = profiles.statements[1]
    final_sql, final_binds = activities.statements[1]
    assert "SELECT DISTINCT" in name_sql and "[dbo].[persons_person]" in name_sql
    assert "REPLACE" in name_sql and "COLLATE Latin1_General_100_BIN2" in name_sql
    assert name_binds == (3, False, "کارمندنمونهپور")
    assert final_binds == (101, False, 27, date(2026, 9, 1), date(2026, 10, 1))
    assert "[dbo].[functionality_activities]" in final_sql and "JOIN" not in final_sql
    assert "t.[is_deleted] = ?" in name_sql and "t.[is_deleted] = ?" in final_sql
    assert profiles.closed and profiles.rolled_back and activities.closed and activities.rolled_back
    assert len(provider.calls) == 1


def test_name_listing_can_be_followed_by_activity_period_clarification(tmp_path, monkeypatch):
    listing = ReportSpec("employees", (), dimension_ids=("first_name", "last_name"))
    daily = ReportSpec("activities", ("activity_hours",),
                       period=PeriodSelection("month", year=2025, month=9),
                       time_grain="day", chart="line")
    engine, actor, _, provider, _ = configured_engine(tmp_path, monkeypatch, (
        Interpretation("ready", listing),
        Interpretation("needs_clarification", question="Which year should September cover?"),
        Interpretation("ready", daily),
    ))
    profiles = FakeConnection(engine.catalog.datasets[1], ("first_name", "last_name"),
                              (("Test", "Employee"),))
    activities = FakeConnection(engine.catalog.datasets[0], ("time_bucket", "activity_hours"),
                                ((date(2025, 9, 1), 4.5),))
    connections = iter((profiles, activities))
    monkeypatch.setattr(sdk, "_connect", lambda settings: next(connections))
    session = engine.create_session(actor)
    first = engine.submit(session.session_id, "List employee names", actor, "names", 0)
    question = engine.submit(session.session_id, "Daily activity hours for September", actor, "period", 1)
    assert first.status == "report_ready"
    assert question.status == "needs_clarification"
    final = engine.submit(session.session_id, "2025", actor, "answer", 2)
    assert final.status == "report_ready", final.to_dict()
    assert final.report.rows == ((date(2025, 9, 1), 4.5),)
    query, parameters = activities.statements[1]
    assert "SUM(t.[time])" in query
    assert "[dbo].[functionality_activities]" in query
    assert parameters == (101, False, date(2025, 9, 1), date(2025, 10, 1))
    assert profiles.closed and activities.closed
    assert len(provider.calls) == 3
    assert provider.calls[-1][1].dataset_id == "employees"
    assert any("September" in message.content for message in provider.calls[-1][0])


@pytest.mark.parametrize("rows", [(), (("PrivateFirst", "PrivateLast"),)])
def test_local_diagnostics_capture_actual_sql_without_personal_data(tmp_path, monkeypatch, rows):
    import json
    from sageql.sdk.models import UserFilter
    listing = ReportSpec("employees", (), dimension_ids=("first_name", "last_name"),
                         filters=(UserFilter("first_name_filter", "eq", ("PrivateFilter",)),))
    engine, actor, _, provider, _ = configured_engine(tmp_path, monkeypatch,
        (Interpretation("ready", listing),), diagnostics=True)
    connection = FakeConnection(engine.catalog.datasets[1], ("first_name", "last_name"), rows)
    monkeypatch.setattr(sdk, "_connect", lambda settings: connection)
    session = engine.create_session(actor)
    payload = engine.submit_with_diagnostics(session.session_id, "PrivateQuestion", actor, "names", 0)
    assert payload["status"] == "report_ready"
    trace = payload["diagnostics"]
    stages = {item["stage"]: item for item in trace["events"]}
    assert stages["validation"]["filters"][0]["values"] == "[redacted]"
    assert stages["validation"]["policies"][0]["values"] == [False]
    execution = next(item for item in trace["events"] if item["stage"] == "sql_execution" and item["status"] == "started")
    assert execution["sql"] == connection.statements[1][0]
    assert execution["parameters"][-1]["value"] == "[redacted]"
    assert len(connection.statements) == 2  # No additional diagnostics/probe query.
    assert stages["database"]["row_count"] == len(rows)
    assert stages["request"]["row_count"] == len(rows)
    if not rows:
        assert "zero rows" in stages["request"]["note"]
        assert "cannot determine" in stages["request"]["note"]
    saved = json.loads((tmp_path / "diagnostics" / (trace["id"] + ".json")).read_text(encoding="utf-8"))
    assert saved == trace and trace["saved"]
    for secret in ("PrivateQuestion", "PrivateFirst", "PrivateLast", "PrivateFilter", "fake-password", "fake-api-key", "test-server"):
        assert secret not in json.dumps(trace)
    assert connection.closed and connection.rolled_back
    cached = engine.submit_with_diagnostics(session.session_id, "PrivateQuestion", actor, "names", 0)
    assert cached["report"] == payload["report"]
    assert any(item["status"] == "cached" for item in cached["diagnostics"]["events"])
    assert len(provider.calls) == 1 and len(connection.statements) == 2


def test_diagnostics_clarification_and_invalid_spec_never_claim_sql_execution(tmp_path, monkeypatch):
    engine, actor, _, _, _ = configured_engine(tmp_path, monkeypatch, (
        Interpretation("needs_clarification", question="Which year?"),
        Interpretation("ready", ReportSpec("unregistered", ("unknown",))),
    ), diagnostics=True)
    monkeypatch.setattr(sdk, "_connect", lambda settings: pytest.fail("must not connect"))
    session = engine.create_session(actor)
    first = engine.submit_with_diagnostics(session.session_id, "September", actor, "period", 0)
    assert first["status"] == "needs_clarification"
    assert "no report SQL" in first["diagnostics"]["events"][-1]["note"]
    second = engine.submit_with_diagnostics(session.session_id, "2026", actor, "year", 1)
    assert second["error"]["code"] == "access_denied"
    assert second["diagnostics"]["events"][-1]["status"] == "failed"
    assert not any(item["stage"] == "sql_execution" for item in second["diagnostics"]["events"])


def test_diagnostics_connection_failure_and_unwritable_log_are_safe(tmp_path, monkeypatch):
    listing = ReportSpec("employees", (), dimension_ids=("first_name",))
    engine, actor, _, _, _ = configured_engine(tmp_path, monkeypatch,
        (Interpretation("ready", listing),), diagnostics=True)
    def broken_connect(settings):
        raise RuntimeError("password=PrivatePassword;server=PrivateServer")
    monkeypatch.setattr(sdk, "_connect", broken_connect)
    # A file cannot be used as a log directory. Reporting must still return its safe failure.
    engine.diagnostics_directory.write_text("blocked", encoding="utf-8")
    session = engine.create_session(actor)
    payload = engine.submit_with_diagnostics(session.session_id, "Names", actor, "names", 0)
    assert payload["error"]["code"] == "database_unavailable"
    assert payload["diagnostics"]["saved"] is False
    assert any(item["stage"] == "connection" and item["status"] == "started" for item in payload["diagnostics"]["events"])
    assert not any(item["stage"] == "sql_execution" for item in payload["diagnostics"]["events"])
    assert "PrivatePassword" not in str(payload) and "PrivateServer" not in str(payload)


def test_diagnostics_metadata_failure_shows_lookup_but_no_executed_report(tmp_path, monkeypatch):
    listing = ReportSpec("employees", (), dimension_ids=("first_name",))
    engine, actor, _, _, _ = configured_engine(tmp_path, monkeypatch,
        (Interpretation("ready", listing),), diagnostics=True)
    connection = FakeConnection(engine.catalog.datasets[1], ("first_name",), ())
    connection.metadata = []
    monkeypatch.setattr(sdk, "_connect", lambda settings: connection)
    session = engine.create_session(actor)
    payload = engine.submit_with_diagnostics(session.session_id, "Names", actor, "names", 0)
    assert payload["error"]["code"] == "schema_drift"
    events = payload["diagnostics"]["events"]
    assert any(item["stage"] == "metadata_sql" and item.get("sql") == connection.statements[0][0] for item in events)
    assert any(item["stage"] == "compilation" and item["status"] == "complete" for item in events)
    assert not any(item["stage"] == "sql_execution" for item in events)
    assert connection.closed and connection.rolled_back


def test_diagnostics_provider_failure_excludes_raw_error(tmp_path, monkeypatch):
    engine, actor, _, provider, _ = configured_engine(tmp_path, monkeypatch, diagnostics=True)
    def broken_provider(*args):
        raise RuntimeError("PrivateKey and private request text")
    monkeypatch.setattr(provider, "interpret", broken_provider)
    session = engine.create_session(actor)
    payload = engine.submit_with_diagnostics(session.session_id, "Names", actor, "names", 0)
    assert payload["error"]["code"] == "provider_failed"
    assert any(item["stage"] == "interpretation" and item["status"] == "failed" for item in payload["diagnostics"]["events"])
    assert "PrivateKey" not in str(payload)
