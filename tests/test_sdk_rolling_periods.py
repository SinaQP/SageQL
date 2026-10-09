from dataclasses import replace
from datetime import date

import pytest

from sageql.sdk import PeriodSelection, ReportSpec, SDKError
from sageql.sdk.semantics import resolve_period


@pytest.mark.parametrize("today,count,unit,start,end", [
    (date(2026,10,9), 3, "month", date(2026,7,9), date(2026,10,10)),
    (date(2026,3,31), 1, "month", date(2026,2,28), date(2026,4,1)),
    (date(2024,3,31), 1, "month", date(2024,2,29), date(2024,4,1)),
    (date(2024,2,29), 1, "year", date(2023,2,28), date(2024,3,1)),
    (date(2026,10,9), 1, "day", date(2026,10,9), date(2026,10,10)),
    (date(2026,10,9), 2, "week", date(2026,9,26), date(2026,10,10)),
    (date(2026,10,9), 2, "quarter", date(2026,4,9), date(2026,10,10)),
])
def test_local_rolling_date_arithmetic(today, count, unit, start, end):
    result = resolve_period(PeriodSelection("rolling", count=count, unit=unit), today)
    assert (result.start, result.end) == (start, end)


@pytest.mark.parametrize("changes", [dict(count=0), dict(count=True), dict(count=1201),
                                     dict(unit="jalali_month"), dict(start="2026-01-01"), dict(count=None)])
def test_rolling_period_rejects_unbounded_or_contradictory_selections(changes):
    with pytest.raises(SDKError) as error:
        resolve_period(replace(PeriodSelection("rolling", count=3, unit="month"), **changes), date(2026,10,9))
    assert error.value.code == "invalid_spec"


def test_legacy_saved_period_shape_remains_readable():
    selected = ReportSpec("sales", ("revenue",)).to_dict()
    selected["period"].pop("count")
    selected["period"].pop("unit")
    assert ReportSpec.from_dict(selected).period == PeriodSelection("all")
