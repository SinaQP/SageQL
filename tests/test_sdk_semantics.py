"""Deterministic semantic rules protect correctness and the model boundary."""

from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal

import pytest

from sageql.schema import Column, Table
from sageql.sdk.models import (
    AccessScope, DatasetAccess, DatasetDefinition, DimensionDefinition,
    FilterDefinition, MetricDefinition, PeriodSelection, ReportSpec,
    ReportingCatalog, RowPolicy, SDKError, TimeDefinition, UserFilter,
)
from sageql.sdk.semantics import (
    column_type, permitted_catalog, resolve_period, validate_catalog,
    validate_report, validate_scope,
)


TODAY = date(2026, 10, 5)


def dataset():
    return DatasetDefinition(
        "activity", "Activity reports", Table("reporting_activity", "dbo", "VIEW"),
        (
            Column("dbo.reporting_activity", "activity_id", "bigint", False),
            Column("dbo.reporting_activity", "tenant_id", "int", False),
            Column("dbo.reporting_activity", "deleted", "bit", False),
            Column("dbo.reporting_activity", "worked_on", "date", False),
            Column("dbo.reporting_activity", "hours", "decimal(18,2)"),
            Column("dbo.reporting_activity", "employee", "nvarchar(100)"),
        ),
        (MetricDefinition("activity_hours", "Activity hours", "sum", "hours", "hours"),
         MetricDefinition("records", "Record count", "count_rows")),
        (DimensionDefinition("employee", "Employee", "employee"),),
        (FilterDefinition("employee_filter", "Employee selection", "employee"),
         FilterDefinition("hours_filter", "Hours selection", "hours", ("gte", "lte", "in"))),
        TimeDefinition("worked_on"), row_key=("activity_id",),
    )


def access():
    return DatasetAccess(
        "activity", policies=(RowPolicy("tenant_id", "eq", (7,)), RowPolicy("deleted", "eq", (False,))),
    )


def spec(**changes):
    return replace(ReportSpec("activity", ("activity_hours",), period=PeriodSelection("month", year=2026, month=9)), **changes)


def assert_error(code, callback):
    with pytest.raises(SDKError) as caught:
        callback()
    assert caught.value.code == code


def test_scope_hides_private_columns_and_denied_definitions_before_model_request():
    definition = dataset()
    allowed = replace(access(), metric_ids=("activity_hours",), dimension_ids=(), filter_ids=())
    visible = permitted_catalog(ReportingCatalog((definition,), "catalog-v2"), AccessScope((allowed,), "tenant-policy-v1"))

    assert visible.version == "catalog-v2"
    selected = visible.datasets[0]
    assert [column.name for column in selected.columns] == ["worked_on", "hours"]
    assert [metric.id for metric in selected.metrics] == ["activity_hours"]
    assert selected.dimensions == selected.filters == selected.row_key == ()
    assert "tenant_id" not in repr(visible)
    assert "tenant-policy" not in repr(visible)
    assert definition.row_key == ("activity_id",)


def test_count_only_dataset_hides_all_unexposed_columns():
    definition = replace(dataset(), metrics=(MetricDefinition("records", "Record count", "count_rows"),), dimensions=(), filters=(), time=None)
    visible = permitted_catalog(ReportingCatalog((definition,)), AccessScope((access(),)))
    assert visible.datasets[0].columns == ()
    assert visible.datasets[0].row_key == ()


def test_scope_without_metrics_keeps_permitted_dimensions_and_empty_scope_grants_nothing():
    catalog = ReportingCatalog((dataset(),))
    visible = permitted_catalog(catalog, AccessScope((replace(access(), metric_ids=()),)))
    assert visible.datasets[0].metrics == ()
    assert visible.datasets[0].dimensions == dataset().dimensions
    assert permitted_catalog(catalog, AccessScope((replace(access(), metric_ids=(), dimension_ids=()),))).datasets == ()
    assert permitted_catalog(catalog, AccessScope(())).datasets == ()


def test_dimension_only_dataset_and_listing_need_no_synthetic_aggregate():
    definition = replace(dataset(), metrics=(), time=None)
    requested = ReportSpec("activity", (), dimension_ids=("employee",))
    validate_catalog(ReportingCatalog((definition,)))
    validated = validate_report(definition, requested, replace(access(), metric_ids=()), today=TODAY)
    assert validated.spec.metric_ids == ()
    assert validated.spec.dimension_ids == ("employee",)
    assert validated.period.start is None


def test_dimension_listing_accepts_registered_filters_dates_and_ordering():
    requested = spec(metric_ids=(), dimension_ids=("employee",),
                     filters=(UserFilter("employee_filter", "is_not_null"),),
                     order_by="employee", descending=True)
    validated = validate_report(dataset(), requested, access(), today=TODAY)
    assert validated.period.start == date(2026, 9, 1)
    assert validated.access.policies == access().policies


@pytest.mark.parametrize("changes", [
    {"chart": "bar"}, {"chart": "line"}, {"chart": "kpi"},
    {"time_grain": "day"},
    {"comparison": PeriodSelection("month", year=2026, month=8)},
])
def test_dimension_listing_rejects_aggregate_presentations_and_comparisons(changes):
    requested = spec(metric_ids=(), dimension_ids=("employee",), **changes)
    assert_error("unsupported", lambda: validate_report(dataset(), requested, access(), today=TODAY))


@pytest.mark.parametrize("time_grain", ["none", "day"])
def test_empty_or_time_only_reports_have_no_selected_reporting_concept(time_grain):
    requested = spec(metric_ids=(), dimension_ids=(), time_grain=time_grain)
    assert_error("invalid_spec", lambda: validate_report(dataset(), requested, access(), today=TODAY))


def test_fieldless_catalog_and_denied_dimension_listing_fail_closed():
    assert_error("invalid_catalog", lambda: validate_catalog(ReportingCatalog((replace(dataset(), metrics=(), dimensions=()),))))
    requested = spec(metric_ids=(), dimension_ids=("employee",))
    assert_error("access_denied", lambda: validate_report(dataset(), requested, replace(access(), dimension_ids=()), today=TODAY))


def test_spec_preserves_immutable_user_filters_and_separate_mandatory_policy():
    user_filter = UserFilter("employee_filter", "eq", ("O'Brien'; DROP TABLE activity;--",))
    requested = spec(filters=(user_filter,), dimension_ids=("employee",), chart="bar")
    trusted = access()
    validated = validate_report(dataset(), requested, trusted, today=TODAY)

    assert validated.spec is requested
    assert validated.access is trusted
    assert validated.spec.filters == (user_filter,)
    assert [condition.column for condition in validated.access.policies] == ["tenant_id", "deleted"]
    assert validated.period.start == date(2026, 9, 1)
    assert validated.period.end == date(2026, 10, 1)


@pytest.mark.parametrize("changes", [
    {"metric_ids": ("tenant_id",)},
    {"dimension_ids": ("tenant_id",)},
    {"filters": (UserFilter("tenant_id", "eq", (8,)),)},
    {"order_by": "tenant_id"},
    {"metric_ids": ("activity_hours", "activity_hours")},
])
def test_unregistered_or_private_ids_never_become_a_report(changes):
    assert_error("invalid_spec", lambda: validate_report(dataset(), spec(**changes), access(), today=TODAY))


@pytest.mark.parametrize("changes,restricted", [
    ({"metric_ids": ("records",)}, {"metric_ids": ("activity_hours",)}),
    ({"dimension_ids": ("employee",)}, {"dimension_ids": ()}),
    ({"filters": (UserFilter("employee_filter", "eq", ("Alice",)),)}, {"filter_ids": ()}),
])
def test_registered_but_denied_ids_fail_authorization(changes, restricted):
    assert_error("access_denied", lambda: validate_report(dataset(), spec(**changes), replace(access(), **restricted), today=TODAY))


@pytest.mark.parametrize("rule", [
    DatasetAccess("other"),
    DatasetAccess("activity", metric_ids=("missing",)),
    DatasetAccess("activity", dimension_ids=("employee", "employee")),
    DatasetAccess("activity", policies=(RowPolicy("missing", "eq", (7,)),)),
    DatasetAccess("activity", policies=(RowPolicy("tenant_id", "eq", (True,)),)),
    DatasetAccess("activity", policies=(RowPolicy("deleted", "eq", (0,)),)),
    DatasetAccess("activity", policies=(RowPolicy("tenant_id", "eq", ()),)),
])
def test_malformed_trusted_scope_fails_before_remote_metadata(rule):
    assert_error("invalid_scope", lambda: validate_scope(ReportingCatalog((dataset(),)), AccessScope((rule,))))


def test_duplicate_scope_and_dataset_ids_are_rejected():
    definition = dataset()
    assert_error("invalid_scope", lambda: validate_scope(ReportingCatalog((definition,)), AccessScope((access(), access()))))
    assert_error("invalid_catalog", lambda: validate_catalog(ReportingCatalog((definition, replace(definition, id="ACTIVITY")))))


@pytest.mark.parametrize("value", [Decimal("12.50"), "12.50", 12, 12.5])
def test_finite_decimal_json_values_are_valid_without_lossy_normalization(value):
    condition = UserFilter("hours_filter", "gte", (value,))
    validated = validate_report(dataset(), spec(filters=(condition,)), access(), today=TODAY)
    assert validated.spec.filters[0].values[0] is value


@pytest.mark.parametrize("operator,values", [
    ("gte", (float("nan"),)), ("gte", (float("inf"),)),
    ("gte", (Decimal("NaN"),)), ("gte", (True,)),
    ("gte", (Decimal("1E+999999"),)), ("gte", (Decimal("0E-999999"),)),
    ("gte", ("123456789012345678901234567890123456789",)),
    ("gte", ("0.000000000000000000000000000000000000001",)),
    ("gte", (None,)), ("gte", ("not a number",)),
    ("gte", (1, 2)), ("in", ()), ("eq", (1,)),
])
def test_invalid_filter_values_and_unregistered_operators_fail_closed(operator, values):
    assert_error("invalid_spec", lambda: validate_report(dataset(), spec(filters=(UserFilter("hours_filter", operator, values),)), access(), today=TODAY))


def test_two_different_predicates_can_express_a_bounded_user_filter():
    requested = spec(filters=(UserFilter("hours_filter", "gte", (0,)), UserFilter("hours_filter", "lte", (8,))))
    assert validate_report(dataset(), requested, access(), today=TODAY).spec is requested
    assert_error("invalid_spec", lambda: validate_report(dataset(), replace(requested, filters=(requested.filters[0], requested.filters[0])), access(), today=TODAY))


@pytest.mark.parametrize("selection,today,start,end", [
    (PeriodSelection("all"), TODAY, None, None),
    (PeriodSelection("month", year=2024, month=2), TODAY, "2024-02-01", "2024-03-01"),
    (PeriodSelection("year", year=2024), TODAY, "2024-01-01", "2025-01-01"),
    (PeriodSelection("today"), TODAY, "2026-10-05", "2026-10-06"),
    (PeriodSelection("yesterday"), date(2024, 3, 1), "2024-02-29", "2024-03-01"),
    (PeriodSelection("this_week"), date(2026, 10, 4), "2026-09-28", "2026-10-05"),
    (PeriodSelection("last_week"), TODAY, "2026-09-28", "2026-10-05"),
    (PeriodSelection("this_month"), TODAY, "2026-10-01", "2026-11-01"),
    (PeriodSelection("last_month"), date(2026, 1, 5), "2025-12-01", "2026-01-01"),
    (PeriodSelection("this_year"), TODAY, "2026-01-01", "2027-01-01"),
    (PeriodSelection("last_year"), TODAY, "2025-01-01", "2026-01-01"),
    (PeriodSelection("this_quarter"), TODAY, "2026-10-01", "2027-01-01"),
    (PeriodSelection("last_quarter"), date(2026, 1, 5), "2025-10-01", "2026-01-01"),
    (PeriodSelection("range", "2024-02-29", "2024-03-01"), TODAY, "2024-02-29", "2024-03-01"),
])
def test_gregorian_period_resolution_uses_exact_exclusive_boundaries(selection, today, start, end):
    result = resolve_period(selection, today)
    assert (result.start.isoformat() if result.start else None) == start
    assert (result.end.isoformat() if result.end else None) == end


@pytest.mark.parametrize("selection", [
    PeriodSelection("month", month=9), PeriodSelection("month", year=True, month=9),
    PeriodSelection("year", year=2026, month=9), PeriodSelection("all", year=2026),
    PeriodSelection("month", year=2026, month=13), PeriodSelection("range", "20260201", "2026-03-01"),
    PeriodSelection("range", "2026-02-30", "2026-03-01"), PeriodSelection("range", "2026-03-01", "2026-03-01"),
    PeriodSelection("range", "2026-03-02", "2026-03-01"), PeriodSelection("range", "2026-03-01T00:00:00", "2026-03-02"),
])
def test_ambiguous_or_contradictory_periods_are_rejected(selection):
    assert_error("invalid_spec", lambda: resolve_period(selection, TODAY))


def test_clock_must_supply_business_date_and_date_overflow_fails_safely():
    assert_error("invalid_spec", lambda: resolve_period(PeriodSelection("today"), datetime(2026, 10, 5)))
    assert_error("invalid_spec", lambda: resolve_period(PeriodSelection("yesterday"), date.min))
    assert_error("unsupported", lambda: resolve_period(PeriodSelection("fiscal_year"), TODAY))


@pytest.mark.parametrize("changes", [
    {"metrics": (MetricDefinition("hours", "Hours", "sum", "employee"),)},
    {"metrics": (MetricDefinition("records", "Rows", "count_rows", "hours"),)},
    {"metrics": (MetricDefinition("time_bucket", "Reserved", "count_rows"),)},
    {"dimensions": (DimensionDefinition("activity_hours", "Collision", "employee"),)},
    {"columns": (Column("dbo.other_table", "hours", "decimal"),)},
    {"row_key": ("missing",)},
])
def test_invalid_metric_grain_and_catalog_references_are_rejected(changes):
    assert_error("invalid_catalog", lambda: validate_catalog(ReportingCatalog((replace(dataset(), **changes),))))


def test_timestamp_and_unimplemented_calendars_fail_before_database_access():
    definition = dataset()
    columns = tuple(replace(column, data_type="datetime2(7)") if column.name == "worked_on" else column for column in definition.columns)
    assert_error("unsupported", lambda: validate_catalog(ReportingCatalog((replace(definition, columns=columns),))))
    assert_error("unsupported", lambda: validate_catalog(ReportingCatalog((replace(definition, time=TimeDefinition("worked_on", calendar="persian")),))))
    assert_error("unsupported", lambda: validate_catalog(ReportingCatalog((replace(definition, time=TimeDefinition("worked_on", week_start=6)),))))


def test_comparison_preserves_both_periods_and_requires_labeled_table_output():
    requested = spec(comparison=PeriodSelection("month", year=2025, month=9), order_by="period_label")
    result = validate_report(dataset(), requested, access(), today=TODAY)
    assert result.comparison_period.start == date(2025, 9, 1)
    assert result.comparison_period.end == date(2025, 10, 1)
    assert_error("invalid_spec", lambda: validate_report(dataset(), replace(requested, comparison=PeriodSelection("all")), access(), today=TODAY))
    assert_error("unsupported", lambda: validate_report(dataset(), replace(requested, chart="line", time_grain="month"), access(), today=TODAY))


@pytest.mark.parametrize("changes", [
    {"limit": True}, {"limit": 0}, {"limit": 10001}, {"descending": "false"},
])
def test_row_limits_and_sort_flags_require_explicit_bounded_types(changes):
    assert_error("invalid_spec", lambda: validate_report(dataset(), spec(**changes), access(), today=TODAY))


def test_malformed_runtime_objects_produce_safe_sdk_errors():
    malformed_catalogs = (
        replace(dataset(), table=Table("reporting_activity", "dbo", [])),
        replace(dataset(), row_key=([],)),
        replace(dataset(), metrics=(MetricDefinition("bad", "Bad aggregate", [], "hours"),)),
        replace(dataset(), filters=(FilterDefinition("bad", "Bad filter", "hours", ([],)),)),
    )
    for definition in malformed_catalogs:
        assert_error("invalid_catalog", lambda: validate_catalog(ReportingCatalog((definition,))))
    assert_error("invalid_spec", lambda: validate_report(dataset(), spec(filters=(UserFilter("hours_filter", [], (1,)),)), access(), today=TODAY))


@pytest.mark.parametrize("changes", [
    {"chart": "kpi", "dimension_ids": ("employee",)},
    {"chart": "bar"}, {"chart": "line"},
    {"chart": "line", "time_grain": "day", "dimension_ids": ("employee",)},
    {"chart": "javascript"},
])
def test_presentations_cannot_invent_unsupported_result_shapes(changes):
    assert_error("unsupported", lambda: validate_report(dataset(), spec(**changes), access(), today=TODAY))


@pytest.mark.parametrize("declared,family", [
    ("BIGINT", "integer"), ("decimal(38, 6)", "decimal"), ("numeric", "decimal"),
    ("FLOAT(53)", "number"), ("NVarChar(MAX)", "text"), ("bit", "boolean"),
    ("date", "date"), ("datetimeoffset(7)", "datetime"),
])
def test_declared_sql_types_have_unambiguous_scalar_families(declared, family):
    assert column_type(declared) == family


def test_decimal_parameter_bounds_match_sql_server_numeric_capacity():
    for value in (Decimal("9" * 38), Decimal("1E-38"), Decimal("0E-38")):
        validate_report(dataset(), spec(filters=(UserFilter("hours_filter", "gte", (value,)),)), access(), today=TODAY)


@pytest.mark.parametrize("declared", [
    "timestamp", "binary", "unknown", "decimal(39,2)", "decimal(18,19)",
    "nvarchar(4001)", "varchar(0)", "int(10)", "date); DROP TABLE secret;--",
])
def test_unsupported_sql_types_and_malformed_type_parameters_fail(declared):
    assert_error("invalid_catalog", lambda: column_type(declared))
