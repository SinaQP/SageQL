"""Fixed registered participant means: fact grain, nulls and policy boundaries."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
import json
import sqlite3

import pytest

from sageql.schema import Column, Table
from sageql.sdk import (
    AccessScope, AggregateFilter, DatasetAccess, DatasetDefinition, DimensionDefinition,
    ExecutionLimits, FilterDefinition, MetricDefinition, ReportingCatalog, ReportSpec,
    RowPolicy, SDKError, SQLiteAdapter, UserFilter,
)
from sageql.sdk.adapters import compile_report
from sageql.sdk.intent import ConceptRef, ReportIntent, check_intent
from sageql.sdk.provider import _metadata
from sageql.sdk.semantics import permitted_catalog, validate_catalog, validate_report


TODAY = date(2026, 10, 11)


def dataset(amount_type="int", participant_type="int"):
    table = Table("facts", "main")
    return DatasetDefinition("facts", "Fact groups", table,
        tuple(Column(table.key, name, kind) for name, kind in (
            ("private_amount", amount_type), ("private_identity", participant_type),
            ("category", "nvarchar"), ("deleted", "bit"))),
        metrics=(MetricDefinition("mean", "Mean per participant", "sum_per_participant", "private_amount",
                                  participant_column="private_identity"),
                 MetricDefinition("total", "Total", "sum", "private_amount"),
                 MetricDefinition("participants", "Participants", "count_distinct", "private_identity")),
        dimensions=(DimensionDefinition("category", "Group", "category"),),
        filters=(FilterDefinition("participant", "Participant", "private_identity"),))


def prepare(definition=None, **changes):
    definition = definition or dataset()
    spec = replace(ReportSpec("facts", ("mean", "total", "participants"), ("category",)), **changes)
    return validate_report(definition, spec, DatasetAccess("facts", policies=(RowPolicy("deleted", "eq", (False,)),)), today=TODAY)


def execute(tmp_path, rows, *, definition=None, **changes):
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "facts.sqlite"
    definition = definition or dataset()
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE facts (private_amount int, private_identity int, category nvarchar, deleted bit)")
        connection.executemany("INSERT INTO facts VALUES (?,?,?,?)", rows)
    request = prepare(definition, **changes)
    return SQLiteAdapter(path).execute(request, ExecutionLimits())


def test_unequal_rows_and_null_duration_participation_are_not_activity_average(tmp_path):
    result = execute(tmp_path, [(1, 1, "A", 0), (2, 1, "A", 0), (8, 2, "A", 0),
                                (None, 3, "A", 0), (999, 4, "A", 1)])
    assert result.rows == (("A", 11 / 3, Decimal(11), 3),)
    assert result.fields[1].type == "number" and not result.truncated


@pytest.mark.parametrize("values,expected", [
    ([(None, 1), (None, 2)], (None, None, 2)),
    ([(0, 1), (0, 2)], (0.0, Decimal(0), 2)),
    ([(1, 1), (2, 2)], (1.5, Decimal(3), 2)),
    ([(-8, 1), (2, 2)], (-3.0, Decimal(-6), 2)),
    ([(5, None), (3, 1)], (None, Decimal(8), 1)),
    ([(5, None)], (None, Decimal(5), 0)),
    ([(None, None), (3, 1)], (None, Decimal(3), 1)),
])
def test_unknown_zero_fractional_negative_and_missing_identities(tmp_path, values, expected):
    result = execute(tmp_path, [(hours, identity, "A", 0) for hours, identity in values])
    assert result.rows == (("A", *expected),)


def test_empty_ungrouped_result_is_unknown_not_zero(tmp_path):
    result = execute(tmp_path, [], dimension_ids=())
    assert result.rows == ((None, None, 0),)


def test_filters_ranking_and_limits_follow_complete_group_aggregation(tmp_path):
    rows = [(1, 1, "A", 0), (2, 1, "A", 0), (8, 2, "A", 0),
            (10, 3, "B", 0), (3, 4, "C", 0)]
    result = execute(tmp_path, rows, order_by="mean", descending=True, limit=1,
                     aggregate_filters=(AggregateFilter("mean", "gte", (5.0,)),))
    assert result.rows == (("B", 10.0, Decimal(10), 1),) and result.truncated
    filtered = execute(tmp_path / "filtered", rows, filters=(UserFilter("participant", "eq", (1,)),))
    assert filtered.rows == (("A", 3.0, Decimal(3), 1),)


@pytest.mark.parametrize("dialect", ["sqlite", "tsql"])
def test_deterministic_sql_and_numeric_aggregate_filter_types(dialect):
    request = prepare(aggregate_filters=(AggregateFilter("mean", "gt", (0.5,)),))
    query = compile_report(request, ExecutionLimits(), dialect=dialect)
    count = "COUNT_BIG" if dialect == "tsql" else "COUNT"
    assert f"{count}(DISTINCT t." in query.sql and "NULLIF(" in query.sql
    assert "CASE WHEN" in query.sql and "ELSE NULL END" in query.sql
    assert "CAST(" in query.sql and query.fields[1].type == "number"
    assert query.parameters == ((101, False, 0.5) if dialect == "tsql" else (False, 0.5, 101))
    intent = ReportIntent(metrics=(ConceptRef("facts", "mean"),),
                          aggregate_filters=(AggregateFilter("mean", "gt", (0.5,)),))
    check_intent(intent, ReportingCatalog((request.dataset,)), today=TODAY)


@pytest.mark.parametrize("amount_type,participant_type", [
    ("int", "int"), ("decimal(18,2)", "nvarchar"), ("float", "int"),
])
def test_registered_numeric_amount_and_integer_or_text_identity_types(amount_type, participant_type):
    definition = dataset(amount_type, participant_type)
    validate_catalog(ReportingCatalog((definition,)))
    assert compile_report(prepare(definition), ExecutionLimits(), dialect="tsql").fields[1].type == "number"


@pytest.mark.parametrize("changes", [
    {"participant_column": None}, {"participant_column": "missing"}, {"participant_column": []},
    {"participant_column": "private_amount"},  # A float amount is not an identity.
    {"column": "category"}, {"column": None}, {"aggregation": "sum"},
])
def test_invalid_host_registrations_fail_closed(changes):
    definition = dataset("float")
    metric = replace(definition.metrics[0], **changes)
    with pytest.raises(SDKError, match="column|Numeric|aggregate"):
        validate_catalog(ReportingCatalog((replace(definition, metrics=(metric,)),)))


@pytest.mark.parametrize("column", ["private_amount", "private_identity"])
def test_imported_amount_or_identity_is_rejected(column):
    definition = replace(dataset(), related_columns=(column,))
    with pytest.raises(SDKError):
        validate_catalog(ReportingCatalog((definition,)))


def test_mean_permission_preserves_compiler_columns_and_hides_identity_metadata():
    definition = dataset()
    scope = AccessScope((DatasetAccess("facts", metric_ids=("mean",), dimension_ids=(), filter_ids=()),))
    visible = permitted_catalog(ReportingCatalog((definition,)), scope)
    assert {column.name for column in visible.datasets[0].columns} == {"private_amount", "private_identity"}
    validate_catalog(visible)
    metadata = json.dumps(_metadata(visible))
    assert "private_amount" not in metadata and "private_identity" not in metadata and "participant_column" not in metadata
    denied = DatasetAccess("facts", metric_ids=("total",))
    with pytest.raises(SDKError) as error:
        validate_report(definition, ReportSpec("facts", ("mean",)), denied, today=TODAY)
    assert error.value.code == "access_denied"


def test_model_cannot_supply_participant_columns_or_formula_fields():
    raw = ReportSpec("facts", ("mean",)).to_dict()
    with pytest.raises(SDKError) as error:
        ReportSpec.from_dict({**raw, "participant_column": "another_identity"})
    assert error.value.code == "invalid_spec"
