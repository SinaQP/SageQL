"""The example host exercises SDK conversations without network services or secrets."""

from contextlib import contextmanager
from decimal import Decimal
import importlib.util
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import sys
from threading import Thread
from types import SimpleNamespace

import pytest

from sageql.sdk.models import ActorContext


_SPEC = importlib.util.spec_from_file_location(
    "sageql_reference_web", Path(__file__).parents[1] / "examples" / "web" / "server.py",
)
web = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(web)


@contextmanager
def running_host(tmp_path, *, mode="demo", token="", engine=None):
    engine = engine or web.create_demo_engine(tmp_path / "demo.sqlite")
    handler = web.handler_for(engine, ActorContext("demo", "1"), mode=mode, token=token)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def request(method, path, data=None, *, headers=None, raw=None):
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        body = raw if raw is not None else json.dumps(data).encode() if data is not None else None
        outgoing = dict(headers or {})
        if body is not None:
            outgoing.setdefault("Content-Type", "application/json")
        try:
            connection.request(method, path, body=body, headers=outgoing)
            response = connection.getresponse()
            content = response.read()
            result = content.decode() if response.getheader("Content-Type", "").startswith("text/html") else json.loads(content)
            return response.status, result, dict(response.getheaders())
        finally:
            connection.close()

    try:
        yield request
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


def test_frontend_clarification_report_refinement_and_retry(tmp_path):
    with running_host(tmp_path) as request:
        code, page, headers = request("GET", "/")
        assert code == 200
        assert 'lang="fa" dir="rtl"' in page
        assert "فضای گزارش‌گیری" in page
        assert "textContent" in page
        assert "innerHTML" not in page
        assert headers["Cache-Control"] == "no-store"
        code, created, _ = request("POST", "/report-sessions", {})
        assert code == 201
        session = created["session_id"]
        endpoint = f"/report-sessions/{session}/messages"
        code, question, _ = request("POST", endpoint, {
            "message": "Daily activity hours for September", "request_id": "first", "expected_revision": 0,
        })
        assert code == 200
        assert question["status"] == "needs_clarification"
        assert "سال میلادی" in question["clarification"]
        ready_request = {"message": "2026", "request_id": "year", "expected_revision": 1}
        _, daily, _ = request("POST", endpoint, ready_request)
        assert daily["status"] == "report_ready"
        assert daily["revision"] == 2
        assert daily["report"]["rows"][0][0] == "2026-09-01"
        assert Decimal(str(daily["report"]["rows"][0][1])) == Decimal("8.75")
        _, repeated, _ = request("POST", endpoint, ready_request)
        assert repeated == daily
        _, grouped, _ = request("POST", endpoint, {
            "message": "Group it by employee instead", "request_id": "employee", "expected_revision": 2,
        })
        assert grouped["status"] == "report_ready"
        assert grouped["report"]["provenance"]["period_start"] == "2026-09-01"
        assert grouped["report"]["provenance"]["period_end_exclusive"] == "2026-10-01"
        totals = {row[0]: Decimal(str(row[1])) for row in grouped["report"]["rows"]}
        assert totals == {"Alex": Decimal("81"), "Sam": Decimal("52.5")}
        code, saved, _ = request("GET", f"/report-sessions/{session}/reports/{daily['report']['id']}")
        assert code == 200
        assert saved == daily["report"]
        assert "private" not in json.dumps(grouped).lower()


@pytest.mark.parametrize("year", ["۲۰۲۶", "٢٠٢٦"])
def test_persian_http_conversation_clarification_and_refinement(tmp_path, year):
    with running_host(tmp_path) as request:
        _, created, _ = request("POST", "/report-sessions", {})
        assert created["assistant"]["text"] == "چه گزارشی می‌خواهید تهیه کنید؟"
        endpoint = f"/report-sessions/{created['session_id']}/messages"
        _, question, _ = request("POST", endpoint, {
            "message": "ساعات فعاليت روزانه در سپتامبر", "request_id": "fa-question", "expected_revision": 0})
        assert question["status"] == "needs_clarification"
        _, daily, _ = request("POST", endpoint, {
            "message": year, "request_id": "fa-year", "expected_revision": 1})
        assert daily["status"] == "report_ready"
        assert daily["report"]["title"] == "ساعات فعالیت به تفکیک روز"
        assert [field["label"] for field in daily["report"]["fields"]] == ["تاریخ", "ساعات فعالیت"]
        assert daily["report"]["rows"][0][0] == "2026-09-01"
        refinement = {"message": "به تفکیک کارمند نمایش بده", "request_id": "fa-group", "expected_revision": 2}
        _, grouped, _ = request("POST", endpoint, refinement)
        assert grouped["status"] == "report_ready"
        assert grouped["report"]["title"] == "ساعات فعالیت به تفکیک کارمند"
        assert {row[0]: Decimal(str(row[1])) for row in grouped["report"]["rows"]} == {
            "Alex": Decimal("81"), "Sam": Decimal("52.5")}
        _, cached, _ = request("POST", endpoint, refinement)
        assert cached == grouped


def test_persian_demo_greeting_and_solar_hijri_do_not_execute(tmp_path):
    with running_host(tmp_path) as request:
        _, created, _ = request("POST", "/report-sessions", {})
        endpoint = f"/report-sessions/{created['session_id']}/messages"
        _, greeting, _ = request("POST", endpoint, {
            "message": "سلام", "request_id": "hi", "expected_revision": 0})
        assert greeting["status"] == "needs_clarification"
        _, unsupported, _ = request("POST", endpoint, {
            "message": "ساعات فعالیت در شهریور ۱۴۰۵ شمسی", "request_id": "jalali", "expected_revision": 1})
        assert unsupported["status"] == "unsupported"
        assert "تاریخ میلادی" in unsupported["assistant"]["text"]
        assert unsupported["report"] is None


def test_host_rejects_browser_configuration_and_cross_origin(tmp_path):
    with running_host(tmp_path) as request:
        code, error, _ = request("POST", "/report-sessions", {"tenant_id": "2"})
        assert code == 400
        assert error["error"]["code"] == "invalid_request"
        code, _, _ = request("POST", "/report-sessions", {}, headers={"Origin": "https://evil.test"})
        assert code == 403
        code, _, _ = request("POST", "/report-sessions", {}, headers={"Host": "evil.test"})
        assert code == 403
        code, _, _ = request("GET", "/config?token=secret")
        assert code == 400


@pytest.mark.parametrize("raw,content_type,expected", [
    (b"x" * 17000, "application/json", 413),
    (b"{}", "text/plain", 400),
    (b"[]", "application/json", 400),
    (b'{"x":1,"x":2}', "application/json", 400),
    (b'{"x":NaN}', "application/json", 400),
], ids=["too-large", "wrong-content-type", "array", "duplicate-key", "non-finite"])
def test_host_rejects_unbounded_or_malformed_bodies(tmp_path, raw, content_type, expected):
    with running_host(tmp_path) as request:
        code, body, _ = request("POST", "/report-sessions", raw=raw,
                                headers={"Content-Type": content_type})
        assert code == expected
        assert "error" in body


@pytest.mark.parametrize("mode", ["sqlserver", "rahtal"])
def test_sqlserver_host_identity_is_authenticated_server_configuration(tmp_path, mode):
    token = "example_workspace_access_token_12345"
    with running_host(tmp_path, mode=mode, token=token) as request:
        code, config, _ = request("GET", "/config")
        assert code == 200
        assert config["requires_auth"] is True
        assert config["mode"] == mode
        code, _, _ = request("POST", "/report-sessions", {})
        assert code == 401
        code, _, _ = request("POST", "/auth", {"token": "incorrect"})
        assert code == 401
        code, logged_in, headers = request("POST", "/auth", {"token": token})
        assert code == 200
        assert logged_in == {"authenticated": True}
        assert "HttpOnly" in headers["Set-Cookie"]
        assert "SameSite=Strict" in headers["Set-Cookie"]
        code, created, _ = request("POST", "/report-sessions", {},
                                   headers={"Cookie": headers["Set-Cookie"].split(";", 1)[0]})
        assert code == 201
        assert created["status"] == "session_ready"
        code, _, _ = request("POST", "/report-sessions", {"actor": {"tenant_id": "2"}},
                            headers={"Authorization": "Bearer " + token})
        assert code == 400


def test_sqlserver_configuration_requires_explicit_credentials_without_connecting(monkeypatch):
    monkeypatch.delenv("SAGEQL_SQLSERVER_CONNECTION_STRING", raising=False)
    with pytest.raises(ValueError, match="SAGEQL_SQLSERVER_CONNECTION_STRING"):
        web.create_sqlserver_engine()


def test_sqlserver_configuration_accepts_existing_llm_alias_without_connecting(monkeypatch):
    captured = {}

    def fake_interpreter(config, **kwargs):
        captured["config"] = config
        return web.DemoInterpreter()

    def unexpected_connect(*args, **kwargs):
        raise AssertionError("startup must not connect to a database")

    for name in ("SAGEQL_API_KEY", "OPENAI_API_KEY", "SAGEQL_BASE_URL", "SAGEQL_MODEL"):
        monkeypatch.delenv(name, raising=False)
    for name, value in {
        "SAGEQL_SQLSERVER_CONNECTION_STRING": "synthetic-connection-setting",
        "SAGEQL_HOST_TOKEN": "example_workspace_access_token_12345",
        "SAGEQL_HOST_SUBJECT": "application-user",
        "SAGEQL_HOST_TENANT_ID": "1",
        "SAGEQL_REPORT_SCHEMA": "dbo", "SAGEQL_REPORT_TABLE": "approved_activity_view",
        "SAGEQL_REPORT_KIND": "VIEW",
        "LLM_API_KEY": "synthetic-model-key", "LLM_BASE_URL": "https://example.test/v1",
        "LLM_MODEL": "configured-model",
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setitem(sys.modules, "pyodbc", SimpleNamespace(connect=unexpected_connect))
    monkeypatch.setattr(web, "OpenAIReportAgent", fake_interpreter)
    engine, actor, token = web.create_sqlserver_engine()
    assert captured["config"].api_key == "synthetic-model-key"
    assert captured["config"].base_url == "https://example.test/v1"
    assert captured["config"].model == "configured-model"
    assert actor.subject == "application-user"
    assert actor.tenant_id == "1"
    assert engine.catalog.datasets[0].table.key == "dbo.approved_activity_view"
    assert engine.catalog.datasets[0].table.kind == "VIEW"


def test_demo_does_not_load_host_env_file(tmp_path):
    config = tmp_path / "local.env"
    config.write_text("SAGEQL_API_KEY=must-not-be-read", encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        web.main(["--demo", "--env-file", str(config)])
    assert error.value.code == 2


@pytest.fixture
def simulated_rahtal_startup(tmp_path, monkeypatch):
    from sageql_rahtal import sdk

    root = tmp_path / "reference"
    private_state = root / ".venv" / "rahtal-web"
    private_state.mkdir(parents=True)
    calls = []

    def create_engine(env_path, *, sessions, diagnostics_directory):
        assert diagnostics_directory == private_state / "diagnostics"
        calls.append((env_path, sessions))
        return object(), ActorContext("test-operator"), "n" * 40

    monkeypatch.setattr(web, "__file__", str(root / "examples" / "web" / "server.py"))
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setattr(sdk, "create_rahtal_engine", create_engine)
    monkeypatch.setattr(web, "handler_for", lambda *args, **kwargs: object())
    return private_state, calls


def test_rahtal_diagnostics_require_auth_and_are_not_used_in_other_modes(tmp_path):
    calls = []
    engine = web.create_demo_engine(tmp_path / "trace-demo.sqlite")
    def traced_submit(*args):
        calls.append(args)
        payload = engine.submit(*args).to_dict()
        payload["diagnostics"] = {"id": "test-trace", "events": []}
        return payload
    engine.submit_with_diagnostics = traced_submit
    token = "t" * 40
    with running_host(tmp_path, mode="rahtal", token=token, engine=engine) as request:
        headers = {"Authorization": "Bearer " + token}
        _, created, _ = request("POST", "/report-sessions", {}, headers=headers)
        path = f"/report-sessions/{created['session_id']}/messages"
        data = {"message": "Daily activity hours for September", "request_id": "period", "expected_revision": 0}
        code, denied, _ = request("POST", path, data)
        assert code == 401 and not calls and "diagnostics" not in denied
        _, reply, _ = request("POST", path, data, headers=headers)
        assert reply["diagnostics"]["id"] == "test-trace" and len(calls) == 1
    with running_host(tmp_path, mode="demo", engine=engine) as request:
        _, created, _ = request("POST", "/report-sessions", {})
        _, reply, _ = request("POST", f"/report-sessions/{created['session_id']}/messages", data)
        assert "diagnostics" not in reply and len(calls) == 1


def test_failed_rahtal_bind_preserves_running_workspace_token(simulated_rahtal_startup, monkeypatch):
    private_state, calls = simulated_rahtal_startup
    token_file = private_state / "host-token.txt"
    token_file.write_text("existing-workspace-token", encoding="utf-8")

    def occupied_port(*args, **kwargs):
        raise OSError("test port is occupied")

    monkeypatch.setattr(web, "WorkspaceHTTPServer", occupied_port)
    with pytest.raises(SystemExit) as error:
        web.main(["--rahtal", "--port", "8766"])
    assert error.value.code == 2
    assert token_file.read_text(encoding="utf-8") == "existing-workspace-token"
    assert len(calls) == 1
    assert calls[0][0] is None
    assert (private_state / "sessions.sqlite").is_file()


def test_failed_rahtal_token_persistence_closes_bound_server(simulated_rahtal_startup, monkeypatch):
    private_state, calls = simulated_rahtal_startup

    class BoundServer:
        closed = False

        def server_close(self):
            self.closed = True

        def serve_forever(self):
            pytest.fail("A workspace without its persisted token must not start serving")

    server = BoundServer()
    monkeypatch.setattr(web, "WorkspaceHTTPServer", lambda *args, **kwargs: server)
    original_write = Path.write_text

    def unavailable_storage(path, *args, **kwargs):
        if path == private_state / "host-token.txt":
            raise OSError("test token storage is unavailable")
        return original_write(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", unavailable_storage)
    with pytest.raises(SystemExit) as error:
        web.main(["--rahtal", "--port", "8766"])
    assert error.value.code == 2
    assert server.closed
    assert len(calls) == 1


def test_real_occupied_port_rejects_second_host_and_preserves_token(simulated_rahtal_startup):
    private_state, _ = simulated_rahtal_startup
    token_file = private_state / "host-token.txt"
    token_file.write_text("existing-workspace-token", encoding="utf-8")
    # Even an older host with address reuse must prevent a second workspace.
    first = ThreadingHTTPServer(("127.0.0.1", 0), web.BaseHTTPRequestHandler)
    try:
        with pytest.raises(SystemExit) as error:
            web.main(["--rahtal", "--port", str(first.server_port)])
        assert error.value.code == 2
        assert token_file.read_text(encoding="utf-8") == "existing-workspace-token"
    finally:
        first.server_close()
