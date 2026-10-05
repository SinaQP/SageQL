"""Offline adapter checks: trusted scope, result correctness and lifecycle."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
import os
import sqlite3
from threading import Event, Thread

import pytest

from sageql.schema import Column, Table
from sageql.sdk.adapters import SQLServerAdapter, SQLiteAdapter, compile_report
from sageql.sdk.models import (
    DatasetAccess, DatasetDefinition, DimensionDefinition, ExecutionLimits,
    FilterDefinition, MetricDefinition, PeriodSelection, ReportSpec, RowPolicy,
    SDKError, TimeDefinition, UserFilter,
)
from sageql.sdk.semantics import validate_report


def dataset(*, schema="", kind="TABLE"):
    table = Table("activity", schema, kind)
    return DatasetDefinition(
        "activity", "Activity", table,
        tuple(Column(table.key, name, kind, nullable) for name, kind, nullable in (
            ("tenant", "int", False), ("day", "date", False),
            ("employee", "nvarchar(100)", False), ("hours", "decimal(18,2)", True),
            ("deleted", "bit", False), ("minutes", "int", True),
        )),
        (MetricDefinition("hours", "Activity hours", "sum", "hours", "hours"),
         MetricDefinition("rows", "Activities", "count_rows"),
         MetricDefinition("employees", "Employees", "count_distinct", "employee"),
         MetricDefinition("minutes", "Minutes", "sum", "minutes"),
         MetricDefinition("average", "Average minutes", "average", "minutes")),
        (DimensionDefinition("employee", "Employee", "employee"),),
        (FilterDefinition("employee_filter", "Employee", "employee"),
         FilterDefinition("hours_filter", "Hours", "hours", ("eq", "gte", "lt", "is_null"))),
        TimeDefinition("day"),
    )


def report(*, configured=None, **changes):
    configured = configured or dataset()
    spec = ReportSpec("activity", ("hours",), period=PeriodSelection("month", year=2026, month=9),
                      time_grain="day")
    spec = replace(spec, **changes)
    access = DatasetAccess("activity", policies=(RowPolicy("tenant", "eq", (1,)), RowPolicy("deleted", "eq", (False,))))
    return validate_report(configured, spec, access, today=date(2026, 10, 5))


class Cursor:
    def __init__(self, owner):
        self.owner = owner
        self.description = None
        self.phase = "metadata"
        self.closed = False
        self.cancelled = Event()
        self.fetch_sizes = []

    def execute(self, sql, *parameters):
        self.owner.statements.append((sql, parameters))
        self.phase = "metadata" if "sys.columns" in sql else "report"
        if self.owner.failure_phase == self.phase:
            raise RuntimeError("secret connection-string and private row-value")
        if self.phase == "report":
            self.description = [(name,) for name in self.owner.field_ids]
            self.owner.report_started.set()
        return self

    def fetchmany(self, size):
        self.fetch_sizes.append(size)
        if self.owner.block_phase == self.phase:
            self.cancelled.wait(1)
            raise RuntimeError("ODBC timeout contains private hostname")
        return self.owner.metadata if self.phase == "metadata" else self.owner.rows[:size]

    def cancel(self):
        self.owner.cancel_calls += 1
        self.cancelled.set()

    def close(self):
        self.closed = True
        if self.owner.fail_cursor_close:
            raise RuntimeError("private close error")


class Connection:
    def __init__(self, configured=None, *, rows=None, fields=("time_bucket", "hours")):
        configured = configured or dataset()
        self.metadata = [(column.name, column.data_type.split("(")[0], column.nullable, "U", 18, 2)
                         for column in configured.columns]
        self.rows = rows if rows is not None else [(date(2026, 9, 1), Decimal("4.00"))]
        self.field_ids = fields
        self.statements = []
        self.timeout = 0
        self.cursor_timeout = None
        self.failure_phase = None
        self.block_phase = None
        self.fail_cursor_close = False
        self.fail_rollback = False
        self.fail_close = False
        self.rolled_back = self.closed = False
        self.cancel_calls = 0
        self.report_started = Event()
        self.handle = Cursor(self)

    def cursor(self):
        self.cursor_timeout = self.timeout
        return self.handle

    def rollback(self):
        self.rolled_back = True
        if self.fail_rollback:
            raise RuntimeError("secret rollback error")

    def close(self):
        self.closed = True
        if self.fail_close:
            raise RuntimeError("secret close error")


@pytest.fixture
def sqlite_file(tmp_path):
    path = tmp_path / "report.sqlite"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE activity (tenant INT NOT NULL, day DATE NOT NULL, employee NVARCHAR(100) NOT NULL, hours DECIMAL(18,2), deleted BIT NOT NULL, minutes INT)")
    connection.executemany("INSERT INTO activity VALUES (?, ?, ?, ?, ?, ?)", (
        (1, "2026-09-01", "Ada", "2.5", 0, 150),
        (1, "2026-09-01", "Ben", "1.5", 0, 90),
        (1, "2026-09-02", "Ada", "3", 0, 180),
        (1, "2026-09-02", "Ada", "50", 1, 3000),
        (2, "2026-09-01", "Ada", "99", 0, 5940),
        (1, "2026-08-31", "Ada", "5", 0, 300),
        (1, "2026-10-01", "Ada", "6", 0, 360),
    ))
    connection.commit()
    connection.close()
    return path


def test_tsql_compilation_has_typed_ordered_bindings_and_hidden_policies():
    validated = report(filters=(UserFilter("hours_filter", "gte", ("1.25",)),))
    query = compile_report(validated, ExecutionLimits(max_rows=20), dialect="tsql")
    assert query.sql.startswith("SELECT TOP (?) [time_bucket], [hours]")
    assert "FROM [dbo].[activity] AS t" in query.sql
    assert "t.[tenant] = ? AND t.[deleted] = ? AND t.[hours] >= ?" in query.sql
    assert query.parameters == (21, 1, False, Decimal("1.25"), date(2026, 9, 1), date(2026, 10, 1))
    assert query.limit == 20
    assert [item.id for item in query.fields] == ["time_bucket", "hours"]
    assert all(item.id not in {"tenant", "deleted"} for item in query.fields)


def test_tsql_dimension_listing_uses_distinct_and_bound_scope_filters_dates_and_cap():
    validated = report(metric_ids=(), dimension_ids=("employee",), time_grain="none",
                       filters=(UserFilter("employee_filter", "eq", ("O'Brien",)),),
                       order_by="employee", descending=True)
    query = compile_report(validated, ExecutionLimits(max_rows=20), dialect="tsql")
    assert query.sql.startswith("SELECT TOP (?) [employee]")
    assert "SELECT DISTINCT t.[employee] AS [employee]" in query.sql
    assert "GROUP BY" not in query.sql and "SUM(" not in query.sql
    assert "t.[tenant] = ? AND t.[deleted] = ? AND t.[employee] = ?" in query.sql
    assert query.sql.endswith("ORDER BY [employee] DESC")
    assert query.parameters == (21, 1, False, "O'Brien", date(2026, 9, 1), date(2026, 10, 1))
    assert query.fields[0].id == "employee" and query.fields[0].type == "text"


def test_sql_server_dimension_listing_retains_schema_verification_and_resource_cleanup():
    configured = replace(dataset(), metrics=())
    connection = Connection(configured, rows=[("Ada",), ("Ben",)], fields=("employee",))
    result = SQLServerAdapter(lambda: connection).execute(
        report(configured=configured, metric_ids=(), dimension_ids=("employee",), time_grain="none"),
        ExecutionLimits(),
    )
    assert result.rows == (("Ada",), ("Ben",))
    assert len(connection.statements) == 2
    assert "SELECT DISTINCT" in connection.statements[1][0]
    assert connection.handle.closed and connection.rolled_back and connection.closed


def test_comparison_rebinds_trusted_policies_for_both_branches():
    validated = report(time_grain="none", comparison=PeriodSelection("month", year=2026, month=8))
    query = compile_report(validated, ExecutionLimits(), dialect="tsql")
    assert query.sql.count("t.[tenant] = ?") == 2
    assert query.sql.count("t.[deleted] = ?") == 2
    assert query.sql.count("TOP (?)") == 1
    assert query.parameters == (101, 1, False, date(2026, 9, 1), date(2026, 10, 1),
                                1, False, date(2026, 8, 1), date(2026, 9, 1))


def test_decimal_input_for_float_column_is_bound_as_float_not_sql_decimal():
    configured = dataset()
    configured = replace(configured, columns=(*configured.columns, Column(configured.table.key, "rate", "float")),
                         filters=(*configured.filters, FilterDefinition("rate_filter", "Rate", "rate", ("gte",))))
    query = compile_report(report(configured=configured, filters=(UserFilter("rate_filter", "gte", (Decimal("1E100"),)),)),
                           ExecutionLimits(), dialect="tsql")
    assert query.parameters[3] == 1e100
    assert type(query.parameters[3]) is float


def test_integer_aggregates_do_not_inherit_sql_server_int_overflow_or_average_truncation():
    query = compile_report(report(metric_ids=("minutes", "average", "rows", "employees"), time_grain="none"),
                           ExecutionLimits(), dialect="tsql")
    assert "SUM(CAST(t.[minutes] AS decimal(38,0)))" in query.sql
    assert "AVG(CAST(t.[minutes] AS decimal(38,6)))" in query.sql
    assert "COUNT_BIG(*)" in query.sql
    assert "COUNT_BIG(DISTINCT t.[employee])" in query.sql
    assert [item.type for item in query.fields] == ["decimal", "decimal", "integer", "integer"]


def test_registered_identifiers_and_unicode_values_are_quoted_and_bound():
    configured = dataset(schema="odd]schema")
    configured = replace(configured, table=Table("activity]name", "odd]schema"),
                         columns=tuple(replace(column, table="odd]schema.activity]name") for column in configured.columns))
    value = "کارمند'; DROP TABLE x;--"
    query = compile_report(report(configured=configured, filters=(UserFilter("employee_filter", "eq", (value,)),)),
                           ExecutionLimits(), dialect="tsql")
    assert "[odd]]schema].[activity]]name]" in query.sql
    assert value not in query.sql
    assert value in query.parameters


def test_sql_server_verifies_metadata_then_executes_and_closes_all_resources():
    connection = Connection()
    result = SQLServerAdapter(lambda: connection).execute(report(), ExecutionLimits(query_timeout_seconds=4))
    assert result.rows == ((date(2026, 9, 1), Decimal("4.00")),)
    assert connection.cursor_timeout == 4
    assert len(connection.statements) == 2
    assert connection.statements[0][1][:2] == ("dbo", "activity")
    assert connection.handle.closed and connection.rolled_back and connection.closed


@pytest.mark.parametrize("change", ("missing", "wrong_type", "wrong_kind", "precision", "nullable"))
def test_schema_drift_blocks_report_query_and_cleans_up(change):
    connection = Connection()
    if change == "missing":
        connection.metadata.pop()
    elif change == "wrong_type":
        connection.metadata[3] = ("hours", "nvarchar", True, "U", 18, 2)
    elif change == "wrong_kind":
        connection.metadata[0] = ("tenant", "int", False, "V", 18, 2)
    elif change == "precision":
        connection.metadata[3] = ("hours", "decimal", True, "U", 18, 3)
    else:
        connection.metadata[0] = ("tenant", "int", True, "U", 18, 2)
    with pytest.raises(SDKError) as failure:
        SQLServerAdapter(lambda: connection).execute(report(), ExecutionLimits())
    assert failure.value.code == "schema_drift"
    assert len(connection.statements) == 1
    assert connection.handle.closed and connection.rolled_back and connection.closed


def test_sql_server_supports_registered_reporting_views():
    configured = dataset(schema="reports", kind="VIEW")
    connection = Connection(configured)
    connection.metadata = [(*row[:3], "V", *row[4:]) for row in connection.metadata]
    result = SQLServerAdapter(lambda: connection).execute(report(configured=configured), ExecutionLimits())
    assert result.rows
    assert "[reports].[activity]" in connection.statements[1][0]


def test_legacy_sql_server_text_is_not_admitted_by_scalar_family_compatibility():
    connection = Connection()
    connection.metadata[2] = ("employee", "ntext", False, "U", 0, 0)
    with pytest.raises(SDKError) as failure:
        SQLServerAdapter(lambda: connection).execute(report(), ExecutionLimits())
    assert failure.value.code == "unsupported"
    assert len(connection.statements) == 1
    assert connection.closed


def test_explicit_numeric_precision_without_scale_means_zero_scale():
    configured = dataset()
    configured = replace(configured, columns=tuple(replace(column, data_type="numeric(18)") if column.name == "hours" else column for column in configured.columns))
    connection = Connection(configured)
    # The fixture exposes scale2 but registration explicitly requested scale0.
    with pytest.raises(SDKError) as failure:
        SQLServerAdapter(lambda: connection).execute(report(configured=configured), ExecutionLimits())
    assert failure.value.code == "schema_drift"
    assert len(connection.statements) == 1


@pytest.mark.parametrize("dialect,policy_count", (("tsql", 21), ("sqlite", 9)))
def test_parameter_budgets_fail_before_database_execution(dialect, policy_count):
    validated = report()
    access = replace(validated.access, policies=(RowPolicy("tenant", "in", tuple(range(100))),) * policy_count)
    validated = validate_report(validated.dataset, validated.spec, access, today=validated.as_of)
    with pytest.raises(SDKError) as failure:
        compile_report(validated, ExecutionLimits(), dialect=dialect)
    assert failure.value.code == "unsupported"


@pytest.mark.parametrize("phase", ("metadata", "report"))
def test_driver_failures_are_sanitized_and_cancelled(phase):
    connection = Connection()
    connection.failure_phase = phase
    with pytest.raises(SDKError) as failure:
        SQLServerAdapter(lambda: connection).execute(report(), ExecutionLimits())
    assert failure.value.code == "execution_failed"
    assert "secret" not in str(failure.value)
    assert failure.value.__cause__ is None
    assert connection.cancel_calls >= 1
    assert connection.handle.closed and connection.rolled_back and connection.closed


def test_factory_failure_is_sanitized():
    def fail():
        raise RuntimeError("PASSWORD=secret;SERVER=private")
    with pytest.raises(SDKError, match="database could not be reached") as failure:
        SQLServerAdapter(fail).execute(report(), ExecutionLimits())
    assert failure.value.code == "database_unavailable"
    assert failure.value.retryable
    assert "secret" not in str(failure.value)
    assert failure.value.__cause__ is None


def test_unavailable_database_releases_slot_and_allows_a_later_successful_connection():
    connection = Connection()
    attempts = []

    def connect():
        attempts.append(True)
        if len(attempts) == 1:
            raise RuntimeError("PASSWORD=secret;SERVER=private")
        return connection

    adapter = SQLServerAdapter(connect, max_concurrent_queries=1)
    with pytest.raises(SDKError) as failure:
        adapter.execute(report(), ExecutionLimits())
    assert failure.value.code == "database_unavailable"
    assert not connection.statements
    assert adapter.execute(report(), ExecutionLimits()).rows
    assert connection.closed and connection.rolled_back


@pytest.mark.parametrize("failed_cleanup", ("fail_cursor_close", "fail_rollback", "fail_close"))
def test_cleanup_attempts_every_resource_even_when_one_step_fails(failed_cleanup):
    connection = Connection()
    setattr(connection, failed_cleanup, True)
    with pytest.raises(SDKError, match="cleanup failed"):
        SQLServerAdapter(lambda: connection).execute(report(), ExecutionLimits())
    assert connection.handle.closed and connection.rolled_back and connection.closed


def test_original_error_survives_a_second_cleanup_error():
    connection = Connection()
    connection.failure_phase = "report"
    connection.fail_rollback = True
    with pytest.raises(SDKError, match="SQL Server report execution failed"):
        SQLServerAdapter(lambda: connection).execute(report(), ExecutionLimits())
    assert connection.closed


def test_sql_server_row_limit_is_enforced_in_sql_and_fetch():
    connection = Connection(rows=[(date(2026, 9, day), Decimal(day)) for day in (1, 2, 3)])
    result = SQLServerAdapter(lambda: connection).execute(report(), ExecutionLimits(max_rows=2))
    assert len(result.rows) == 2 and result.truncated
    assert connection.statements[1][1][0] == 3
    assert connection.handle.fetch_sizes[-1] == 3


@pytest.mark.parametrize("phase", ("metadata", "report"))
def test_sql_server_deadline_cancels_blocking_cursor_and_cleans_up(phase):
    connection = Connection()
    connection.block_phase = phase
    with pytest.raises(SDKError) as failure:
        SQLServerAdapter(lambda: connection).execute(report(), ExecutionLimits(query_timeout_seconds=0.05))
    assert failure.value.code == "query_timeout"
    assert connection.cancel_calls >= 1
    assert connection.handle.closed and connection.rolled_back and connection.closed


def test_pre_cancelled_request_never_opens_connection():
    cancelled = Event()
    cancelled.set()
    opened = []
    with pytest.raises(SDKError) as failure:
        SQLServerAdapter(lambda: opened.append(True)).execute(report(), ExecutionLimits(), cancel=cancelled)
    assert failure.value.code == "cancelled"
    assert not opened


def test_external_cancellation_stops_running_report_and_releases_concurrency_slot():
    connection = Connection()
    connection.block_phase = "report"
    cancelled = Event()
    checkouts = iter((connection, Connection()))
    adapter = SQLServerAdapter(lambda: next(checkouts), max_concurrent_queries=1)
    failures = []

    def run():
        try:
            adapter.execute(report(), ExecutionLimits(), cancel=cancelled)
        except SDKError as error:
            failures.append(error.code)

    worker = Thread(target=run)
    worker.start()
    assert connection.report_started.wait(1)
    try:
        with pytest.raises(SDKError) as busy:
            adapter.execute(report(), ExecutionLimits())
        assert busy.value.code == "database_busy"
    finally:
        cancelled.set()
        worker.join(timeout=2)
    assert not worker.is_alive()
    assert failures == ["cancelled"]
    assert connection.closed and connection.handle.closed and connection.rolled_back
    # Retry can check out a new report after the interrupted call released its slot.
    assert adapter.execute(report(), ExecutionLimits()).rows


def test_tampered_resolved_period_fails_before_connect():
    validated = report()
    forged = replace(validated, period=replace(validated.period, start=date(2025, 1, 1)))
    opened = []
    with pytest.raises(SDKError) as failure:
        SQLServerAdapter(lambda: opened.append(True)).execute(forged, ExecutionLimits())
    assert failure.value.code == "invalid_spec"
    assert not opened


def test_unauthorized_model_reference_fails_before_connect():
    validated = report()
    forged = replace(validated, spec=replace(validated.spec, dimension_ids=("tenant",)))
    opened = []
    with pytest.raises(SDKError):
        SQLServerAdapter(lambda: opened.append(True)).execute(forged, ExecutionLimits())
    assert not opened


def test_adapter_has_no_model_sql_execution_interface():
    opened = []
    with pytest.raises(SDKError) as failure:
        SQLServerAdapter(lambda: opened.append(True)).execute("SELECT * FROM private; DELETE FROM private", ExecutionLimits())
    assert failure.value.code == "invalid_spec"
    assert not opened


def test_result_description_and_binary_values_fail_closed():
    for connection in (Connection(fields=("private", "hours")), Connection(rows=[(date(2026, 9, 1), b"private")])):
        with pytest.raises(SDKError):
            SQLServerAdapter(lambda: connection).execute(report(), ExecutionLimits())
        assert connection.closed


def test_sqlite_actual_totals_apply_trusted_tenant_active_and_half_open_dates(sqlite_file):
    result = SQLiteAdapter(sqlite_file).execute(report(), ExecutionLimits())
    assert result.rows == ((date(2026, 9, 1), Decimal("4")), (date(2026, 9, 2), Decimal("3")))
    assert not result.truncated


def test_sqlite_refinement_preserves_period_and_metric_and_changes_grouping(sqlite_file):
    result = SQLiteAdapter(sqlite_file).execute(report(time_grain="none", dimension_ids=("employee",)), ExecutionLimits())
    assert result.rows == (("Ada", Decimal("5.5")), ("Ben", Decimal("1.5")))


def test_sqlite_dimension_listing_deduplicates_and_excludes_other_tenants_deleted_and_outside_period(sqlite_file):
    connection = sqlite3.connect(sqlite_file)
    connection.executemany("INSERT INTO activity VALUES (?, ?, ?, ?, ?, ?)", (
        (2, "2026-09-01", "Private tenant employee", "99", 0, 5940),
        (1, "2026-09-01", "Deleted employee", "99", 1, 5940),
        (1, "2026-08-31", "Outside period employee", "99", 0, 5940),
    ))
    connection.commit()
    connection.close()
    before = sqlite_file.read_bytes()
    result = SQLiteAdapter(sqlite_file).execute(
        report(metric_ids=(), dimension_ids=("employee",), time_grain="none"), ExecutionLimits(),
    )
    assert result.rows == (("Ada",), ("Ben",))
    assert result.fields[0].id == "employee"
    assert not result.truncated
    assert sqlite_file.read_bytes() == before


def test_sqlite_dimension_listing_user_filter_and_row_cap_apply_after_distinct(sqlite_file):
    adapter = SQLiteAdapter(sqlite_file)
    requested = dict(metric_ids=(), dimension_ids=("employee",), time_grain="none")
    one = adapter.execute(report(**requested, order_by="employee", descending=True, limit=1), ExecutionLimits())
    assert one.rows == (("Ben",),) and one.truncated
    filtered = adapter.execute(report(**requested, filters=(UserFilter("employee_filter", "eq", ("Ada",)),)), ExecutionLimits())
    assert filtered.rows == (("Ada",),) and not filtered.truncated
    empty = adapter.execute(report(**requested, period=PeriodSelection("month", year=2030, month=9)), ExecutionLimits())
    assert empty.rows == ()


def test_sqlite_user_filters_cannot_override_mandatory_scope(sqlite_file):
    result = SQLiteAdapter(sqlite_file).execute(report(filters=(UserFilter("employee_filter", "eq", ("Ada",)),)), ExecutionLimits())
    assert result.rows == ((date(2026, 9, 1), Decimal("2.5")), (date(2026, 9, 2), Decimal("3")))


def test_sqlite_comparison_has_real_correct_totals_for_both_scopes(sqlite_file):
    result = SQLiteAdapter(sqlite_file).execute(report(time_grain="none", comparison=PeriodSelection("month", year=2026, month=8)), ExecutionLimits())
    assert result.rows == (("base", Decimal("7")), ("comparison", Decimal("5")))


@pytest.mark.parametrize("grain,expected", (("week", "2026-08-31"), ("month", "2026-09-01"),
                                             ("quarter", "2026-07-01"), ("year", "2026-01-01")))
def test_sqlite_calendar_buckets_have_correct_boundaries(sqlite_file, grain, expected):
    result = SQLiteAdapter(sqlite_file).execute(report(time_grain=grain), ExecutionLimits())
    assert result.rows == ((date.fromisoformat(expected), Decimal("7")),)


def test_sqlite_metric_sort_and_topn_cap(sqlite_file):
    result = SQLiteAdapter(sqlite_file).execute(report(time_grain="none", dimension_ids=("employee",),
                                                     order_by="hours", descending=True, limit=1), ExecutionLimits())
    assert result.rows == (("Ada", Decimal("5.5")),)
    assert result.truncated


def test_sqlite_empty_groups_and_empty_scalar_are_distinguished(sqlite_file):
    options = dict(period=PeriodSelection("month", year=2030, month=9))
    result = SQLiteAdapter(sqlite_file).execute(report(**options), ExecutionLimits())
    assert result.rows == ()
    scalar = SQLiteAdapter(sqlite_file).execute(report(time_grain="none", **options), ExecutionLimits())
    assert scalar.rows == ((None,),)


def test_sqlite_connection_opens_readonly_and_does_not_change_database(sqlite_file):
    before = sqlite_file.read_bytes()
    SQLiteAdapter(sqlite_file).execute(report(), ExecutionLimits())
    assert sqlite_file.read_bytes() == before


def test_sqlite_missing_or_mismatched_schema_fails_safely(sqlite_file, tmp_path):
    with pytest.raises(SDKError) as missing:
        SQLiteAdapter(tmp_path / "absent.sqlite").execute(report(), ExecutionLimits())
    assert missing.value.code == "database_unavailable"
    changed = replace(dataset(), columns=tuple(replace(column, data_type="text") if column.name == "hours" else column for column in dataset().columns))
    # A text SUM definition is semantically invalid, independently of metadata.
    with pytest.raises(SDKError):
        validate_report(changed, report().spec, report().access, today=date(2026, 10, 5))


def test_sqlite_view_requires_a_separate_reviewed_execution_scope(sqlite_file):
    with pytest.raises(SDKError) as failure:
        SQLiteAdapter(sqlite_file).execute(report(configured=dataset(kind="VIEW")), ExecutionLimits())
    assert failure.value.code == "unsupported"


def test_sqlite_vm_budget_stops_expensive_aggregate(sqlite_file):
    connection = sqlite3.connect(sqlite_file)
    connection.executemany("INSERT INTO activity VALUES (1, '2026-09-01', 'Ada', 1, 0, 60)", [()] * 2_000)
    connection.commit()
    connection.close()
    with pytest.raises(SDKError) as failure:
        SQLiteAdapter(sqlite_file, max_vm_steps=1000).execute(report(), ExecutionLimits())
    assert failure.value.code == "query_work_limit"


def test_opt_in_sql_server_synthetic_fixture_is_readonly_and_scoped():
    """Opt-in integration; the host seeds this test fixture before running it.

    Set SAGEQL_SQLSERVER_TEST_CONFIRM_SYNTHETIC=1, an ODBC connection string in
    SAGEQL_SQLSERVER_TEST_CONNECTION, and SAGEQL_SQLSERVER_TEST_TABLE. Optional
    SCHEMA (default dbo) and KIND (TABLE or VIEW) use the same variable prefix.
    The object must expose the columns and rows documented by sqlite_file above.
    This test performs SELECTs only, never creates/seeds objects or calls a model.
    """
    connection_string = os.environ.get("SAGEQL_SQLSERVER_TEST_CONNECTION")
    table_name = os.environ.get("SAGEQL_SQLSERVER_TEST_TABLE")
    if (os.environ.get("SAGEQL_SQLSERVER_TEST_CONFIRM_SYNTHETIC") != "1"
            or not connection_string or not table_name):
        pytest.skip("SQL Server integration requires explicit synthetic-fixture configuration")
    pyodbc = pytest.importorskip("pyodbc")
    registered = dataset()
    table = Table(table_name, os.environ.get("SAGEQL_SQLSERVER_TEST_SCHEMA", "dbo"),
                  os.environ.get("SAGEQL_SQLSERVER_TEST_KIND", "TABLE"))
    registered = replace(registered, table=table,
                         columns=tuple(replace(column, table=table.key) for column in registered.columns))
    adapter = SQLServerAdapter(lambda: pyodbc.connect(connection_string, timeout=5, autocommit=False))
    limits = ExecutionLimits(max_rows=10, query_timeout_seconds=5)
    tenant_one = report(configured=registered)
    one = adapter.execute(tenant_one, limits)
    expected_one = ((date(2026, 9, 1), Decimal("4")), (date(2026, 9, 2), Decimal("3")))
    tenant_two_access = replace(tenant_one.access, policies=(RowPolicy("tenant", "eq", (2,)),
                                                          RowPolicy("deleted", "eq", (False,))))
    tenant_two = validate_report(registered, tenant_one.spec, tenant_two_access, today=tenant_one.as_of)
    two = adapter.execute(tenant_two, limits)
    if one.rows != expected_one or two.rows != ((date(2026, 9, 1), Decimal("99")),):
        pytest.fail("The explicitly configured synthetic SQL Server fixture returned unexpected scoped totals.")
    if one.truncated or two.truncated:
        pytest.fail("The synthetic integration fixture exceeded its expected row bounds.")
