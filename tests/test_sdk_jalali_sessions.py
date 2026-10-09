"""Calendar comparisons keep effective dates through persistence/refinement."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
import sqlite3

import pytest

from sageql import Column, Table
from sageql.sdk import (
    AccessScope, ActorContext, DatasetAccess, DatasetDefinition, ExecutionLimits,
    Interpretation, MetricDefinition, PeriodSelection, ReportingCatalog,
    ReportSpec, RowPolicy, SDKError, SageQL, SQLiteAdapter, SQLiteSessionStore,
    TimeDefinition,
)
from sageql.sdk.adapters import compile_report
from sageql.sdk.semantics import validate_report


ACTOR = ActorContext("calendar-reviewer", "1")
AS_OF = date(2026, 10, 8)
SHAHRIVAR = PeriodSelection("jalali_month", year=1405, month=6)
MORDAD = PeriodSelection("jalali_month", year=1405, month=5)
SEPTEMBER = PeriodSelection("range", start="2026-09-01", end="2026-10-01")


def catalog():
    table = Table("calendar_activity")
    return ReportingCatalog((DatasetDefinition(
        "activity", "فعالیت", table,
        tuple(Column(table.key, name, kind) for name, kind in (
            ("tenant", "int"), ("deleted", "int"),
            ("worked_on", "date"), ("hours", "decimal"),
        )),
        (MetricDefinition("hours_sum", "ساعات فعالیت", "sum", "hours", "ساعت"),),
        time=TimeDefinition("worked_on"),
    ),))


def policy(actor):
    return AccessScope((DatasetAccess("activity", policies=(
        RowPolicy("tenant", "eq", (int(actor.tenant_id),)),
        RowPolicy("deleted", "eq", (0,)),
    )),))


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "calendar-comparisons.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE calendar_activity "
                           "(tenant INTEGER, deleted INTEGER, worked_on DATE, hours DECIMAL)")
        connection.executemany("INSERT INTO calendar_activity VALUES (?, ?, ?, ?)", [
            (1, 0, "2026-07-22", 100),
            (1, 0, "2026-07-23", 1),
            (1, 0, "2026-08-22", 2),
            (1, 0, "2026-08-23", 4),
            (1, 0, "2026-09-01", 8),
            (1, 0, "2026-09-22", 16),
            (1, 0, "2026-09-23", 32),
            (1, 0, "2026-09-30", 64),
            (1, 0, "2026-10-01", 1000),
            (2, 0, "2026-09-01", 9999),
            (1, 1, "2026-09-01", 8888),
        ])
    return path


@pytest.mark.parametrize("base, comparison, frozen_base, frozen_comparison, bounds, totals", [
    (SHAHRIVAR, MORDAD, SHAHRIVAR, MORDAD,
     (date(2026, 8, 23), date(2026, 9, 23), date(2026, 7, 23), date(2026, 8, 23)),
     (28, 3)),
    (PeriodSelection("last_month"), SHAHRIVAR, SEPTEMBER, SHAHRIVAR,
     (date(2026, 9, 1), date(2026, 10, 1), date(2026, 8, 23), date(2026, 9, 23)),
     (120, 28)),
    (SHAHRIVAR, PeriodSelection("last_month"), SHAHRIVAR, SEPTEMBER,
     (date(2026, 8, 23), date(2026, 9, 23), date(2026, 9, 1), date(2026, 10, 1)),
     (28, 120)),
])
def test_jalali_and_mixed_comparisons_retain_original_bounds_after_restart(
    database, tmp_path, base, comparison, frozen_base, frozen_comparison, bounds, totals,
):
    requested = ReportSpec("activity", ("hours_sum",), period=base,
                           comparison=comparison, order_by="period_label")
    definition = catalog().datasets[0]
    prepared = validate_report(definition, requested, policy(ACTOR).datasets[0], today=AS_OF)
    query = compile_report(prepared, ExecutionLimits(), dialect="tsql")
    assert query.parameters == (101, 1, 0, bounds[0], bounds[1], 1, 0, bounds[2], bounds[3])
    assert query.sql.count("[tenant] = ?") == 2
    assert query.sql.count("[deleted] = ?") == 2

    class Provider:
        def __init__(self):
            self.calls = 0

        def interpret(self, messages, current_spec, allowed, today):
            self.calls += 1
            if self.calls == 1:
                assert current_spec is None
                return Interpretation("ready", requested)
            assert current_spec == replace(requested, period=frozen_base, comparison=frozen_comparison)
            return Interpretation("ready", replace(current_spec, descending=True))

    provider = Provider()
    session_path = tmp_path / "calendar-session.sqlite"

    def engine(today):
        return SageQL(catalog=catalog(), database=SQLiteAdapter(database), provider=provider,
                      policy=policy, sessions=SQLiteSessionStore(session_path),
                      clock=lambda: today, execution="validated")

    first_engine = engine(AS_OF)
    created = first_engine.create_session(ACTOR)
    first = first_engine.submit(created.session_id, "مقایسه ساعات دو دوره", ACTOR, "first", 0)
    assert first.status == "report_ready"
    assert first.report.rows == (("base", Decimal(totals[0])), ("comparison", Decimal(totals[1])))
    assert first.report.provenance["period_selection"] == requested.to_dict()["period"]
    assert first.report.provenance["comparison_selection"] == requested.to_dict()["comparison"]
    captions = first.report.provenance["period_labels"]
    assert set(captions) == {"base", "comparison"}
    for key, selection, start, end in (
        ("base", base, bounds[0], bounds[1]),
        ("comparison", comparison, bounds[2], bounds[3]),
    ):
        expected = ({5: "مرداد 1405", 6: "شهریور 1405"}[selection.month]
                    if selection.kind == "jalali_month"
                    else f"{start.isoformat()} تا پیش از {end.isoformat()}")
        assert captions[key] == expected
        assert expected in first.report.title
    assert "در مقایسه با" in first.report.title

    # Both the Gregorian year and Jalali year change before a persistent restart.
    restarted = engine(date(2027, 4, 1))
    refined = restarted.submit(created.session_id, "ترتیب دوره‌ها را برعکس کن", ACTOR, "refine", 1)
    assert refined.status == "report_ready"
    assert refined.report.rows == tuple(reversed(first.report.rows))
    provenance = refined.report.provenance
    assert (provenance["period_start"], provenance["period_end_exclusive"],
            provenance["comparison_start"], provenance["comparison_end_exclusive"]) == tuple(
        value.isoformat() for value in bounds
    )
    frozen = replace(requested, period=frozen_base, comparison=frozen_comparison).to_dict()
    assert provenance["period_selection"] == frozen["period"]
    assert provenance["comparison_selection"] == frozen["comparison"]
    assert provenance["period_labels"] == captions
    assert restarted.get_report(created.session_id, first.report.id, ACTOR) == first.report

    # A retry still returns the original period metadata/result without reinterpreting.
    retried = restarted.submit(created.session_id, "مقایسه ساعات دو دوره", ACTOR, "first", 0)
    assert retried == first
    assert provider.calls == 2


@pytest.mark.parametrize("grain", ["week", "month", "quarter", "year"])
def test_jalali_comparison_alone_rejects_coarse_gregorian_buckets(grain):
    requested = ReportSpec("activity", ("hours_sum",), period=SEPTEMBER,
                           comparison=SHAHRIVAR, time_grain=grain)
    with pytest.raises(SDKError) as caught:
        validate_report(catalog().datasets[0], requested, policy(ACTOR).datasets[0], today=AS_OF)
    assert caught.value.code == "unsupported"


def test_gregorian_comparison_has_resolved_english_period_labels(database):
    requested = ReportSpec("activity", ("hours_sum",), period=PeriodSelection("last_month"),
                           comparison=PeriodSelection("month", year=2026, month=8))

    class Provider:
        def interpret(self, *args):
            return Interpretation("ready", requested)

    sdk = SageQL(catalog=catalog(), database=SQLiteAdapter(database), provider=Provider(),
                 policy=policy, clock=lambda: AS_OF, execution="validated", language="en")
    session = sdk.create_session(ACTOR)
    reply = sdk.submit(session.session_id, "Compare September with August", ACTOR, "comparison", 0)
    assert reply.status == "report_ready"
    assert reply.report.provenance["period_labels"] == {
        "base": "[2026-09-01, 2026-10-01)",
        "comparison": "[2026-08-01, 2026-09-01)",
    }
    assert "compared with [2026-08-01, 2026-09-01)" in reply.report.title
    assert {row[0] for row in reply.report.rows} == {"base", "comparison"}
