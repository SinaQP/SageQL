"""Golden boundaries and strict scope checks for date-only Jalali months."""

from datetime import date, datetime, timedelta, timezone

import pytest

from sageql.sdk.calendars import (
    JALALI_MONTH_NAMES, gregorian_to_jalali, jalali_month_bounds,
)


@pytest.mark.parametrize("year, month, start, end", [
    (1300, 1, "1921-03-21", "1921-04-21"),
    (1399, 12, "2021-02-19", "2021-03-21"),
    (1400, 12, "2022-02-20", "2022-03-21"),
    (1403, 1, "2024-03-20", "2024-04-20"),
    (1403, 12, "2025-02-19", "2025-03-21"),
    (1404, 1, "2025-03-21", "2025-04-21"),
    (1404, 12, "2026-02-20", "2026-03-21"),
    (1405, 1, "2026-03-21", "2026-04-21"),
    (1405, 6, "2026-08-23", "2026-09-23"),
    (1405, 7, "2026-09-23", "2026-10-23"),
    (1405, 12, "2027-02-20", "2027-03-21"),
    (1499, 12, "2121-02-20", "2121-03-21"),
])
def test_explicit_month_golden_inclusive_exclusive_bounds(year, month, start, end):
    assert jalali_month_bounds(year, month) == (
        date.fromisoformat(start), date.fromisoformat(end),
    )


def test_all_months_have_contiguous_bounds_and_correct_season_lengths():
    previous_end = None
    for year in range(1300, 1500):
        annual_days = 0
        for month in range(1, 13):
            start, end = jalali_month_bounds(year, month)
            if previous_end is not None:
                assert start == previous_end
            length = (end - start).days
            if month <= 6:
                assert length == 31
            elif month <= 11:
                assert length == 30
            else:
                assert length in (29, 30)
            assert type(start) is type(end) is date
            annual_days += length
            previous_end = end
        assert annual_days in (365, 366)


@pytest.mark.parametrize("year", [1299, 1500, 0, -1405, True, False, 1405.0, "1405", None])
def test_year_outside_explicit_integer_scope_is_rejected(year):
    with pytest.raises(ValueError, match="year"):
        jalali_month_bounds(year, 6)


@pytest.mark.parametrize("month", [0, 13, -1, True, False, 6.0, "6", None])
def test_month_outside_explicit_integer_scope_is_rejected(month):
    with pytest.raises(ValueError, match="month"):
        jalali_month_bounds(1405, month)


@pytest.mark.parametrize("value, expected", [
    (date(1921, 3, 21), (1300, 1, 1)),
    (date(2024, 2, 29), (1402, 12, 10)),
    (date(2024, 3, 19), (1402, 12, 29)),
    (date(2024, 3, 20), (1403, 1, 1)),
    (date(2025, 3, 20), (1403, 12, 30)),
    (date(2025, 3, 21), (1404, 1, 1)),
    (date(2026, 9, 22), (1405, 6, 31)),
    (date(2026, 9, 23), (1405, 7, 1)),
    (date(2121, 3, 20), (1499, 12, 29)),
])
def test_date_display_conversion_at_gregorian_and_persian_leap_boundaries(value, expected):
    assert gregorian_to_jalali(value) == expected


def test_every_supported_month_start_and_final_day_converts_to_its_own_month():
    for year in range(1300, 1500):
        for month in range(1, 13):
            start, end = jalali_month_bounds(year, month)
            assert gregorian_to_jalali(start) == (year, month, 1)
            assert gregorian_to_jalali(end - timedelta(days=1)) == (
                year, month, (end - start).days,
            )


@pytest.mark.parametrize("value", [
    date(1921, 3, 20), date(2121, 3, 21), date.min, date.max,
    datetime(2026, 9, 23), datetime(2026, 9, 23, tzinfo=timezone.utc),
    "2026-09-23", None, True,
])
def test_display_conversion_rejects_out_of_scope_dates_and_timestamps(value):
    with pytest.raises(ValueError):
        gregorian_to_jalali(value)


def test_month_display_names_are_fixed_and_ordered():
    assert len(JALALI_MONTH_NAMES) == 12
    assert JALALI_MONTH_NAMES[0] == "فروردین"
    assert JALALI_MONTH_NAMES[5:7] == ("شهریور", "مهر")
    assert JALALI_MONTH_NAMES[-1] == "اسفند"
