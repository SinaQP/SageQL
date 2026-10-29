"""Default pytest must stay offline even when stale native opt-ins are present."""
import os
from contextlib import closing
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest


ROOT = Path(__file__).parents[1]
NATIVE = "tests/test_sdk_sqlserver_phase11_integration.py::test_opt_in_phase11_driver_types_unicode_policies_and_collation"
LEGACY = "tests/test_sdk_adapters.py::test_opt_in_sql_server_synthetic_fixture_is_readonly_and_scoped"
BOOTSTRAP = """
import sys, types, pytest
driver = types.ModuleType('pyodbc')
def reject(*args, **kwargs):
    raise AssertionError('Synthetic subprocess must never dispatch a native connection')
driver.connect = reject
sys.modules['pyodbc'] = driver
raise SystemExit(pytest.main(sys.argv[1:]))
"""


def native_probe(tmp_path, node, *options, extra_env=None):
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("SAGEQL_SQLSERVER_TEST_", "SAGEQL_EVAL_", "RAHTAL_"))}
    env.update(PYTHONUTF8="1", SAGEQL_SQLSERVER_TEST_CONFIRM_PHASE11="1",
               SAGEQL_SQLSERVER_TEST_PHASE11_APPROVAL=str(tmp_path / "absent-approval.json"),
               SAGEQL_SQLSERVER_TEST_CONFIRM_SYNTHETIC="1",
               SAGEQL_SQLSERVER_TEST_CONNECTION="synthetic-unused", SAGEQL_SQLSERVER_TEST_TABLE="synthetic_only")
    env.update(extra_env or {})
    return subprocess.run([sys.executable, "-c", BOOTSTRAP, node, "-q", *options],
                          cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)


@pytest.mark.parametrize("node", [NATIVE, LEGACY])
def test_plain_pytest_skips_native_before_stale_configuration_or_driver_access(tmp_path, node):
    result = native_probe(tmp_path, node)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 skipped" in result.stdout


def test_explicit_native_flag_still_requires_separate_existing_approval(tmp_path):
    result = native_probe(tmp_path, NATIVE, "--run-sqlserver-integration")
    assert result.returncode == 1
    assert "FileNotFoundError" in result.stdout
    assert "1 skipped" not in result.stdout


def test_inherited_pytest_options_cannot_enable_native_execution(tmp_path):
    result = native_probe(tmp_path, NATIVE, extra_env={"PYTEST_ADDOPTS": "--run-sqlserver-integration"})
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 skipped" in result.stdout


def test_private_configuration_guard_rejects_before_calling_any_reader():
    from conftest import PRIVATE_ENV, _guard_open
    calls = []
    guarded = _guard_open(lambda *args, **kwargs: calls.append(args))
    for path in PRIVATE_ENV:
        with pytest.raises(AssertionError, match="production environment"):
            guarded(path, "r")
    assert calls == []  # No real file is opened, even if this assertion fails.


@pytest.mark.parametrize("host", ["192.0.2.1", "example.invalid", "::"])
def test_network_guard_rejects_before_dns_or_connection_dispatch(host):
    from conftest import _local_connection
    calls = []
    guarded = _local_connection(lambda *args, **kwargs: calls.append(args))
    with pytest.raises(AssertionError, match="loopback"):
        guarded(None, (host, 443))
    assert calls == []


@pytest.mark.parametrize("domain,dataset,metric,dimension", [
    ("retail", "sales", "revenue", "department"),
    ("library", "loans", "borrowings", "shelf"),
    ("workshop", "jobs", "billed", "service"),
])
def test_reused_sqlite_hosts_are_isolated_and_match_independent_reference(
        sqlite_host_factory, domain, dataset, metric, dimension):
    from evaluations.phase03_hosts import ACTOR, TODAY
    from evaluations.reference import expected_report
    from evaluations.scoring import rows_match
    from sageql.sdk import ExecutionLimits, PeriodSelection, ReportSpec
    from sageql.sdk.lookups import prepare_request
    from sageql.sdk.models import json_value
    first = sqlite_host_factory(domain, wal=True)
    second = sqlite_host_factory(domain)
    assert first.path != second.path
    selected = ReportSpec(dataset, (metric,), (dimension,),
                          period=PeriodSelection("month", year=2026, month=9), order_by=metric)
    expected = expected_report(domain, json_value(selected), ["2026-09-01", "2026-10-01"])
    for host in (first, second):
        prepared, lookup = prepare_request(host.catalog, selected, host.policy(ACTOR), TODAY)
        assert lookup is None
        result = host.database.execute(prepared, ExecutionLimits())
        fields = [{"id": key, "type": kind} for key, kind in zip(expected["fields"], expected["types"])]
        assert rows_match(fields, json_value(result.rows), expected["rows"])
        assert result.truncated == expected["truncated"]
    # Writer state in one disposable fixture cannot contaminate another fixture.
    before = second.path.read_bytes()
    with closing(sqlite3.connect(first.path)) as connection, connection:
        connection.execute("CREATE TABLE fixture_isolation_marker (value INT)")
    assert second.path.read_bytes() == before
